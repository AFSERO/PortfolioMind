# Finance ↔ PortfolioMind Bridge Implementation

This document details the bridge integration layer between the **Finance / Investment Intelligence System** and **PortfolioMind**.

---

## 1. Integration Architecture & Workflow

```text
┌────────────────────────────────────────────────────────┐
│            Finance Protocol Run / Codex                │
│    (e.g., ThesisReviewWorkflow, run_asset_protocol)   │
└───────────────────────────┬────────────────────────────┘
                            │
               Machine Record + Human Brief
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              PortfolioMindBridge                       │
│    (Finance/src/investment_intelligence/portfoliomind) │
│                                                        │
│    1. Evaluates PORTFOLIOMIND_SYNC_ENABLED             │
│    2. SafeInstrumentResolver maps symbol & metadata    │
│    3. Handles source_run_id idempotency                │
│    4. Syncs review + auto-applies state                │
│    5. Syncs Technical Plan if produced                │
│    6. Captures persistence errors gracefully           │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP Bearer (JWT or Integration Token)
                            ▼
┌────────────────────────────────────────────────────────┐
│                  PortfolioMind Backend                 │
│    - POST /api/instruments/{id}/reviews                │
│    - PUT  /api/instruments/{id}/intelligence          │
│    - PUT  /api/instruments/{id}/technical-plan        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  PostgreSQL Database                   │
│    - instruments                                       │
│    - intelligence_reviews (audit trail)                │
│    - instrument_intelligence_states (latest state)     │
│    - technical_plans (active setup zones)              │
└────────────────────────────────────────────────────────┘
```

---

## 2. Integration Point in Finance

- **Location**: Natural integration boundary occurs immediately after protocol execution and validation have succeeded in Finance.
- **Independence**: The bridge adapter is strictly an integration and persistence gateway. It contains zero financial calculations or investment thesis reasoning.
- **Preservation of Local State**: The detailed research artifacts remain in `Finance/research/` (e.g. `research/UBER/2026-09-14-pass-3/research-report.md`). Only the structured `Machine Record`, `Human Brief`, confidence level, and source reference path are synced to PostgreSQL.

---

## 3. Adapter / Client Components

The bridge lives in `Finance/src/investment_intelligence/portfoliomind/`:

1. **`PortfolioMindBridge` (`bridge.py`)**:
   - High-level coordinator with `sync_protocol_run(...)` (sync) and `async_sync_protocol_run(...)` (async).
   - Extracts machine records, briefs, confidence, run ID, and resolves the target instrument.
   - Posts the review with `auto_apply_state=True`.
   - If a technical plan is included in the run or machine record, syncs the technical plan as active.
   - Returns a structured `SyncResult` envelope (`synced`, `instrument_id`, `review_id`, `state_updated`, `technical_plan_synced`, `error`, `skipped_reason`).

2. **`PortfolioMindClient` & `AsyncPortfolioMindClient` (`client.py`)**:
   - HTTP clients (sync and async via `httpx`) handling requests to `/api/instruments`, `/reviews`, `/technical-plan`, `/intelligence`.
   - Automatic Bearer authentication and token lifecycle management.

3. **`PortfolioMindBridgeConfig` (`config.py`)**:
   - Reads environment variables with clean fallbacks.

---

## 4. Instrument Resolution (`SafeInstrumentResolver`)

Finance tracks assets by symbol, asset type, and venue (e.g., `UBER`, `equity`, `NYSE`, `USD`), whereas PortfolioMind attaches intelligence to UUID-based `Instrument` records.

### Safety Invariants:
1. Queries PortfolioMind `/api/instruments?q={symbol}`.
2. Filters candidate instruments strictly matching uppercase symbol.
3. Checks asset type mapping (e.g. `equity`/`stock` -> `STOCK`, `crypto` -> `CRYPTO`, `fund`/`etf` -> `FUND`).
4. Checks exchange/venue compatibility (e.g. `NYSE == NYSE`, `BIST == BIST`).
5. Checks currency compatibility (e.g. `USD == USD`).
6. **Safety Principle (Fail Closed)**:
   - If `0` candidates match: raises `InstrumentNotFoundError`.
   - If `>1` candidates match: raises `AmbiguousInstrumentResolutionError`. It will **never** guess or attach research to the wrong instrument.
   - Exactly `1` candidate matches: returns `UUID(instrument_id)`.

---

## 5. Authentication Approach

PortfolioMind requires authenticated requests. To support seamless machine-to-machine local integration without complex OAuth flows:

1. **Static Integration Token Support**:
   - Added `INTEGRATION_TOKEN: Optional[SecretStr] = None` in `backend/app/config.py`.
   - In `backend/app/middleware/auth.py`, `get_current_user` recognizes `Authorization: Bearer <INTEGRATION_TOKEN>` and binds to the primary active user.
