"""Structured contracts and schemas for Copilot V2.

Defines the output outcomes of the FAST Orchestrator and the Handoff schema.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.copilot_v2.profiles import ModelProfile, ReasoningEffort


class OrchestratorAction(str, Enum):
    """The action outcome decided by the FAST Orchestrator."""

    TOOL_CALL = "TOOL_CALL"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    HANDOFF = "HANDOFF"


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    tool: str = Field(description="Name of the registered tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


class ToolResult(BaseModel):
    """The outcome of a tool execution."""

    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.error is None


class HandoffContext(BaseModel):
    """Structured context passed from FAST Orchestrator to BALANCED or DEEP reasoners.

    Invariants:
    1. `original_user_message` is NEVER mutated, truncated, or summarized.
    2. `already_retrieved_tool_results` preserves all tool outputs gathered by FAST.
    3. `suggested_tools` are advisory hints, not rigid permissions.
    """

    original_user_message: str
    task_brief: str
    active_entities: List[str] = Field(default_factory=list)
    relevant_conversation_reference: Optional[str] = None
    already_retrieved_tool_results: Dict[str, Any] = Field(default_factory=dict)
    external_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)
    target_profile: ModelProfile = ModelProfile.BALANCED
    reasoning_effort: ReasoningEffort = ReasoningEffort.MEDIUM
    tool_budget: int = 5
    escalation_reason: str
    session_id: Optional[str] = None
    proposal_id: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None
    simulation: Optional[Dict[str, Any]] = None


class OrchestratorResult(BaseModel):
    """Outcome produced by the FAST Orchestrator in a given iteration."""

    action: OrchestratorAction
    final_answer: Optional[str] = None
    handoff: Optional[HandoffContext] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    external_sources: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None
    proposal_id: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None
    simulation: Optional[Dict[str, Any]] = None

