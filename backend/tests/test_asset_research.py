import os
from pathlib import Path
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetType
from app.services.formal_review import (
    _find_finance_src,
    resolve_specialized_protocol,
)
from investment_intelligence.execution import AIExecutionResult
from investment_intelligence.protocols import ProtocolNotFoundError, load_protocol


def test_specialized_protocols_loadable():
    """Verify that all 4 specialized deep-research protocols exist, resolve to valid absolute paths, and load without error."""
    protocols = [
        "deep-research-equity",
        "deep-research-crypto",
        "deep-research-fund",
        "deep-research-gold",
    ]
    for proto_name in protocols:
        proto_def = load_protocol(proto_name)
        assert proto_def is not None
        assert proto_def.canonical_name == proto_name
        assert len(proto_def.content) > 100
        p = Path(proto_def.path)
        assert p.is_file()
        assert p.is_absolute()


def test_resolve_specialized_protocol_mapping():
    """Verify that deep-research automatically resolves to the correct asset-class protocol."""
    # Equity
    assert resolve_specialized_protocol("deep-research", AssetType.STOCK) == "deep-research-equity"
    assert resolve_specialized_protocol("DEEP_RESEARCH", AssetType.STOCK) == "deep-research-equity"

    # Crypto
    assert resolve_specialized_protocol("deep-research", AssetType.CRYPTO) == "deep-research-crypto"

    # Funds
    assert resolve_specialized_protocol("deep-research", AssetType.FUND) == "deep-research-fund"

    # Physical Gold / Precious Metals
    assert resolve_specialized_protocol("deep-research", AssetType.PRECIOUS_METALS) == "deep-research-gold"

    # Explicit specialized protocol names pass through
    assert resolve_specialized_protocol("deep-research-crypto", AssetType.STOCK) == "deep-research-crypto"
    assert resolve_specialized_protocol("thesis-review", AssetType.STOCK) == "thesis-review"


