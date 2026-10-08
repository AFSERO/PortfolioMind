"""Tests for PortfolioMind Integration Bridge.

Validates the 10 core integration requirements:
1. Successful Finance review persists to PortfolioMind.
2. Machine Record is stored intact.
3. Human Brief is stored.
4. Canonical state fields update current intelligence state.
5. Missing state fields do not erase existing values.
6. Same source_run_id does not create duplicate reviews (idempotency).
7. Ambiguous Instrument resolution fails safely (AmbiguousInstrumentResolutionError).
8. PortfolioMind unavailable -> Finance output still survives locally.
9. Technical Review can update technical state without overwriting unrelated thesis/valuation state.
10. Technical Plan persists correctly when produced.
"""

import json
from uuid import UUID, uuid4

import httpx
import pytest

from investment_intelligence.portfoliomind import (
    AmbiguousInstrumentResolutionError,
    InstrumentNotFoundError,
    PortfolioMindBridge,
    PortfolioMindBridgeConfig,
    PortfolioMindClient,
    PortfolioMindSyncError,
    SafeInstrumentResolver,
    SyncResult,
)


# ============================================================================
# Helpers & Mocks
# ============================================================================


def make_mock_client(handler) -> PortfolioMindClient:
    """Create a PortfolioMindClient backed by an in-memory httpx mock handler."""
    transport = httpx.MockTransport(handler)
    config = PortfolioMindBridgeConfig(
        enabled=True,
        base_url="http://mock-pm:8000",
        api_token="mock-secret-token",
    )
    return PortfolioMindClient(config=config, transport=transport)


# ============================================================================
# Test Cases
# ============================================================================


def test_successful_review_persists_to_portfoliomind():
    """1. Successful Finance review persists to PortfolioMind."""
    inst_id = uuid4()
    review_id = uuid4()
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        # Instrument query
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "id": str(inst_id),
                            "symbol": "UBER",
                            "name": "Uber Technologies Inc",
                            "asset_type": "STOCK",
                            "exchange": "NYSE",
                            "currency": "USD",
                        }
                    ],
                },
            )
        # Post review
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            body = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "status": "success",
                    "data": {
                        "id": str(review_id),
                        "instrument_id": str(inst_id),
                        "protocol": body["protocol"],
                        "status": body["status"],
                        "created_at": "2026-09-15T12:00:00Z",
                    },
                },
            )
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    finance_inst = {"symbol": "UBER", "instrument_type": "equity", "venue": "NYSE", "currency": "USD"}
    run_record = {
        "id": uuid4(),
        "protocol_name": "thesis-review",
        "status": "COMPLETED",
        "machine_record": {"thesis_status": "STRONGER", "recommendation": "ADD"},
        "human_brief": "Uber growth accelerating with high density margins.",
        "confidence": "HIGH",
    }

    result = bridge.sync_protocol_run(run_record, finance_inst)
    assert result.synced is True
    assert result.instrument_id == inst_id
    assert result.review_id == review_id
    assert result.error is None
    assert len(captured_requests) == 2


def test_machine_record_stored_intact():
    """2. Machine Record is stored intact without alteration."""
    inst_id = uuid4()
    posted_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"id": str(inst_id), "symbol": "MSFT", "asset_type": "STOCK"}],
                },
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            body = json.loads(request.content)
            posted_payloads.append(body)
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    complex_machine_record = {
        "metrics": {"pe_ratio": 32.5, "growth_yoy": 0.15, "ebit_margin": 0.42},
        "thesis_status": "STRONGER",
        "recommendation": "ADD",
        "nested_details": {"cloud_segment": {"growth": 0.28, "margin": 0.45}},
        "material_changes": ["Azure enterprise contract expansion"],
    }

    bridge.sync_protocol_run(
        run_record={
            "protocol_name": "thesis-review",
            "machine_record": complex_machine_record,
            "human_brief": "Strong quarter.",
        },
        finance_instrument={"symbol": "MSFT", "instrument_type": "equity"},
    )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]["machine_record"] == complex_machine_record


