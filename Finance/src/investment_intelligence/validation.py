"""Protocol Machine Record validation layer (Part 5A)."""

from dataclasses import dataclass, field
from typing import Any

from investment_intelligence.enums import (
    ExecutionStatus,
    FundQuality,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)


# ============================================================================
# 1. Validation Exceptions
# ============================================================================


class MachineRecordValidationError(ValueError):
    """Base exception for invalid protocol Machine Records."""


class UnsupportedProtocolError(MachineRecordValidationError, LookupError):
    """Requested protocol does not have a Machine Record schema/validator."""


# ============================================================================
# 2. Thesis Review Validated Record
# ============================================================================


@dataclass(frozen=True)
class ThesisReviewRecord:
    """Validated Machine Record for 'thesis-review' protocol."""

    thesis_status: ThesisStatus
    recommendation: Recommendation
    material_changes: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    raw_record: dict[str, Any] = field(default_factory=dict)


def validate_thesis_review_record(record: Any) -> ThesisReviewRecord:
    """Validate a raw Machine Record dictionary against the Thesis Review schema.

    Rules:
    - Input must be a dictionary.
    - 'thesis_status' (required): must match ThesisStatus enum.
    - 'recommendation' (required): must match Recommendation enum.
    - 'material_changes' (optional): if present, must be a list of strings.
    - 'open_questions' (optional): if present, must be a list of strings.
    - Extra JSON keys: tolerated in raw_record, but only validated fields are typed.
    """
    if not isinstance(record, dict):
        raise MachineRecordValidationError(
            f"Machine record must be a dictionary, got {type(record).__name__}"
        )

    # 1. Validate thesis_status (required)
    if "thesis_status" not in record:
        raise MachineRecordValidationError("Missing required field 'thesis_status'")
    raw_status = record["thesis_status"]
    if isinstance(raw_status, ThesisStatus):
        thesis_status = raw_status
    elif isinstance(raw_status, str):
        try:
            thesis_status = ThesisStatus(raw_status)
        except ValueError:
            allowed = [s.value for s in ThesisStatus]
            raise MachineRecordValidationError(
                f"Invalid thesis_status '{raw_status}'; must be one of {allowed}"
            )
    else:
        raise MachineRecordValidationError(
            f"thesis_status must be a string or ThesisStatus, got {type(raw_status).__name__}"
        )

    # 2. Validate recommendation (required)
    if "recommendation" not in record:
        raise MachineRecordValidationError("Missing required field 'recommendation'")
    raw_rec = record["recommendation"]
    if isinstance(raw_rec, Recommendation):
        recommendation = raw_rec
    elif isinstance(raw_rec, str):
        try:
            recommendation = Recommendation(raw_rec)
        except ValueError:
            allowed = [r.value for r in Recommendation]
            raise MachineRecordValidationError(
                f"Invalid recommendation '{raw_rec}'; must be one of {allowed}"
            )
    else:
        raise MachineRecordValidationError(
            f"recommendation must be a string or Recommendation, got {type(raw_rec).__name__}"
        )

    # 3. Validate material_changes (optional string list)
    material_changes: tuple[str, ...] = ()
    if "material_changes" in record and record["material_changes"] is not None:
        raw_changes = record["material_changes"]
        if not isinstance(raw_changes, list):
            raise MachineRecordValidationError(
                f"material_changes must be a list of strings, got {type(raw_changes).__name__}"
            )
        if not all(isinstance(item, str) for item in raw_changes):
            raise MachineRecordValidationError(
                "All items in material_changes must be strings"
            )
        material_changes = tuple(raw_changes)

    # 4. Validate open_questions (optional string list)
    open_questions: tuple[str, ...] = ()
    if "open_questions" in record and record["open_questions"] is not None:
        raw_questions = record["open_questions"]
        if not isinstance(raw_questions, list):
            raise MachineRecordValidationError(
                f"open_questions must be a list of strings, got {type(raw_questions).__name__}"
            )
        if not all(isinstance(item, str) for item in raw_questions):
            raise MachineRecordValidationError(
                "All items in open_questions must be strings"
            )
        open_questions = tuple(raw_questions)

    return ThesisReviewRecord(
        thesis_status=thesis_status,
        recommendation=recommendation,
        material_changes=material_changes,
        open_questions=open_questions,
        raw_record=dict(record),
    )


