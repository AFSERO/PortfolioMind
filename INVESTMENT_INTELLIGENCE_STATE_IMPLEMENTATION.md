# PortfolioMind - Investment Intelligence Persistence Layer Implementation

This document provides a technical overview of the first Investment Intelligence persistence layer implemented for **PortfolioMind**, attached to the canonical `Instrument` identity layer.

---

## 1. Architecture

### Structural Hierarchy
```text
                  Instrument (Global Security Identity)
                   ├── symbol, asset_type, exchange, isin, currency
                   │
                   ├── Asset (User Holdings / Positions)
                   │    └── Transactions, Cash movements, Cost basis, Realized P&L
                   │
                   └── Investment Intelligence (AI Research & Thesis Layer)
                        ├── InstrumentIntelligenceState (1:1 latest snapshot)
                        ├── IntelligenceReview (1:N immutable audit log of protocol runs)
                        └── TechnicalPlan (1:N plans, latest marked active=True)
```

### Key Architectural Decisions

1. **Instrument-Level Association (Never Asset-Level)**:
   - Investment analysis, thesis invalidation points, valuation models, and technical setups belong to the financial security (e.g. `UBER`, `THYAO.IS`, `BTC`), not to an individual user's trade history.
   - Deleting a user holding (`Asset`) preserves all accumulated intelligence history on the `Instrument`.

2. **Separation of Latest State vs. Review History**:
   - `InstrumentIntelligenceState` provides an immediate $O(1)$ read path for dashboards, stock badges, and portfolio overview widgets (`thesis_status`, `valuation_status`, `technical_status`, `recommendation`, `human_brief`).
   - `IntelligenceReview` is an immutable append-only audit trail capturing every protocol execution (quarterly review, technical momentum scan, valuation rerating) with its complete `machine_record` payload, research artifact path, confidence level, and source run ID.

3. **Separate Technical Plan Entity**:
   - Technical setups change on different timeframes and contain multi-level zone structures (entry zones, support zones, resistance zones, invalidation zones, profit-taking targets).
   - Separating `TechnicalPlan` allows active trading plans to be tracked independently of fundamental thesis reviews while still allowing updates to trigger state transitions.

---

## 2. Models & Database

### Database Tables Created

1. **`instrument_intelligence_states`**:
   - `id`: UUID (Primary Key)
   - `instrument_id`: UUID (Unique Foreign Key -> `instruments.id`, ON DELETE CASCADE)
   - `thesis_status`: String(20) enum (`STRONGER`, `UNCHANGED`, `WEAKER`, `INVALIDATED`)
   - `valuation_status`: String(20) enum (`ATTRACTIVE`, `FAIR`, `EXPENSIVE`)
   - `technical_status`: String(20) enum (`ON_TRACK`, `NEUTRAL`, `DEVIATED`, `REVIEW_REQUIRED`)
   - `recommendation`: String(20) enum (`ADD`, `HOLD`, `REDUCE`, `SELL`, `REVIEW_REQUIRED`)
   - `last_review_at`: DateTime(timezone=True)
   - `last_monitoring_at`: DateTime(timezone=True)
   - `next_review_at`: DateTime(timezone=True)
   - `human_brief`: Text
   - `created_at`, `updated_at`: DateTime(timezone=True)

2. **`intelligence_reviews`**:
   - `id`: UUID (Primary Key)
   - `instrument_id`: UUID (Foreign Key -> `instruments.id`, ON DELETE CASCADE)
   - `protocol`: String(128) (e.g., `quarterly_fundamental_review`, `technical_momentum_scan`)
   - `run_type`: String(64) (e.g., `scheduled`, `trigger`, `adhoc`)
   - `status`: String(20) enum (`COMPLETED`, `FAILED`, `IN_PROGRESS`, `PARTIAL`)
   - `machine_record`: JSONB (PostgreSQL) / JSON (SQLite) for metrics, inputs, raw signals
   - `human_brief`: Text
   - `confidence`: String(32) (e.g., `HIGH`, `MEDIUM`, `LOW`)
   - `research_path`: Text (relative file or artifact path)
   - `source_run_id`: String(128) (link to execution run ID)
   - `created_at`: DateTime(timezone=True)

