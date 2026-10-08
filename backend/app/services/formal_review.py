"""Formal Review Orchestration Service.

Closes the intelligence loop:
BriefingItem -> Intentional Formal Review -> Finance Protocol -> Codex ->
PortfolioMindBridge -> IntelligenceReview -> InstrumentIntelligenceState -> DecisionLog.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import inspect
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional, Tuple
import uuid
from uuid import UUID

from fastapi import HTTPException, status
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.asset import Asset
from app.models.briefing import BriefingItem
from app.models.instrument import Instrument
from app.models.intelligence import IntelligenceReview
from app.services.auth import create_access_token
from app.services.intelligence import (
    get_active_technical_plan,
    get_intelligence_state,
    get_reviews,
)


def _find_finance_src() -> Optional[Path]:
    """Locate Finance/src across host, docker containers, and varying working directories."""
    # 1. Environment variable override
    env_src = os.environ.get("FINANCE_SRC")
    if env_src:
        p = Path(env_src).resolve()
        if p.is_dir():
            return p

    # 2. Check if investment_intelligence is already imported
    if "investment_intelligence" in sys.modules:
        mod = sys.modules["investment_intelligence"]
        mod_file = getattr(mod, "__file__", None)
        if mod_file:
            try:
                candidate = Path(mod_file).resolve().parent.parent
                if candidate.is_dir():
                    return candidate
            except Exception:
                pass

    # 3. Walk up from this file's path
    curr = Path(__file__).resolve().parent
    for parent in [curr, *curr.parents]:
        cand1 = parent / "Finance" / "src"
        if cand1.is_dir():
            return cand1
        if parent.name == "Finance" and (parent / "src").is_dir():
            return parent / "src"

    # 4. Walk up from cwd
    try:
        cwd = Path.cwd().resolve()
        for parent in [cwd, *cwd.parents]:
            cand1 = parent / "Finance" / "src"
            if cand1.is_dir():
                return cand1
            if parent.name == "Finance" and (parent / "src").is_dir():
                return parent / "src"
    except Exception:
        pass

    # 5. Standard container paths
    for container_cand in (Path("/Finance/src"), Path("/app/Finance/src")):
        if container_cand.is_dir():
            return container_cand

def _is_authorized_test_environment() -> bool:
    """Determine if execution is occurring within an authorized automated test environment."""
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return True
    if os.environ.get("ENVIRONMENT") in ("test", "testing"):
        return True
    if os.environ.get("TESTING") in ("1", "true", "True"):
        return True
    return False


_finance_src = _find_finance_src()
if _finance_src and str(_finance_src) not in sys.path:
    sys.path.insert(0, str(_finance_src))

_protocol_import_error: Optional[str] = None
try:
    from investment_intelligence.protocols import ProtocolNotFoundError, load_protocol
except Exception as err:
    _protocol_import_error = f"{type(err).__name__}: {err} (searched Finance/src: {_finance_src})"
    logging.getLogger(__name__).warning("Could not import Finance protocols: %s", _protocol_import_error)
    load_protocol = None  # type: ignore[assignment,misc]
    ProtocolNotFoundError = Exception  # type: ignore[assignment,misc]

_provider_import_error: Optional[str] = None
try:
    from investment_intelligence.codex_provider import CodexCLIProvider
    from investment_intelligence.execution import AIExecutionRequest, AIProvider
    from investment_intelligence.live_providers import GoogleNewsRSSProvider, SECDisclosureProvider
    from investment_intelligence.portfoliomind import (
        AsyncPortfolioMindClient,
        PortfolioMindBridge,
        PortfolioMindBridgeConfig,
    )
    from investment_intelligence.records import InstrumentRecord
except Exception as err:
    _provider_import_error = f"{type(err).__name__}: {err}"
    logging.getLogger(__name__).warning("Could not import Finance AI execution providers: %s", _provider_import_error)
    CodexCLIProvider = None  # type: ignore[assignment,misc]
    AIExecutionRequest = None  # type: ignore[assignment,misc]
    AIProvider = None  # type: ignore[assignment,misc]
    GoogleNewsRSSProvider = None  # type: ignore[assignment,misc]
    SECDisclosureProvider = None  # type: ignore[assignment,misc]
    AsyncPortfolioMindClient = None  # type: ignore[assignment,misc]
    PortfolioMindBridge = None  # type: ignore[assignment,misc]
    PortfolioMindBridgeConfig = None  # type: ignore[assignment,misc]
logger = logging.getLogger(__name__)


def _is_authentic_provider(provider: Any) -> bool:
    """Check if the provider is an authentic, non-synthetic production Codex CLI provider."""
    if provider is None:
        return False
    if CodexCLIProvider is not None and isinstance(CodexCLIProvider, type):
        return isinstance(provider, CodexCLIProvider)
    return False


# Strict canonical protocol mapping from Briefing recommendations
RECOMMENDED_REVIEW_PROTOCOL_MAP: dict[str, str] = {
    "THESIS_REVIEW": "thesis-review",
    "VALUATION_UPDATE": "valuation-update",
    "EARNINGS_REVIEW": "earnings-review",
    "TECHNICAL_REVIEW": "technical-review",
    "PRICE_REVIEW": "technical-review",
    "DEEP_RESEARCH": "deep-research",
    "DEEP_RESEARCH_EQUITY": "deep-research-equity",
    "DEEP_RESEARCH_CRYPTO": "deep-research-crypto",
    "DEEP_RESEARCH_FUND": "deep-research-fund",
    "DEEP_RESEARCH_GOLD": "deep-research-gold",
    "SCREENING": "preliminary-screening",
    "PRELIMINARY_SCREENING": "preliminary-screening",
}


def resolve_protocol_from_recommendation(
    recommended_review: Optional[str],
    review_required: bool = False,
) -> str:
    """Map a BriefingItem's recommended_review to an approved canonical Finance protocol.

    Raises ValueError if unsupported or empty when review is not required.
    """
    if recommended_review:
        clean = recommended_review.strip().upper().replace("-", "_")
        if clean in RECOMMENDED_REVIEW_PROTOCOL_MAP:
            return RECOMMENDED_REVIEW_PROTOCOL_MAP[clean]
        if clean in ("NONE", "") and review_required:
            return "thesis-review"
        raise ValueError(f"Unsupported review recommendation: '{recommended_review}'")

    if review_required:
        return "thesis-review"

    raise ValueError("Briefing item does not recommend or require a review")


async def execute_briefing_formal_review(
    db: AsyncSession,
    briefing_item_id: UUID,
    user_id: UUID,
    force_rerun: bool = False,
    ai_provider: Optional[Any] = None,
) -> dict[str, Any]:
    """Execute a formal Finance review protocol triggered from a Briefing item.

    Coordinates:
    1. Authorization & BriefingItem eligibility validation.
    2. Protocol name resolution via strict whitelist mapping.
    3. Idempotency check: reuses existing review unless force_rerun is True.
    4. Bounded context assembly (Instrument state + Briefing event + live evidence).
    5. CodexCLI protocol execution with ephemeral, read-only sandbox protections.
    6. Sync through PortfolioMindBridge (creates IntelligenceReview and updates state).
    7. State-change DecisionLog creation via existing bridge/review hooks.
    8. Linkage back to the triggering BriefingItem.
    """
    # 1. Fetch BriefingItem and verify ownership
    stmt = (
        select(BriefingItem)
        .options(selectinload(BriefingItem.instrument))
        .where(BriefingItem.id == briefing_item_id, BriefingItem.user_id == user_id)
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing item not found",
        )

    inst = item.instrument
    if inst is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated instrument not found",
        )

    # 2. Check eligibility & resolve protocol
    source_meta = dict(item.source_metadata or {})
    recommended_review = source_meta.get("recommended_review")
    try:
        protocol_name = resolve_protocol_from_recommendation(
            recommended_review=recommended_review,
            review_required=item.review_required,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 3. Idempotency check: reuse existing completed review if not forcing re-run
    existing_review_id = source_meta.get("triggered_review_id")
    if existing_review_id and not force_rerun:
        try:
            rev_uuid = UUID(existing_review_id)
            rev_stmt = select(IntelligenceReview).where(IntelligenceReview.id == rev_uuid)
            rev_res = await db.execute(rev_stmt)
            existing_rev = rev_res.scalar_one_or_none()
            if existing_rev is not None:
                return {
                    "status": "COMPLETED",
                    "review_id": str(existing_rev.id),
                    "protocol": existing_rev.protocol,
                    "summary": source_meta.get("review_summary"),
                    "reused": True,
                }
        except Exception as e:
            logger.debug("Failed to fetch existing review %s: %s", existing_review_id, e)

    # 4. Load canonical protocol file
    if load_protocol is None:
        detail_msg = f"Protocol loading subsystem unavailable: {_protocol_import_error or 'unknown import failure'}"
        logger.error(detail_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg,
        )

    try:
        proto_def = load_protocol(protocol_name)
    except ProtocolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved protocol '{protocol_name}' file not found: {e}",
        )

    # 5. Assemble bounded context
    now = datetime.now(timezone.utc)

    # A. Persistent instrument context
    state = await get_intelligence_state(db, inst.id)
    recent_reviews = await get_reviews(db, inst.id, limit=3)
    plan = await get_active_technical_plan(db, inst.id)

    # Position holding context
    asset_stmt = select(Asset).where(
        Asset.instrument_id == inst.id, Asset.user_id == user_id
    )
    asset_res = await db.execute(asset_stmt)
    holding_asset = asset_res.scalars().first()

    persistent_context: dict[str, Any] = {
        "instrument": {
            "symbol": inst.symbol,
            "name": inst.name,
            "asset_type": inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            "exchange": inst.exchange,
            "currency": inst.currency,
        },
        "intelligence_state": {
            "thesis_status": state.thesis_status.value if (state and state.thesis_status) else None,
            "valuation_status": state.valuation_status.value if (state and state.valuation_status) else None,
            "technical_status": state.technical_status.value if (state and state.technical_status) else None,
            "recommendation": state.recommendation.value if (state and state.recommendation) else None,
            "human_brief": state.human_brief if state else None,
            "last_review_at": state.last_review_at.isoformat() if (state and state.last_review_at) else None,
        } if state else None,
        "recent_reviews": [
            {
                "protocol": r.protocol,
                "confidence": r.confidence,
                "human_brief": r.human_brief,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_reviews
        ],
        "active_technical_plan": {
            "trend_expectation": plan.trend_expectation,
            "notes": plan.notes,
        } if plan else None,
        "portfolio_position": {
            "asset_id": str(holding_asset.id),
            "current_price": float(holding_asset.current_price) if holding_asset.current_price else None,
            "currency": holding_asset.current_price_currency,
        } if holding_asset else None,
    }

    # B. Supplemental Briefing & live evidence context
    briefing_context = {
        "briefing_item_id": str(item.id),
        "headline": item.headline,
        "summary": item.summary,
        "why_it_matters": item.why_it_matters,
        "impact": item.impact.value if hasattr(item.impact, "value") else str(item.impact),
        "materiality": item.materiality.value if hasattr(item.materiality, "value") else str(item.materiality),
        "time_horizon": item.time_horizon.value if hasattr(item.time_horizon, "value") else str(item.time_horizon),
        "category": item.category.value if hasattr(item.category, "value") else str(item.category),
        "preliminary_thesis_impact": item.thesis_impact.value if hasattr(item.thesis_impact, "value") else str(item.thesis_impact),
        "recommended_review": recommended_review,
        "briefing_codex_confidence": source_meta.get("reasoning_confidence"),
        "source": source_meta.get("source"),
        "source_url": source_meta.get("url"),
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }

    supplemental_context: dict[str, Any] = {
        "triggering_briefing_event": briefing_context,
        "review_request": {
            "protocol": proto_def.canonical_name,
            "requested_at": now.isoformat(),
        },
    }

    # C. Bounded live provider evidence
    try:
        inst_rec = InstrumentRecord(
            inst.id,
            inst.symbol,
            inst.name,
            inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            exchange=inst.exchange,
            currency=inst.currency,
        )
        if GoogleNewsRSSProvider:
            news_provider = GoogleNewsRSSProvider([inst_rec])
            news_items = news_provider.get_recent_news(
                instrument=inst_rec,
                since=now - timedelta(days=7),
                limit=5,
            )
            supplemental_context["recent_news"] = [
                {"title": n.title, "source": n.source, "url": n.url, "published_at": n.published_at.isoformat()}
                for n in news_items
            ]
        if SECDisclosureProvider and (inst.exchange or "").upper() in {"NASDAQ", "NYSE", "BATS", "ARCA", "AMEX"}:
            sec_provider = SECDisclosureProvider([inst_rec])
            sec_items = sec_provider.get_recent_disclosures(
                inst_rec,
                since=now - timedelta(days=14),
                limit=3,
            )
            supplemental_context["recent_sec_filings"] = [
                {"disclosure_type": s.disclosure_type, "title": s.title, "url": s.url, "published_at": s.published_at.isoformat()}
                for s in sec_items
            ]
    except Exception as e:
        logger.debug("Live provider collection for %s skipped: %s", inst.symbol, e)

    # 6. Execute Protocol via AIProvider (Codex CLI)
    active_provider = ai_provider
    if active_provider is not None:
        is_authentic = _is_authentic_provider(active_provider)
        if not is_authentic and not _is_authorized_test_environment():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Synthetic or mock AI execution is strictly prohibited from mutating user intelligence state outside test environments.",
            )

    _codex_init_error: Optional[str] = None
    if active_provider is None:
        if CodexCLIProvider is not None:
            try:
                active_provider = CodexCLIProvider(
                    default_timeout=settings.CODEX_DEFAULT_TIMEOUT_SECONDS,
                    deep_research_timeout=settings.CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS,
                )
            except Exception as e:
                _codex_init_error = str(e)
                logger.warning("CodexCLIProvider could not be initialized: %s", e)
                active_provider = None
        else:
            _codex_init_error = _provider_import_error or "CodexCLIProvider could not be imported"

    if active_provider is None:
        detail_msg = "AI protocol execution engine is currently unavailable"
        if _codex_init_error:
            detail_msg += f": {_codex_init_error}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail_msg,
        )

    execution_req = AIExecutionRequest(
        protocol_name=proto_def.canonical_name,
        protocol_text=proto_def.content,
        persistent_context=persistent_context,
        supplemental_context=supplemental_context,
        execution_metadata={
            "trigger": "BRIEFING_ITEM",
            "briefing_item_id": str(item.id),
            "workflow": proto_def.canonical_name,
            "user_id": str(user_id),
            "instrument_symbol": inst.symbol,
        },
    )

    start_time = time.monotonic()
    configured_timeout = (
        active_provider.resolve_timeout(execution_req)
        if hasattr(active_provider, "resolve_timeout")
        else (
            settings.CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS
            if proto_def.canonical_name.startswith("deep-research")
            else settings.CODEX_DEFAULT_TIMEOUT_SECONDS
        )
    )

    try:
        if inspect.iscoroutinefunction(active_provider.execute):
            ai_result = await active_provider.execute(execution_req)
        else:
            ai_result = await asyncio.to_thread(active_provider.execute, execution_req)
    except Exception as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "Formal review protocol execution failed for %s (%s) after %.1fs (timeout: %.1fs): %s",
            inst.symbol,
            proto_def.canonical_name,
            elapsed,
            configured_timeout,
            e,
            exc_info=True,
        )
        source_meta["review_status"] = "FAILED"
        source_meta["review_error"] = str(e)
        item.source_metadata = source_meta
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Protocol execution failed: {e}",
        )

    # 7. Construct ProtocolRun record for PortfolioMindBridge
    run_id = f"briefing_review_{item.id}_{uuid.uuid4().hex[:8]}_{now.strftime('%Y%m%d%H%M%S')}"
    machine_record = dict(ai_result.machine_record or {})
    # Embed triggering briefing context into machine_record for transparent provenance
    machine_record["triggering_briefing_item_id"] = str(item.id)
    machine_record["briefing_headline"] = item.headline

    canonical_proto = proto_def.canonical_name.strip().lower().replace("_", "-")
    if canonical_proto == "deep-research" or canonical_proto.startswith("deep-research-"):
        from investment_intelligence.validation import validate_deep_research_record
        validated_mr = validate_deep_research_record(
            machine_record,
            asset_type=inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            protocol_name=canonical_proto,
        )
        machine_record = validated_mr.to_dict()
        if not ai_result.confidence:
            ai_result.confidence = f"{validated_mr.confidence}%"

    run_record = {
        "id": run_id,
        "protocol_name": proto_def.canonical_name,
        "status": "COMPLETED",
        "machine_record": machine_record,
        "human_brief": ai_result.human_brief,
        "confidence": ai_result.confidence,
        "is_synthetic": not _is_authentic_provider(active_provider),
    }
    finance_instrument = {
        "symbol": inst.symbol,
        "instrument_type": inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
        "venue": inst.exchange,
        "currency": inst.currency,
    }

    # 8. Sync via PortfolioMindBridge
    from app.main import app

    token = create_access_token(user_id)
    transport = httpx.ASGITransport(app=app)
    config = PortfolioMindBridgeConfig(
        enabled=True,
        base_url="http://test",
        api_token=token,
    )
    client = AsyncPortfolioMindClient(config=config, transport=transport)
    bridge = PortfolioMindBridge(client=client, config=config)

    sync_result = await bridge.async_sync_protocol_run(
        run_record=run_record,
        finance_instrument=finance_instrument,
        research_path=None,
        auto_apply_state=True,
        raise_on_error=True,
    )

    if not sync_result.synced or not sync_result.review_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bridge synchronization failed: {sync_result.error}",
        )

    # 9. Link Review back to BriefingItem
    source_meta["triggered_review_id"] = str(sync_result.review_id)
    source_meta["review_status"] = "COMPLETED"
    source_meta["triggered_protocol"] = proto_def.canonical_name
    source_meta["triggered_at"] = now.isoformat()
    source_meta["review_summary"] = {
        "protocol": proto_def.canonical_name,
        "thesis_status": machine_record.get("thesis_status"),
        "valuation_status": machine_record.get("valuation_status"),
        "technical_status": machine_record.get("technical_status"),
        "recommendation": machine_record.get("recommendation"),
        "confidence": ai_result.confidence,
        "human_brief": ai_result.human_brief,
        "state_updated": sync_result.state_updated,
        "primary_reason": machine_record.get("primary_reason"),
        "confidence_score": machine_record.get("confidence_score"),
        "assessment_type": machine_record.get("assessment_type"),
        "asset_class_assessment": machine_record.get("asset_class_assessment"),
    }
    source_meta.pop("review_error", None)

    item.source_metadata = source_meta
    await db.commit()
    await db.refresh(item)

    return {
        "status": "COMPLETED",
        "review_id": str(sync_result.review_id),
        "protocol": proto_def.canonical_name,
        "summary": source_meta["review_summary"],
        "reused": False,
    }


async def get_briefing_formal_review_status(
    db: AsyncSession,
    briefing_item_id: UUID,
    user_id: UUID,
) -> dict[str, Any]:
    """Retrieve the formal review status and linked review record for a Briefing item."""
    stmt = select(BriefingItem).where(
        BriefingItem.id == briefing_item_id, BriefingItem.user_id == user_id
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing item not found",
        )

    source_meta = item.source_metadata or {}
    review_status = source_meta.get("review_status")
    review_id = source_meta.get("triggered_review_id")

    if review_id and review_status == "COMPLETED":
        return {
            "status": "COMPLETED",
            "review_id": review_id,
            "protocol": source_meta.get("triggered_protocol"),
            "summary": source_meta.get("review_summary"),
            "error": None,
        }

    if review_status == "FAILED":
        return {
            "status": "FAILED",
            "review_id": None,
            "protocol": None,
            "summary": None,
            "error": source_meta.get("review_error"),
        }

    return {
        "status": "READY",
        "review_id": None,
        "protocol": None,
        "summary": None,
        "error": None,
    }


SUPPORTED_DEEP_RESEARCH_TYPES: dict[str, str] = {
    "STOCK": "deep-research-equity",
    "EQUITY": "deep-research-equity",
    "CRYPTO": "deep-research-crypto",
    "FUND": "deep-research-fund",
    "FUNDS": "deep-research-fund",
    "PRECIOUS_METALS": "deep-research-gold",
    "GOLD": "deep-research-gold",
}


def resolve_specialized_protocol(base_protocol: str, asset_type: Any) -> str:
    """Resolve an asset-class specialized protocol when deep research is requested."""
    clean = base_protocol.strip().lower().replace("_", "-")
    resolved = RECOMMENDED_REVIEW_PROTOCOL_MAP.get(clean.upper().replace("-", "_"), clean)
    raw_type = asset_type.value if hasattr(asset_type, "value") else str(asset_type).upper()

    if resolved in ("deep-research", "deep_research"):
        if raw_type in SUPPORTED_DEEP_RESEARCH_TYPES:
            return SUPPORTED_DEEP_RESEARCH_TYPES[raw_type]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Deep Research is not supported for asset type '{raw_type}'. Supported types: STOCK, CRYPTO, FUND, PRECIOUS_METALS.",
        )
    elif resolved.startswith("deep-research-"):
        if raw_type not in SUPPORTED_DEEP_RESEARCH_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deep Research is not supported for asset type '{raw_type}'. Supported types: STOCK, CRYPTO, FUND, PRECIOUS_METALS.",
            )
        return resolved

    return resolved


async def execute_instrument_formal_review(
    db: AsyncSession,
    instrument_id: UUID,
    protocol_name: str,
    user_id: UUID,
    ai_provider: Optional[Any] = None,
) -> dict[str, Any]:
    """Execute a formal Finance protocol for an instrument directly (e.g. from opportunity queue or UI)."""
    inst_stmt = select(Instrument).where(Instrument.id == instrument_id)
    inst_res = await db.execute(inst_stmt)
    inst = inst_res.scalar_one_or_none()
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    resolved_proto = resolve_specialized_protocol(protocol_name, inst.asset_type)

    if load_protocol is None:
        detail_msg = f"Protocol loading subsystem unavailable: {_protocol_import_error or 'unknown import failure'}"
        logger.error(detail_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg,
        )

    try:
        proto_def = load_protocol(resolved_proto)
    except ProtocolNotFoundError as e:
        if resolved_proto.startswith("deep-research-"):
            try:
                proto_def = load_protocol("deep-research")
            except ProtocolNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Approved protocol '{resolved_proto}' file not found: {e}",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approved protocol '{resolved_proto}' file not found: {e}",
            )

    now = datetime.now(timezone.utc)
    state = await get_intelligence_state(db, inst.id)
    recent_reviews = await get_reviews(db, inst.id, limit=3)
    plan = await get_active_technical_plan(db, inst.id)

    # Position holding context if user owns this asset
    asset_stmt = select(Asset).where(
        Asset.instrument_id == inst.id, Asset.user_id == user_id
    )
    asset_res = await db.execute(asset_stmt)
    holding_asset = asset_res.scalars().first()
    holding_data = None
    if holding_asset is not None:
        from app.services.asset import get_asset_with_stats
        pair = await get_asset_with_stats(db, holding_asset.id, user_id)
        if pair is not None:
            _, stats = pair

            def _to_float(v: Any) -> Optional[float]:
                if v is None:
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            holding_data = {
                "total_quantity": _to_float(stats.get("total_quantity")),
                "avg_cost": _to_float(stats.get("avg_cost")),
                "total_cost": _to_float(stats.get("total_cost")),
                "realized_pl": _to_float(stats.get("realized_pl")),
                "current_price": _to_float(holding_asset.current_price),
                "currency": holding_asset.current_price_currency or inst.currency,
            }

    persistent_context: dict[str, Any] = {
        "instrument": {
            "symbol": inst.symbol,
            "name": inst.name,
            "asset_type": inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            "exchange": inst.exchange,
            "currency": inst.currency,
        },
        "intelligence_state": {
            "thesis_status": state.thesis_status.value if (state and state.thesis_status) else None,
            "valuation_status": state.valuation_status.value if (state and state.valuation_status) else None,
            "technical_status": state.technical_status.value if (state and state.technical_status) else None,
            "recommendation": state.recommendation.value if (state and state.recommendation) else None,
            "human_brief": state.human_brief if state else None,
            "last_review_at": state.last_review_at.isoformat() if (state and state.last_review_at) else None,
        } if state else None,
        "recent_reviews": [
            {
                "protocol": r.protocol,
                "confidence": r.confidence,
                "human_brief": r.human_brief,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_reviews
        ],
        "active_technical_plan": {
            "trend_expectation": plan.trend_expectation,
            "notes": plan.notes,
        } if plan else None,
        "user_holding": holding_data,
    }

    supplemental_context = {
        "review_request": {
            "protocol": proto_def.canonical_name,
            "requested_at": now.isoformat(),
            "trigger": "OPPORTUNITY_RESEARCH_ACTION",
        },
    }

    active_provider = ai_provider
    if active_provider is not None:
        is_authentic = _is_authentic_provider(active_provider)
        if not is_authentic and not _is_authorized_test_environment():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Synthetic or mock AI execution is strictly prohibited from mutating user intelligence state outside test environments.",
            )

    _codex_init_error: Optional[str] = None
    if active_provider is None:
        if CodexCLIProvider is not None:
            try:
                active_provider = CodexCLIProvider(
                    default_timeout=settings.CODEX_DEFAULT_TIMEOUT_SECONDS,
                    deep_research_timeout=settings.CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS,
                )
            except Exception as e:
                _codex_init_error = str(e)
                logger.warning("CodexCLIProvider could not be initialized: %s", e)
                active_provider = None
        else:
            _codex_init_error = _provider_import_error or "CodexCLIProvider could not be imported"

    if active_provider is None:
        detail_msg = "AI protocol execution engine is currently unavailable"
        if _codex_init_error:
            detail_msg += f": {_codex_init_error}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail_msg,
        )

    execution_req = AIExecutionRequest(
        protocol_name=proto_def.canonical_name,
        protocol_text=proto_def.content,
        persistent_context=persistent_context,
        supplemental_context=supplemental_context,
        execution_metadata={
            "trigger": "OPPORTUNITY_QUEUE",
            "instrument_id": str(inst.id),
            "workflow": proto_def.canonical_name,
            "user_id": str(user_id),
            "instrument_symbol": inst.symbol,
        },
    )

    start_time = time.monotonic()
    configured_timeout = (
        active_provider.resolve_timeout(execution_req)
        if hasattr(active_provider, "resolve_timeout")
        else (
            settings.CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS
            if proto_def.canonical_name.startswith("deep-research")
            else settings.CODEX_DEFAULT_TIMEOUT_SECONDS
        )
    )

    try:
        if inspect.iscoroutinefunction(active_provider.execute):
            ai_result = await active_provider.execute(execution_req)
        else:
            ai_result = await asyncio.to_thread(active_provider.execute, execution_req)
    except Exception as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "Direct formal review failed for %s (%s) after %.1fs (timeout: %.1fs): %s",
            inst.symbol,
            proto_def.canonical_name,
            elapsed,
            configured_timeout,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Protocol execution failed: {e}",
        )

    run_id = f"opp_review_{inst.id}_{uuid.uuid4().hex[:8]}_{now.strftime('%Y%m%d%H%M%S')}"
    machine_record = dict(ai_result.machine_record or {})

    canonical_proto = proto_def.canonical_name.strip().lower().replace("_", "-")
    if canonical_proto == "deep-research" or canonical_proto.startswith("deep-research-"):
        from investment_intelligence.validation import validate_deep_research_record
        validated_mr = validate_deep_research_record(
            machine_record,
            asset_type=inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            protocol_name=canonical_proto,
        )
        machine_record = validated_mr.to_dict()
        if not ai_result.confidence:
            ai_result.confidence = f"{validated_mr.confidence}%"

    run_record = {
        "id": run_id,
        "protocol_name": proto_def.canonical_name,
        "status": "COMPLETED",
        "machine_record": machine_record,
        "human_brief": ai_result.human_brief,
        "confidence": ai_result.confidence,
        "is_synthetic": not _is_authentic_provider(active_provider),
    }
    finance_instrument = {
        "id": str(inst.id),
        "symbol": inst.symbol,
        "instrument_type": inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
        "venue": inst.exchange,
        "currency": inst.currency,
    }

    from app.main import app

    token = create_access_token(user_id)
    transport = httpx.ASGITransport(app=app)
    config = PortfolioMindBridgeConfig(enabled=True, base_url="http://test", api_token=token)
    client = AsyncPortfolioMindClient(config=config, transport=transport)
    bridge = PortfolioMindBridge(client=client, config=config)

    sync_result = await bridge.async_sync_protocol_run(
        run_record=run_record,
        finance_instrument=finance_instrument,
        research_path=None,
        auto_apply_state=True,
        raise_on_error=True,
    )

    if not sync_result.synced or not sync_result.review_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bridge synchronization failed: {sync_result.error}",
        )

    # If WatchlistItem exists, progress research stage logically
    from app.models.opportunity import ResearchStage, WatchlistItem
    wl_stmt = select(WatchlistItem).where(
        WatchlistItem.user_id == user_id, WatchlistItem.instrument_id == inst.id
    )
    wl_res = await db.execute(wl_stmt)
    wl_item = wl_res.scalar_one_or_none()
    if wl_item is not None:
        if proto_def.canonical_name == "preliminary-screening" and wl_item.research_stage == ResearchStage.DISCOVERED:
            wl_item.research_stage = ResearchStage.SCREENED
        elif proto_def.canonical_name.startswith("deep-research") and wl_item.research_stage in (ResearchStage.DISCOVERED, ResearchStage.SCREENED):
            wl_item.research_stage = ResearchStage.VALUED
        await db.commit()

    return {
        "status": "COMPLETED",
        "review_id": str(sync_result.review_id),
        "protocol": proto_def.canonical_name,
        "summary": {
            "protocol": proto_def.canonical_name,
            "thesis_status": machine_record.get("thesis_status"),
            "valuation_status": machine_record.get("valuation_status"),
            "technical_status": machine_record.get("technical_status"),
            "recommendation": machine_record.get("recommendation"),
            "confidence": ai_result.confidence,
            "human_brief": ai_result.human_brief,
            "state_updated": sync_result.state_updated,
            "primary_reason": machine_record.get("primary_reason"),
            "confidence_score": machine_record.get("confidence_score"),
            "assessment_type": machine_record.get("assessment_type"),
            "asset_class_assessment": machine_record.get("asset_class_assessment"),
            "execution_status": machine_record.get("execution_status"),
            "recovery_value_confidence": machine_record.get("recovery_value_confidence"),
            "execution_confidence": machine_record.get("execution_confidence"),
            "data_quality_score": machine_record.get("data_quality_score"),
        },
    }

