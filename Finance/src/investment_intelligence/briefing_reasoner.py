"""Finance-owned Briefing Reasoning Layer (BriefingReasoner).

Executes selective, bounded investment reasoning for high-materiality or
review-required events using CodexCLIProvider and structured schema validation.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import logging

from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    AIProvider,
)
from investment_intelligence.codex_provider import CodexCLIProvider

logger = logging.getLogger(__name__)

VALID_IMPACTS = {"POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"}
VALID_MATERIALITIES = {"MEDIUM", "HIGH", "CRITICAL"}
VALID_TIME_HORIZONS = {"SHORT", "MEDIUM", "LONG"}
VALID_THESIS_IMPACTS = {
    "STRONGER",
    "UNCHANGED",
    "WEAKER",
    "POTENTIALLY_INVALIDATING",
    "INVALIDATED",
    "NOT_EVALUATED",
}
VALID_RECOMMENDED_REVIEWS = {
    "NONE",
    "THESIS_REVIEW",
    "EARNINGS_REVIEW",
    "VALUATION_UPDATE",
    "TECHNICAL_REVIEW",
    "DEEP_RESEARCH",
}
VALID_CONFIDENCES = {"LOW", "MEDIUM", "HIGH"}


class BriefingAssessmentError(Exception):
    """Raised when an AI briefing assessment is invalid or fails schema validation."""


@dataclass(frozen=True)
class BriefingAssessment:
    """Validated structured intelligence assessment produced by Codex for an event."""

    event_summary: str
    impact: str
    materiality: str
    time_horizon: str
    thesis_impact: str
    review_required: bool
    why_it_matters: str
    recommended_review: str
    confidence: str = "MEDIUM"
    human_brief: str = ""
    raw_machine_record: dict[str, Any] = field(default_factory=dict)


BRIEFING_PROTOCOL_TEXT = """You are an expert investment intelligence engine evaluating a specific market development for a monitored asset.
Analyze whether the development materially affects the existing investment thesis, risk/return parameters, or valuation.
Provide:
1. A concise, factual event_summary.
2. Impact direction (POSITIVE, NEGATIVE, NEUTRAL, MIXED).
3. Materiality (MEDIUM, HIGH, CRITICAL).
4. Time horizon (SHORT, MEDIUM, LONG).
5. Potential thesis impact (STRONGER, UNCHANGED, WEAKER, POTENTIALLY_INVALIDATING, NOT_EVALUATED).
6. Whether formal review is required (review_required: true/false).
7. A contextual why_it_matters explanation directly linking the event facts to the asset's thesis.
8. recommended_review: What specific formal review protocol (if any) should be launched (NONE, THESIS_REVIEW, EARNINGS_REVIEW, VALUATION_UPDATE, TECHNICAL_REVIEW, DEEP_RESEARCH).
"""


class BriefingReasoner:
    """Coordinates bounded context assembly, Codex execution, and output validation for briefing events."""

    def __init__(self, ai_provider: Optional[AIProvider] = None):
        self.ai_provider = ai_provider or CodexCLIProvider()

    def assess_event(
        self,
        *,
        instrument: dict[str, Any],
        intelligence_state: Optional[dict[str, Any]] = None,
        latest_review: Optional[dict[str, Any]] = None,
        event: dict[str, Any],
    ) -> BriefingAssessment:
        """Evaluate a qualifying material event and return structured BriefingAssessment.

        Raises BriefingAssessmentError or AIExecutionError if execution or validation fails.
        """
        # 1. Assemble bounded persistent asset context
        persistent_context: dict[str, Any] = {
            "instrument": {
                "symbol": instrument.get("symbol"),
                "name": instrument.get("name"),
                "asset_type": instrument.get("asset_type"),
                "exchange": instrument.get("exchange"),
                "currency": instrument.get("currency"),
                "is_portfolio": bool(instrument.get("is_portfolio", True)),
            }
        }

        if intelligence_state:
            persistent_context["intelligence_state"] = {
                "thesis_status": intelligence_state.get("thesis_status"),
                "valuation_status": intelligence_state.get("valuation_status"),
                "recommendation": intelligence_state.get("recommendation"),
                "confidence": intelligence_state.get("confidence"),
                "last_review_at": intelligence_state.get("last_review_at"),
            }

        if latest_review:
            persistent_context["latest_review"] = {
                "protocol": latest_review.get("protocol"),
                "confidence": latest_review.get("confidence"),
                "human_brief": latest_review.get("human_brief"),
                "key_assumptions": latest_review.get("key_assumptions"),
                "growth_drivers": latest_review.get("growth_drivers"),
                "key_risks": latest_review.get("key_risks"),
            }

        # 2. Assemble bounded event context
        supplemental_context: dict[str, Any] = {
            "event": {
                "headline": event.get("headline"),
                "summary": event.get("summary"),
                "source": event.get("source"),
                "url": event.get("url"),
                "published_at": event.get("published_at"),
                "sec_form": event.get("sec_form"),
                "preliminary_category": event.get("category"),
                "preliminary_materiality": event.get("materiality"),
            }
        }

        request = AIExecutionRequest(
            protocol_name="briefing-assessment",
            protocol_text=BRIEFING_PROTOCOL_TEXT,
            persistent_context=persistent_context,
            supplemental_context=supplemental_context,
            execution_metadata={"action": "briefing_event_assessment"},
        )

        # 3. Execute via AIProvider
        result: AIExecutionResult = self.ai_provider.execute(request)
        if not isinstance(result, AIExecutionResult):
            raise BriefingAssessmentError(f"Invalid AI result type: {type(result).__name__}")

        machine = result.machine_record
        if not isinstance(machine, dict):
            raise BriefingAssessmentError("AI machine_record must be a dictionary")

        # 4. Validate schema and enforce enums
        event_summary = str(machine.get("event_summary") or event.get("headline") or "").strip()
        why_it_matters = str(machine.get("why_it_matters") or "").strip()
        if not why_it_matters:
            raise BriefingAssessmentError("AI output missing required non-empty 'why_it_matters'")

        raw_impact = str(machine.get("impact", "")).upper().strip()
        if raw_impact not in VALID_IMPACTS:
            raise BriefingAssessmentError(f"Invalid impact '{raw_impact}' in AI output")

        raw_materiality = str(machine.get("materiality", "")).upper().strip()
        if raw_materiality not in VALID_MATERIALITIES:
            raise BriefingAssessmentError(f"Invalid materiality '{raw_materiality}' in AI output")

        raw_time_horizon = str(machine.get("time_horizon", "")).upper().strip()
        if raw_time_horizon not in VALID_TIME_HORIZONS:
            raw_time_horizon = "MEDIUM"

        raw_thesis_impact = str(machine.get("thesis_impact", "")).upper().strip()
        if raw_thesis_impact == "POTENTIALLY_INVALIDATING":
            raw_thesis_impact = "INVALIDATED"
        elif raw_thesis_impact not in VALID_THESIS_IMPACTS:
            raw_thesis_impact = "NOT_EVALUATED"

        raw_review_required = machine.get("review_required")
        if not isinstance(raw_review_required, bool):
            raw_review_required = raw_materiality in ("HIGH", "CRITICAL")

        raw_rec_review = str(machine.get("recommended_review", "")).upper().strip()
        if raw_rec_review not in VALID_RECOMMENDED_REVIEWS:
            raw_rec_review = "NONE"

        confidence = str(result.confidence or machine.get("confidence", "MEDIUM")).upper().strip()
        if confidence not in VALID_CONFIDENCES:
            confidence = "MEDIUM"

        human_brief = result.human_brief.strip() if result.human_brief else why_it_matters

        return BriefingAssessment(
            event_summary=event_summary,
            impact=raw_impact,
            materiality=raw_materiality,
            time_horizon=raw_time_horizon,
            thesis_impact=raw_thesis_impact,
            review_required=raw_review_required,
            why_it_matters=why_it_matters,
            recommended_review=raw_rec_review,
            confidence=confidence,
            human_brief=human_brief,
            raw_machine_record=machine,
        )
