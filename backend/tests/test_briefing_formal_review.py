"""Comprehensive test suite for the Briefing -> Formal Review closed-loop intelligence workflow.

Covers all 20 required scenarios:
1. Ineligible item (no review required/recommended) rejects review (HTTP 400).
2. Valid recommendation maps to canonical Finance protocol.
3. Arbitrary/unmapped protocol names or path traversal rejected safely (HTTP 400).
4. Duplicate request reuses existing review (idempotent, returns reused=True).
5. Force re-run executes new review when explicitly requested (force_rerun=True).
6. BriefingItem itself never mutates InstrumentIntelligenceState.
7. Failed formal review leaves intelligence state unchanged and records review_status="FAILED".
8. Successful formal review updates state only through PortfolioMindBridge.
9. Successful review links triggered_review_id back to BriefingItem.
10. Subsequent reads return linked review (GET /items/{id}/review).
11. THESIS_CHANGED creates Decision Log entry when thesis changes.
12. VALUATION_CHANGED creates Decision Log entry when valuation changes.
13. RECOMMENDATION_CHANGED creates Decision Log entry when recommendation changes.
14. Unchanged states produce zero Decision Log events.
15. Idempotent bridge sync does not duplicate Decision Log events.
16. Codex failure produces FAILED status, preserves BriefingItem, no fake review.
17. User can intentionally retry after failure.
18. Supplemental context passes bounded Briefing event data to protocol.
19. Decision log entry metadata includes triggering_briefing_item_id, protocol, and states.
20. Non-owner cannot trigger review on another user's briefing item (HTTP 404).
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingThesisImpact,
    BriefingTimeHorizon,
)
from app.models.decision_log import DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from app.services.formal_review import resolve_protocol_from_recommendation

# Ensure Finance/src is accessible for AI execution structures
_FINANCE_SRC = Path(__file__).resolve().parents[2] / "Finance" / "src"
if str(_FINANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_FINANCE_SRC))

from investment_intelligence.execution import AIExecutionResult


async def _setup_test_context(client: AsyncClient, db_session: AsyncSession, symbol: str = "UBER"):
    """Helper to provision user, asset, instrument, briefing run, and briefing item."""
    email = f"rev_{uuid.uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Review Tester"},
    )
    token = resp.json()["data"]["access_token"]
    user_id = uuid.UUID(resp.json()["data"]["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create asset -> automatically creates instrument
    asset_resp = await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": symbol,
            "name": f"{symbol} Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )
    instrument_id = uuid.UUID(asset_resp.json()["data"]["instrument_id"])

    # Create BriefingRun
    run = BriefingRun(
        user_id=user_id,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    # Create BriefingItem
    item = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=instrument_id,
        headline=f"{symbol} files material 8-K with commercial contract",
        summary="Multi-year autonomous vehicle commercial agreement expanding across top metros.",
        why_it_matters="Direct portfolio holding. Major unit economic inflection impacting long-term valuation.",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.OPERATIONAL,
        source_metadata={
            "source": "SEC EDGAR",
            "recommended_review": "VALUATION_UPDATE",
        },
        is_portfolio=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    return {
        "token": token,
        "headers": headers,
        "user_id": user_id,
        "instrument_id": instrument_id,
        "run_id": run.id,
        "item": item,
        "symbol": symbol,
    }


# ============================================================================
# 1. Ineligible Item Rejection
# ============================================================================


@pytest.mark.asyncio
async def test_ineligible_item_rejects_review_400(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T1_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Mark as ineligible: not review_required and no recommended_review
    item.review_required = False
    item.source_metadata = {"source": "RSS", "recommended_review": None}
    await db_session.commit()

    resp = await client.post(
        f"/api/briefing/items/{item.id}/review",
        json={"force_rerun": False},
        headers=ctx["headers"],
    )
    assert resp.status_code == 400
    assert "does not recommend or require a review" in resp.json()["message"]


# ============================================================================
# 2. Canonical Protocol Name Mapping
# ============================================================================


def test_valid_recommendation_maps_to_canonical_protocols():
    assert resolve_protocol_from_recommendation("VALUATION_UPDATE") == "valuation-update"
    assert resolve_protocol_from_recommendation("THESIS_REVIEW") == "thesis-review"
    assert resolve_protocol_from_recommendation("EARNINGS_REVIEW") == "earnings-review"
    assert resolve_protocol_from_recommendation("TECHNICAL_REVIEW") == "technical-review"
    assert resolve_protocol_from_recommendation("DEEP_RESEARCH") == "deep-research"
    # Fallback to thesis-review when review_required is True
    assert resolve_protocol_from_recommendation(None, review_required=True) == "thesis-review"
    assert resolve_protocol_from_recommendation("", review_required=True) == "thesis-review"
    assert resolve_protocol_from_recommendation("NONE", review_required=True) == "thesis-review"


# ============================================================================
# 3. Path Traversal & Unmapped Protocol Rejection
# ============================================================================


@pytest.mark.asyncio
async def test_unmapped_or_arbitrary_protocol_rejected(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T3_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    with pytest.raises(ValueError, match="Unsupported review recommendation"):
        resolve_protocol_from_recommendation("../../malicious_path")

    with pytest.raises(ValueError, match="Unsupported review recommendation"):
        resolve_protocol_from_recommendation("CUSTOM_UNKNOWN_PROTOCOL")

    # Set invalid recommendation on item
    item.source_metadata = {"recommended_review": "CUSTOM_UNKNOWN_PROTOCOL"}
    await db_session.commit()

    resp = await client.post(
        f"/api/briefing/items/{item.id}/review",
        json={"force_rerun": False},
        headers=ctx["headers"],
    )
    assert resp.status_code == 400
    assert "Unsupported review recommendation" in resp.json()["message"]


# ============================================================================
# 4. Idempotency (Duplicate Request Reuses Existing Review)
# ============================================================================


@pytest.mark.asyncio
async def test_duplicate_request_reuses_existing_review_idempotency(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T4_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "thesis_status": "UNCHANGED",
            "recommendation": "BUY",
        },
        human_brief="Valuation model confirms fair value upside.",
        confidence="HIGH",
    )

    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        # 1st run: executes review
        resp1 = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["status"] == "COMPLETED"
        assert data1["reused"] is False
        assert mock_provider.execute.call_count == 1
        review_id_1 = data1["review_id"]

        # 2nd run: duplicate call reuses existing review
        resp2 = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp2.status_code == 200
        data2 = resp2.json()["data"]
        assert data2["status"] == "COMPLETED"
        assert data2["reused"] is True
        assert data2["review_id"] == review_id_1
        # AI provider was NOT invoked a second time
        assert mock_provider.execute.call_count == 1


# ============================================================================
# 5. Force Re-run Bypasses Idempotency
# ============================================================================


@pytest.mark.asyncio
async def test_force_rerun_executes_new_review(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T5_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "ATTRACTIVE",
            "thesis_status": "STRONGER",
            "recommendation": "BUY",
        },
        human_brief="Upgraded to CHEAP after updated model inputs.",
        confidence="HIGH",
    )

    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        # Initial run
        resp1 = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp1.status_code == 200
        assert mock_provider.execute.call_count == 1

        # Force rerun
        resp2 = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["reused"] is False
        assert mock_provider.execute.call_count == 2


# ============================================================================
# 6. BriefingItem Never Mutates Intelligence State Directly
# ============================================================================


@pytest.mark.asyncio
async def test_briefing_item_never_mutates_intelligence_state_directly(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T6_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Before review is executed, intelligence state is None
    stmt = select(InstrumentIntelligenceState).where(
        InstrumentIntelligenceState.instrument_id == ctx["instrument_id"]
    )
    res = await db_session.execute(stmt)
    state = res.scalar_one_or_none()
    assert state is None

    # Even after querying the briefing item or its status
    status_resp = await client.get(
        f"/api/briefing/items/{item.id}/review",
        headers=ctx["headers"],
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "READY"

    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


# ============================================================================
# 7. Failed Review Leaves State Untouched & Records review_status="FAILED"
# ============================================================================


@pytest.mark.asyncio
async def test_failed_formal_review_leaves_intelligence_state_unchanged(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T7_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_provider = MagicMock()
    mock_provider.execute.side_effect = RuntimeError("Codex CLI process timed out")

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp.status_code == 502
        assert "Protocol execution failed" in resp.json()["message"]

    # Verify item status was recorded as FAILED
    await db_session.refresh(item)
    assert item.source_metadata.get("review_status") == "FAILED"
    assert "Codex CLI process timed out" in item.source_metadata.get("review_error", "")

    # State remains untouched (None)
    stmt = select(InstrumentIntelligenceState).where(
        InstrumentIntelligenceState.instrument_id == ctx["instrument_id"]
    )
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


# ============================================================================
# 8. Successful Review Updates State via Bridge
# ============================================================================


@pytest.mark.asyncio
async def test_successful_review_updates_state_via_bridge(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T8_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "EXPENSIVE",
            "thesis_status": "WEAKER",
            "recommendation": "SELL",
        },
        human_brief="Valuation multiple exceeded boundary. Recommended profit taking.",
        confidence="HIGH",
    )

    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200

    # Verify state updated in DB through bridge
    stmt = select(InstrumentIntelligenceState).where(
        InstrumentIntelligenceState.instrument_id == ctx["instrument_id"]
    )
    res = await db_session.execute(stmt)
    state = res.scalar_one_or_none()
    assert state is not None
    assert state.valuation_status == ValuationStatus.EXPENSIVE
    assert state.thesis_status == ThesisStatus.WEAKER
    assert state.recommendation == Recommendation.SELL


# ============================================================================
# 9. Review Links ID, Status, Protocol, and Summary to BriefingItem
# ============================================================================


@pytest.mark.asyncio
async def test_successful_review_links_id_to_briefing_item(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T9_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "EXPENSIVE",
            "thesis_status": "WEAKER",
            "recommendation": "SELL",
        },
        human_brief="Valuation multiple exceeded boundary. Recommended profit taking.",
        confidence="HIGH",
    )

    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        review_id = data["review_id"]

    # Verify linkage on BriefingItem
    await db_session.refresh(item)
    assert item.source_metadata.get("triggered_review_id") == review_id
    assert item.source_metadata.get("review_status") == "COMPLETED"
    assert item.source_metadata.get("triggered_protocol") == "valuation-update"
    summary = item.source_metadata.get("review_summary")
    assert summary["recommendation"] == "SELL"
    assert summary["state_updated"] is True


# ============================================================================
# 10. Subsequent Reads Return Linked Review (GET /items/{id}/review)
# ============================================================================


@pytest.mark.asyncio
async def test_subsequent_reads_return_linked_review(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T10_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
        },
        human_brief="Thesis affirmed intact.",
        confidence="HIGH",
    )

    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    # Read status endpoint
    get_resp = await client.get(
        f"/api/briefing/items/{item.id}/review",
        headers=ctx["headers"],
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["review_id"] is not None
    assert data["protocol"] == "valuation-update"
    assert data["summary"]["recommendation"] == "HOLD"


# ============================================================================
# 11. THESIS_CHANGED Creates Decision Log Entry
# ============================================================================


@pytest.mark.asyncio
async def test_thesis_changed_creates_decision_log_entry(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T11_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed initial state via API
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    # Trigger review that alters thesis to WEAKER
    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "thesis_status": "WEAKER",
            "recommendation": "HOLD",
        },
        human_brief="Competition eroding pricing leverage.",
        confidence="MEDIUM",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    # Verify DecisionLogEntry created
    dec_resp = await client.get("/api/decisions", headers=ctx["headers"])
    assert dec_resp.status_code == 200
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "THESIS_CHANGED"
    ]
    assert len(entries) >= 1
    entry = entries[0]
    assert "WEAKER" in entry["title"]
    assert entry.get("metadata", {}).get("triggering_briefing_item_id") == str(item.id)
    assert entry.get("metadata", {}).get("previous_state") == "UNCHANGED"
    assert entry.get("metadata", {}).get("new_state") == "WEAKER"


# ============================================================================
# 12. VALUATION_CHANGED Creates Decision Log Entry
# ============================================================================


@pytest.mark.asyncio
async def test_valuation_changed_creates_decision_log_entry(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T12_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed initial state via API
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "EXPENSIVE",
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
        },
        human_brief="Valuation multiple expanded past fair value zone.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    dec_resp = await client.get("/api/decisions", headers=ctx["headers"])
    assert dec_resp.status_code == 200
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "VALUATION_CHANGED"
    ]
    assert len(entries) >= 1
    assert entries[0].get("metadata", {}).get("previous_state") == "FAIR"
    assert entries[0].get("metadata", {}).get("new_state") == "EXPENSIVE"


# ============================================================================
# 13. RECOMMENDATION_CHANGED Creates Decision Log Entry
# ============================================================================


@pytest.mark.asyncio
async def test_recommendation_changed_creates_decision_log_entry(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T13_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed initial state via API
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "thesis_status": "UNCHANGED",
            "recommendation": "ADD",
        },
        human_brief="Upgraded stance to ADD following margin expansion.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    dec_resp = await client.get("/api/decisions", headers=ctx["headers"])
    assert dec_resp.status_code == 200
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "RECOMMENDATION_CHANGED"
    ]
    assert len(entries) >= 1
    assert entries[0].get("metadata", {}).get("previous_state") == "HOLD"
    assert entries[0].get("metadata", {}).get("new_state") == "ADD"


# ============================================================================
# 14. Unchanged States Produce Zero Decision Log Events
# ============================================================================


@pytest.mark.asyncio
async def test_unchanged_states_produce_zero_decision_log_events(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T14_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed initial state via API
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    # Review returns IDENTICAL states: HOLD, UNCHANGED, FAIR
    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
        },
        human_brief="All fundamentals intact and on track.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    # Verify zero transition DecisionLog entries created
    dec_resp = await client.get("/api/decisions", headers=ctx["headers"])
    assert dec_resp.status_code == 200
    changed_entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] in ("THESIS_CHANGED", "VALUATION_CHANGED", "RECOMMENDATION_CHANGED", "TECHNICAL_PLAN_CHANGED")
    ]
    assert len(changed_entries) == 0


# ============================================================================
# 15. Idempotent Bridge Sync Does Not Duplicate Decision Log Events
# ============================================================================


@pytest.mark.asyncio
async def test_idempotent_bridge_sync_does_not_duplicate_decision_log(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T15_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    init_state = InstrumentIntelligenceState(
        instrument_id=ctx["instrument_id"],
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
    )
    db_session.add(init_state)
    await db_session.commit()

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "ATTRACTIVE",
            "thesis_status": "STRONGER",
            "recommendation": "BUY",
        },
        human_brief="Inflection confirmed.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        # 1st run: creates decision log entries
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

        stmt = select(DecisionLogEntry).where(DecisionLogEntry.user_id == ctx["user_id"])
        res1 = await db_session.execute(stmt)
        count_after_first = len(list(res1.scalars().all()))
        assert count_after_first > 0

        # Duplicate run (reusing existing review)
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

        res2 = await db_session.execute(stmt)
        count_after_second = len(list(res2.scalars().all()))
        assert count_after_second == count_after_first


# ============================================================================
# 16. Codex Failure Produces FAILED Status & No Fake Review
# ============================================================================


@pytest.mark.asyncio
async def test_codex_failure_produces_failed_status_no_fake_review(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T16_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    mock_provider = MagicMock()
    mock_provider.execute.side_effect = Exception("Codex CLI returned non-zero exit code 1")

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp.status_code == 502

    # Verify no review record created
    stmt = select(IntelligenceReview).where(IntelligenceReview.instrument_id == ctx["instrument_id"])
    res = await db_session.execute(stmt)
    assert len(list(res.scalars().all())) == 0


# ============================================================================
# 17. User Can Intentionally Retry After Failure
# ============================================================================


@pytest.mark.asyncio
async def test_user_can_retry_after_failure(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T17_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # 1. First execution fails
    mock_failing_provider = MagicMock()
    mock_failing_provider.execute.side_effect = RuntimeError("Temporary rate limit")

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_failing_provider):
        fail_resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert fail_resp.status_code == 502

    # Status shows FAILED
    status_resp = await client.get(
        f"/api/briefing/items/{item.id}/review",
        headers=ctx["headers"],
    )
    assert status_resp.json()["data"]["status"] == "FAILED"

    # 2. User retries -> now succeeds
    mock_succ_result = AIExecutionResult(
        machine_record={"valuation_status": "FAIR", "recommendation": "HOLD"},
        human_brief="Retry successful.",
        confidence="HIGH",
    )
    mock_succ_provider = MagicMock()
    mock_succ_provider.execute.return_value = mock_succ_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_succ_provider):
        retry_resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert retry_resp.status_code == 200
        assert retry_resp.json()["data"]["status"] == "COMPLETED"

    # Status now shows COMPLETED
    status_resp2 = await client.get(
        f"/api/briefing/items/{item.id}/review",
        headers=ctx["headers"],
    )
    assert status_resp2.json()["data"]["status"] == "COMPLETED"


# ============================================================================
# 18. Supplemental Context Passes Bounded Briefing Event Data
# ============================================================================


@pytest.mark.asyncio
async def test_supplemental_context_passes_bounded_briefing_event_data(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T18_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    captured_request = None

    def capture_execute(req):
        nonlocal captured_request
        captured_request = req
        return AIExecutionResult(
            machine_record={"valuation_status": "FAIR", "recommendation": "HOLD"},
            human_brief="Context validated.",
            confidence="HIGH",
        )

    mock_provider = MagicMock()
    mock_provider.execute.side_effect = capture_execute

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200

    assert captured_request is not None
    # Check bounded briefing event data in supplemental_context
    supp = captured_request.supplemental_context
    assert "triggering_briefing_event" in supp
    b_ev = supp["triggering_briefing_event"]
    assert b_ev["headline"] == item.headline
    assert b_ev["summary"] == item.summary
    assert b_ev["why_it_matters"] == item.why_it_matters
    assert b_ev["materiality"] == item.materiality.value
    assert b_ev["category"] == item.category.value


# ============================================================================
# 19. Decision Log Metadata Includes Provenance and State Transitions
# ============================================================================


@pytest.mark.asyncio
async def test_decision_log_metadata_includes_provenance(client: AsyncClient, db_session: AsyncSession):
    ctx = await _setup_test_context(client, db_session, symbol=f"T19_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed initial state via API
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "ATTRACTIVE",
            "recommendation": "ADD",
        },
        headers=ctx["headers"],
    )

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "EXPENSIVE",
            "thesis_status": "WEAKER",
            "recommendation": "SELL",
        },
        human_brief="Full downgrade across thesis and valuation.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": False},
            headers=ctx["headers"],
        )

    dec_resp = await client.get("/api/decisions", headers=ctx["headers"])
    assert dec_resp.status_code == 200
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] in ("THESIS_CHANGED", "VALUATION_CHANGED", "RECOMMENDATION_CHANGED")
    ]
    assert len(entries) >= 1

    for entry in entries:
        meta = entry.get("metadata", {})
        assert meta.get("triggering_briefing_item_id") == str(item.id)
        assert meta.get("protocol") == "valuation-update"
        assert "previous_state" in meta
        assert "new_state" in meta


# ============================================================================
# 20. Non-Owner Cannot Trigger Review on Another User's Briefing Item
# ============================================================================


@pytest.mark.asyncio
async def test_non_owner_cannot_trigger_review_on_another_users_item(client: AsyncClient, db_session: AsyncSession):
    ctx_owner = await _setup_test_context(client, db_session, symbol=f"T20_{uuid.uuid4().hex[:4].upper()}")
    item = ctx_owner["item"]

    # Register a second, unrelated user
    resp_other = await client.post(
        "/api/auth/register",
        json={
            "email": f"other_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123!",
            "display_name": "Other User",
        },
    )
    other_token = resp_other.json()["data"]["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Other user attempts to trigger review on owner's briefing item
    resp = await client.post(
        f"/api/briefing/items/{item.id}/review",
        json={"force_rerun": False},
        headers=other_headers,
    )
    assert resp.status_code == 404
    assert "Briefing item not found" in resp.json()["message"]

    # Other user attempts to read review status on owner's item
    get_resp = await client.get(
        f"/api/briefing/items/{item.id}/review",
        headers=other_headers,
    )
    assert get_resp.status_code == 404


# ============================================================================
# Regression Tests: Authoritative Before-State & state_updated Semantics
# ============================================================================


@pytest.mark.asyncio
async def test_regression_persisted_review_required_incoming_review_required_no_change(client: AsyncClient, db_session: AsyncSession):
    """1. Persisted recommendation REVIEW_REQUIRED + incoming REVIEW_REQUIRED
    -> state_updated false -> zero RECOMMENDATION_CHANGED events.
    """
    ctx = await _setup_test_context(client, db_session, symbol=f"REG1_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed persisted state: REVIEW_REQUIRED / UNCHANGED / FAIR
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "REVIEW_REQUIRED",
        },
        headers=ctx["headers"],
    )

    # Formal review produces identical state: REVIEW_REQUIRED / FAIR
    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "recommendation": "REVIEW_REQUIRED",
        },
        human_brief="Re-evaluating valuation; conditions remain REVIEW_REQUIRED.",
        confidence="LOW",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Invariant: state_updated must be false when no persistent field changed
        assert data["summary"]["state_updated"] is False

    # Invariant: zero RECOMMENDATION_CHANGED events logged
    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "RECOMMENDATION_CHANGED"
    ]
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_regression_persisted_hold_incoming_review_required_creates_event(client: AsyncClient, db_session: AsyncSession):
    """2. Persisted HOLD + incoming REVIEW_REQUIRED
    -> state_updated true -> exactly one RECOMMENDATION_CHANGED event.
    """
    ctx = await _setup_test_context(client, db_session, symbol=f"REG2_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed persisted state: HOLD / UNCHANGED / FAIR
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    # Formal review produces: REVIEW_REQUIRED / FAIR
    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "recommendation": "REVIEW_REQUIRED",
        },
        human_brief="Debt financing requires new valuation model.",
        confidence="LOW",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["summary"]["state_updated"] is True

    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "RECOMMENDATION_CHANGED"
    ]
    assert len(entries) == 1
    assert entries[0]["metadata"]["previous_state"] == "HOLD"
    assert entries[0]["metadata"]["new_state"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_regression_persisted_thesis_unchanged_incoming_unchanged_no_event(client: AsyncClient, db_session: AsyncSession):
    """3. Persisted thesis UNCHANGED + incoming UNCHANGED -> no THESIS_CHANGED event."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG3_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    mock_ai_result = AIExecutionResult(
        machine_record={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        human_brief="Thesis remains intact.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["summary"]["state_updated"] is False

    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "THESIS_CHANGED"
    ]
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_regression_persisted_fair_incoming_fair_no_event(client: AsyncClient, db_session: AsyncSession):
    """4. Persisted FAIR + incoming FAIR -> no VALUATION_CHANGED event."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG4_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        headers=ctx["headers"],
    )

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        human_brief="Valuation still fair.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["summary"]["state_updated"] is False

    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "VALUATION_CHANGED"
    ]
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_regression_no_prior_state_does_not_invent_hold_as_baseline(client: AsyncClient, db_session: AsyncSession):
    """5. No prior state -> must not invent HOLD as old recommendation (previous_state is None)."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG5_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Verify no state exists
    stmt = select(InstrumentIntelligenceState).where(
        InstrumentIntelligenceState.instrument_id == ctx["instrument_id"]
    )
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None

    mock_ai_result = AIExecutionResult(
        machine_record={
            "valuation_status": "ATTRACTIVE",
            "thesis_status": "STRONGER",
            "recommendation": "ADD",
        },
        human_brief="First deep review establishing ADD stance.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/briefing/items/{item.id}/review",
            json={"force_rerun": True},
            headers=ctx["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["summary"]["state_updated"] is True

    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entries = [
        d for d in dec_resp.json()["data"]["items"]
        if d["event_type"] == "RECOMMENDATION_CHANGED"
    ]
    assert len(entries) == 1
    # Invariant: Absent prior state must be None, NOT an invented 'HOLD'
    assert entries[0]["metadata"]["previous_state"] is None
    assert entries[0]["metadata"]["new_state"] == "ADD"
    assert "Initial recommendation established as ADD" in entries[0]["summary"]


@pytest.mark.asyncio
async def test_regression_idempotent_bridge_resync_zero_duplicate_transitions(client: AsyncClient, db_session: AsyncSession):
    """6. Idempotent bridge re-sync with same source_run_id -> zero duplicate transitions, state_updated=False."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG6_{uuid.uuid4().hex[:4].upper()}")
    inst_id = ctx["instrument_id"]

    run_id = f"test_run_idempotency_{uuid.uuid4().hex[:8]}"
    review_payload = {
        "protocol": "deep-research",
        "status": "COMPLETED",
        "confidence": "HIGH",
        "human_brief": "Idempotency test review.",
        "machine_record": {
            "recommendation": "ADD",
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
        },
        "source_run_id": run_id,
        "auto_apply_state": True,
    }

    # First sync
    resp1 = await client.post(f"/api/instruments/{inst_id}/reviews", json=review_payload, headers=ctx["headers"])
    assert resp1.status_code == 201
    assert resp1.json()["data"]["state_updated"] is True

    dec_resp1 = await client.get(f"/api/decisions?instrument_id={inst_id}", headers=ctx["headers"])
    count_after_first = len(dec_resp1.json()["data"]["items"])

    # Second sync with identical source_run_id
    resp2 = await client.post(f"/api/instruments/{inst_id}/reviews", json=review_payload, headers=ctx["headers"])
    assert resp2.status_code == 201
    # Invariant: Resync must return state_updated=False
    assert resp2.json()["data"]["state_updated"] is False

    # Invariant: Zero duplicate decisions created
    dec_resp2 = await client.get(f"/api/decisions?instrument_id={inst_id}", headers=ctx["headers"])
    count_after_second = len(dec_resp2.json()["data"]["items"])
    assert count_after_second == count_after_first


@pytest.mark.asyncio
async def test_regression_decision_log_previous_state_matches_authoritative_snapshot(client: AsyncClient, db_session: AsyncSession):
    """7. Decision Log previous_state metadata exactly matches the persisted pre-review value."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG7_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Step 1: Establish HOLD
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={"recommendation": "HOLD", "valuation_status": "FAIR", "thesis_status": "UNCHANGED"},
        headers=ctx["headers"],
    )

    # Step 2: Review transitions HOLD -> SELL
    mock_ai_result1 = AIExecutionResult(
        machine_record={"recommendation": "SELL", "valuation_status": "EXPENSIVE"},
        human_brief="Downgrade to SELL.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result1

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(f"/api/briefing/items/{item.id}/review", json={"force_rerun": True}, headers=ctx["headers"])
        assert resp.status_code == 200

    dec_resp = await client.get(f"/api/decisions?instrument_id={ctx['instrument_id']}", headers=ctx["headers"])
    entry = [d for d in dec_resp.json()["data"]["items"] if d["event_type"] == "RECOMMENDATION_CHANGED"][0]
    assert entry["metadata"]["previous_state"] == "HOLD"
    assert entry["metadata"]["new_state"] == "SELL"


@pytest.mark.asyncio
async def test_regression_review_summary_state_updated_matches_transition_result(client: AsyncClient, db_session: AsyncSession):
    """8. review_summary.state_updated matches the actual transition result."""
    ctx = await _setup_test_context(client, db_session, symbol=f"REG8_{uuid.uuid4().hex[:4].upper()}")
    item = ctx["item"]

    # Seed state: REDUCE
    await client.put(
        f"/api/instruments/{ctx['instrument_id']}/intelligence",
        json={"recommendation": "REDUCE", "valuation_status": "EXPENSIVE", "thesis_status": "WEAKER"},
        headers=ctx["headers"],
    )

    # Review 1: Reconfirms REDUCE (state_updated must be False)
    mock_ai_result1 = AIExecutionResult(
        machine_record={"recommendation": "REDUCE", "valuation_status": "EXPENSIVE", "thesis_status": "WEAKER"},
        human_brief="Reconfirming REDUCE.",
        confidence="HIGH",
    )
    mock_provider = MagicMock()
    mock_provider.execute.return_value = mock_ai_result1

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp1 = await client.post(f"/api/briefing/items/{item.id}/review", json={"force_rerun": True}, headers=ctx["headers"])
        assert resp1.status_code == 200
        assert resp1.json()["data"]["summary"]["state_updated"] is False

    # Review 2: Transitions REDUCE -> SELL (state_updated must be True)
    mock_ai_result2 = AIExecutionResult(
        machine_record={"recommendation": "SELL", "valuation_status": "EXPENSIVE", "thesis_status": "INVALIDATED"},
        human_brief="Thesis invalidated, moving to SELL.",
        confidence="HIGH",
    )
    mock_provider.execute.return_value = mock_ai_result2

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp2 = await client.post(f"/api/briefing/items/{item.id}/review", json={"force_rerun": True}, headers=ctx["headers"])
        assert resp2.status_code == 200
        assert resp2.json()["data"]["summary"]["state_updated"] is True

