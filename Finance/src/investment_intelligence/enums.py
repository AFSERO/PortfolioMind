"""Independent intelligence dimensions; unreviewed dimensions remain null."""

from enum import StrEnum


class ThesisStatus(StrEnum):
    STRONGER = "STRONGER"
    UNCHANGED = "UNCHANGED"
    WEAKER = "WEAKER"
    INVALIDATED = "INVALIDATED"


class ValuationStatus(StrEnum):
    ATTRACTIVE = "ATTRACTIVE"
    FAIR = "FAIR"
    EXPENSIVE = "EXPENSIVE"
    UNKNOWN = "UNKNOWN"
    N_A = "N_A"


class TechnicalStatus(StrEnum):
    ON_TRACK = "ON_TRACK"
    PULLBACK = "PULLBACK"
    EXTENDED = "EXTENDED"
    BREAKDOWN = "BREAKDOWN"
    NEUTRAL = "NEUTRAL"
    DEVIATED = "DEVIATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"
    N_A = "N_A"


class Recommendation(StrEnum):
    ADD = "ADD"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ExecutionStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class FundQuality(StrEnum):
    STRONG = "STRONG"
    ACCEPTABLE = "ACCEPTABLE"
    WEAK = "WEAK"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


class ProtocolRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
