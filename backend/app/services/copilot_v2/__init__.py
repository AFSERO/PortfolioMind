"""Copilot V2 Package.

Architecture:
- Pure Codex CLI runtime.
- Model profile abstraction: FAST, BALANCED, DEEP.
- Safe read-only deterministic tool registry.
- Fast Orchestrator with structured HANDOFF or FINAL_RESPONSE outcomes.
- Same-session escalation & persistent thread continuity.
- Canonical PostgreSQL memory with automatic Codex session recovery.
- Ephemeral progress events (STARTED, TOOL_RUNNING, ESCALATING, REASONING, COMPLETED, FAILED).
- Observability and telemetry traces.
"""

from app.services.copilot_v2.contracts import (
    HandoffContext,
    OrchestratorAction,
    OrchestratorResult,
    ToolCall,
    ToolResult,
)
from app.services.copilot_v2.errors import (
    CodexAuthError,
    CodexCLIExecutionError,
    CodexParseError,
    CodexSessionResumeError,
    CodexTimeoutError,
    CodexV2Error,
    ToolExecutionError,
)
from app.services.copilot_v2.events import (
    EventEmitter,
    ProgressCallback,
    ProgressEvent,
    ProgressEventType,
)
from app.services.copilot_v2.profiles import (
    ModelProfile,
    ProfileConfig,
    ReasoningEffort,
    get_profile_config,
)
from app.services.copilot_v2.service import CopilotV2Service
from app.services.copilot_v2.session import SessionManager, build_recovery_context
from app.services.copilot_v2.telemetry import ExecutionTrace

__all__ = [
    "CopilotV2Service",
    "ModelProfile",
    "ReasoningEffort",
    "ProfileConfig",
    "get_profile_config",
    "OrchestratorAction",
    "OrchestratorResult",
    "HandoffContext",
    "ToolCall",
    "ToolResult",
    "ExecutionTrace",
    "CodexV2Error",
    "CodexTimeoutError",
    "CodexAuthError",
    "CodexCLIExecutionError",
    "CodexSessionResumeError",
    "CodexParseError",
    "ToolExecutionError",
    "ProgressEvent",
    "ProgressEventType",
    "EventEmitter",
    "ProgressCallback",
    "SessionManager",
    "build_recovery_context",
]
