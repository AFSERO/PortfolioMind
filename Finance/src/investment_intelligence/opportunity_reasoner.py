"""Finance-owned Opportunity Reasoning Layer (OpportunityReasoner).

Evaluates whether an investment candidate on the watchlist/research pipeline
deserves deeper research now based on new evidence, valuation shifts, price entry,
or catalyst progression.
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

VALID_OPPORTUNITY_STATUSES = {"NO_CHANGE", "WATCH", "RESEARCH_SOON", "RESEARCH_NOW"}
VALID_PRIMARY_DRIVERS = {
    "VALUATION",
    "FUNDAMENTAL",
    "CATALYST",
    "PRICE_MOVE",
    "RESEARCH_STALENESS",
    "OTHER",
}
VALID_VALUATION_SIGNALS = {"ATTRACTIVE", "FAIR", "EXPENSIVE", "UNKNOWN"}
VALID_RESEARCH_FRESHNESS = {"FRESH", "REVIEW", "STALE", "UNKNOWN"}
VALID_SUGGESTED_NEXT_STEPS = {
    "NONE",
    "SCREENING",
    "DEEP_RESEARCH",
    "VALUATION_UPDATE",
    "THESIS_REVIEW",
    "PRICE_REVIEW",
}
VALID_CONFIDENCES = {"LOW", "MEDIUM", "HIGH"}


class OpportunityAssessmentError(Exception):
    """Raised when an AI opportunity assessment is invalid or fails schema validation."""


@dataclass(frozen=True)
class OpportunityAssessment:
    """Validated structured intelligence assessment for a watchlist or research candidate."""

    opportunity_status: str
    reason: str
    primary_driver: str
    valuation_signal: str
    research_freshness: str
    suggested_next_step: str
    confidence: str = "MEDIUM"
    raw_machine_record: dict[str, Any] = field(default_factory=dict)


OPPORTUNITY_PROTOCOL_TEXT = """You are an expert investment intelligence engine evaluating whether a monitored watchlist or research candidate deserves deeper research or review now.
This is NOT an automatic stock picker and NOT a buy/sell signal. You are evaluating RESEARCH PRIORITIZATION and OPPORTUNITY QUALITY.

CRITICAL VALUATION AUTHORITY RULE:
Valuation status is determined authoritatively by formal Valuation Review and persisted intelligence state. It CANNOT be altered, promoted, or guessed by this opportunity protocol.
Target entry range entry or price movement alone does NOT justify an ATTRACTIVE valuation signal.
If an authoritative valuation status is provided in context (e.g. FAIR, EXPENSIVE, ATTRACTIVE, UNKNOWN), you MUST respect it and NOT promote it independently.

Evaluate:
1. Does the new evidence or price action materially improve or change the investment case?
2. Does this candidate deserve deeper research attention now, soon, or merely continued passive watch?
3. Is the apparent opportunity real or merely price noise / temporary sentiment?
4. What is the next logical research step (SCREENING, DEEP_RESEARCH, VALUATION_UPDATE, THESIS_REVIEW, PRICE_REVIEW, or NONE)?

