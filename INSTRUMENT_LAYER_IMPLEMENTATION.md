# Instrument Layer Implementation Report

This document outlines the design, implementation, migration strategy, and verification of the newly introduced **Instrument layer** in the NetWorth / future PortfolioMind codebase.

---

## 1. Architectural Overview

Prior to this change, `Asset` conflated two distinct responsibilities:
1. The **financial security/instrument** (e.g. `UBER`, `THYAO.IS`, `BTC`, exchange, currency, provider identity).
2. The **user's position/holding** (user ownership, notes, manual price preferences, transactions, cost basis, quantities).

The new architecture separates these concerns into a clean 3-tier hierarchy:

```text
┌────────────────────────────────────────────────────────┐
│                      Instrument                        │
│        (Canonical Investment Security Identity)        │
│   id, symbol, name, asset_type, exchange, currency,    │
│       country, isin, provider, provider_id             │
└───────────────────────────┬────────────────────────────┘
                            │ 1:N
                            │ (Instrument has many Positions)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Asset / User Position                  │
│             (User-specific Holding / Account)          │
│   id, user_id, instrument_id [FK], symbol, name, ...   │
└───────────────────────────┬────────────────────────────┘
                            │ 1:N
                            │ (Asset has many Transactions)
                            ▼
┌────────────────────────────────────────────────────────┐
│                      Transaction                       │
│              (BUY / SELL execution history)            │
│   id, asset_id [FK], type, qty, price, cash, date      │
└────────────────────────────────────────────────────────┘
```

---

## 2. What Changed

| Area | Component | Description |
|---|---|---|
| **Models** | `backend/app/models/instrument.py` | New `Instrument` entity with security metadata, indexes on `symbol`, `asset_type`, and `isin`. |
| **Models** | `backend/app/models/asset.py` | Added `instrument_id` (FK to `instruments.id`, `ondelete="SET NULL"`), indexed with `lazy="selectin"` relationship. |
| **Models** | `backend/app/models/__init__.py` | Exported `Instrument` for Alembic discovery. |
| **Alembic** | `c4d5e6f7a8b9_create_instruments_and_link_assets.py` | Creates `instruments` table, adds `assets.instrument_id`, and safely backfills/deduplicates all existing assets. |
| **Schemas** | `backend/app/schemas/instrument.py` | New `InstrumentResponse`, `InstrumentCreateRequest`, `InstrumentUpdateRequest`. |
| **Schemas** | `backend/app/schemas/asset.py` | Added optional `instrument_id`, `instrument` (`InstrumentResponse`), and `exchange` to request/response schemas. |
| **Services** | `backend/app/services/instrument.py` | New service handling lookup, conservative deduplication, metadata enrichment, and creation. |
| **Services** | `backend/app/services/asset.py` | Integrated `find_or_create_instrument` on position creation, safe relinking on symbol/type change, eager loading. |
| **Routers** | `backend/app/routers/instruments.py` | New authenticated endpoints: `GET /api/instruments` (list & search) and `GET /api/instruments/{id}`. |
| **Main** | `backend/app/main.py` | Registered `/api/instruments` router. |
| **Frontend** | `frontend/src/types/index.ts` | Added `Instrument` interface; linked `instrument_id` and `instrument` on `Asset`. |
| **Frontend** | `frontend/src/pages/AssetDetailPage.tsx` | Displays instrument exchange badge (e.g. `BIST`, `NASDAQ`) when available. |
| **Tests** | `backend/tests/test_instruments.py` | 9 new comprehensive end-to-end integration tests. |

---

## 3. New Instrument Model

Located in `backend/app/models/instrument.py`:

```python
class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        Index("ix_instruments_symbol", "symbol"),
        Index("ix_instruments_asset_type", "asset_type"),
        Index("ix_instruments_isin", "isin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    symbol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=20), nullable=False
    )
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    isin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assets: Mapped[List["Asset"]] = relationship(
        "Asset", back_populates="instrument", lazy="selectin"
    )
```

---

## 4. Asset → Instrument Relationship

In `backend/app/models/asset.py`:

```python
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )

    instrument: Mapped[Optional["Instrument"]] = relationship(
        "Instrument", back_populates="assets", lazy="selectin"
    )
```

### Key Principles Preserved:
1. **Existing Asset IDs remain untouched**: Transactions continue to reference `transactions.asset_id -> assets.id`.
2. **Cascades**: Deleting a user's `Asset` does **not** delete the shared `Instrument`. The `Instrument` remains intact for any other user positions and future intelligence records.
3. **Eager Loading**: `lazy="selectin"` guarantees that whenever an `Asset` is retrieved, its `Instrument` is fetched efficiently in a batch without triggering N+1 query latency or async greenlet issues.

---

## 5. Identity & Uniqueness Strategy

Ticker symbols are **not** globally unique (e.g. `BAT` is a stock on NYSE/NASDAQ, a stock on LSE, and Basic Attention Token in crypto).

To provide a robust foundation without overengineering a universal security master:
1. **Custom & Real Estate Assets**:
   - `asset_type in (CUSTOM, REAL_ESTATE)` or assets without a symbol are **never** shared across users or positions. Each position receives its own dedicated `Instrument`.
2. **Standard Market Assets** (`STOCK`, `CRYPTO`, `FUND`, `PRECIOUS_METALS`, `FOREX`):
   - Deduplication uses a compound identity: `(asset_type, UPPER(symbol), exchange, currency)`.
   - **Conflict Checks**: Candidates with conflicting exchanges (e.g. `NASDAQ` vs `LSE`), conflicting currencies (e.g. `USD` vs `GBP`), or conflicting ISINs are **never merged**.
   - **Ambiguity Guard**: If multiple candidate instruments match the asset type and ticker, and the caller does not provide disambiguating metadata (exchange/currency), the system creates a separate instrument rather than making an unsafe guess.
   - **Enrichment**: When an exact, unambiguous match is found, any previously missing metadata (e.g. provider or exchange) is safely backfilled onto the existing instrument.

