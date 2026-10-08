"""Reasoner Engine for BALANCED and DEEP profiles in Copilot V2.

Executes complex analysis when a task is escalated from the FAST Orchestrator.

Invariants:
1. Receives and preserves the original_user_message unchanged.
2. Directly consumes already_retrieved_tool_results from HandoffContext,
   preventing duplicate tool executions and saving latency.
3. Uses the target_profile (BALANCED or DEEP) and configured reasoning_effort.
4. Safe read-only tool execution loop up to the handoff tool_budget.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.copilot_v2.adapter import CodexV2Adapter
from app.services.copilot_v2.contracts import HandoffContext
from app.services.copilot_v2.events import EventEmitter, ProgressEvent
from app.services.copilot_v2.profiles import ModelProfile
from app.services.copilot_v2.telemetry import ExecutionTrace
from app.services.copilot_v2.tools.registry import ToolRegistry, default_tool_registry

logger = logging.getLogger(__name__)

REASONER_SYSTEM_PROMPT = """You are the Senior Portfolio & Investment Intelligence Reasoner for PortfolioMind Copilot V2.
You operate under the {profile} model tier with {effort} reasoning effort.

Your role:
Provide in-depth, rigorous, objective, and structured portfolio intelligence and financial analysis.
Analyze positions, risks, valuation status, thesis health, and briefing developments systematically.

Available safe READ tools:
{tool_schemas}

Context Provided in Handoff:
- The FAST orchestrator escalated this task because: {escalation_reason}
- Task Brief: {task_brief}
- Active Entities: {active_entities}
- Suggested Tools (Hints): {suggested_tools}

ALREADY RETRIEVED DATA (Do NOT refetch these unless absolutely needed):
{already_retrieved}

Instructions:
1. Examine the user's original request and the already retrieved data carefully.
2. If additional critical data is missing to answer the user thoroughly, you may request tool calls using "TOOL_CALL".
3. For causal or market movement inquiries (e.g. why an asset dropped or rose):
   - Rely strictly on retrieved data and news.
   - Distinguish: VERIFIED FACT (from news/briefing), SUPPORTED INFERENCE (logical deduction), UNKNOWN (if no evidence confirms reason).
   - Cite sources naturally in the text: [Kaynak, Tarih].
   - If no verified cause exists, clearly state the uncertainty. NEVER fabricate causal claims or hallucinate sources.
4. FRESH DETERMINISTIC DATA PRECEDENCE:
   - Data in ALREADY RETRIEVED DATA comes directly from the user's PostgreSQL database and live tools. It represents the absolute ground truth.
   - Fresh tool outputs always supersede any past conversational assertions, prior assistant statements, or past technical errors.
   - If a past conversation message claimed a technical error or missing data, but the retrieved tool output now contains valid data (status: 'success', ownership, quantities, prices, etc.), you MUST rely entirely on the fresh tool data and NEVER repeat past claims of error or missing data.
5. ACTION PROPOSALS & MUTATIONS PROTOCOL:
6. DETERMINISTIC PORTFOLIO SIMULATION (HYPOTHETICAL "WHAT-IF" SCENARIOS):
   - Available simulation tool: `simulate_transaction`
   - When the user asks hypothetical portfolio questions ("satsam ne olur?", "dağılım ne olur?", "nakit oranım kaç olur?"):
     * ALWAYS call `simulate_transaction`!
     * NEVER perform manual arithmetic on portfolio percentages, values, or cash balances.
     * Incorporate the exact deterministic before/after figures, target weights, cash impacts, and assumptions.
     * STRICT SAFETY INVARIANT: `simulate_transaction` is purely read-only and causes ZERO mutations. DO NOT call proposal tools for hypothetical questions.
     * Clearly state in your answer that this is a hypothetical scenario and has NOT modified their portfolio.
