"""Protocol Runner and AI execution contracts (Part 4C)."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from investment_intelligence.context import ContextBuilder, ContextJSONEncoder
from investment_intelligence.protocols import (
    ExecutionError,
    ProtocolNotFoundError,
    load_protocol,
)
from investment_intelligence.providers import _as_uuid
from investment_intelligence.records import InstrumentRecord, ProtocolRunRecord
from investment_intelligence.services import ProtocolRunService


# ============================================================================
# 1. Execution Errors
# ============================================================================


class AIExecutionError(ExecutionError):
    """External AI provider failed to execute or returned invalid output."""


# ============================================================================
# 2. Execution Request and Result Data Structures
# ============================================================================


@dataclass(frozen=True)
class AIExecutionRequest:
    """Bounded, JSON-serializable request payload delivered to AIProvider."""

    protocol_name: str
    protocol_text: str
    persistent_context: dict[str, Any]
    supplemental_context: dict[str, Any] | None = None
    execution_metadata: dict[str, Any] | None = None
    timeout: float | None = None

    def __post_init__(self):
        if self.timeout is not None and float(self.timeout) <= 0:
            raise ValueError("timeout must be greater than 0")
        try:
            json.dumps(self.persistent_context, cls=ContextJSONEncoder)
        except Exception as err:
            raise ValueError(f"persistent_context must be JSON-serializable: {err}") from err
        if self.supplemental_context is not None:
            try:
                json.dumps(self.supplemental_context, cls=ContextJSONEncoder)
            except Exception as err:
                raise ValueError(f"supplemental_context must be JSON-serializable: {err}") from err
        if self.execution_metadata is not None:
            try:
                json.dumps(self.execution_metadata, cls=ContextJSONEncoder)
            except Exception as err:
                raise ValueError(f"execution_metadata must be JSON-serializable: {err}") from err


@dataclass(frozen=True)
class AIExecutionResult:
    """Standardized AI execution output containing Machine Record and Human Brief."""

    machine_record: dict[str, Any]
    human_brief: str
    confidence: str | None = None

    def __post_init__(self):
        if not isinstance(self.machine_record, dict):
            raise ValueError("machine_record must be a dictionary")
        try:
            json.dumps(self.machine_record, cls=ContextJSONEncoder)
        except Exception as err:
            raise ValueError(f"machine_record must be JSON-serializable: {err}") from err
        if not isinstance(self.human_brief, str) or not self.human_brief.strip():
            raise ValueError("human_brief must be non-empty text")


@dataclass(frozen=True)
class ProtocolRunExecution:
    """Runner execution envelope containing the persisted run record and AI result."""

    run: ProtocolRunRecord
    result: AIExecutionResult | None = None

    def __iter__(self):
        yield self.run
        yield self.result


# ============================================================================
# 3. AIProvider Abstract Contract & Deterministic Test Double
# ============================================================================


class AIProvider(ABC):
    """Vendor-independent contract for AI / LLM protocol execution."""

    @abstractmethod
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        """Execute the protocol with the provided context and return structured output."""


class StaticAIProvider(AIProvider):
    """Deterministic in-memory AI provider for test doubles and mocks."""

    def __init__(
        self,
        default_result: AIExecutionResult | None = None,
        *,
        should_fail: bool = False,
        failure_error: Exception | None = None,
    ):
        self.default_result = default_result or AIExecutionResult(
            machine_record={"analysis": "Static protocol review completed"},
            human_brief="Default static review brief.",
            confidence="MEDIUM",
        )
        self.should_fail = should_fail
        self.failure_error = failure_error
        self.recorded_requests: list[AIExecutionRequest] = []

    def set_result(self, result: AIExecutionResult) -> None:
        self.default_result = result
        self.should_fail = False

    def simulate_failure(self, error: Exception | None = None) -> None:
        self.should_fail = True
        self.failure_error = error or AIExecutionError("Simulated AI execution failure")

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        self.recorded_requests.append(request)
        if self.should_fail:
            raise self.failure_error or AIExecutionError("Simulated AI execution failure")
        return self.default_result


# ============================================================================
# 4. Protocol Runner
# ============================================================================


class ProtocolRunner:
    """Coordinates context preparation, AI execution, and ProtocolRun persistence."""

    def __init__(
        self,
        session: Session,
        ai_provider: AIProvider,
        *,
        protocols_dir: Path | str | None = None,
    ):
        self.session = session
        self.ai_provider = ai_provider
        self.protocols_dir = protocols_dir
        self.protocol_svc = ProtocolRunService(session)
        self.context_builder = ContextBuilder(session)

    def run_asset_protocol(
        self,
        instrument_id: UUID | InstrumentRecord | str,
        protocol_name: str,
        *,
        supplemental_context: dict[str, Any] | None = None,
        execution_metadata: dict[str, Any] | None = None,
    ) -> ProtocolRunExecution:
        """Execute an asset-level protocol against an instrument.

        Transaction Lifecycle:
        1. Pre-validation: Protocol is loaded and supplemental context validated before DB writes.
        2. Transaction 1: Read asset context and persist initial ProtocolRun (status=RUNNING).
        3. External Call: AI executes outside of any active DB transaction (zero DB locks held).
        4. Transaction 2: Persist terminal result as COMPLETED (on success) or FAILED (on error).
        5. Invariant: Current IntelligenceState is NEVER mutated automatically.
        """
        # 1. Pre-validation (Fails early without creating DB records)
        proto_def = load_protocol(protocol_name, protocols_dir=self.protocols_dir)
        iid = _as_uuid(instrument_id)

        # Validate supplemental context serializability before starting run
        if supplemental_context is not None:
            try:
                json.dumps(supplemental_context, cls=ContextJSONEncoder)
            except Exception as err:
                raise ValueError(f"supplemental_context must be JSON-serializable: {err}") from err

        # 2. Transaction 1: Build context and start protocol run
        with self.session.begin():
            persistent_context = self.context_builder.build_asset_context(iid)
            run = self.protocol_svc.start(proto_def.canonical_name, instrument_id=iid)
            run_id = run.id

        # At this point, Transaction 1 is committed and closed.
        # No DB transaction or row lock is held during external AI execution.

        request = AIExecutionRequest(
            protocol_name=proto_def.canonical_name,
            protocol_text=proto_def.content,
            persistent_context=persistent_context,
            supplemental_context=supplemental_context,
            execution_metadata=execution_metadata,
        )

        # 3. External AI Execution & Terminal Record Persistence
        try:
            ai_result = self.ai_provider.execute(request)
            if not isinstance(ai_result, AIExecutionResult):
                raise AIExecutionError(
                    f"AI provider returned invalid result type: {type(ai_result).__name__}"
                )
        except Exception as err:
            # Transaction 2 (Failure branch): Persist FAILED run record
            fail_reason = f"AI execution failed: {type(err).__name__}"
            with self.session.begin():
                failed_run = self.protocol_svc.fail(run_id, reason=fail_reason)
            raise AIExecutionError(fail_reason) from err

        # Transaction 2 (Success branch): Persist COMPLETED run record
        with self.session.begin():
            completed_run = self.protocol_svc.complete(
                run_id,
                machine_record=ai_result.machine_record,
                human_brief=ai_result.human_brief,
                confidence=ai_result.confidence,
            )

        # PortfolioMind live sync hook (fails open: errors never abort local execution)
        try:
            from investment_intelligence.portfoliomind.bridge import PortfolioMindBridge
            from investment_intelligence.portfoliomind.config import PortfolioMindBridgeConfig
            from investment_intelligence.repositories import InstrumentRepository

            pm_config = PortfolioMindBridgeConfig.from_env()
            if pm_config.enabled:
                inst_record = InstrumentRepository(self.session).get(iid)
                if inst_record:
                    bridge = PortfolioMindBridge(config=pm_config)
                    bridge.sync_protocol_run(
                        completed_run,
                        inst_record,
                        research_path=(
                            execution_metadata.get("research_path")
                            if execution_metadata
                            else None
                        ),
                        auto_apply_state=True,
                        raise_on_error=False,
                    )
        except Exception:
            pass

        return ProtocolRunExecution(run=completed_run, result=ai_result)


def run_asset_protocol(
    session: Session,
    instrument_id: UUID | InstrumentRecord | str,
    protocol_name: str,
    ai_provider: AIProvider,
    *,
    supplemental_context: dict[str, Any] | None = None,
    execution_metadata: dict[str, Any] | None = None,
    protocols_dir: Path | str | None = None,
) -> ProtocolRunExecution:
    """Convenience function to run an asset protocol using ProtocolRunner."""
    runner = ProtocolRunner(session, ai_provider, protocols_dir=protocols_dir)
    return runner.run_asset_protocol(
        instrument_id,
        protocol_name,
        supplemental_context=supplemental_context,
        execution_metadata=execution_metadata,
    )