@pytest.mark.asyncio
async def test_execute_asset_research_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test POST /api/assets/{asset_id}/research endpoint."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Crypto User"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a crypto asset
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "CRYPTO",
            "symbol": "BTC",
            "name": "Bitcoin",
            "current_price_currency": "USD",
        },
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["data"]["id"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
            "recommendation": "ADD",
        },
        human_brief="Bitcoin on-chain activity and halving dynamics remain exceptionally robust.",
        confidence="0.92",
    )
    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(return_value=mock_ai_result)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/assets/{asset_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["data"]["status"] == "COMPLETED"
        assert data["data"]["protocol"] == "deep-research-crypto"
        assert data["data"]["summary"]["thesis_status"] == "STRONGER"
        assert data["data"]["summary"]["valuation_status"] == "ATTRACTIVE"
        assert data["data"]["summary"]["recommendation"] == "ADD"


@pytest.mark.asyncio
async def test_execute_instrument_research_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test POST /api/instruments/{instrument_id}/research endpoint for gold."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Gold User"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create precious metals instrument
    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "PRECIOUS_METALS",
            "symbol": "GLD",
            "name": "Physical Gold Gram",
            "currency": "TRY",
        },
    )
    assert inst_resp.status_code == 201, inst_resp.text
    inst_id = inst_resp.json()["data"]["id"]

    mock_ai_result = AIExecutionResult(
        machine_record={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        human_brief="Gold is providing effective hedge against inflation and USD/TRY depreciation.",
        confidence="0.88",
    )
    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(return_value=mock_ai_result)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/instruments/{inst_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["data"]["status"] == "COMPLETED"
        assert data["data"]["protocol"] == "deep-research-gold"
        assert data["data"]["summary"]["recommendation"] == "HOLD"


@pytest.mark.asyncio
async def test_unsupported_asset_type_fails_clearly(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that unsupported asset types (REAL_ESTATE, CUSTOM) fail clearly with HTTP 400."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Property Owner"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Real Estate asset
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "REAL_ESTATE",
            "name": "Apartment Kadikoy",
            "current_price_currency": "TRY",
        },
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["data"]["id"]

    res = await client.post(
        f"/api/assets/{asset_id}/research",
        headers=headers,
        json={"protocol": "deep-research"},
    )
    assert res.status_code == 400
    err_body = res.json()
    assert err_body["status"] == "error"
    assert "not supported for asset type 'REAL_ESTATE'" in err_body["message"]


@pytest.mark.asyncio
async def test_fund_asset_research_resolves_fund_protocol(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that a FUND asset holding resolves to deep-research-fund and includes holding stats."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Fund Investor"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create FUND asset with initial BUY transaction
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "TCD",
            "name": "Tacirler Degisken Fon",
            "current_price": 12.50,
            "current_price_currency": "TRY",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": 1000,
                "price_per_unit": 12.50,
                "transaction_currency": "TRY",
                "affects_cash": False,
            },
        },
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["data"]["id"]

    captured_requests = []

    def mock_execute(req):
        captured_requests.append(req)
        return AIExecutionResult(
            machine_record={
                "thesis_status": "STRONGER",
                "valuation_status": "ATTRACTIVE",
                "recommendation": "ADD",
            },
            human_brief="TCD continues to display exceptional Sharpe ratio and proactive portfolio allocation.",
            confidence="0.95",
        )

    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(side_effect=mock_execute)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/assets/{asset_id}/research",
            headers=headers,
            json={},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["data"]["protocol"] == "deep-research-fund"
        assert data["data"]["summary"]["recommendation"] == "ADD"

        # Verify position holding context was delivered to AI provider
        assert len(captured_requests) == 1
        req = captured_requests[0]
        user_holding = req.persistent_context.get("user_holding")
        assert user_holding is not None
        assert user_holding["total_quantity"] == 1000.0


@pytest.mark.asyncio
async def test_watchlist_progression_after_deep_research(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that WatchlistItem research stage progresses from DISCOVERED to VALUED after deep research."""
    from app.models.opportunity import ResearchStage, WatchlistItem
    from sqlalchemy import select

    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Watchlist User"},
    )
    user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create an instrument and add to watchlist
    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "THYAO",
            "name": "Turk Hava Yollari",
            "currency": "TRY",
        },
    )
    inst_id = uuid.UUID(inst_resp.json()["data"]["id"])

    # Add to watchlist directly
    wl_item = WatchlistItem(
        user_id=user_id,
        instrument_id=inst_id,
        research_stage=ResearchStage.DISCOVERED,
    )
    db_session.add(wl_item)
    await db_session.commit()

    mock_ai_result = AIExecutionResult(
        machine_record={
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
            "recommendation": "ADD",
        },
        human_brief="THYAO passenger traffic and load factors show strong recovery.",
        confidence="0.90",
    )
    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(return_value=mock_ai_result)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/instruments/{inst_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 200, res.text

    # Re-query watchlist item to verify stage transition to VALUED
    await db_session.refresh(wl_item)
    assert wl_item.research_stage == ResearchStage.VALUED


def test_protocol_loader_cwd_invariance():
    """Verify that load_protocol and Finance/src resolution work irrespective of whether cwd is repo root or backend/."""
    original_cwd = os.getcwd()
    if Path("/app").is_dir() and Path("/Finance").is_dir():
        backend_dir = Path("/app")
        repo_root = Path("/")
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        backend_dir = repo_root / "backend"

    try:
        # 1. Test from repo root
        os.chdir(str(repo_root))
        src_root = _find_finance_src()
        assert src_root is not None and src_root.is_dir()
        proto = load_protocol("deep-research-fund")
        assert proto.canonical_name == "deep-research-fund"
        assert len(proto.content) > 100

        # 2. Test from backend directory
        os.chdir(str(backend_dir))
        src_backend = _find_finance_src()
        assert src_backend is not None and src_backend.is_dir()
        proto_b = load_protocol("deep-research-equity")
        assert proto_b.canonical_name == "deep-research-equity"
        assert len(proto_b.content) > 100
    finally:
        os.chdir(original_cwd)


def test_missing_protocol_raises_protocol_not_found_with_available_list():
    """Verify that requesting a missing protocol raises ProtocolNotFoundError with available protocols listed."""
    with pytest.raises(ProtocolNotFoundError) as exc_info:
        load_protocol("nonexistent-test-protocol")
    err_msg = str(exc_info.value)
    assert "nonexistent-test-protocol" in err_msg
    assert "Available protocols in" in err_msg
    assert "deep-research-fund" in err_msg


@pytest.mark.asyncio
async def test_protocol_subsystem_unavailable_surfaces_detailed_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that when load_protocol is unavailable, the endpoint returns 500 with diagnostic detail."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Diag User"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "THF",
            "name": "Turk Portfoy Fon",
            "current_price_currency": "TRY",
        },
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["data"]["id"]

    with patch("app.services.formal_review.load_protocol", None), \
         patch("app.services.formal_review._protocol_import_error", "Simulated import error for tests"):
        res = await client.post(
            f"/api/assets/{asset_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 500
        data = res.json()
        assert data["status"] == "error"
        assert "Protocol loading subsystem unavailable: Simulated import error for tests" in data["message"]


@pytest.mark.asyncio
async def test_nonexistent_protocol_override_returns_404(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that specifying a nonexistent protocol returns HTTP 404 with helpful message."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Proto 404 User"},
    )
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "SISE",
            "name": "Sise Cam",
            "current_price_currency": "TRY",
        },
    )
    assert asset_resp.status_code == 201, asset_resp.text
    asset_id = asset_resp.json()["data"]["id"]

    res = await client.post(
        f"/api/assets/{asset_id}/research",
        headers=headers,
        json={"protocol": "nonexistent-special-protocol"},
    )
    assert res.status_code == 404
    data = res.json()
    assert data["status"] == "error"
    assert "Approved protocol 'nonexistent-special-protocol' file not found" in data["message"]


@pytest.mark.asyncio
async def test_synthetic_provider_guard_blocks_non_test_execution(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that passing a mock/synthetic AI provider outside an authorized test environment raises HTTP 403."""
    from fastapi import HTTPException
    from app.services import formal_review as formal_review_service

    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Guard User"},
    )
    user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "TESTFUND",
            "name": "Test Fund",
            "currency": "TRY",
        },
    )
    assert inst_resp.status_code == 201, inst_resp.text
    inst_id = uuid.UUID(inst_resp.json()["data"]["id"])

    mock_provider = MagicMock()

    # Simulate non-test environment (e.g. external helper script running against live DB)
    with patch("app.services.formal_review._is_authorized_test_environment", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await formal_review_service.execute_instrument_formal_review(
                db=db_session,
                instrument_id=inst_id,
                protocol_name="deep-research",
                user_id=user_id,
                ai_provider=mock_provider,
            )
        assert exc_info.value.status_code == 403
        assert "Synthetic or mock AI execution is strictly prohibited" in exc_info.value.detail


@pytest.mark.asyncio
async def test_synthetic_review_create_guard_blocks_non_test_execution(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that posting a synthetic review outside an authorized test environment raises HTTP 403."""
    from fastapi import HTTPException
    from app.services import intelligence as intelligence_service
    from app.schemas.intelligence import IntelligenceReviewCreateRequest

    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Guard User 2"},
    )
    user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "TESTSTK",
            "name": "Test Stock",
            "currency": "TRY",
        },
    )
    assert inst_resp.status_code == 201, inst_resp.text
    inst_id = uuid.UUID(inst_resp.json()["data"]["id"])

    req = IntelligenceReviewCreateRequest(
        protocol="deep-research-equity",
        machine_record={"thesis_status": "STRONGER", "recommendation": "ADD"},
        auto_apply_state=True,
        is_synthetic=True,
    )

    with patch("app.services.intelligence._is_authorized_test_environment", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await intelligence_service.create_review(
                db=db_session,
                instrument_id=inst_id,
                data=req,
                user_id=user_id,
            )
        assert exc_info.value.status_code == 403
        assert "Synthetic or mock reviews are strictly prohibited" in exc_info.value.detail


@pytest.mark.asyncio
async def test_formal_review_protocol_timeout_propagation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that deep research protocols use 600s timeout and standard protocols use 180s."""
    from app.services import formal_review as formal_review_service
    from investment_intelligence.codex_provider import CodexCLIProvider, resolve_protocol_timeout

    email = f"timeout_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Timeout User"},
    )
    user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "THF",
            "name": "Tera Portfoy",
            "currency": "TRY",
        },
    )
    inst_id = uuid.UUID(inst_resp.json()["data"]["id"])

    captured_timeouts = {}

    def mock_provider_factory(*args, **kwargs):
        provider = MagicMock(spec=CodexCLIProvider)

        def fake_execute(req):
            timeout = getattr(req, "timeout", None)
            if timeout is None:
                timeout = resolve_protocol_timeout(req.protocol_name)
            captured_timeouts[req.protocol_name] = timeout
            return AIExecutionResult(
                machine_record={"thesis_status": "STRONGER", "recommendation": "ADD"},
                human_brief="Brief analysis.",
                confidence="HIGH",
            )

        provider.execute = fake_execute
        provider.resolve_timeout = lambda req: resolve_protocol_timeout(req.protocol_name)
        return provider

    with patch("app.services.formal_review.CodexCLIProvider", side_effect=mock_provider_factory):
        # 1. Execute deep research on FUND (should resolve to deep-research-fund -> 600s)
        resp1 = await client.post(
            f"/api/instruments/{inst_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert resp1.status_code == 200, resp1.text
        assert captured_timeouts.get("deep-research-fund") == 600.0

        # 2. Execute technical review (should resolve to 180s)
        resp2 = await client.post(
            f"/api/instruments/{inst_id}/research",
            headers=headers,
            json={"protocol": "technical-review"},
        )
        assert resp2.status_code == 200, resp2.text
        assert captured_timeouts.get("technical-review") == 180.0


@pytest.mark.asyncio
async def test_deep_research_timeout_returns_clear_error(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Verify that a timeout during Deep Research returns a 502 with the clear limit message."""
    from investment_intelligence.codex_provider import CodexCLIProvider
    from investment_intelligence.execution import AIExecutionError

    email = f"timeout_err_{uuid.uuid4().hex[:6]}@example.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Timeout Err User"},
    )
    user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    inst_resp = await client.post(
        "/api/instruments",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "THF2",
            "name": "Tera Portfoy 2",
            "currency": "TRY",
        },
    )
    inst_id = uuid.UUID(inst_resp.json()["data"]["id"])

    mock_provider = MagicMock(spec=CodexCLIProvider)
    mock_provider.execute = MagicMock(
        side_effect=AIExecutionError(
            "Deep Research exceeded the 600-second execution limit (Codex CLI execution timed out after 600.0 seconds)."
        )
    )
    mock_provider.resolve_timeout = MagicMock(return_value=600.0)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        resp = await client.post(
            f"/api/instruments/{inst_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert resp.status_code == 502
        data = resp.json()
        error_text = data.get("message", "") or data.get("detail", "")
        assert "Deep Research exceeded the 600-second execution limit" in error_text



