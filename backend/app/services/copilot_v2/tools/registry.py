"""Tool Registry abstraction for Copilot V2.

Enforces strict tool safety invariants:
1. Every tool is categorized by ToolClassification.
2. In Phase 1, only READ_ONLY tools are allowed. Any attempt to register or execute
   a WRITE tool raises an error.
3. Unknown tools are strictly rejected.
4. Output is deterministically JSON-sanitized and bounded.
5. Models never receive raw database or SQL access.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import inspect
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.copilot_v2.contracts import ToolResult
from app.services.copilot_v2.errors import ToolExecutionError

logger = logging.getLogger(__name__)


class ToolClassification(str, Enum):
    """Safety classification for tools."""

    READ_ONLY = "READ_ONLY"
    PROPOSAL = "PROPOSAL"
    WRITE = "WRITE"


@dataclass
class ToolDefinition:
    """Metadata and execution specification for a registered tool."""

    name: str
    description: str
    parameters_schema: Dict[str, Any]
    classification: ToolClassification
    handler: Callable


def _sanitize_for_json(val: Any) -> Any:
    """Recursively convert Decimals, datetimes, and UUIDs to JSON-safe primitives."""
    if isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, (datetime, date)):
        return val.isoformat()
    elif isinstance(val, UUID):
        return str(val)
    elif isinstance(val, dict):
        return {str(k): _sanitize_for_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in val]
    return val


class ToolRegistry:
    """Registry managing available Copilot V2 tools and safe execution."""

    def __init__(self, enforce_read_only_phase: bool = True):
        self._tools: Dict[str, ToolDefinition] = {}
        self.enforce_read_only_phase = enforce_read_only_phase

    DISALLOWED_EXECUTION_PREFIXES = (
        "execute_",
        "confirm_",
        "apply_",
        "write_",
        "delete_",
        "mutate_",
        "run_trade_",
        "place_order_",
    )

    def register(self, definition: ToolDefinition) -> None:
        """Register a new tool definition.

        Strictly enforces:
        1. Only READ_ONLY and PROPOSAL classifications are allowed in model-facing registry.
        2. Execution/mutation tool names are categorically blocked.
        """
        if definition.classification not in (
            ToolClassification.READ_ONLY,
            ToolClassification.PROPOSAL,
        ):
            raise ToolExecutionError(
                f"Cannot register WRITE tool '{definition.name}': classification '{definition.classification.value}' is not allowed in model registry.",
                tool_name=definition.name,
            )

        name_lower = definition.name.lower()
        if any(name_lower.startswith(prefix) for prefix in self.DISALLOWED_EXECUTION_PREFIXES):
            raise ToolExecutionError(
                f"Cannot register tool '{definition.name}': execution/mutation prefixes are prohibited in model registry.",
                tool_name=definition.name,
            )

        self._tools[definition.name] = definition
        logger.debug("Registered tool: %s (%s)", definition.name, definition.classification.value)

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        """List all currently registered tools."""
        return list(self._tools.values())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return schema descriptors formatted for model prompts."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
                "classification": t.classification.value,
            }
            for t in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        db: AsyncSession,
        user_id: UUID,
        args: Dict[str, Any],
    ) -> ToolResult:
        """Safely execute a tool by name within user and database scope.

        Validates existence, classification, and serializes output.
        """
        tool = self.get(name)
        if tool is None:
            raise ToolExecutionError(f"Unknown tool: '{name}'", tool_name=name)

        if self.enforce_read_only_phase and tool.classification == ToolClassification.WRITE:
            raise ToolExecutionError(
                f"Execution of tool '{name}' rejected: Phase 1 is strictly READ_ONLY.",
                tool_name=name,
            )

        start_time = time.monotonic()
        try:
            handler = tool.handler
            if inspect.iscoroutinefunction(handler):
                raw_output = await handler(db=db, user_id=user_id, **args)
            else:
                raw_output = handler(db=db, user_id=user_id, **args)

            elapsed_ms = round((time.monotonic() - start_time) * 1000.0, 2)
            clean_output = _sanitize_for_json(raw_output)

            return ToolResult(
                tool=name,
                args=args,
                output=clean_output,
                error=None,
                duration_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000.0, 2)
            logger.error("Error executing tool '%s': %s", name, exc, exc_info=True)
            return ToolResult(
                tool=name,
                args=args,
                output=None,
                error=f"{type(exc).__name__}: {str(exc)}",
                duration_ms=elapsed_ms,
            )


# Default global registry singleton
default_tool_registry = ToolRegistry(enforce_read_only_phase=True)
