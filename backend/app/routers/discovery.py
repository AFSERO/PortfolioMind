"""FastAPI router for Market-Wide Discovery Engine v1."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.discovery import DiscoveryTriggerType, DiscoveryUniverse
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.discovery import (
    ActionResponse,
    DiscoveryCandidateResponse,
    DiscoveryRunResponse,
    TriggerScanRequest,
)
from app.services import discovery as discovery_service
from app.services import formal_review as formal_review_service

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _candidate_to_response(cand) -> DiscoveryCandidateResponse:
    inst = getattr(cand, "instrument", None)
    return DiscoveryCandidateResponse(
        id=cand.id,
        run_id=cand.run_id,
        instrument_id=cand.instrument_id,
        symbol=inst.symbol if inst else None,
        name=inst.name if inst else None,
        asset_type=inst.asset_type.value if inst and inst.asset_type else None,
        exchange=inst.exchange if inst else None,
        currency=inst.currency if inst else None,
        status=cand.status.value if hasattr(cand.status, "value") else str(cand.status),
        candidate_state=cand.candidate_state.value if hasattr(cand.candidate_state, "value") else str(cand.candidate_state),
        primary_reason=cand.primary_reason,
        signals=cand.signals or [],
        key_question=cand.key_question,
        key_risk=cand.key_risk,
        suggested_next_step=cand.suggested_next_step.value if hasattr(cand.suggested_next_step, "value") else str(cand.suggested_next_step),
        confidence=cand.confidence.value if hasattr(cand.confidence, "value") else str(cand.confidence),
        score_band=cand.score_band,
        current_price=float(cand.current_price) if cand.current_price is not None else None,
        current_price_currency=cand.current_price_currency,
        market_data_snapshot=cand.market_data_snapshot or {},
        source_metadata=cand.source_metadata or {},
        created_at=cand.created_at,
    )


def _run_to_response(run) -> DiscoveryRunResponse:
    cands = [_candidate_to_response(c) for c in (run.candidates or [])]
    return DiscoveryRunResponse(
        id=run.id,
        universe=run.universe,
        trigger_type=run.trigger_type.value if hasattr(run.trigger_type, "value") else str(run.trigger_type),
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        instruments_scanned=run.instruments_scanned,
        candidates_filtered=run.candidates_filtered,
        candidates_reasoned=run.candidates_reasoned,
        candidates_surfaced=run.candidates_surfaced,
        started_at=run.started_at,
        completed_at=run.completed_at,
        diagnostics=run.diagnostics or {},
        candidates=cands,
    )


@router.get("/runs/latest", response_model=Optional[DiscoveryRunResponse])
async def get_latest_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent discovery run and surfaced candidates for current user."""
    run = await discovery_service.get_latest_discovery_run(db, current_user.id)
    if run is None:
        return None
    return _run_to_response(run)


@router.post("/scan", response_model=DiscoveryRunResponse)
async def trigger_discovery_scan(
    body: Optional[TriggerScanRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an on-demand market-wide discovery scan."""
    universe_str = (body.universe if body and body.universe else DiscoveryUniverse.US_LARGE_CAP.value)
    force = body.force_refresh if body else False

    run = await discovery_service.run_discovery_scan_for_user(
        db=db,
        user_id=current_user.id,
        universe=universe_str,
        trigger_type=DiscoveryTriggerType.MANUAL,
        force_refresh=force,
    )
    # Reload with relations
    reloaded = await discovery_service.get_latest_discovery_run(db, current_user.id)
    return _run_to_response(reloaded or run)


@router.post("/candidates/{candidate_id}/add-to-watchlist", response_model=ActionResponse)
async def add_candidate_to_watchlist(
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote a discovered candidate into the active Watchlist pipeline."""
    try:
        wl_item = await discovery_service.add_candidate_to_watchlist(db, current_user.id, candidate_id)
        return ActionResponse(
            status="success",
            message="Candidate successfully added to Watchlist.",
            candidate_id=candidate_id,
            extra={"watchlist_item_id": str(wl_item.id)},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/candidates/{candidate_id}/dismiss", response_model=ActionResponse)
async def dismiss_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss and suppress candidate from discovery inbox."""
    try:
        cand = await discovery_service.dismiss_discovery_candidate(db, current_user.id, candidate_id)
        return ActionResponse(
            status="success",
            message="Candidate dismissed and suppressed.",
            candidate_id=cand.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/candidates/{candidate_id}/screen", response_model=ActionResponse)
async def screen_candidate(
    candidate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute formal preliminary screening protocol on the discovery candidate."""
    try:
        cand, review_res = await discovery_service.screen_discovery_candidate(
            db=db,
            user_id=current_user.id,
            candidate_id=candidate_id,
        )
        return ActionResponse(
            status="success",
            message="Preliminary screening completed.",
            candidate_id=cand.id,
            extra={"review": review_res},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