# ============================================================================
# 3. Deep Research Validated Record (Decision Model v2)
# ============================================================================


def normalize_confidence(val: Any, default: int = 70) -> int:
    """Normalize confidence input into an integer score between 0 and 100."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if 0.0 <= val <= 1.0:
            return int(round(val * 100))
        return max(0, min(100, int(round(val))))
    if isinstance(val, str):
        clean = val.strip().upper()
        if clean.endswith("%"):
            clean = clean[:-1].strip()
        if clean in ("HIGH", "YUKSEK", "YÜKSEK"):
            return 85
        if clean in ("MEDIUM", "MED", "ORTA"):
            return 65
        if clean in ("LOW", "DUSUK", "DÜŞÜK"):
            return 40
        try:
            f = float(clean)
            if 0.0 <= f <= 1.0:
                return int(round(f * 100))
            return max(0, min(100, int(round(f))))
        except ValueError:
            return default
    return default


def derive_confidence_level(score: int) -> str:
    """Derive categorical confidence level from 0-100 score."""
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


@dataclass(frozen=True)
class DeepResearchRecord:
    """Validated and semantically repaired Machine Record for Deep Research protocols."""

    thesis_status: ThesisStatus
    valuation_status: ValuationStatus
    technical_status: TechnicalStatus
    recommendation: Recommendation
    confidence: int
    execution_status: ExecutionStatus = ExecutionStatus.AVAILABLE
    recovery_value_confidence: str | None = None
    execution_confidence: str | None = None
    data_quality_score: int | None = None
    primary_reason: str = ""
    supporting_reasons: tuple[str, ...] = ()
    key_risks: tuple[str, ...] = ()
    what_would_change_my_view: str | None = None
    evidence_gaps: tuple[str, ...] = ()
    review_required_reason: str | None = None
    assessment_type: str | None = None
    asset_class_assessment: dict[str, Any] = field(default_factory=dict)
    raw_record: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert validated record to persistent machine_record dictionary."""
        d = dict(self.raw_record)
        d["thesis_status"] = self.thesis_status.value
        d["valuation_status"] = self.valuation_status.value
        d["technical_status"] = self.technical_status.value
        d["recommendation"] = self.recommendation.value
        d["execution_status"] = self.execution_status.value
        d["confidence"] = self.confidence
        d["confidence_score"] = self.confidence
        d["confidence_level"] = derive_confidence_level(self.confidence)
        if self.recovery_value_confidence:
            d["recovery_value_confidence"] = self.recovery_value_confidence
        if self.execution_confidence:
            d["execution_confidence"] = self.execution_confidence
        if self.data_quality_score is not None:
            d["data_quality_score"] = self.data_quality_score
        if self.primary_reason:
            d["primary_reason"] = self.primary_reason
        if self.supporting_reasons:
            d["supporting_reasons"] = list(self.supporting_reasons)
        if self.key_risks:
            d["key_risks"] = list(self.key_risks)
        if self.what_would_change_my_view:
            d["what_would_change_my_view"] = self.what_would_change_my_view
        if self.evidence_gaps:
            d["evidence_gaps"] = list(self.evidence_gaps)
        if self.review_required_reason:
            d["review_required_reason"] = self.review_required_reason
        else:
            d.pop("review_required_reason", None)
        if self.assessment_type:
            d["assessment_type"] = self.assessment_type
        if self.asset_class_assessment:
            d["asset_class_assessment"] = self.asset_class_assessment
            d.update(self.asset_class_assessment)
        return d