3. **`technical_plans`**:
   - `id`: UUID (Primary Key)
   - `instrument_id`: UUID (Foreign Key -> `instruments.id`, ON DELETE CASCADE)
   - `reference_at`: DateTime(timezone=True)
   - `reference_price`: Numeric(18, 6)
   - `trend_expectation`: String(64)
   - `entry_zones`: JSONB / JSON array
   - `support_zones`: JSONB / JSON array
   - `resistance_zones`: JSONB / JSON array
   - `review_or_invalidation_zones`: JSONB / JSON array
   - `profit_taking_or_reassessment_zones`: JSONB / JSON array
   - `notes`: Text
   - `active`: Boolean (Default: False)
   - `created_at`, `updated_at`: DateTime(timezone=True)

### Indexes Added
- `ix_instrument_intelligence_states_instrument_id`
- `ix_instrument_intelligence_states_thesis_status`
- `ix_instrument_intelligence_states_recommendation`
- `ix_intelligence_reviews_instrument_id`
- `ix_intelligence_reviews_created_at`
- `ix_technical_plans_instrument_id`
- `ix_technical_plans_active`

### Alembic Migration
- **Revision ID**: `d5e6f7a8b9c0`
- **File**: `backend/alembic/versions/d5e6f7a8b9c0_add_investment_intelligence_tables.py`
- **Down Revision**: `c4d5e6f7a8b9` (instrument table migration)
- Successfully upgraded against PostgreSQL `networth` database.

---

## 3. APIs Added

All endpoints are authenticated with JWT (`Bearer <token>`) and nested under `/api/instruments`.