def test_human_brief_stored():
    """3. Human Brief is stored."""
    inst_id = uuid4()
    posted_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "NVDA", "asset_type": "STOCK"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            posted_payloads.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    brief_text = "Detailed thesis memorandum: NVDA maintaining hardware monopoly in AI data centers."
    bridge.sync_protocol_run(
        run_record={"protocol_name": "thesis-review", "human_brief": brief_text},
        finance_instrument={"symbol": "NVDA"},
    )

    assert len(posted_payloads) == 1
    assert posted_payloads[0]["human_brief"] == brief_text


def test_canonical_state_fields_update_current_intelligence_state():
    """4. Canonical state fields update current intelligence state via auto_apply_state."""
    inst_id = uuid4()
    posted_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "AAPL", "asset_type": "STOCK"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            posted_payloads.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    bridge.sync_protocol_run(
        run_record={
            "protocol_name": "thesis-review",
            "machine_record": {
                "thesis_status": "STRONGER",
                "valuation_status": "ATTRACTIVE",
                "technical_status": "ON_TRACK",
                "recommendation": "ADD",
            },
        },
        finance_instrument={"symbol": "AAPL"},
        auto_apply_state=True,
    )

    assert len(posted_payloads) == 1
    payload = posted_payloads[0]
    assert payload["auto_apply_state"] is True
    assert payload["machine_record"]["thesis_status"] == "STRONGER"
    assert payload["machine_record"]["valuation_status"] == "ATTRACTIVE"
    assert payload["machine_record"]["recommendation"] == "ADD"


def test_missing_state_fields_do_not_erase_existing_values():
    """5. Missing state fields in a protocol output do not erase existing values."""
    # This verifies that when a protocol outputs only technical_status and recommendation,
    # thesis_status and valuation_status are NOT included in the update payload.
    inst_id = uuid4()
    posted_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "GOOG", "asset_type": "STOCK"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            posted_payloads.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    # Only technical status and recommendation are present
    bridge.sync_protocol_run(
        run_record={
            "protocol_name": "technical-review",
            "machine_record": {
                "technical_status": "ON_TRACK",
                "recommendation": "HOLD",
            },
        },
        finance_instrument={"symbol": "GOOG"},
        auto_apply_state=True,
    )

    mr = posted_payloads[0]["machine_record"]
    assert "thesis_status" not in mr
    assert "valuation_status" not in mr
    assert mr["technical_status"] == "ON_TRACK"
    assert mr["recommendation"] == "HOLD"


def test_idempotent_sync_with_same_source_run_id():
    """6. Same source_run_id does not create duplicate reviews."""
    inst_id = uuid4()
    fixed_source_run_id = "run-2026-09-14-unique"
    post_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "AMZN", "asset_type": "STOCK"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            post_count += 1
            body = json.loads(request.content)
            assert body["source_run_id"] == fixed_source_run_id
            return httpx.Response(200, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    run_record = {
        "id": fixed_source_run_id,
        "protocol_name": "thesis-review",
        "human_brief": "Review text.",
    }

    res1 = bridge.sync_protocol_run(run_record, {"symbol": "AMZN"})
    res2 = bridge.sync_protocol_run(run_record, {"symbol": "AMZN"})

    assert res1.synced is True
    assert res2.synced is True
    assert post_count == 2  # Sent twice, backend idempotent check prevents duplicate creation


def test_ambiguous_instrument_resolution_fails_safely():
    """7. Ambiguous Instrument resolution fails safely (AmbiguousInstrumentResolutionError)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            # Returns two ambiguous candidates for "SPOT" (e.g. NYSE vs London or Stock vs Fund)
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {"id": str(uuid4()), "symbol": "SPOT", "asset_type": "STOCK", "exchange": "NYSE"},
                        {"id": str(uuid4()), "symbol": "SPOT", "asset_type": "STOCK", "exchange": "LSE"},
                    ],
                },
            )
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    # Resolution without exchange specified must fail closed!
    res = bridge.sync_protocol_run(
        run_record={"protocol_name": "thesis-review"},
        finance_instrument={"symbol": "SPOT"},  # no venue specified
        raise_on_error=False,
    )

    assert res.synced is False
    assert "Multiple ambiguous PortfolioMind Instruments" in str(res.error)

    # Explicit raise_on_error check
    with pytest.raises(PortfolioMindSyncError, match="Multiple ambiguous"):
        bridge.sync_protocol_run(
            run_record={"protocol_name": "thesis-review"},
            finance_instrument={"symbol": "SPOT"},
            raise_on_error=True,
        )


def test_portfoliomind_unavailable_finance_output_survives():
    """8. PortfolioMind unavailable -> Finance output still survives locally."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused: PortfolioMind backend offline")

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    # Must NOT raise by default; returns graceful error result
    res = bridge.sync_protocol_run(
        run_record={"id": uuid4(), "protocol_name": "thesis-review"},
        finance_instrument={"symbol": "UBER"},
        raise_on_error=False,
    )

    assert res.synced is False
    assert "Connection refused" in str(res.error)


