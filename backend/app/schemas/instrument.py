import uuid
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.asset import AssetType

if TYPE_CHECKING:
    from app.schemas.intelligence import IntelligenceStateResponse


class InstrumentResponse(BaseModel):
    """Canonical representation of an investment instrument."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: Optional[str] = None
    name: str
    asset_type: AssetType
    exchange: Optional[str] = None
    currency: Optional[str] = None
    country: Optional[str] = None
    isin: Optional[str] = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    intelligence_state: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data: Any) -> Any:
        if not isinstance(data, dict) and hasattr(data, "__dict__"):
            from sqlalchemy import inspect as sa_inspect

            insp = sa_inspect(data)
            intel_state = None
            if "intelligence_state" not in insp.unloaded:
                raw_state = getattr(data, "intelligence_state", None)
                if raw_state is not None:
                    from app.schemas.intelligence import IntelligenceStateResponse

                    intel_state = (
                        IntelligenceStateResponse.model_validate(raw_state).model_dump(mode="json")
                        if not isinstance(raw_state, dict)
                        else dict(raw_state)
                    )
                    if "reviews" not in insp.unloaded:
                        reviews = getattr(data, "reviews", None)
                        if reviews and len(reviews) > 0:
                            latest_rev = reviews[0]
                            mr = getattr(latest_rev, "machine_record", None) or {}
                            if not intel_state.get("confidence"):
                                intel_state["confidence"] = getattr(latest_rev, "confidence", None) or (
                                    f"{mr['confidence_score']}%" if "confidence_score" in mr else (
                                        f"{mr['confidence']}%" if "confidence" in mr and isinstance(mr["confidence"], (int, float)) and mr["confidence"] > 1 else str(mr.get("confidence") or "")
                                    )
                                ) or None
                            if intel_state.get("confidence_score") is None:
                                intel_state["confidence_score"] = mr.get("confidence_score") or (
                                    mr.get("confidence") if isinstance(mr.get("confidence"), int) else None
                                )
                            if not intel_state.get("confidence_level"):
                                intel_state["confidence_level"] = mr.get("confidence_level")
                            if not intel_state.get("execution_status"):
                                intel_state["execution_status"] = mr.get("execution_status")
                            if not intel_state.get("recovery_value_confidence"):
                                intel_state["recovery_value_confidence"] = mr.get("recovery_value_confidence")
                            if not intel_state.get("execution_confidence"):
                                intel_state["execution_confidence"] = mr.get("execution_confidence")
                            if intel_state.get("data_quality_score") is None:
                                intel_state["data_quality_score"] = mr.get("data_quality_score")
                            if not intel_state.get("primary_reason"):
                                intel_state["primary_reason"] = mr.get("primary_reason")
                            if not intel_state.get("supporting_reasons"):
                                intel_state["supporting_reasons"] = mr.get("supporting_reasons")
                            if not intel_state.get("key_risks"):
                                intel_state["key_risks"] = mr.get("key_risks")
                            if not intel_state.get("what_would_change_my_view"):
                                intel_state["what_would_change_my_view"] = mr.get("what_would_change_my_view")
                            if not intel_state.get("evidence_gaps"):
                                intel_state["evidence_gaps"] = mr.get("evidence_gaps")
                            if not intel_state.get("review_required_reason"):
                                intel_state["review_required_reason"] = mr.get("review_required_reason")
                            if not intel_state.get("assessment_type"):
                                intel_state["assessment_type"] = mr.get("assessment_type")
                            if not intel_state.get("asset_class_assessment"):
                                intel_state["asset_class_assessment"] = mr.get("asset_class_assessment")

            return {
                "id": data.id,
                "symbol": data.symbol,
                "name": data.name,
                "asset_type": data.asset_type,
                "exchange": data.exchange,
                "currency": data.currency,
                "country": data.country,
                "isin": data.isin,
                "provider": data.provider,
                "provider_id": data.provider_id,
                "intelligence_state": intel_state,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class InstrumentCreateRequest(BaseModel):
    """Schema for creating an instrument directly."""

    symbol: Optional[str] = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    asset_type: AssetType
    exchange: Optional[str] = Field(default=None, max_length=50)
    currency: Optional[str] = Field(default=None, max_length=3)
    country: Optional[str] = Field(default=None, max_length=50)
    isin: Optional[str] = Field(default=None, max_length=50)
    provider: Optional[str] = Field(default=None, max_length=50)
    provider_id: Optional[str] = Field(default=None, max_length=100)


class InstrumentUpdateRequest(BaseModel):
    """Schema for updating an instrument."""

    symbol: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    asset_type: Optional[AssetType] = None
    exchange: Optional[str] = Field(default=None, max_length=50)
    currency: Optional[str] = Field(default=None, max_length=3)
    country: Optional[str] = Field(default=None, max_length=50)
    isin: Optional[str] = Field(default=None, max_length=50)
    provider: Optional[str] = Field(default=None, max_length=50)
    provider_id: Optional[str] = Field(default=None, max_length=100)