### Endpoints Summary

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/instruments/{id}/intelligence` | Get current intelligence state for an instrument (or `null` if unreviewed) |
| `PUT` | `/api/instruments/{id}/intelligence` | Upsert current intelligence state |
| `GET` | `/api/instruments/{id}/reviews` | List review history (descending chronological order, paginated) |
| `POST` | `/api/instruments/{id}/reviews` | Record a protocol review run (optionally auto-applies state if `auto_apply_state: true`) |
| `GET` | `/api/instruments/{id}/technical-plan` | Retrieve the active technical plan (or `null`) |
| `PUT` | `/api/instruments/{id}/technical-plan` | Create or update active technical plan (deactivates prior active plans) |

*(Note: Aliases under `/api/instruments/{id}/intelligence/reviews` and `/api/instruments/{id}/intelligence/technical-plan` are also supported).*

### Sample Payloads

#### 1. Upsert State (`PUT /api/instruments/{id}/intelligence`)
```json
{
  "thesis_status": "UNCHANGED",
  "valuation_status": "FAIR",
  "technical_status": "ON_TRACK",
  "recommendation": "HOLD",
  "human_brief": "Thesis intact. Valuation is fair at current trading levels.",
  "last_review_at": "2024-06-15T10:00:00Z",
  "next_review_at": "2024-09-15T10:00:00Z"
}
```

#### 2. Record Review Run (`POST /api/instruments/{id}/reviews`)
```json
{
  "protocol": "quarterly_fundamental_review",
  "run_type": "scheduled",
  "status": "COMPLETED",
  "machine_record": {
    "pe_ratio": 24.2,
    "growth_yoy": 0.18,
    "thesis_status": "STRONGER",
    "recommendation": "ADD"
  },
  "human_brief": "Q2 earnings beat expectations. Growth accelerating in core divisions.",
  "confidence": "HIGH",
  "research_path": "/intelligence/runs/run-2024-06-15-01",
  "source_run_id": "run-2024-06-15-01",
  "auto_apply_state": true
}
```

#### 3. Upsert Technical Plan (`PUT /api/instruments/{id}/technical-plan`)
```json
{
  "reference_price": 178.50,
  "trend_expectation": "bullish_continuation",
  "entry_zones": [
    {"min": 172.0, "max": 175.0, "rationale": "50-day EMA pullback"}
  ],
  "support_zones": [
    {"min": 168.0, "max": 170.0}
  ],
  "resistance_zones": [
    {"min": 190.0, "max": 195.0}
  ],
  "review_or_invalidation_zones": [
    {"min": 162.0, "max": 164.0}
  ],
  "profit_taking_or_reassessment_zones": [
    {"min": 192.0, "max": 200.0}
  ],
  "notes": "Healthy consolidation above prior pivot high.",
  "active": true
}
```

---

## 4. Testing & Verification

### Test Coverage (`backend/tests/test_intelligence.py`)
1. `test_unreviewed_instrument_returns_null_state`: Confirms unreviewed instruments return clean `null` data without exceptions.
2. `test_upsert_intelligence_state`: Verifies initial creation and subsequent in-place updates.
3. `test_create_and_list_reviews`: Confirms review records are appended and sorted newest-first.
4. `test_auto_apply_review_to_state`: Confirms `auto_apply_state=True` updates the current `InstrumentIntelligenceState` automatically.
5. `test_review_history_preserved_across_state_updates`: Confirms updating state via `PUT` preserves historical review records unmodified.
6. `test_asset_deletion_preserves_instrument_intelligence`: Confirms deleting user position (`Asset`) does not cascade to `Instrument` or intelligence records.
7. `test_validation_rejects_invalid_enums`: Confirms FastAPI/Pydantic returns HTTP 422 on invalid enum inputs.
8. `test_technical_plan_lifecycle`: Confirms creating a new active technical plan cleanly deactivates previous active plans.
9. `test_authentication_and_404_handling`: Confirms HTTP 401 on unauthenticated calls and HTTP 404 on nonexistent instruments.

### Full Suite Verification
- **Backend**: `228 passed, 1 skipped` (0 failures across all tests including assets, transactions, liabilities, statements, cash, and intelligence).
- **Frontend**: `37 passed` (13 test files passed including dropzones, modals, unified asset form dialogs, liabilities, statements, and summary cards).
- **Financial Calculations**: Zero changes made to transactions, cash balances, cost basis calculations, realized P&L, portfolio snapshots, or liabilities.

---

## 5. Future Codex / Investment Intelligence Integration Flow

### Integration Architecture
```text
┌────────────────────────────────────────────────────────┐
│   Investment Intelligence Engine / Protocol Runners    │
│   (Finance/src/investment_intelligence/)               │
└───────────────────────────┬────────────────────────────┘
                            │
              HTTP POST /api/instruments/{id}/reviews
              (with auto_apply_state: true)
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  PortfolioMind Backend                 │
│  - Appends to intelligence_reviews                     │
│  - Updates instrument_intelligence_states              │
└───────────────────────────┬────────────────────────────┘
                            │
               GET /api/instruments (with state)
               GET /api/instruments/{id}/intelligence
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  PortfolioMind Frontend                │
│  - Instrument badges (e.g. HOLD, FAIR, ON_TRACK)       │
│  - Human brief expandable card                         │
│  - Technical setup target & invalidation levels        │
└────────────────────────────────────────────────────────┘
```

1. **Review Execution**:
   - The intelligence runner runs a protocol (e.g. `thesis_evaluation`, `valuation_assessment`, `technical_analysis`).
   - It outputs a structured `machine_record` and markdown/plain text `human_brief`.

2. **Persistence**:
   - The runner queries `GET /api/instruments?q={symbol}` to resolve the canonical instrument ID.
   - It posts the execution result to `POST /api/instruments/{id}/reviews` with `auto_apply_state: true`.
   - The persistence service atomically inserts the historical review and refreshes `InstrumentIntelligenceState`.

3. **Frontend Presentation**:
   - In asset lists and instrument detail views, components read `instrument.intelligence_state` to render status tags:
     - Thesis: `STRONGER` (green), `UNCHANGED` (neutral), `WEAKER` (yellow), `INVALIDATED` (red)
     - Recommendation: `ADD`, `HOLD`, `REDUCE`, `SELL`
     - Human brief: summaries visible directly in portfolio cards.