7. Once you have sufficient context, provide a comprehensive, clear, professional analysis in Turkish using "FINAL_RESPONSE".
8. Address the user's explicit goals, trade-offs, and risk factors directly.

Response Format:
You MUST respond with a single valid JSON object strictly matching one of these structures:

Option 1: Requesting additional data:
{{
  "action": "TOOL_CALL",
  "tool_calls": [
    {{"tool": "get_asset_context", "args": {{"symbol": "THYAO"}}}}
  ]
}}

Option 2: Final in-depth response:
{{
  "action": "FINAL_RESPONSE",
  "answer": "Detaylı portföy ve risk analizi..."
}}
"""


class ReasonerEngine:
    """Executes high-depth reasoning under BALANCED or DEEP profiles."""

    def __init__(
        self,
        adapter: Optional[CodexV2Adapter] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.adapter = adapter or CodexV2Adapter()
        self.registry = registry or default_tool_registry
        self.last_external_sources: List[Dict[str, Any]] = []
        self.last_proposal_id: Optional[str] = None
        self.last_proposal: Optional[Dict[str, Any]] = None
        self.last_simulation: Optional[Dict[str, Any]] = None


    def build_prompt(
        self,
        handoff: HandoffContext,
        accumulated_tools: Dict[str, Any],
    ) -> str:
        """Compose in-depth prompt combining handoff context and already retrieved tool results."""
        tool_schemas_json = json.dumps(self.registry.get_tool_schemas(), indent=2, ensure_ascii=False)
        system_text = REASONER_SYSTEM_PROMPT.format(
            profile=handoff.target_profile.value,
            effort=handoff.reasoning_effort.value,
            escalation_reason=handoff.escalation_reason,
            task_brief=handoff.task_brief,
            active_entities=json.dumps(handoff.active_entities, ensure_ascii=False),
            suggested_tools=json.dumps(handoff.suggested_tools, ensure_ascii=False),
            tool_schemas=tool_schemas_json,
            already_retrieved=json.dumps(accumulated_tools, indent=2, ensure_ascii=False),
        )

        sections = [
            system_text,
            "",
            "=== ORIGINAL USER MESSAGE (UNCHANGED) ===",
            handoff.original_user_message,
            "",
            "Respond strictly in the JSON format specified above.",
        ]
        return "\n".join(sections)

    async def execute(
        self,
        db: AsyncSession,
        user_id: UUID,
        handoff: HandoffContext,
        trace: ExecutionTrace,
        session_id: Optional[str] = None,
        event_emitter: Optional[EventEmitter] = None,
    ) -> str:
        """Execute the escalated reasoning workflow until a final answer is produced."""
        accumulated_tools = dict(handoff.already_retrieved_tool_results)
        self.last_external_sources = list(handoff.external_evidence)
        self.last_proposal_id = handoff.proposal_id
        self.last_proposal = handoff.proposal
        self.last_simulation = handoff.simulation
        budget = max(1, handoff.tool_budget)

        current_session_id = session_id or handoff.session_id

        if handoff.already_retrieved_tool_results:
            trace.record_tool_reuse(len(handoff.already_retrieved_tool_results))

        if event_emitter:
            await event_emitter.emit(
                ProgressEvent.reasoning(
                    profile=handoff.target_profile.value,
                    effort=handoff.reasoning_effort.value,
                )
            )

        for _ in range(budget):
            prompt = self.build_prompt(handoff, accumulated_tools)

            try:
                result = await asyncio.to_thread(
                    self.adapter.execute,
                    prompt=prompt,
                    profile=handoff.target_profile,
                    reasoning_effort=handoff.reasoning_effort,
                    session_id=current_session_id,
                    require_json=True,
                    persist_session=True,
                )
            except Exception as exc:
                logger.error("Reasoner invocation failed: %s", exc, exc_info=True)
                trace.record_failure(type(exc).__name__)
                raise

            trace.record_codex_call(result.duration_ms)
            if result.session_id:
                current_session_id = result.session_id
            trace.record_session(current_session_id, mode="RESUMED" if (session_id or handoff.session_id) else "NEW")
            handoff.session_id = current_session_id

            parsed = result.parsed_json or {}
            raw_action = str(parsed.get("action", "")).upper()

            if raw_action == "FINAL_RESPONSE":
                return str(parsed.get("answer", ""))

            elif raw_action == "TOOL_CALL":
                raw_tool_calls = parsed.get("tool_calls", [])
                if not raw_tool_calls:
                    return str(parsed.get("answer", "Analiz tamamlandı."))

                for tc_dict in raw_tool_calls:
                    tool_name = str(tc_dict.get("tool", "")).strip()
                    tool_args = tc_dict.get("args") or {}
                    result_key = f"{tool_name}({json.dumps(tool_args, sort_keys=True)})"

                    # Deduplication guard: reuse existing output if already fetched
                    if result_key in accumulated_tools:
                        logger.debug("Tool call %s already executed; reusing output without refetching", result_key)
                        trace.record_tool_reuse(1)
                        continue

                    if event_emitter:
                        await event_emitter.emit(
                            ProgressEvent.tool_running(tool_name=tool_name, tool_args=tool_args)
                        )

                    tool_res = await self.registry.execute(
                        name=tool_name,
                        db=db,
                        user_id=user_id,
                        args=tool_args,
                    )

                    trace.record_tool_call(tool_name, tool_res.duration_ms)
                    if tool_res.is_success:
                        accumulated_tools[result_key] = tool_res.output
                        if tool_name in {"search_news", "search_web"} and isinstance(tool_res.output, dict):
                            for item in tool_res.output.get("results", []):
                                if isinstance(item, dict) and "url" in item:
                                    self.last_external_sources.append({
                                        "title": item.get("title", ""),
                                        "source": item.get("source", "Haber"),
                                        "url": item.get("url", ""),
                                        "published_at": item.get("published_at"),
                                    })
                        elif tool_name == "fetch_web_page" and isinstance(tool_res.output, dict) and tool_res.output.get("status") == "success":
                            self.last_external_sources.append({
                                "title": tool_res.output.get("title") or "Web Sayfası",
                                "source": "Web",
                                "url": tool_res.output.get("url", ""),
                                "published_at": tool_res.output.get("retrieved_at"),
                            })
                    else:
                        accumulated_tools[result_key] = {
                            "status": "error",
                            "error": tool_res.error,
                            "message": f"Tool execution failed: {tool_res.error}",
                        }
                continue

            else:
                for k, v in accumulated_tools.items():
                    if isinstance(v, dict):
                        if "proposal_id" in v and v.get("status") == "success":
                            self.last_proposal_id = v.get("proposal_id")
                            self.last_proposal = v
                        if "simulation_type" in v and "before" in v and "after" in v:
                            self.last_simulation = v
                            sim_val = v.get("validation", {})
                            trace.record_simulation_outcome(
                                sim_type=v.get("simulation_type", "SELL"),
                                is_valid=sim_val.get("is_valid", True),
                            )
                answer = parsed.get("answer")
                if answer:
                    return str(answer)

        for k, v in accumulated_tools.items():
            if isinstance(v, dict):
                if "proposal_id" in v and v.get("status") == "success":
                    self.last_proposal_id = v.get("proposal_id")
                    self.last_proposal = v
                if "simulation_type" in v and "before" in v and "after" in v:
                    self.last_simulation = v
                    sim_val = v.get("validation", {})
                    trace.record_simulation_outcome(
                        sim_type=v.get("simulation_type", "SELL"),
                        is_valid=sim_val.get("is_valid", True),
                    )

        # Fallback if budget ends without explicit answer

        return (
            "Detaylı analiz verileri değerlendirildi. "
            "Portföy durumunuz ve ilgili veriler incelendi."
        )
