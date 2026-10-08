"""Tool Registry and Built-in Safe Tools for Copilot V2."""

from app.services.copilot_v2.tools.registry import (
    ToolClassification,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)
from app.services.copilot_v2.tools.builtins import register_builtin_tools
from app.services.copilot_v2.tools.proposals import (
    propose_decision_note_handler,
    propose_transaction_record_handler,
    propose_watchlist_change_handler,
    register_proposal_tools,
)
from app.services.copilot_v2.tools.simulation import (
    register_simulation_tools,
    simulate_transaction_handler,
)
from app.services.copilot_v2.tools.web_research import (
    ExternalEvidenceItem,
    fetch_web_page_handler,
    search_news_handler,
    search_web_handler,
)

# Register built-ins, proposal tools, and simulation tools immediately into the default registry
register_builtin_tools(default_tool_registry)
register_proposal_tools(default_tool_registry)
register_simulation_tools(default_tool_registry)

__all__ = [
    "ExternalEvidenceItem",
    "ToolClassification",
    "ToolDefinition",
    "ToolRegistry",
    "default_tool_registry",
    "fetch_web_page_handler",
    "register_simulation_tools",
    "search_news_handler",
    "search_web_handler",
    "simulate_transaction_handler",
]