2. **API Login Fallback**:
   - If `PORTFOLIOMIND_API_TOKEN` is not set, `PortfolioMindClient` can use `PORTFOLIOMIND_EMAIL` and `PORTFOLIOMIND_PASSWORD` to log in via `/api/auth/login` and cache the JWT token.
3. **Security Invariant**:
   - No endpoints are made public; authentication is strictly enforced.

---

## 6. Idempotency

To prevent duplicate review entries when the same Finance research run is synced multiple times:
- `backend/app/services/intelligence.py` checks `source_run_id` on review creation.
- If a review with matching `(instrument_id, source_run_id)` already exists, `create_review` returns the existing review record instead of inserting a duplicate row.
- If `auto_apply_state=True` is passed, the current state is still ensured to be in sync.

---

## 7. State Application Rules

1. **Selective Updating**:
   - Canonical state dimensions: `thesis_status`, `valuation_status`, `technical_status`, `recommendation`.
   - The backend `auto_apply_state` only updates fields that the protocol explicitly produced.
   - Example: A Technical Review producing `technical_status` and `recommendation` updates only those two dimensions without erasing or overwriting preexisting `thesis_status` or `valuation_status`.
2. **Technical Plan Activation**:
   - When a protocol outputs a structured technical plan (entry, support, resistance, invalidation zones), the bridge posts it to `PUT /api/instruments/{id}/technical-plan`.
   - The previous active technical plan is cleanly marked inactive (`active=False`), and the new plan is activated.

---

## 8. Failure Behavior & Loose Coupling

- **Loose Coupling**: The Finance system is completely decoupled from PortfolioMind. If `PORTFOLIOMIND_SYNC_ENABLED=false` (the default), the bridge simply returns `SyncResult(synced=False, skipped_reason="PORTFOLIOMIND_SYNC_ENABLED is disabled")`.
- **Failure Resilience**: If PortfolioMind is offline (connection refused, HTTP 500/503, timeout):
  - Local research memos and local database records remain completely intact and uncorrupted.
  - By default (`raise_on_error=False`), the bridge logs the failure and returns `SyncResult(synced=False, error="...")`.
  - The caller can inspect `result.error` and take appropriate action.

---

## 9. Configuration

Environment variables recognized by the bridge:

| Variable | Type | Default | Description |
|---|---|---|---|
| `PORTFOLIOMIND_SYNC_ENABLED` | bool | `false` | Enable/disable automatic sync to PortfolioMind |
| `PORTFOLIOMIND_BASE_URL` | string | `http://localhost:8000` | Base URL of PortfolioMind API |
| `PORTFOLIOMIND_API_TOKEN` | string | `None` | Static integration token or JWT token |
| `PORTFOLIOMIND_EMAIL` | string | `None` | User email for automatic login |
| `PORTFOLIOMIND_PASSWORD` | string | `None` | User password for automatic login |
| `PORTFOLIOMIND_TIMEOUT` | float | `15.0` | HTTP request timeout in seconds |

---

## 10. Testing & Results

### 1. Bridge Unit & Contract Tests (`Finance/tests/test_portfoliomind_bridge.py`)
All 10 requested test cases were executed and passed:
1. `test_successful_review_persists_to_portfoliomind` — **PASSED**
2. `test_machine_record_stored_intact` — **PASSED**
3. `test_human_brief_stored` — **PASSED**
4. `test_canonical_state_fields_update_current_intelligence_state` — **PASSED**
5. `test_missing_state_fields_do_not_erase_existing_values` — **PASSED**
6. `test_idempotent_sync_with_same_source_run_id` — **PASSED**
7. `test_ambiguous_instrument_resolution_fails_safely` — **PASSED**
8. `test_portfoliomind_unavailable_finance_output_survives` — **PASSED**
9. `test_technical_review_updates_technical_state_only` — **PASSED**
10. `test_technical_plan_persists_correctly_when_produced` — **PASSED**

### 2. End-to-End Integration Test (`backend/tests/test_portfoliomind_bridge_e2e.py`)
- Real dated research extraction seed: `Finance/system/database/seeds/uber-thesis-2026-09-14.json`.
- Safely resolved `UBER` (STOCK, NYSE, USD) to canonical PortfolioMind Instrument ID.
- Successfully created `IntelligenceReview` with complete machine record and human brief.
- Successfully updated `InstrumentIntelligenceState` (`thesis_status=UNCHANGED`, `valuation_status=FAIR`, `recommendation=HOLD`).
- Demonstrated idempotent re-sync: second sync of the same run produced 0 duplicate reviews.
- Result: **PASSED** (0.17s).

### 3. Full PortfolioMind Suite
- `231 passed, 1 skipped` in 55.98s. Zero regressions.