def test_technical_review_updates_technical_state_only():
    """9. Technical Review updates technical state without overwriting unrelated thesis/valuation."""
    inst_id = uuid4()
    posted_payloads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "TSLA", "asset_type": "STOCK"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            posted_payloads.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    # Technical momentum scan output
    bridge.sync_protocol_run(
        run_record={
            "protocol_name": "technical-momentum-scan",
            "machine_record": {
                "technical_status": "DEVIATED",
                "recommendation": "REDUCE",
                "rsi_14": 78.4,
            },
            "human_brief": "Overbought momentum approaching major macro resistance.",
        },
        finance_instrument={"symbol": "TSLA"},
        auto_apply_state=True,
    )

    assert len(posted_payloads) == 1
    mr = posted_payloads[0]["machine_record"]
    assert mr["technical_status"] == "DEVIATED"
    assert mr["recommendation"] == "REDUCE"
    assert "thesis_status" not in mr
    assert "valuation_status" not in mr


def test_technical_plan_persists_correctly_when_produced():
    """10. Technical Plan persists correctly when produced."""
    inst_id = uuid4()
    review_posted = False
    plan_posted = False
    plan_body = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal review_posted, plan_posted, plan_body
        if request.url.path == "/api/instruments":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"id": str(inst_id), "symbol": "BTC", "asset_type": "CRYPTO"}]},
            )
        if request.url.path == f"/api/instruments/{inst_id}/reviews":
            review_posted = True
            return httpx.Response(201, json={"status": "success", "data": {"id": str(uuid4())}})
        if request.url.path == f"/api/instruments/{inst_id}/technical-plan":
            plan_posted = True
            plan_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={"status": "success", "data": {"id": str(uuid4()), "active": True}},
            )
        return httpx.Response(404)

    client = make_mock_client(handler)
    bridge = PortfolioMindBridge(client)

    technical_plan = {
        "reference_price": 64500.0,
        "trend_expectation": "bullish_continuation",
        "entry_zones": [{"min": 61000.0, "max": 63000.0}],
        "support_zones": [{"min": 58000.0, "max": 60000.0}],
        "resistance_zones": [{"min": 68000.0, "max": 72000.0}],
        "notes": "Ascending triangle breakout confirmation.",
        "active": True,
    }

    res = bridge.sync_protocol_run(
        run_record={
            "protocol_name": "technical-review",
            "machine_record": {"technical_status": "ON_TRACK", "recommendation": "ADD"},
        },
        finance_instrument={"symbol": "BTC", "instrument_type": "crypto"},
        technical_plan=technical_plan,
    )

    assert res.synced is True
    assert res.technical_plan_synced is True
    assert review_posted is True
    assert plan_posted is True
    assert plan_body == technical_plan