Required output fields in machine_record:
- opportunity_status: NO_CHANGE, WATCH, RESEARCH_SOON, RESEARCH_NOW
- reason: A concise, explainable rationale linking the facts to why research is or is not warranted now.
- primary_driver: VALUATION, FUNDAMENTAL, CATALYST, PRICE_MOVE, RESEARCH_STALENESS, OTHER
- valuation_signal: ATTRACTIVE, FAIR, EXPENSIVE, UNKNOWN (Reflects authoritative valuation from formal review; do NOT promote independently)
- research_freshness: FRESH, REVIEW, STALE, UNKNOWN
- suggested_next_step: NONE, SCREENING, DEEP_RESEARCH, VALUATION_UPDATE, THESIS_REVIEW, PRICE_REVIEW
- confidence: LOW, MEDIUM, HIGH
"""


class OpportunityReasoner:
    """Coordinates bounded context assembly, Codex execution, and output validation for candidate opportunities."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider or CodexCLIProvider()

    def assess_opportunity(
        self,
        *,
        instrument: dict[str, Any],
        watchlist_candidate: Optional[dict[str, Any]] = None,
        intelligence_state: Optional[dict[str, Any]] = None,
        latest_review: Optional[dict[str, Any]] = None,
        current_price: Optional[dict[str, Any]] = None,
        deterministic_context: Optional[dict[str, Any]] = None,
        recent_events: Optional[list[dict[str, Any]]] = None,
    ) -> OpportunityAssessment:
        """Evaluate a qualifying candidate and return structured OpportunityAssessment.

        Raises OpportunityAssessmentError or AIExecutionError if execution or validation fails.
        """
        # 1. Resolve authoritative valuation signal from context
        auth_valuation = "UNKNOWN"
        if deterministic_context and "valuation_signal" in deterministic_context:
            val_sig = deterministic_context["valuation_signal"]
            auth_valuation = val_sig.value if hasattr(val_sig, "value") else str(val_sig).upper()
        elif intelligence_state and intelligence_state.get("valuation_status"):
            auth_valuation = str(intelligence_state["valuation_status"]).upper()
        elif latest_review and latest_review.get("valuation_status"):
            auth_valuation = str(latest_review["valuation_status"]).upper()

        if auth_valuation not in VALID_VALUATION_SIGNALS:
            auth_valuation = "UNKNOWN"

        # 2. Assemble bounded persistent candidate context
        persistent_context: dict[str, Any] = {
            "instrument": {
                "symbol": instrument.get("symbol"),
                "name": instrument.get("name"),
                "asset_type": instrument.get("asset_type"),
                "exchange": instrument.get("exchange"),
                "currency": instrument.get("currency"),
            },
            "authoritative_valuation_status": auth_valuation,
        }

        if watchlist_candidate:
            persistent_context["watchlist"] = {
                "research_stage": watchlist_candidate.get("research_stage"),
                "priority": watchlist_candidate.get("priority"),
                "why_interesting": watchlist_candidate.get("why_interesting"),
                "target_entry_min": watchlist_candidate.get("target_entry_min"),
                "target_entry_max": watchlist_candidate.get("target_entry_max"),
                "key_catalyst": watchlist_candidate.get("key_catalyst"),
                "key_risk": watchlist_candidate.get("key_risk"),
                "next_expected_event": watchlist_candidate.get("next_expected_event"),
            }

        if intelligence_state:
            persistent_context["intelligence_state"] = {
                "thesis_status": intelligence_state.get("thesis_status"),
                "valuation_status": intelligence_state.get("valuation_status"),
                "recommendation": intelligence_state.get("recommendation"),
                "last_review_at": intelligence_state.get("last_review_at"),
                "authoritative_valuation_status": auth_valuation,
            }

        if latest_review:
            persistent_context["latest_review"] = {
                "protocol": latest_review.get("protocol"),
                "confidence": latest_review.get("confidence"),
                "human_brief": latest_review.get("human_brief"),
                "valuation_status": latest_review.get("valuation_status"),
            }

        # 3. Assemble supplemental trigger context
        supplemental_context: dict[str, Any] = {
            "deterministic_trigger": deterministic_context or {},
            "current_price": current_price or {},
            "recent_events": (recent_events or [])[:5],
        }

        request = AIExecutionRequest(
            protocol_name="opportunity-assessment",
            protocol_text=OPPORTUNITY_PROTOCOL_TEXT,
            persistent_context=persistent_context,
            supplemental_context=supplemental_context,
            execution_metadata={"action": "candidate_opportunity_assessment"},
        )

        # 4. Execute via AIProvider
        result: AIExecutionResult = self.ai_provider.execute(request)
        if not isinstance(result, AIExecutionResult):
            raise OpportunityAssessmentError(
                f"Invalid AI result type: {type(result).__name__}"
            )

        machine = result.machine_record
        if not isinstance(machine, dict):
            raise OpportunityAssessmentError("AI machine_record must be a dictionary")

        # 5. Validate schema and enforce enums
        raw_status = str(machine.get("opportunity_status", "")).upper().strip()
        if raw_status not in VALID_OPPORTUNITY_STATUSES:
            raise OpportunityAssessmentError(
                f"Invalid opportunity_status '{raw_status}' in AI output"
            )

        reason = str(machine.get("reason") or "").strip()
        if not reason:
            raise OpportunityAssessmentError(
                "AI output missing required non-empty 'reason'"
            )

        raw_driver = str(machine.get("primary_driver", "")).upper().strip()
        if raw_driver not in VALID_PRIMARY_DRIVERS:
            raw_driver = "OTHER"

        raw_freshness = str(machine.get("research_freshness", "")).upper().strip()
        if raw_freshness not in VALID_RESEARCH_FRESHNESS:
            raw_freshness = "UNKNOWN"

        raw_next_step = str(machine.get("suggested_next_step", "")).upper().strip()
        if raw_next_step not in VALID_SUGGESTED_NEXT_STEPS:
            raw_next_step = "NONE"

        confidence = str(
            result.confidence or machine.get("confidence", "MEDIUM")
        ).upper().strip()
        if confidence not in VALID_CONFIDENCES:
            confidence = "MEDIUM"

        # Valuation signal strictly adheres to authoritative valuation source of truth.
        # Opportunity Engine is for research prioritization only and can never promote valuation.
        final_valuation = auth_valuation

        return OpportunityAssessment(
            opportunity_status=raw_status,
            reason=reason,
            primary_driver=raw_driver,
            valuation_signal=final_valuation,
            research_freshness=raw_freshness,
            suggested_next_step=raw_next_step,
            confidence=confidence,
            raw_machine_record=machine,
        )
