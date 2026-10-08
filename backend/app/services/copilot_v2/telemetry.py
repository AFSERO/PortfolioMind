"""Telemetry and Execution Trace foundation for Copilot V2.

Captures performance metrics, Codex invocation counts, tool latencies,
profile transitions, session continuity state, and error categories for observability.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

from app.services.copilot_v2.profiles import ModelProfile, ReasoningEffort

logger = logging.getLogger(__name__)


@dataclass
class ExecutionTrace:
    """Detailed telemetry record for a single Copilot V2 request."""

    starting_profile: ModelProfile = ModelProfile.FAST
    final_profile: ModelProfile = ModelProfile.FAST
    reasoning_effort: ReasoningEffort = ReasoningEffort.LOW
    total_latency_ms: float = 0.0
    codex_invocation_count: int = 0
    tools_called: List[str] = field(default_factory=list)
    tool_durations: Dict[str, float] = field(default_factory=dict)
    escalation_occurred: bool = False
    failure_category: Optional[str] = None
    _start_time: float = field(default_factory=time.monotonic, repr=False)

    # Phase 2 session & multi-turn telemetry
    conversation_id: Optional[str] = None
    codex_session_id: Optional[str] = None
    session_mode: str = "NEW"  # NEW, RESUMED, RECOVERED
    profile_sequence: List[str] = field(default_factory=list)
    reasoning_effort_sequence: List[str] = field(default_factory=list)
    tool_results_reused: int = 0
    session_resume_failed: bool = False
    session_recovery_occurred: bool = False
    time_to_first_progress_event_ms: Optional[float] = None
    progress_events: List[Dict[str, Any]] = field(default_factory=list)

    # Phase 2.6 external search & evidence telemetry
    external_search_used: bool = False
    external_tools_called: List[str] = field(default_factory=list)
    search_queries_count: int = 0
    search_results_count: int = 0
    pages_fetched: int = 0
    external_tool_latency_ms: float = 0.0
    source_count_used_in_final_answer: int = 0

    # Phase 3.2 portfolio simulation telemetry
    simulation_used: bool = False
    simulation_type: Optional[str] = None
    simulation_tool_latency_ms: float = 0.0
    simulation_validation_status: Optional[str] = None


    def __post_init__(self) -> None:
        if not self.profile_sequence:
            self.profile_sequence.append(self.starting_profile.value)
        if not self.reasoning_effort_sequence:
            self.reasoning_effort_sequence.append(self.reasoning_effort.value)

    def record_session(self, session_id: Optional[str], mode: str = "RESUMED") -> None:
        """Record the active Codex session ID and mode."""
        self.codex_session_id = session_id
        if self.session_recovery_occurred:
            self.session_mode = "RECOVERED"
        else:
            self.session_mode = mode

    def record_profile_step(self, profile: ModelProfile, effort: ReasoningEffort) -> None:
        """Record a profile step in multi-stage execution."""
        self.profile_sequence.append(profile.value)
        self.reasoning_effort_sequence.append(effort.value)
        self.final_profile = profile
        self.reasoning_effort = effort

    def record_progress_event(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record a progress event for observability."""
        now_ms = round((time.monotonic() - self._start_time) * 1000.0, 2)
        if self.time_to_first_progress_event_ms is None:
            self.time_to_first_progress_event_ms = now_ms

        self.progress_events.append({
            "event_type": event_type,
            "message": message,
            "elapsed_ms": now_ms,
            "details": details or {},
        })

    def record_codex_call(self, duration_ms: float) -> None:
        """Increment Codex CLI invocation count."""
        self.codex_invocation_count += 1
        logger.debug(
            "Codex call #%d completed in %.2fms",
            self.codex_invocation_count,
            duration_ms,
        )

    def record_tool_call(self, tool_name: str, duration_ms: float) -> None:
        """Record an executed tool and its latency."""
        self.tools_called.append(tool_name)
        prev = self.tool_durations.get(tool_name, 0.0)
        self.tool_durations[tool_name] = round(prev + duration_ms, 2)
        if tool_name in {"search_news", "search_web", "fetch_web_page"}:
            self.external_search_used = True
            self.external_tools_called.append(tool_name)
            self.external_tool_latency_ms = round(self.external_tool_latency_ms + duration_ms, 2)
            if tool_name in {"search_news", "search_web"}:
                self.search_queries_count += 1
            elif tool_name == "fetch_web_page":
                self.pages_fetched += 1
        elif tool_name == "simulate_transaction":
            self.simulation_used = True
            self.simulation_tool_latency_ms = round(self.simulation_tool_latency_ms + duration_ms, 2)
        logger.debug("Tool '%s' executed in %.2fms", tool_name, duration_ms)

    def record_simulation_outcome(self, sim_type: str, is_valid: bool) -> None:
        """Record the simulated transaction type and whether validation succeeded."""
        self.simulation_used = True
        self.simulation_type = sim_type
        self.simulation_validation_status = "VALID" if is_valid else "INVALID"

    def record_tool_reuse(self, count: int = 1) -> None:

        """Record count of tool outputs reused across handoff without refetching."""
        self.tool_results_reused += count

    def record_escalation(
        self,
        target_profile: ModelProfile,
        effort: ReasoningEffort,
    ) -> None:
        """Record profile escalation from FAST to BALANCED/DEEP."""
        self.escalation_occurred = True
        self.record_profile_step(target_profile, effort)
        logger.info(
            "Escalated request from %s to %s (effort=%s)",
            self.starting_profile.value,
            target_profile.value,
            effort.value,
        )

    def record_resume_failure(self) -> None:
        """Record that resuming a previous Codex session failed."""
        self.session_resume_failed = True

    def record_recovery(self, new_session_id: Optional[str] = None) -> None:
        """Record that DB-backed session recovery occurred."""
        self.session_recovery_occurred = True
        self.session_mode = "RECOVERED"
        if new_session_id:
            self.codex_session_id = new_session_id

    def record_failure(self, category: str) -> None:
        """Record a failure category (e.g. TIMEOUT, AUTH, CLI_ERROR, PARSE_ERROR)."""
        self.failure_category = category
        logger.warning("Copilot V2 execution failure recorded: %s", category)

    def finalize(self) -> "ExecutionTrace":
        """Compute final total latency and log execution summary."""
        self.total_latency_ms = round((time.monotonic() - self._start_time) * 1000.0, 2)
        logger.info(
            "Copilot V2 trace finalized: starting=%s, final=%s, effort=%s, latency=%.2fms, "
            "session=%s (%s), codex_invocations=%d, tools_called=%s, tools_reused=%d, "
            "escalation=%s, recovery=%s, failure=%s",
            self.starting_profile.value,
            self.final_profile.value,
            self.reasoning_effort.value,
            self.total_latency_ms,
            self.codex_session_id,
            self.session_mode,
            self.codex_invocation_count,
            self.tools_called,
            self.tool_results_reused,
            self.escalation_occurred,
            self.session_recovery_occurred,
            self.failure_category,
        )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to a JSON-serializable dictionary."""
        return {
            "starting_profile": self.starting_profile.value,
            "final_profile": self.final_profile.value,
            "reasoning_effort": self.reasoning_effort.value,
            "total_latency_ms": self.total_latency_ms,
            "codex_invocation_count": self.codex_invocation_count,
            "tools_called": list(self.tools_called),
            "tool_durations": dict(self.tool_durations),
            "escalation_occurred": self.escalation_occurred,
            "failure_category": self.failure_category,
            "conversation_id": self.conversation_id,
            "codex_session_id": self.codex_session_id,
            "session_mode": self.session_mode,
            "profile_sequence": list(self.profile_sequence),
            "reasoning_effort_sequence": list(self.reasoning_effort_sequence),
            "tool_results_reused": self.tool_results_reused,
            "session_resume_failed": self.session_resume_failed,
            "session_recovery_occurred": self.session_recovery_occurred,
            "time_to_first_progress_event_ms": self.time_to_first_progress_event_ms,
            "progress_events": list(self.progress_events),
            "external_search_used": self.external_search_used,
            "external_tools_called": list(self.external_tools_called),
            "search_queries_count": self.search_queries_count,
            "search_results_count": self.search_results_count,
            "pages_fetched": self.pages_fetched,
            "external_tool_latency_ms": self.external_tool_latency_ms,
            "source_count_used_in_final_answer": self.source_count_used_in_final_answer,
            "simulation_used": self.simulation_used,
            "simulation_type": self.simulation_type,
            "simulation_tool_latency_ms": self.simulation_tool_latency_ms,
            "simulation_validation_status": self.simulation_validation_status,
        }