def validate_deep_research_record(
    record: Any,
    asset_type: str | None = None,
    protocol_name: str | None = None,
) -> DeepResearchRecord:
    """Validate and semantically repair a raw Deep Research Machine Record.

    Enforces Decision Model v2.1:
    1. Normal output is a directional recommendation (ADD, HOLD, REDUCE, SELL).
    2. UNKNOWN and N_A semantics replace misleading FAIR/NEUTRAL placeholders.
    3. Fund quality supports POOR; underlying valuation supports UNKNOWN.
    4. Execution feasibility (AVAILABLE, RESTRICTED, BLOCKED, UNKNOWN) is separated from investment view.
    5. Execution restriction does not force HOLD or REVIEW_REQUIRED on broken theses.
    6. Confidence is calibrated against material evidence gaps (capped when gaps exist).
    7. Supports secondary certainty fields (recovery_value_confidence, execution_confidence).
    """
    if not isinstance(record, dict):
        raise MachineRecordValidationError(
            f"Machine record must be a dictionary, got {type(record).__name__}"
        )

    # 1. Validate thesis_status
    if "thesis_status" not in record or not record["thesis_status"]:
        raise MachineRecordValidationError("Missing required field 'thesis_status'")
    raw_thesis = record["thesis_status"]
    if isinstance(raw_thesis, ThesisStatus):
        thesis_status = raw_thesis
    else:
        try:
            thesis_status = ThesisStatus(str(raw_thesis).strip().upper())
        except ValueError:
            allowed = [s.value for s in ThesisStatus]
            raise MachineRecordValidationError(
                f"Invalid thesis_status '{raw_thesis}'; must be one of {allowed}"
            )

    # Determine asset class from protocol_name or record
    clean_proto = (protocol_name or "").strip().lower().replace("_", "-")
    clean_type = (asset_type or record.get("assessment_type") or "").strip().upper()
    if clean_proto == "deep-research-fund" or clean_type in ("FUND", "FUNDS"):
        resolved_asset_class = "FUND"
    elif clean_proto == "deep-research-crypto" or clean_type in ("CRYPTO", "DIGITAL_ASSETS"):
        resolved_asset_class = "CRYPTO"
    elif clean_proto == "deep-research-gold" or clean_type in ("PRECIOUS_METALS", "GOLD"):
        resolved_asset_class = "PRECIOUS_METALS"
    else:
        resolved_asset_class = "EQUITY"

    # Context analysis for liquidation, redemption freezes, and unassessed evidence
    all_context_text = " ".join([
        str(record.get("primary_reason") or ""),
        str(record.get("human_brief") or ""),
        str(record.get("review_required_reason") or ""),
        " ".join(str(x) for x in record.get("key_risks") or []),
        " ".join(str(x) for x in record.get("evidence_gaps") or []),
    ]).lower()

    is_frozen_or_liquidating = any(
        kw in all_context_text
        for kw in [
            "liquidation", "tasfiye", "redemption default", "redemption suspend",
            "redemptions suspended", "işlem yasağı", "işlemler durdurul",
            "işleme kapalı", "trading suspended", "freeze", "donduruldu", "temerrüt",
            "sales are currently blocked", "satış engelli", "satılamaz", "kısıtlı",
            "itfa temerrüdü", "alacak tahsil", "icra takibi"
        ]
    )

    is_valuation_unassessed = any(
        kw in all_context_text
        for kw in [
            "underlying assets were not valued", "değerleme yapılamadı",
            "portföy dağılımı bilinmiyor", "holdings unavailable",
            "portfolio composition unavailable", "varlıklar değerlenemedi",
            "could not actually be assessed", "cannot be established reliably",
            "değerleme yapılamamış"
        ]
    )

    # 2. Validate valuation_status and asset-class specific valuation
    asset_class_assessment: dict[str, Any] = {}
    val_status: ValuationStatus | None = None

    if resolved_asset_class == "FUND":
        und_val = record.get("underlying_valuation") or record.get("valuation_status")
        if und_val:
            clean_und = str(und_val).strip().upper()
            if clean_und in ("N_A", "N/A", "NA"):
                val_status = ValuationStatus.N_A
            elif clean_und in ("UNKNOWN", "UNASSESSED", "BELİRSİZ", "BILINMIYOR", "BİLİNMİYOR") or is_valuation_unassessed:
                val_status = ValuationStatus.UNKNOWN
            else:
                try:
                    val_status = ValuationStatus(clean_und)
                except ValueError:
                    val_status = ValuationStatus.UNKNOWN
            asset_class_assessment["underlying_valuation"] = val_status.value
        else:
            val_status = ValuationStatus.UNKNOWN
            asset_class_assessment["underlying_valuation"] = "UNKNOWN"

        fund_q = record.get("fund_quality")
        if fund_q:
            clean_q = str(fund_q).strip().upper()
            if clean_q in [q.value for q in FundQuality]:
                asset_class_assessment["fund_quality"] = clean_q
            elif clean_q in ("POOR", "KÖTÜ", "ZAYIF", "BATIK", "CRITICAL"):
                asset_class_assessment["fund_quality"] = FundQuality.POOR.value
            else:
                asset_class_assessment["fund_quality"] = clean_q
        else:
            asset_class_assessment["fund_quality"] = (
                FundQuality.POOR.value if is_frozen_or_liquidating else FundQuality.UNKNOWN.value
            )

        fund_att = record.get("fund_attractiveness")
        if fund_att:
            asset_class_assessment["fund_attractiveness"] = str(fund_att).strip().upper()

    elif resolved_asset_class == "CRYPTO":
        mkt_att = record.get("market_attractiveness") or record.get("valuation_status")
        if mkt_att:
            clean_mkt = str(mkt_att).strip().upper()
            asset_class_assessment["market_attractiveness"] = clean_mkt
            if clean_mkt == "ATTRACTIVE":
                val_status = ValuationStatus.ATTRACTIVE
            elif clean_mkt in ("NEUTRAL", "FAIR"):
                val_status = ValuationStatus.FAIR
            elif clean_mkt in ("UNATTRACTIVE", "EXPENSIVE"):
                val_status = ValuationStatus.EXPENSIVE
            elif clean_mkt in ("UNKNOWN", "UNASSESSED"):
                val_status = ValuationStatus.UNKNOWN
            elif clean_mkt in ("N_A", "N/A", "NA"):
                val_status = ValuationStatus.N_A
        net_ad = record.get("network_adoption")
        if net_ad:
            asset_class_assessment["network_adoption"] = str(net_ad).strip().upper()

    elif resolved_asset_class == "PRECIOUS_METALS":
        macro_att = record.get("macro_attractiveness") or record.get("valuation_status")
        if macro_att:
            clean_macro = str(macro_att).strip().upper()
            asset_class_assessment["macro_attractiveness"] = clean_macro
            if clean_macro == "ATTRACTIVE":
                val_status = ValuationStatus.ATTRACTIVE
            elif clean_macro in ("NEUTRAL", "FAIR"):
                val_status = ValuationStatus.FAIR
            elif clean_macro in ("UNATTRACTIVE", "EXPENSIVE"):
                val_status = ValuationStatus.EXPENSIVE
            elif clean_macro in ("UNKNOWN", "UNASSESSED"):
                val_status = ValuationStatus.UNKNOWN
            elif clean_macro in ("N_A", "N/A", "NA"):
                val_status = ValuationStatus.N_A
        macro_reg = record.get("macro_regime")
        if macro_reg:
            asset_class_assessment["macro_regime"] = str(macro_reg).strip().upper()

    # Fallback to standard valuation_status if not yet set
    if val_status is None:
        raw_val = record.get("valuation_status")
        if raw_val:
            clean_val = str(raw_val).strip().upper()
            if clean_val in ("N_A", "N/A", "NA"):
                val_status = ValuationStatus.N_A
            elif clean_val in ("UNKNOWN", "UNASSESSED", "BELİRSİZ") or is_valuation_unassessed:
                val_status = ValuationStatus.UNKNOWN
            else:
                try:
                    val_status = ValuationStatus(clean_val)
                except ValueError:
                    val_status = ValuationStatus.UNKNOWN
        else:
            val_status = ValuationStatus.UNKNOWN

    # Rule: If Human Brief explicitly says underlying assets were not valued, repair FAIR -> UNKNOWN
    if val_status == ValuationStatus.FAIR and is_valuation_unassessed:
        val_status = ValuationStatus.UNKNOWN
        if "underlying_valuation" in asset_class_assessment:
            asset_class_assessment["underlying_valuation"] = "UNKNOWN"

    # 3. Validate technical_status & Applicability
    raw_tech = record.get("technical_status")
    if raw_tech:
        clean_tech = str(raw_tech).strip().upper()
        if clean_tech in ("N_A", "N/A", "NA"):
            technical_status = TechnicalStatus.N_A
        elif clean_tech in ("UNKNOWN", "BELİRSİZ"):
            technical_status = TechnicalStatus.UNKNOWN
        else:
            try:
                technical_status = TechnicalStatus(clean_tech)
            except ValueError:
                technical_status = TechnicalStatus.UNKNOWN
    else:
        if is_frozen_or_liquidating or resolved_asset_class == "FUND":
            technical_status = TechnicalStatus.N_A
        else:
            technical_status = TechnicalStatus.UNKNOWN

    # Technical analysis is non-applicable for liquidating/frozen assets
    if is_frozen_or_liquidating and technical_status in (TechnicalStatus.NEUTRAL, TechnicalStatus.UNKNOWN):
        technical_status = TechnicalStatus.N_A

    # 4. Extract reasoning & auxiliary fields
    primary_reason = str(record.get("primary_reason") or "").strip()
    what_would_change_my_view = record.get("what_would_change_my_view")
    if what_would_change_my_view is not None:
        what_would_change_my_view = str(what_would_change_my_view).strip()

    def _str_tuple(key: str) -> tuple[str, ...]:
        v = record.get(key)
        if isinstance(v, list):
            return tuple(str(x).strip() for x in v if x is not None)
        elif isinstance(v, str) and v.strip():
            return (v.strip(),)
        return ()

    supporting_reasons = _str_tuple("supporting_reasons")
    key_risks = _str_tuple("key_risks")
    evidence_gaps = _str_tuple("evidence_gaps")

    # 5. Execution Status (AVAILABLE, RESTRICTED, BLOCKED, UNKNOWN)
    raw_exec = record.get("execution_status")
    if raw_exec:
        clean_exec = str(raw_exec).strip().upper()
        if clean_exec in [e.value for e in ExecutionStatus]:
            execution_status = ExecutionStatus(clean_exec)
        elif clean_exec in ("KISITLI", "LIMITED", "RESTRICTED"):
            execution_status = ExecutionStatus.RESTRICTED
        elif clean_exec in ("ENGELLİ", "BLOCKED", "FROZEN", "SUSPENDED"):
            execution_status = ExecutionStatus.BLOCKED
        else:
            execution_status = ExecutionStatus.UNKNOWN
    else:
        if is_frozen_or_liquidating:
            execution_status = ExecutionStatus.RESTRICTED
        else:
            execution_status = ExecutionStatus.AVAILABLE

    # If context says sales are blocked/suspended, repair AVAILABLE -> RESTRICTED
    if execution_status == ExecutionStatus.AVAILABLE and is_frozen_or_liquidating:
        execution_status = ExecutionStatus.RESTRICTED

    # 6. Secondary Certainty Fields
    recovery_value_confidence = record.get("recovery_value_confidence")
    if recovery_value_confidence is not None:
        recovery_value_confidence = str(recovery_value_confidence).strip().upper()
    elif is_frozen_or_liquidating:
        recovery_value_confidence = "LOW"

    execution_confidence = record.get("execution_confidence")
    if execution_confidence is not None:
        execution_confidence = str(execution_confidence).strip().upper()
    elif is_frozen_or_liquidating:
        execution_confidence = "LOW"

    data_quality_score = record.get("data_quality_score")
    if data_quality_score is not None:
        try:
            data_quality_score = int(data_quality_score)
        except (ValueError, TypeError):
            data_quality_score = None

    # 7. Normalize & Calibrate confidence (0-100)
    raw_conf = record.get("confidence") or record.get("confidence_score")
    confidence = normalize_confidence(raw_conf, default=70)

    # Post-validation confidence calibration against evidence gaps
    num_gaps = len(evidence_gaps)
    has_major_gap_text = is_frozen_or_liquidating or is_valuation_unassessed or any(
        kw in all_context_text for kw in [
            "recovery amount unknown", "kurtarma tutarı belirsiz",
            "unverified", "veri eksik", "incomplete data"
        ]
    )

    if num_gaps >= 3 or (has_major_gap_text and num_gaps >= 2):
        if confidence > 65:
            confidence = 65
    elif num_gaps >= 1 or has_major_gap_text:
        if confidence > 80:
            confidence = 80

    review_required_reason = record.get("review_required_reason")
    if review_required_reason is not None:
        review_required_reason = str(review_required_reason).strip()
        if not review_required_reason:
            review_required_reason = None

    # 8. Validate & Semantically Repair recommendation
    raw_rec = record.get("recommendation")
    if not raw_rec:
        raise MachineRecordValidationError("Missing required field 'recommendation'")
    try:
        rec = (
            raw_rec
            if isinstance(raw_rec, Recommendation)
            else Recommendation(str(raw_rec).strip().upper())
        )
    except ValueError:
        allowed = [r.value for r in Recommendation]
        raise MachineRecordValidationError(
            f"Invalid recommendation '{raw_rec}'; must be one of {allowed}"
        )

    # ------------------------------------------------------------------------
    # Deterministic Semantic Consistency & Repair Engine
    # ------------------------------------------------------------------------

    # RULE A: Technical uncertainty alone must NEVER cause final REVIEW_REQUIRED.
    if rec == Recommendation.REVIEW_REQUIRED:
        is_tech_reason = (
            (technical_status == TechnicalStatus.REVIEW_REQUIRED and (review_required_reason is None or len(review_required_reason) < 15))
            or (
                review_required_reason is not None
                and any(
                    kw in review_required_reason.lower()
                    for kw in ["technical", "chart", "price action", "indicator", "momentum", "trend", "teknik"]
                )
            )
        )
        if is_tech_reason:
            # Deterministically repair recommendation directionally based on thesis & valuation
            if thesis_status == ThesisStatus.INVALIDATED:
                rec = Recommendation.REDUCE
            elif thesis_status == ThesisStatus.STRONGER:
                rec = (
                    Recommendation.HOLD
                    if val_status == ValuationStatus.EXPENSIVE
                    else Recommendation.ADD
                )
            elif thesis_status == ThesisStatus.WEAKER:
                rec = (
                    Recommendation.REDUCE
                    if val_status == ValuationStatus.EXPENSIVE
                    else Recommendation.HOLD
                )
            else:  # UNCHANGED
                if val_status == ValuationStatus.ATTRACTIVE:
                    rec = Recommendation.ADD
                elif val_status == ValuationStatus.EXPENSIVE:
                    rec = Recommendation.REDUCE
                else:
                    rec = Recommendation.HOLD
            review_required_reason = None
            if not primary_reason:
                primary_reason = f"Directional view formed as {rec.value}; technical review alone does not block investment stance."

    # RULE B: Thesis INVALIDATED cannot coexist with ADD or HOLD, and should produce REDUCE or SELL.
    if thesis_status == ThesisStatus.INVALIDATED:
        if rec in (Recommendation.ADD, Recommendation.HOLD):
            rec = (
                Recommendation.SELL
                if val_status in (ValuationStatus.EXPENSIVE, ValuationStatus.UNKNOWN, ValuationStatus.N_A)
                else Recommendation.REDUCE
            )
            if not primary_reason:
                primary_reason = f"Repaired from contradictory {raw_rec} to {rec.value}: thesis is INVALIDATED."
        elif rec == Recommendation.REVIEW_REQUIRED:
            has_genuine_evidence_gap = bool(
                review_required_reason
                and any(
                    kw in review_required_reason.lower()
                    for kw in ["missing", "unavailable", "conflict", "incomplete", "unverified", "veri", "kaynak", "eksik"]
                )
                and len(review_required_reason) >= 15
            )
            if not has_genuine_evidence_gap:
                rec = (
                    Recommendation.SELL
                    if val_status in (ValuationStatus.EXPENSIVE, ValuationStatus.UNKNOWN, ValuationStatus.N_A)
                    else Recommendation.REDUCE
                )
                review_required_reason = None
                if not primary_reason:
                    primary_reason = f"Thesis is INVALIDATED based on available evidence; stance set to {rec.value}."

    # RULE C: Thesis WEAKER cannot coexist with ADD.
    if thesis_status == ThesisStatus.WEAKER and rec == Recommendation.ADD:
        rec = Recommendation.HOLD
        if not primary_reason:
            primary_reason = "Repaired from ADD to HOLD: thesis is WEAKER."

    # RULE D: Thesis STRONGER cannot coexist with SELL without critical risk reason.
    if thesis_status == ThesisStatus.STRONGER and rec == Recommendation.SELL:
        rec = Recommendation.HOLD
        if not primary_reason:
            primary_reason = "Repaired from SELL to HOLD: thesis is STRONGER."

    # RULE E: If REVIEW_REQUIRED remains, concrete review_required_reason is strictly required.
    if rec == Recommendation.REVIEW_REQUIRED:
        if not review_required_reason or len(review_required_reason.strip()) < 10:
            raise MachineRecordValidationError(
                "REVIEW_REQUIRED requires a concrete missing-evidence 'review_required_reason' (at least 10 chars)"
            )

    # RULE F: Execution restriction (RESTRICTED, BLOCKED) does NOT alter recommendation away from SELL/REDUCE.
    # Investment judgment and execution feasibility are independent dimensions.
    if thesis_status == ThesisStatus.INVALIDATED and execution_status in (
        ExecutionStatus.RESTRICTED,
        ExecutionStatus.BLOCKED,
    ):
        if rec not in (Recommendation.SELL, Recommendation.REDUCE):
            rec = Recommendation.SELL

    return DeepResearchRecord(
        thesis_status=thesis_status,
        valuation_status=val_status,
        technical_status=technical_status,
        recommendation=rec,
        confidence=confidence,
        execution_status=execution_status,
        recovery_value_confidence=recovery_value_confidence,
        execution_confidence=execution_confidence,
        data_quality_score=data_quality_score,
        primary_reason=primary_reason,
        supporting_reasons=supporting_reasons,
        key_risks=key_risks,
        what_would_change_my_view=what_would_change_my_view,
        evidence_gaps=evidence_gaps,
        review_required_reason=review_required_reason,
        assessment_type=resolved_asset_class,
        asset_class_assessment=asset_class_assessment,
        raw_record=dict(record),
    )


# ============================================================================
# 4. Dispatcher API
# ============================================================================


def validate_machine_record(protocol_name: str, machine_record: Any) -> Any:
    """Validate a protocol Machine Record using the appropriate protocol validator."""
    if not isinstance(protocol_name, str) or not protocol_name.strip():
        raise UnsupportedProtocolError("protocol_name must be non-empty text")

    canonical = protocol_name.strip().lower().replace("_", "-")
    if canonical == "thesis-review":
        return validate_thesis_review_record(machine_record)

    if canonical == "deep-research" or canonical.startswith("deep-research-"):
        return validate_deep_research_record(machine_record, protocol_name=canonical)

    raise UnsupportedProtocolError(
        f"Protocol '{protocol_name}' does not have a Machine Record validator"
    )
