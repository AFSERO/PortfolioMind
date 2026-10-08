"""FAST Orchestrator for Copilot V2.

The FAST Orchestrator is an LLM running via the Codex CLI under the FAST profile.
It understands user intent and conversational context, executing simple queries
directly via safe read tools or preparing a structured HANDOFF to BALANCED/DEEP.

Critical Invariants:
1. It does NOT behave like an inflexible regex classifier.
2. It does NOT forbid tools for subsequent reasoners (suggestions are hints).
3. The original user message is ALWAYS preserved unchanged.
4. Any tool results already retrieved during FAST execution are preserved in the handoff.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.copilot_v2.adapter import CodexV2Adapter
from app.services.copilot_v2.contracts import (
    HandoffContext,
    OrchestratorAction,
    OrchestratorResult,
    ToolCall,
)
from app.services.copilot_v2.events import EventEmitter, ProgressEvent
from app.services.copilot_v2.profiles import ModelProfile, ReasoningEffort, get_profile_config
from app.services.copilot_v2.telemetry import ExecutionTrace
from app.services.copilot_v2.tools.registry import ToolRegistry, default_tool_registry

logger = logging.getLogger(__name__)

FAST_ORCHESTRATOR_SYSTEM_PROMPT = """You are the FAST Orchestrator for PortfolioMind Copilot V2.
You run under a fast, low-latency reasoning model. Your goal is to evaluate user requests,
execute safe read tools for simple tasks, and immediately synthesize answers OR escalate complex
reasoning to BALANCED or DEEP models.

Available safe READ tools:
{tool_schemas}

Decision Protocol:
1. SIMPLE TASK & ASSET VISIBILITY / HOLDING LOOKUP:
   - Factual queries about portfolio totals, cash balances, asset positions, recent prices, or holding checks.
   - Examples: "Portföyüm toplam kaç TL?", "BTC pozisyonum ne kadar?", "bu thf fonunu gördün mü", "THYAO bende var mı?"
   - CRITICAL TOOL ROUTING RULE:
     * When the user asks about holding, existence, or visibility of an asset (e.g. "bu thf fonunu gördün mü", "THYAO var mı?", "bende ne kadar altın var?"):
       Call ONLY `get_asset_context` (or `get_holdings`).
       Do NOT call `get_briefing` or `search_news` for simple ownership, existence, or visibility checks.
     * When `get_asset_context` returns, check `user_holding.is_owned`:
       - If `is_owned: true`: confirm ownership, state quantity, market value, cost, and price.
       - If `is_owned: false`: clearly state that the asset is recognized in the market/system but is NOT currently held in the user's portfolio.
     * Immediately synthesize a direct, helpful, and concise answer in Turkish and return "FINAL_RESPONSE". Do NOT chain unnecessary follow-up tools.

2. EXTERNAL EVIDENCE & CAUSAL QUESTIONS:
   - When the user asks WHY an asset dropped/rose (e.g. "THF niye bu kadar düşmüş?", "BTC neden düştü?") or asks for recent news/developments:
     a. Check internal asset context first (get_asset_context, and get_briefing if seeking recent briefing alerts).
     b. If internal evidence does not explain the cause or if current public news is needed, call search_news (with query and symbols).
     c. Distinguish: VERIFIED FACT (supported by retrieved evidence), SUPPORTED INFERENCE (logical deduction), or UNKNOWN (if no evidence confirms a cause).
     d. Cite sources naturally: [Kaynak, Tarih]. If evidence is incomplete or unavailable, explicitly state that no verified cause was found. NEVER fabricate/hallucinate causal stories or source URLs.
   - Do NOT search the web for internal portfolio totals, asset balances, or generic definitions ("Diversification ne demek?").

3. FRESH DETERMINISTIC DATA PRECEDENCE (CRITICAL INVARIANT):
   - Fresh deterministic tool results in === RETRIEVED TOOL RESULTS (SO FAR) === ALWAYS OVERRIDE prior conversational beliefs, previous assistant statements, or past errors.
   - Previous assistant statements in conversation context are NOT canonical financial truth. The latest PostgreSQL tool outputs in RETRIEVED TOOL RESULTS are the sole canonical truth.
   - If a tool returns `status: "success"`, treat its data (`is_owned`, `quantity`, `instrument`, etc.) as authoritative. NEVER claim "teknik bir hata oluştu" or "veriye erişilemedi" when the current tool result in RETRIEVED TOOL RESULTS contains valid data.

