"""Codex execution adapter for PortfolioMind Copilot.

Delegates AI reasoning strictly to the existing CodexCLIProvider, formatting inputs
and validating structured Copilot responses.
"""

import asyncio
import inspect
import logging
from typing import Any, Optional

from app.config import settings
from app.schemas.copilot import (
    CopilotResponseType,
    CopilotStructuredResponse,
    ExecutionMode,
    IntentResult,
)
from app.services.copilot.context_engine import ContextBundle

logger = logging.getLogger(__name__)

# Ensure Finance/src is accessible for CodexCLIProvider
from app.services.formal_review import CodexCLIProvider, AIExecutionRequest, AIProvider


class CopilotCodexAdapter:
    """Invokes Codex via CodexCLIProvider and enforces the Copilot response contract."""

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    def _get_provider(self) -> AIProvider:
        if self._provider is not None:
            return self._provider
        if CodexCLIProvider is None:
            raise RuntimeError("CodexCLIProvider is not available in the current environment.")
        self._provider = CodexCLIProvider(
            default_timeout=getattr(settings, "CODEX_DEFAULT_TIMEOUT_SECONDS", 180.0),
            deep_research_timeout=getattr(settings, "CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS", 600.0),
        )
        return self._provider

    async def execute(
        self,
        prompt: str,
        intent: IntentResult,
        context_bundle: ContextBundle,
        timeout: Optional[float] = 60.0,
    ) -> CopilotStructuredResponse:
        """Execute Copilot prompt through CodexCLIProvider and parse structured response."""
        provider = self._get_provider()

        exec_req = AIExecutionRequest(
            protocol_name="copilot-task",
            protocol_text=prompt,
            persistent_context=context_bundle.to_context_dict(),
            supplemental_context={"intent": intent.model_dump(mode="json")},
            timeout=timeout,
        )

        try:
            if inspect.iscoroutinefunction(provider.execute):
                ai_result = await provider.execute(exec_req)
            else:
                ai_result = await asyncio.to_thread(provider.execute, exec_req)
        except Exception as err:
            logger.error("Codex execution for copilot task failed: %s", err, exc_info=True)
            # Safe degraded fallback
            return CopilotStructuredResponse(
                response_type=CopilotResponseType.ANSWER,
                answer=(
                    "I encountered an issue processing this request via the reasoning engine. "
                    "Your portfolio and data remain completely safe."
                ),
                intent=intent.intent,
                execution_mode=intent.execution_mode,
                context_used=context_bundle.provenance,
            )

        machine_record: dict[str, Any] = dict(ai_result.machine_record or {})
        raw_resp_type = str(machine_record.get("response_type", "ANSWER")).upper()

        if raw_resp_type == "NEEDS_INPUT":
            resp_type = CopilotResponseType.NEEDS_INPUT
            question = (
                machine_record.get("question")
                or machine_record.get("answer")
                or ai_result.human_brief
            )
            missing = machine_record.get("missing_fields") or intent.missing_information
            return CopilotStructuredResponse(
                response_type=resp_type,
                question=question,
                intent=intent.intent,
                execution_mode=ExecutionMode.NEEDS_INPUT.value,
                missing_fields=missing,
                context_used=context_bundle.provenance,
            )

        elif raw_resp_type == "ACTION_INTENT":
            resp_type = CopilotResponseType.ACTION_INTENT
            action = machine_record.get("action") or {}
            answer = (
                machine_record.get("answer")
                or ai_result.human_brief
                or "Action recognized. Write execution is scheduled for Phase 2."
            )
            mode = machine_record.get("execution_mode") or intent.execution_mode
            return CopilotStructuredResponse(
                response_type=resp_type,
                answer=answer,
                intent=intent.intent,
                execution_mode=mode,
                action=action,
                context_used=context_bundle.provenance,
            )

        else:
            resp_type = CopilotResponseType.ANSWER
            answer = (
                machine_record.get("answer")
                or ai_result.human_brief
            )
            return CopilotStructuredResponse(
                response_type=resp_type,
                answer=answer,
                intent=intent.intent,
                execution_mode=intent.execution_mode,
                context_used=context_bundle.provenance,
            )
