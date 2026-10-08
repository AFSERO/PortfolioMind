"""Test suite verifying canonical entity resolution across Copilot V2.

Verifies the 9 core data-integrity invariants:
1. User-owned asset resolves strictly through asset.instrument_id
2. Duplicate same-symbol instruments cannot silently cross-resolve
3. get_asset_context uses canonical instrument for holding, stats, and metadata
4. get_briefing uses same canonical identity without loose substring pollution
5. research/intelligence uses same canonical identity
6. decision history belongs strictly to same canonical instrument
7. web enrichment uses correct canonical name from user-owned instrument
8. unowned asset fallback remains safe when instrument is unique
9. ambiguous symbol fallback returns controlled structured result without arbitrary .limit(1)
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingTimeHorizon,
)
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, Recommendation, ThesisStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot_v2.entity_resolver import EntityResolver
from app.services.copilot_v2.tools.builtins import (
    get_asset_context_handler,
    get_briefing_handler,
    get_holdings_handler,
)
from app.services.copilot_v2.tools.web_research import _enrich_query_with_symbol_metadata


async def _create_test_user(db_session, prefix: str = "canon_user") -> User:
    user = User(
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test_pw_hash",
        display_name="Canonical Test User",
        base_currency="TRY",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_user_owned_asset_resolves_through_asset_instrument_id(db_session):
    """Verify user-owned asset resolves to Asset.instrument_id even when multiple instruments share the symbol."""
    user = await _create_test_user(db_session, "user_res")

    # Instrument A (e.g. legacy/conflicting)
    inst_a = Instrument(
        symbol="CLASH",
        name="Clash Legacy Instrument A",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    # Instrument B (the user's canonical instrument)
    inst_b = Instrument(
        symbol="CLASH",
        name="Clash Canonical Instrument B",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.flush()

    # User owns Asset linked specifically to Instrument B
    asset = Asset(
        user_id=user.id,
        instrument_id=inst_b.id,
        asset_type=AssetType.STOCK,
        symbol="CLASH",
        name="Clash Canonical Instrument B",
        current_price=Decimal("150.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.commit()

    entity = await EntityResolver.resolve(db=db_session, query="CLASH", user_id=user.id)

    assert entity.is_resolved is True
    assert entity.is_owned is True
    assert entity.canonical_instrument_id == inst_b.id
    assert entity.canonical_name == "Clash Canonical Instrument B"
    assert entity.match_type == "OWNED_ASSET_INSTRUMENT"
    assert entity.asset.id == asset.id


@pytest.mark.asyncio
async def test_duplicate_same_symbol_instruments_cannot_silently_cross_resolve(db_session):
    """When user does NOT own asset and multiple instruments share the symbol, resolution must report ambiguity."""
    user = await _create_test_user(db_session, "dup_res")

    inst_1 = Instrument(
        symbol="DUPGOLD",
        name="Duplicate Gold Record 1",
        asset_type=AssetType.PRECIOUS_METALS,
        exchange="EXCHANGE_1",
        currency="TRY",
    )
    inst_2 = Instrument(
        symbol="DUPGOLD",
        name="Duplicate Gold Record 2",
        asset_type=AssetType.PRECIOUS_METALS,
        exchange="EXCHANGE_2",
        currency="TRY",
    )
    db_session.add_all([inst_1, inst_2])
    await db_session.commit()

    # User does NOT own DUPGOLD
    entity = await EntityResolver.resolve(db=db_session, query="DUPGOLD", user_id=user.id)

    assert entity.is_ambiguous is True
    assert entity.canonical_instrument_id is None
    assert entity.match_type == "AMBIGUOUS"
    assert len(entity.ambiguous_candidates) == 2
    cand_ids = {c["id"] for c in entity.ambiguous_candidates}
    assert str(inst_1.id) in cand_ids
    assert str(inst_2.id) in cand_ids


@pytest.mark.asyncio
async def test_get_asset_context_uses_canonical_instrument(db_session):
    """get_asset_context must return the canonical instrument tied to user holding and include stats."""
    user = await _create_test_user(db_session, "ctx_canon")

    inst_other = Instrument(
        symbol="FONX",
        name="FONX Competitor Fund",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    inst_target = Instrument(
        symbol="FONX",
        name="FONX Real Owned Fund",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add_all([inst_other, inst_target])
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst_target.id,
        asset_type=AssetType.FUND,
        symbol="FONX",
        name="FONX Real Owned Fund",
        current_price=Decimal("12.50"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.flush()

    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("1000.0"),
        price_per_unit=Decimal("12.50"),
        total_amount=Decimal("12500.0"),
        transaction_currency="TRY",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tx)
    await db_session.commit()

    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="FONX")

    assert ctx["status"] == "success"
    assert ctx["instrument"]["id"] == str(inst_target.id)
    assert ctx["instrument"]["name"] == "FONX Real Owned Fund"
    assert ctx["user_holding"]["is_owned"] is True
    assert ctx["user_holding"]["asset_id"] == str(asset.id)
    assert pytest.approx(ctx["user_holding"]["quantity"], 0.01) == 1000.0


@pytest.mark.asyncio
async def test_get_briefing_uses_same_canonical_identity(db_session):
    """get_briefing must filter items strictly by canonical instrument_id rather than loose substring."""
    user = await _create_test_user(db_session, "brief_canon")

    inst_canonical = Instrument(
        symbol="TKN",
        name="Teknoloji Fonu",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    inst_other = Instrument(
        symbol="TKN2",
        name="Teknoloji 2 Fonu",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add_all([inst_canonical, inst_other])
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst_canonical.id,
        asset_type=AssetType.FUND,
        symbol="TKN",
        name="Teknoloji Fonu",
        current_price=Decimal("5.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset)

    run = BriefingRun(
        user_id=user.id,
        generated_at=datetime.now(timezone.utc),
        scope="PORTFOLIO",
        status="SUCCESS",
        trigger_type="MANUAL",
        items_found=2,
        items_shown=2,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    item_target = BriefingItem(
        briefing_run_id=run.id,
        user_id=user.id,
        instrument_id=inst_canonical.id,
        headline="Canonical TKN Update",
        summary="Summary of TKN.",
        why_it_matters="Relevant to portfolio.",
        category=BriefingCategory.EARNINGS,
        materiality=BriefingMateriality.HIGH,
        impact=BriefingImpact.POSITIVE,
        time_horizon=BriefingTimeHorizon.SHORT,
        review_required=False,
    )
    item_other = BriefingItem(
        briefing_run_id=run.id,
        user_id=user.id,
        instrument_id=inst_other.id,
        headline="Unrelated TKN2 Update",
        summary="Summary of TKN2.",
        why_it_matters="Not owned.",
        category=BriefingCategory.EARNINGS,
        materiality=BriefingMateriality.LOW,
        impact=BriefingImpact.NEUTRAL,
        time_horizon=BriefingTimeHorizon.SHORT,
        review_required=False,
    )
    db_session.add_all([item_target, item_other])
    await db_session.commit()

    briefing = await get_briefing_handler(db=db_session, user_id=user.id, symbol="TKN")

    assert briefing["status"] == "success"
    assert briefing["returned_count"] == 1
    assert briefing["items"][0]["headline"] == "Canonical TKN Update"
    assert briefing["items"][0]["symbol"] == "TKN"


@pytest.mark.asyncio
async def test_research_intelligence_uses_same_canonical_identity(db_session):
    """Intelligence state in get_asset_context must match the canonical instrument_id."""
    user = await _create_test_user(db_session, "intel_canon")

    inst_canonical = Instrument(
        symbol="INTEL_SYM",
        name="Target Instrument",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    inst_other = Instrument(
        symbol="INTEL_SYM",
        name="Other Duplicate Instrument",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add_all([inst_canonical, inst_other])
    await db_session.flush()

    # User owns target
    asset = Asset(
        user_id=user.id,
        instrument_id=inst_canonical.id,
        asset_type=AssetType.STOCK,
        symbol="INTEL_SYM",
        name="Target Instrument",
    )
    db_session.add(asset)

    # Intelligence attached to canonical instrument
    state_target = InstrumentIntelligenceState(
        instrument_id=inst_canonical.id,
        thesis_status=ThesisStatus.STRONGER,
        recommendation=Recommendation.ADD,
        human_brief="Thesis confirmed for canonical instrument.",
    )
    # Different intelligence on other instrument
    state_other = InstrumentIntelligenceState(
        instrument_id=inst_other.id,
        thesis_status=ThesisStatus.INVALIDATED,
        recommendation=Recommendation.SELL,
        human_brief="Wrong brief.",
    )
    db_session.add_all([state_target, state_other])
    await db_session.commit()

    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="INTEL_SYM")

    assert ctx["status"] == "success"
    assert ctx["instrument"]["id"] == str(inst_canonical.id)
    assert ctx["intelligence_state"]["recommendation"] == "ADD"
    assert ctx["intelligence_state"]["thesis_status"] == "STRONGER"


@pytest.mark.asyncio
async def test_decision_history_belongs_to_same_asset_instrument(db_session):
    """Decision log entries must strictly match the canonical instrument_id."""
    user = await _create_test_user(db_session, "dec_canon")

    inst_canonical = Instrument(
        symbol="DEC_SYM",
        name="Canonical Dec Instrument",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    inst_other = Instrument(
        symbol="DEC_SYM",
        name="Other Dec Instrument",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add_all([inst_canonical, inst_other])
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst_canonical.id,
        asset_type=AssetType.STOCK,
        symbol="DEC_SYM",
        name="Canonical Dec Instrument",
    )
    db_session.add(asset)

    # Decision on canonical instrument
    dl_target = DecisionLogEntry(
        user_id=user.id,
        instrument_id=inst_canonical.id,
        event_type=DecisionEventType.POSITION_OPENED,
        title="Valid Canonical Decision",
        summary="Opened position on canonical.",
        occurred_at=datetime.now(timezone.utc),
    )
    # Decision on other instrument
    dl_other = DecisionLogEntry(
        user_id=user.id,
        instrument_id=inst_other.id,
        event_type=DecisionEventType.SELL,
        title="Unrelated Decision on other inst",
        summary="Should not appear.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add_all([dl_target, dl_other])
    await db_session.commit()

    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="DEC_SYM")

    assert ctx["status"] == "success"
    assert len(ctx["recent_decisions"]) == 1
    assert ctx["recent_decisions"][0]["title"] == "Valid Canonical Decision"


@pytest.mark.asyncio
async def test_web_enrichment_uses_correct_canonical_name(db_session):
    """_enrich_query_with_symbol_metadata must return canonical instrument name from user holding."""
    user = await _create_test_user(db_session, "web_canon")

    inst_canonical = Instrument(
        symbol="THF_ENRICH",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    inst_other = Instrument(
        symbol="THF_ENRICH",
        name="Some Noncanonical Fund",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add_all([inst_canonical, inst_other])
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst_canonical.id,
        asset_type=AssetType.FUND,
        symbol="THF_ENRICH",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
    )
    db_session.add(asset)
    await db_session.commit()

    enriched_name = await _enrich_query_with_symbol_metadata(
        db=db_session, symbol="THF_ENRICH", user_id=user.id
    )

    assert enriched_name == "TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)"


@pytest.mark.asyncio
async def test_unowned_asset_fallback_remains_safe(db_session):
    """Unowned asset with a unique instrument record resolves cleanly with is_owned=False."""
    user = await _create_test_user(db_session, "unowned_safe")

    inst = Instrument(
        symbol="NVDA_TEST",
        name="NVIDIA Corporation",
        asset_type=AssetType.STOCK,
        currency="USD",
    )
    db_session.add(inst)
    await db_session.commit()

    entity = await EntityResolver.resolve(db=db_session, query="NVDA_TEST", user_id=user.id)

    assert entity.is_resolved is True
    assert entity.is_owned is False
    assert entity.canonical_instrument_id == inst.id
    assert entity.canonical_name == "NVIDIA Corporation"
    assert entity.match_type == "INSTRUMENT_EXACT"


@pytest.mark.asyncio
async def test_ambiguous_symbol_fallback_returns_controlled_result(db_session):
    """get_asset_context_handler returns status='ambiguous' when symbol is duplicated and not owned."""
    user = await _create_test_user(db_session, "ambig_ctx")

    inst_a = Instrument(
        symbol="AMBIG_SYM",
        name="Ambiguous Record A",
        asset_type=AssetType.STOCK,
        exchange="BIST",
        currency="TRY",
    )
    inst_b = Instrument(
        symbol="AMBIG_SYM",
        name="Ambiguous Record B",
        asset_type=AssetType.STOCK,
        exchange="NASDAQ",
        currency="USD",
    )
    db_session.add_all([inst_a, inst_b])
    await db_session.commit()

    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="AMBIG_SYM")

    assert ctx["status"] == "ambiguous"
    assert "candidates" in ctx
    assert len(ctx["candidates"]) == 2
    assert ctx["user_holding"]["is_owned"] is False