4. ACTION PROPOSALS & MUTATIONS (CRITICAL SAFETY PROTOCOL):
   - Available proposal tools: `propose_transaction_record`, `propose_watchlist_change`, `propose_decision_note`.
   - HYPOTHETICAL VS EXPLICIT MUTATION INTENT:
     * If user asks hypothetical or analytical questions (e.g. "THF satsam ne olur?", "portföyüm nasıl değişir?", "satmalı mıyım?"):
       DO NOT call proposal tools! Provide analytical explanation, trade-offs, and projections.
     * ONLY call proposal tools when the user expresses EXPLICIT INTENT to record an executed transaction or update portfolio records (e.g. "THF sattım kaydet", "100 adet THYAO aldım ekle", "GARAN'ı izleme listeme ekle", "Karar günlüğüme şu notu düş").
   - PRODUCT BOUNDARY & NO AUTONOMOUS TRADING:
     * PortfolioMind is an internal portfolio tracker, NOT connected to live brokers or exchanges.
     * You cannot execute trades directly. Calling `propose_*` creates a PENDING proposal for the user to review and confirm with a button in the UI.
     * When a proposal tool succeeds, synthesize a response informing the user that the action proposal has been prepared for their confirmation, summarize the details, and remind them to click the confirmation button on the screen.
   - MISSING REQUIRED FIELDS:
     * For transaction records: if the user did not specify the trade unit price or if the quantity requires holding resolution (e.g. "yarısını sattım"), resolve holding first via `get_asset_context`, and ask the user for missing trade execution price rather than silently guessing.

5. DETERMINISTIC PORTFOLIO SIMULATION (HYPOTHETICAL "WHAT-IF" SCENARIOS):
   - Available simulation tool: `simulate_transaction`
   - When the user asks hypothetical portfolio questions:
     * e.g. "THF'nin yarısını satsam portföy nasıl görünür?"
     * e.g. "BTC'nin %25'ini satsam nakit oranım ne olur?"
     * e.g. "100.000 TL NVDA alsam portföyde ağırlığı kaç olur?"
     * e.g. "THF'yi tamamen çıkarsam dağılım nasıl değişir?"
   - ALWAYS call `simulate_transaction`!
   - NEVER calculate portfolio percentages, new weights, or cash balances with manual arithmetic.
   - Deterministic calculations returned by `simulate_transaction` must be explained directly:
     * Before vs after total portfolio value
     * Target asset quantity, market value, and percentage weight
     * Cash balance and total cash allocation percentage
     * Allocation shifts across asset types and assets
   - STRICT SAFETY INVARIANT:
     * `simulate_transaction` is purely read-only and causes ZERO mutations.
     * NEVER call proposal tools (`propose_*`) for hypothetical or what-if questions!
     * Proposals are reserved ONLY for explicit user intent to record an actual transaction (e.g. "sattım kaydet").
   - In your final response, summarize the scenario clearly and explicitly state that this is a mathematical projection and has NOT modified their portfolio.

6. COMPLEX TASK:
   - Deep multi-asset portfolio evaluation, risk capacity vs allocation assessment, comprehensive thesis reviews,
     strategic rebalancing proposals, or scenario stress testing.
   - Example: "Portföyümü hedeflerim, son araştırmalar, briefingler ve risk kapasitem ile birlikte detaylı değerlendir."
   - For complex tasks, do NOT attempt to solve them with superficial reasoning.
   - Return "HANDOFF" with target_profile, reasoning_effort, escalation_reason, task_brief, active_entities, suggested_tools.


Response Format:
You MUST respond with a single valid JSON object strictly matching one of these structures:

Option 1: Requesting tool execution (Data needed):
{{
  "action": "TOOL_CALL",
  "tool_calls": [
    {{"tool": "get_asset_context", "args": {{"symbol": "THF"}}}},
    {{"tool": "search_news", "args": {{"query": "THF fonu düşüş neden", "symbols": ["THF"]}}}}
  ]
}}

