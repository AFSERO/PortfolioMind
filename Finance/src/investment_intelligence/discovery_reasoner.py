"""Finance-owned Market-Wide Discovery Reasoning Layer (DiscoveryReasoner).

Evaluates whether an unowned, unwatched market candidate genuinely deserves
preliminary research attention based on deterministic signals, market context,
recent news, and SEC disclosures.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from investment_intelligence.codex_provider import CodexCLIProvider
from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    AIProvider,
)

logger = logging.getLogger(__name__)

VALID_DISCOVERY_STATUSES = {
    "HIGH_PRIORITY_SCREEN",
    "SCREEN",
    "WATCH",
    "IGNORE",
}
VALID_SUGGESTED_NEXT_STEPS = {
    "NONE",
    "ADD_TO_WATCHLIST",
    "PRELIMINARY_SCREENING",
}
VALID_CONFIDENCES = {"LOW", "MEDIUM", "HIGH"}


class DiscoveryAssessmentError(Exception):
    """Raised when an AI discovery assessment is invalid or fails schema validation."""


@dataclass(frozen=True)
class DiscoveryAssessment:
    """Structured assessment produced by DiscoveryReasoner for a screened market candidate."""

    discovery_status: str
    primary_reason: str
    signal_summary: str
    key_question: str
    key_risk: str
    suggested_next_step: str
    confidence: str = "MEDIUM"
    raw_machine_record: dict[str, Any] = field(default_factory=dict)


DISCOVERY_PROTOCOL_TEXT = """You are an expert investment intelligence engine evaluating a newly screened market candidate outside the user's current portfolio and watchlist.
This is NOT an automatic stock picker and NOT a buy/sell signal. You are evaluating RESEARCH WORTHINESS and OPPORTUNITY QUALITY.

STRICT INVARIANTS:
1. Do NOT produce BUY, SELL, ADD, REDUCE, target price, position size, or portfolio allocation recommendations.
2. Focus strictly on whether this candidate warrants spending research time.
3. Determine whether apparent price/valuation dislocations represent genuine opportunity or uninvestable value traps / fundamental deterioration.

Evaluate:
1. Does the evidence suggest a genuine dislocation, quality pullback, or catalyst worthy of preliminary research?
2. Are the apparent signals likely meaningful or just temporary sentiment / noise?
3. What is the single most important research question that must be answered first?
4. What is the primary risk or thesis failure mode?
5. What is the logical next step: PRELIMINARY_SCREENING, ADD_TO_WATCHLIST, or NONE?

Required output fields in machine_record:
- discovery_status: HIGH_PRIORITY_SCREEN, SCREEN, WATCH, IGNORE
- primary_reason: A concise, explainable rationale linking the facts to why research is or is not warranted.
- signal_summary: Concise summary of the market signals that triggered this candidate.
- key_question: The primary research question to answer if research is undertaken.
- key_risk: The primary risk, potential flaw, or value trap concern.
- suggested_next_step: NONE, ADD_TO_WATCHLIST, PRELIMINARY_SCREENING
- confidence: LOW, MEDIUM, HIGH
"""


class DiscoveryReasoner:
    """Coordinates bounded context assembly, Codex execution, and output validation for discovery candidates."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider or CodexCLIProvider()

    def assess_candidate(
        self,
        *,
        instrument: dict[str, Any],
        market_data: Optional[dict[str, Any]] = None,
        signals: Optional[list[dict[str, Any]]] = None,
        recent_news: Optional[list[dict[str, Any]]] = None,
        sec_filings: Optional[list[dict[str, Any]]] = None,
        portfolio_context: Optional[dict[str, Any]] = None,
    ) -> DiscoveryAssessment:
        """Screen an unowned candidate and return structured DiscoveryAssessment.

        Raises DiscoveryAssessmentError or AIExecutionError if execution or validation fails.
        """
        # 1. Assemble bounded persistent context
        persistent_context: dict[str, Any] = {
            "instrument": {
                "symbol": instrument.get("symbol"),
                "name": instrument.get("name"),
                "asset_type": instrument.get("asset_type"),
                "exchange": instrument.get("exchange"),
                "currency": instrument.get("currency"),
            },
            "market_data": market_data or {},
            "signals": signals or [],
        }

        if portfolio_context:
            persistent_context["portfolio_summary"] = {
                "owned_symbols": portfolio_context.get("owned_symbols", []),
                "watchlisted_symbols": portfolio_context.get("watchlisted_symbols", []),
                "sector_exposures": portfolio_context.get("sector_exposures", {}),
            }

        # 2. Assemble supplemental evidence context
        supplemental_context: dict[str, Any] = {
            "recent_news": (recent_news or [])[:5],
            "sec_filings": (sec_filings or [])[:3],
        }

        request = AIExecutionRequest(
            protocol_name="opportunity-discovery",
            protocol_text=DISCOVERY_PROTOCOL_TEXT,
            persistent_context=persistent_context,
            supplemental_context=supplemental_context,
            execution_metadata={"action": "market_candidate_discovery_assessment"},
        )

        # 3. Execute via AIProvider
        result: AIExecutionResult = self.ai_provider.execute(request)
        if not isinstance(result, AIExecutionResult):
            raise DiscoveryAssessmentError(
                f"Invalid AI result type: {type(result).__name__}"
            )

        machine = result.machine_record
        if not isinstance(machine, dict):
            raise DiscoveryAssessmentError("AI machine_record must be a dictionary")

        # 4. Validate schema and enforce enums
        raw_status = str(machine.get("discovery_status", "")).upper().strip()
        if raw_status not in VALID_DISCOVERY_STATUSES:
            raise DiscoveryAssessmentError(
                f"Invalid discovery_status '{raw_status}' in AI output"
            )

        primary_reason = str(machine.get("primary_reason") or "").strip()
        if not primary_reason:
            raise DiscoveryAssessmentError(
                "AI output missing required non-empty 'primary_reason'"
            )

        signal_summary = str(machine.get("signal_summary") or "").strip()
        key_question = str(machine.get("key_question") or "").strip()
        key_risk = str(machine.get("key_risk") or "").strip()

        raw_next_step = str(machine.get("suggested_next_step", "")).upper().strip()
        if raw_next_step not in VALID_SUGGESTED_NEXT_STEPS:
            raw_next_step = "NONE"

        confidence = str(
            result.confidence or machine.get("confidence", "MEDIUM")
        ).upper().strip()
        if confidence not in VALID_CONFIDENCES:
            confidence = "MEDIUM"

        return DiscoveryAssessment(
            discovery_status=raw_status,
            primary_reason=primary_reason,
            signal_summary=signal_summary,
            key_question=key_question,
            key_risk=key_risk,
            suggested_next_step=raw_next_step,
            confidence=confidence,
            raw_machine_record=machine,
        )
