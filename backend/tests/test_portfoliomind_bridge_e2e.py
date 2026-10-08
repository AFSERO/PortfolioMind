"""End-to-End integration test demonstrating the Finance-to-PortfolioMind Bridge.

Uses the real, existing UBER research extraction seed:
Finance/system/database/seeds/uber-thesis-2026-09-14.json

Demonstrates the full flow:
Existing Finance Research Output
        ↓
PortfolioMind Safe Instrument Resolver (UBER, STOCK, NYSE, USD)
        ↓
PortfolioMindBridge.sync_protocol_run
        ↓
PortfolioMind HTTP API (POST /api/instruments/{id}/reviews with auto_apply_state)
        ↓
PostgreSQL / DB Entities Created:
  - IntelligenceReview created with complete Machine Record & Human Brief
  - InstrumentIntelligenceState updated
        ↓
Idempotent Re-sync Verification (zero duplicate review records)
"""

import json
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.asset import AssetType
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    ThesisStatus,
    ValuationStatus,
)
from app.models.user import User
from app.services.auth import create_access_token

# Import bridge components from Finance
import sys
_FINANCE_SRC = Path(__file__).resolve().parents[2] / "Finance" / "src"
if str(_FINANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_FINANCE_SRC))

from investment_intelligence.portfoliomind import (
    AsyncPortfolioMindClient,
    PortfolioMindBridge,
    PortfolioMindBridgeConfig,
    PortfolioMindClient,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("credential_kind", ["jwt", "integration"])
async def test_uber_finance_output_end_to_end_sync(db_session: AsyncSession, monkeypatch, credential_kind):
    # 1. Provision user and create valid JWT auth token
    user = User(
        email="analyst@portfoliomind.com",
        password_hash="fakehash",
        display_name="Senior Analyst",
        base_currency="USD",
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(user.id)
    if credential_kind == "integration":
        import secrets
        from pydantic import SecretStr
        from app.config import settings
        token = secrets.token_urlsafe(32)
        monkeypatch.setattr(settings, "INTEGRATION_TOKEN", SecretStr(token))
        monkeypatch.setattr(settings, "INTEGRATION_USER_ID", user.id)

    # 2. Provision canonical UBER Instrument in PortfolioMind
    uber_instrument = Instrument(
        symbol="UBER",
        name="Uber Technologies, Inc.",
        asset_type=AssetType.STOCK,
        exchange="NYSE",
        currency="USD",
        country="USA",
    )
    db_session.add(uber_instrument)
    await db_session.commit()
    await db_session.refresh(uber_instrument)
    uber_id = uber_instrument.id

    # 3. Load existing, dated UBER research extraction seed
    seed_path = (
        Path(__file__).resolve().parents[2]
        / "Finance"
        / "system"
        / "database"
        / "seeds"
        / "uber-thesis-2026-09-14.json"
    )
    assert seed_path.is_file(), f"Seed file missing at {seed_path}"
    uber_payload = json.loads(seed_path.read_text(encoding="utf-8"))

    # Construct the Finance protocol run output structure from the seed
    machine_record = {
        "as_of": uber_payload["as_of"],
        "key_assumptions": uber_payload["key_assumptions"],
        "growth_drivers": uber_payload["growth_drivers"],
        "key_risks": uber_payload["key_risks"],
        "invalidation_conditions": uber_payload["invalidation_conditions"],
        "key_kpis": uber_payload["key_kpis"],
        "catalysts": uber_payload["catalysts"],
        "thesis_status": "UNCHANGED",
        "valuation_status": "FAIR",
        "recommendation": "HOLD",
    }
    human_brief = uber_payload["core_investment_rationale"]
    research_path = uber_payload["source_artifact_references"][0]["path"]
    confidence = uber_payload["confidence"]
    source_run_id = "uber-thesis-2026-09-14"

    run_record = {
        "id": source_run_id,
        "protocol_name": "thesis-review",
        "status": "COMPLETED",
        "machine_record": machine_record,
        "human_brief": human_brief,
        "confidence": confidence,
    }
    finance_instrument = {
        "symbol": "UBER",
        "instrument_type": "equity",
        "venue": "NYSE",
        "currency": "USD",
    }

    # 4. Wire AsyncPortfolioMindClient directly to the FastAPI ASGI application
    transport = httpx.ASGITransport(app=app)
    config = PortfolioMindBridgeConfig(
        enabled=True,
        base_url="http://test",
        api_token=token,
    )
    client = AsyncPortfolioMindClient(config=config, transport=transport)
    bridge = PortfolioMindBridge(client=client, config=config)

    # 5. Execute Bridge Sync
    sync_result = await bridge.async_sync_protocol_run(
        run_record=run_record,
        finance_instrument=finance_instrument,
        research_path=research_path,
        auto_apply_state=True,
        raise_on_error=True,
    )

    # 6. Verify Sync Result Envelope
    assert sync_result.synced is True
    assert sync_result.instrument_id == uber_id
    assert sync_result.review_id is not None
    assert sync_result.state_updated is True
    assert sync_result.error is None

    # 7. Verify Database State directly via SQLAlchemy
    # A. IntelligenceReview
    review_row = (
        await db_session.execute(
            select(IntelligenceReview).where(IntelligenceReview.id == sync_result.review_id)
        )
    ).scalar_one()

    assert review_row.instrument_id == uber_id
    assert review_row.protocol == "thesis-review"
    assert review_row.source_run_id == source_run_id
    assert review_row.confidence == "MEDIUM"
    assert review_row.research_path == "research/UBER/2026-09-14-pass-3/research-report.md"
    assert review_row.human_brief == human_brief
    assert review_row.machine_record["thesis_status"] == "UNCHANGED"
    assert len(review_row.machine_record["growth_drivers"]) == 3

    # B. InstrumentIntelligenceState
    state_row = (
        await db_session.execute(
            select(InstrumentIntelligenceState).where(
                InstrumentIntelligenceState.instrument_id == uber_id
            )
        )
    ).scalar_one()

    assert state_row.thesis_status == ThesisStatus.UNCHANGED
    assert state_row.valuation_status == ValuationStatus.FAIR
    assert state_row.recommendation == Recommendation.HOLD
    assert state_row.human_brief == human_brief
    assert state_row.last_review_at is not None

    # 8. Verify Idempotent Re-sync (no duplicate review created)
    resync_result = await bridge.async_sync_protocol_run(
        run_record=run_record,
        finance_instrument=finance_instrument,
        research_path=research_path,
        auto_apply_state=True,
        raise_on_error=True,
    )
    assert resync_result.synced is True
    assert resync_result.review_id == sync_result.review_id  # same review reused

    all_reviews = (
        await db_session.execute(
            select(IntelligenceReview).where(IntelligenceReview.instrument_id == uber_id)
        )
    ).scalars().all()
    assert len(all_reviews) == 1, "Idempotency failed: duplicate review rows found!"