---

## 6. Migration Strategy

Migration `c4d5e6f7a8b9_create_instruments_and_link_assets.py`:
- Revises `b8c9d0e1f2a3`.
- Creates `instruments` table and indices.
- Adds `assets.instrument_id` foreign key.
- **Data Backfill**:
  - Iterates over all existing `assets` rows in the database.
  - Reconstructs standard exchange and provider metadata (`.IS` -> BIST/TRY, US stocks -> NASDAQ/USD, crypto -> Crypto/CoinGecko, funds -> TEFAS, forex -> Forex).
  - Groups standard market assets by `(asset_type, UPPER(symbol), exchange, currency)` to reuse instruments across users.
  - Allocates dedicated instruments for custom assets and real estate.
  - Updates `assets.instrument_id` for every record.
- **Downgrade**: Drops the foreign key, drops `assets.instrument_id`, and drops `instruments`.

---

## 7. Asset Creation & Update Behavior

### Creation Flow
```text
User creates Asset (POST /api/assets)
  ↓
find_or_create_instrument(
    asset_type, name, symbol, exchange, currency, instrument_id
)
  ↓
Create Asset with asset.instrument_id = instrument.id
  ↓
Stage initial BUY transaction (if provided)
  ↓
Commit & Refresh
  ↓
Return AssetResponse (including instrument_id and instrument payload)
```

### Update Behavior
- **User updates position fields** (`notes`, `current_price` via manual override, transactions):
  - Modifies only the user's `Asset` row. The shared `Instrument` is unaffected.
- **User updates display name**:
  - Updates `Asset.name` (the user's personal label). The shared `Instrument.name` is not overwritten, preventing cross-user pollution.
- **User updates `symbol` or `asset_type`**:
  - The asset is **relinked** to a matching `Instrument` (found or newly created).
  - The previous `Instrument` is not altered, preserving integrity for any other users referencing it.

---

## 8. Backward Compatibility & Source of Truth

To ensure zero regressions:
- **Canonical going forward**: `Instrument` is the canonical identity layer for economic securities (`symbol`, `name`, `asset_type`, `exchange`, `currency`, `country`, `isin`, `provider`, `provider_id`).
- **Compatibility fields**: Existing `Asset` fields (`symbol`, `name`, `asset_type`, `current_price_currency`, `current_price`, `is_manual_price`) remain present and populated.
- **Price Fetching**: Continues to operate via existing Asset methods without changes.
- **Financial Calculations**: Cost basis, transactions, cash accounts, realized/unrealized P&L, dashboard metrics, net worth snapshots, and liabilities remain 100% untouched.

---

## 9. Tests & Verification

### Test Results
- **Backend Suite**: **219 passed, 1 skipped** (across 18 test modules, including `test_instruments.py`, `test_assets.py`, `test_transactions.py`, `test_dashboard.py`, `test_cash.py`, etc.).
- **Frontend Suite**: **37 passed** (across 13 test files).

### Dedicated Test Coverage (`tests/test_instruments.py`):
1. `test_asset_creation_creates_and_links_instrument`: Verifies instrument creation and linkage on new assets.
2. `test_identical_assets_reuse_same_instrument`: Verifies two users creating the same stock share the same `Instrument`.
3. `test_ambiguous_or_different_instruments_not_merged`: Confirms stocks and cryptos with the same ticker (e.g. `BAT`) or different exchanges (`NASDAQ` vs `LSE`) remain separate.
4. `test_custom_and_real_estate_assets_never_shared`: Verifies manual/custom assets never share instruments.
5. `test_asset_transactions_and_quantity_still_work`: Verifies BUY/SELL, average cost, quantity, and realized P&L calculations remain intact.
6. `test_asset_deletion_preserves_shared_instrument`: Verifies deleting one user's asset leaves the shared instrument intact.
7. `test_asset_update_relinks_instrument_safely`: Verifies updating a ticker relinks the asset without mutating other users' positions.
8. `test_migration_backfill_assigns_instruments`: Verifies backfill logic on unlinked assets.
9. `test_instruments_api_endpoints`: Verifies `GET /api/instruments` and `GET /api/instruments/{id}`.

---

## 10. Known Limitations

- **No external ticker validation on custom instruments**: If a user submits a completely unrecognized ticker with manual price, an `Instrument` is still created for it.
- **Single active currency per instrument**: Multi-currency listings or secondary dual-listings on different foreign exchanges are currently modeled as distinct `Instrument` records.

---

## 11. Future Investment Intelligence Integration Points

With the `Instrument` layer in place, future PortfolioMind modules can anchor directly to `Instrument` rather than the user's position:

```text
                     ┌──────────────────┐
                     │    Instrument    │
                     └────────┬─────────┘
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Asset Position│     │ Thesis & Notes│     │   Valuation   │
│ (User Account)│     │  (AI / User)  │     │ (DCF / Comps) │
└───────┬───────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Transactions  │     │   Research    │     │ Technical Plan│
│  (Cash / PL)  │     │(Filings/News) │     │(Alerts/Ranges)│
└───────────────┘     └───────────────┘     └───────────────┘
```

When building Investment Intelligence:
- Intelligence tables (`Thesis`, `Valuation`, `ResearchItem`, `TechnicalPlan`, `MonitoringRule`) will define a foreign key: `instrument_id: UUID = ForeignKey("instruments.id")`.
- AI analysis, fundamental metrics, and research dossiers can be cached and shared globally per `Instrument`, regardless of how many users hold that instrument or how many individual positions exist.