Option 2: Final answer (Data available or no data needed):
{{
  "action": "FINAL_RESPONSE",
  "answer": "THF fonundaki düşüşle ilgili son gelişmeler incelendiğinde...",
  "external_sources": [
    {{"title": "Haber Başlığı", "source": "Yayıncı", "url": "https://...", "published_at": "2026-09-18T..."}}
  ]
}}

Option 3: Escalation (Complex task):
{{
  "action": "HANDOFF",
  "handoff": {{
    "target_profile": "BALANCED",
    "reasoning_effort": "medium",
    "escalation_reason": "Kapsamlı portföy ve risk analizi gerektiriyor.",
    "task_brief": "Kullanıcının portföyünü hedefler ve risk kapasitesiyle detaylı değerlendir.",
    "active_entities": [],
    "suggested_tools": ["get_portfolio_summary", "get_holdings", "get_briefing"]
  }}
}}
"""


class FastOrchestrator:
    """Orchestrates FAST model turns, tool executions, and escalations."""

    def __init__(
        self,
        adapter: Optional[CodexV2Adapter] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.adapter = adapter or CodexV2Adapter()
        self.registry = registry or default_tool_registry

    def build_prompt(
        self,
        user_message: str,
        already_retrieved: Dict[str, Any],
        conversation_context: Optional[str] = None,
    ) -> str:
        """Compose structured prompt for the FAST orchestrator turn."""
        tool_schemas_json = json.dumps(self.registry.get_tool_schemas(), indent=2, ensure_ascii=False)
        system_text = FAST_ORCHESTRATOR_SYSTEM_PROMPT.format(tool_schemas=tool_schemas_json)

        sections = [
            system_text,
            "=== CURRENT CONVERSATION CONTEXT ===",
            conversation_context or "No previous conversation context.",
            "",
            "=== RETRIEVED TOOL RESULTS (SO FAR) ===",
            json.dumps(already_retrieved, indent=2, ensure_ascii=False) if already_retrieved else "None yet.",
            "",
            "=== USER MESSAGE ===",
            user_message,
            "",
            "Respond strictly in the JSON format specified above.",
        ]
        return "\n".join(sections)

    async def run(
        self,
        db: AsyncSession,
        user_id: UUID,
        user_message: str,
        trace: ExecutionTrace,
        conversation_context: Optional[str] = None,
        max_iterations: Optional[int] = None,
        session_id: Optional[str] = None,
        event_emitter: Optional[EventEmitter] = None,
    ) -> OrchestratorResult:
        """Run the FAST orchestrator loop.

        Returns either FINAL_RESPONSE (simple task completed) or HANDOFF (complex task escalated).
        """
        cfg = get_profile_config(ModelProfile.FAST)
        iterations_limit = max_iterations if max_iterations is not None else cfg.default_tool_budget

        already_retrieved: Dict[str, Any] = {}
        tools_called: List[str] = []
        current_session_id = session_id

        for iteration in range(iterations_limit):
            prompt = self.build_prompt(
                user_message=user_message,
                already_retrieved=already_retrieved,
                conversation_context=conversation_context,
            )

            try:
                result = await asyncio.to_thread(
                    self.adapter.execute,
                    prompt=prompt,
                    profile=ModelProfile.FAST,
                    session_id=current_session_id,
                    require_json=True,
                    persist_session=True,
                )
            except Exception as exc:
                logger.error("FastOrchestrator invocation failed: %s", exc, exc_info=True)
                trace.record_failure(type(exc).__name__)
                raise

            trace.record_codex_call(result.duration_ms)
            if result.session_id:
                current_session_id = result.session_id
            trace.record_session(current_session_id, mode="RESUMED" if session_id else "NEW")

            parsed = result.parsed_json or {}
            raw_action = str(parsed.get("action", "")).upper()

            if raw_action == OrchestratorAction.FINAL_RESPONSE.value:
                answer = parsed.get("answer") or parsed.get("final_response", {}).get("answer", "")
                sources = []
                for k, v in already_retrieved.items():
                    if (k.startswith("search_news") or k.startswith("search_web")) and isinstance(v, dict):
                        for item in v.get("results", []):
                            if isinstance(item, dict) and "url" in item:
                                sources.append({
                                    "title": item.get("title", ""),
                                    "source": item.get("source", "Haber"),
                                    "url": item.get("url", ""),
                                    "published_at": item.get("published_at"),
                                })
                    elif k.startswith("fetch_web_page") and isinstance(v, dict) and v.get("status") == "success":
                        sources.append({
                            "title": v.get("title") or "Web Sayfası",
                            "source": "Web",
                            "url": v.get("url", ""),
                            "published_at": v.get("retrieved_at"),
                        })
                dedup_sources = []
                seen_urls = set()
                for s in sources:
                    u = s.get("url")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        dedup_sources.append(s)

                detected_proposal_id = None
                detected_proposal = None
                detected_simulation = None
                for k, v in already_retrieved.items():
                    if isinstance(v, dict):
                        if "proposal_id" in v and v.get("status") == "success":
                            detected_proposal_id = v.get("proposal_id")
                            detected_proposal = v
                        if "simulation_type" in v and "before" in v and "after" in v:
                            detected_simulation = v
                            sim_val = v.get("validation", {})
                            trace.record_simulation_outcome(
                                sim_type=v.get("simulation_type", "SELL"),
                                is_valid=sim_val.get("is_valid", True),
                            )

                return OrchestratorResult(
                    action=OrchestratorAction.FINAL_RESPONSE,
                    final_answer=answer,
                    tools_used=tools_called,
                    external_sources=dedup_sources[:5],
                    session_id=current_session_id,
                    proposal_id=detected_proposal_id,
                    proposal=detected_proposal,
                    simulation=detected_simulation,
                )

            elif raw_action == OrchestratorAction.HANDOFF.value:
                handoff_data = parsed.get("handoff", {})
                target_str = str(handoff_data.get("target_profile", "BALANCED")).upper()
                target_profile = (
                    ModelProfile.DEEP
                    if "DEEP" in target_str
                    else ModelProfile.BALANCED
                )
                effort_str = str(handoff_data.get("reasoning_effort", "medium")).lower()
                try:
                    effort = ReasoningEffort(effort_str)
                except ValueError:
                    effort = (
                        ReasoningEffort.HIGH
                        if target_profile == ModelProfile.DEEP
                        else ReasoningEffort.MEDIUM
                    )

                ext_ev: List[Dict[str, Any]] = []
                for k, v in already_retrieved.items():
                    if (k.startswith("search_news") or k.startswith("search_web")) and isinstance(v, dict) and "results" in v:
                        ext_ev.extend(v["results"])
                    elif k.startswith("fetch_web_page") and isinstance(v, dict) and v.get("status") == "success":
                        ext_ev.append(v)

                detected_proposal_id = None
                detected_proposal = None
                detected_simulation = None
                for k, v in already_retrieved.items():
                    if isinstance(v, dict):
                        if "proposal_id" in v and v.get("status") == "success":
                            detected_proposal_id = v.get("proposal_id")
                            detected_proposal = v
                        if "simulation_type" in v and "before" in v and "after" in v:
                            detected_simulation = v
                            sim_val = v.get("validation", {})
                            trace.record_simulation_outcome(
                                sim_type=v.get("simulation_type", "SELL"),
                                is_valid=sim_val.get("is_valid", True),
                            )

                handoff_ctx = HandoffContext(
                    original_user_message=user_message,  # CRITICAL INVARIANT: NEVER MUTATED
                    task_brief=handoff_data.get("task_brief") or user_message,
                    active_entities=handoff_data.get("active_entities") or [],
                    relevant_conversation_reference=conversation_context,
                    already_retrieved_tool_results=dict(already_retrieved),  # REUSED!
                    external_evidence=ext_ev,
                    suggested_tools=handoff_data.get("suggested_tools") or [],
                    target_profile=target_profile,
                    reasoning_effort=effort,
                    tool_budget=handoff_data.get("tool_budget", 5),
                    escalation_reason=handoff_data.get("escalation_reason") or "Task requires deeper reasoning",
                    session_id=current_session_id,
                    proposal_id=detected_proposal_id,
                    proposal=detected_proposal,
                    simulation=detected_simulation,
                )
                trace.record_escalation(target_profile, effort)

                if event_emitter:
                    await event_emitter.emit(
                        ProgressEvent.escalating(
                            target_profile=target_profile.value,
                            reason=handoff_ctx.escalation_reason,
                            effort=effort.value,
                        )
                    )

                return OrchestratorResult(
                    action=OrchestratorAction.HANDOFF,
                    handoff=handoff_ctx,
                    tools_used=tools_called,
                    session_id=current_session_id,
                )

            elif raw_action == OrchestratorAction.TOOL_CALL.value:
                raw_tool_calls = parsed.get("tool_calls", [])
                if not raw_tool_calls:
                    # If tool call action was indicated but list is empty, treat as final response fallback
                    answer = parsed.get("answer", "İsteğinizi işledim.")
                    return OrchestratorResult(
                        action=OrchestratorAction.FINAL_RESPONSE,
                        final_answer=answer,
                        tools_used=tools_called,
                        session_id=current_session_id,
                    )

                for tc_dict in raw_tool_calls:
                    tool_name = str(tc_dict.get("tool", "")).strip()
                    tool_args = tc_dict.get("args") or {}
                    result_key = f"{tool_name}({json.dumps(tool_args, sort_keys=True)})"

                    # Deduplication guard: do not refetch identical query in the same turn
                    if result_key in already_retrieved:
                        logger.debug("Tool call %s already executed; reusing cached output", result_key)
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

                    tools_called.append(tool_name)
                    trace.record_tool_call(tool_name, tool_res.duration_ms)

                    if tool_res.is_success:
                        already_retrieved[result_key] = tool_res.output
                    else:
                        already_retrieved[result_key] = {"error": tool_res.error}

                # Proceed to next turn with the newly retrieved data in already_retrieved
                continue

            else:
                # Unrecognized action; fallback to answer if present, or handoff
                answer = parsed.get("answer")
                if answer:
                    return OrchestratorResult(
                        action=OrchestratorAction.FINAL_RESPONSE,
                        final_answer=answer,
                        tools_used=tools_called,
                        session_id=current_session_id,
                    )
                # Escalate safely
                handoff_ctx = HandoffContext(
                    original_user_message=user_message,
                    task_brief=user_message,
                    already_retrieved_tool_results=dict(already_retrieved),
                    target_profile=ModelProfile.BALANCED,
                    reasoning_effort=ReasoningEffort.MEDIUM,
                    escalation_reason="FAST orchestrator response format uncertain; escalating to BALANCED.",
                    session_id=current_session_id,
                )
                trace.record_escalation(ModelProfile.BALANCED, ReasoningEffort.MEDIUM)
                if event_emitter:
                    await event_emitter.emit(
                        ProgressEvent.escalating(
                            target_profile=ModelProfile.BALANCED.value,
                            reason=handoff_ctx.escalation_reason,
                            effort=ReasoningEffort.MEDIUM.value,
                        )
                    )
                return OrchestratorResult(
                    action=OrchestratorAction.HANDOFF,
                    handoff=handoff_ctx,
                    tools_used=tools_called,
                    session_id=current_session_id,
                )

        # Budget exhausted without explicit final answer: escalate with gathered results
        handoff_ctx = HandoffContext(
            original_user_message=user_message,
            task_brief=user_message,
            already_retrieved_tool_results=dict(already_retrieved),
            target_profile=ModelProfile.BALANCED,
            reasoning_effort=ReasoningEffort.MEDIUM,
            escalation_reason="FAST tool budget reached; escalating with retrieved data to BALANCED.",
            session_id=current_session_id,
        )
        trace.record_escalation(ModelProfile.BALANCED, ReasoningEffort.MEDIUM)
        if event_emitter:
            await event_emitter.emit(
                ProgressEvent.escalating(
                    target_profile=ModelProfile.BALANCED.value,
                    reason=handoff_ctx.escalation_reason,
                    effort=ReasoningEffort.MEDIUM.value,
                )
            )
        return OrchestratorResult(
            action=OrchestratorAction.HANDOFF,
            handoff=handoff_ctx,
            tools_used=tools_called,
            session_id=current_session_id,
        )
