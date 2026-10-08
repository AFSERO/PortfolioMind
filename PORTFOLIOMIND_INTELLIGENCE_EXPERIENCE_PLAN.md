# PortfolioMind Intelligence Experience Plan
## Decision Log + Intelligence Briefing + Dashboard Integration

**Date:** September 16, 2026  
**Status:** In Implementation  
**References:**
- `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md`
- `UI_UX_DESIGN_DECISIONS.md`
- `PORTFOLIOMIND_UI_IMPLEMENTATION_PLAN.md`
- `PORTFOLIOMIND_UI_REFINEMENT_NOTES.md`

---

## 1. Product Lifecycle & Goal

PortfolioMind answers three connected questions:
```text
What happened? (Intelligence Briefing)
       ↓
Does it matter to my portfolio or watchlist? (Materiality, thesis impact, review required)
       ↓
What did I decide because of it? (Decision Log)
```

The unified lifecycle:
```text
Portfolio + Watchlist
        ↓
Intelligence Briefing (Noise filtered, material developments highlighted)
        ↓
Important Development (Review triggered if thesis is impacted)
        ↓
User Decision (BUY, SELL, HOLD, Trim, Revise Thesis)
        ↓
Decision Log (Objective context auto-captured + optional user rationale)
        ↓
Dashboard (Recent decisions, active material events, and attention counts)
```

---

## 2. Decision Log Architecture

### 2.1 Backend Data Model: `DecisionLogEntry`
Table: `decision_log_entries`

- `id`: UUID (Primary Key)
- `user_id`: UUID (ForeignKey to `users.id`, ondelete="CASCADE", Indexed)
- `instrument_id`: Optional[UUID] (ForeignKey to `instruments.id`, ondelete="SET NULL", Indexed)
- `asset_id`: Optional[UUID] (ForeignKey to `assets.id`, ondelete="SET NULL", Indexed)
- `event_type`: String (Enum: `POSITION_OPENED`, `POSITION_ADDED`, `POSITION_REDUCED`, `POSITION_CLOSED`, `BUY`, `SELL`, `THESIS_REVIEWED`, `THESIS_CHANGED`, `VALUATION_CHANGED`, `TECHNICAL_PLAN_CHANGED`, `RECOMMENDATION_CHANGED`, `INTELLIGENCE_REVIEW_COMPLETED`, `MANUAL_DECISION_NOTE`)
- `title`: String(255) (e.g. *"Position Added: UBER"*, *"Recommendation Changed: HOLD → REDUCE"*)
- `summary`: Text (Objective system-generated context: price, quantity, state transition)
- `user_rationale`: Optional[Text] (User's reasoning, thesis expectation, or reflection)
- `confidence`: Optional[String(32)] (`HIGH`, `MEDIUM`, `LOW`)
- `expectation`: Optional[Text] (Expected horizon or target catalyst)
- `related_review_id`: Optional[UUID] (ForeignKey to `intelligence_reviews.id`, ondelete="SET NULL")
- `related_transaction_id`: Optional[UUID] (ForeignKey to `transactions.id`, ondelete="SET NULL")
- `metadata`: JSONB (Stores transition details, old/new values, execution context)
- `occurred_at`: DateTime(timezone=True) (Timestamp of actual decision/event)
- `created_at`: DateTime(timezone=True) (Server timestamp)
- `updated_at`: DateTime(timezone=True)

### 2.2 Auto-Logging Rules (Noise Prevention)
1. **Transactions (`create_transaction`):**
   - When a `BUY` transaction is executed:
     - If current holding was 0: Logs `POSITION_OPENED`.
     - If current holding > 0: Logs `POSITION_ADDED`.
   - When a `SELL` transaction is executed:
     - If remaining holding is 0: Logs `POSITION_CLOSED`.
     - If remaining holding > 0: Logs `POSITION_REDUCED`.
   - Captures price, quantity, currency, and user's transaction notes into `user_rationale`.
2. **Intelligence Reviews (`create_review`):**
   - Only log when a **meaningful state transition** occurs:
     - `Recommendation` changes (e.g. `HOLD → REDUCE`, `ADD → HOLD`, `HOLD → SELL`).
     - `ThesisStatus` changes (e.g. `STRONGER → WEAKER`, `UNCHANGED → INVALIDATED`).
     - `ValuationStatus` changes (e.g. `FAIR → EXPENSIVE`).
   - Rule: Identical transitions (e.g. `HOLD → HOLD`, `UNCHANGED → UNCHANGED`) do **NOT** create a decision log entry.
3. **Technical Plan Replacement (`create_technical_plan`):**
   - When an active plan is replaced or deactivated, logs `TECHNICAL_PLAN_CHANGED`.
4. **Manual Entries (`POST /api/decisions`):**
   - Allows users to attach rationale, confidence, and expectations to any instrument or holding.

---

## 3. Intelligence Briefing Architecture

### 3.1 Scope & Purpose
The Briefing is **not** an unfocused market-wide news feed. It scans strictly for developments relevant to:
1. **Portfolio Instruments:** Assets currently owned by the user.
2. **Watchlist Instruments:** Candidate securities under active research/monitoring.

### 3.2 Backend Data Models
- **`BriefingRun`** (`briefing_runs`):
  - `id`: UUID (Primary Key)
  - `user_id`: UUID (ForeignKey to `users.id`, ondelete="CASCADE")
  - `generated_at`: DateTime(timezone=True)
  - `scope`: String (`PORTFOLIO_AND_WATCHLIST`)
  - `status`: String (`COMPLETED`, `FAILED`)
  - `items_found`: Integer (Total raw events discovered)
  - `items_shown`: Integer (Items meeting Medium/High threshold)
  - `items_filtered`: Integer (Low materiality / noise count)
  - `created_at`: DateTime(timezone=True)

- **`BriefingItem`** (`briefing_items`):
  - `id`: UUID (Primary Key)
  - `briefing_run_id`: UUID (ForeignKey to `briefing_runs.id`, ondelete="CASCADE")
  - `user_id`: UUID (ForeignKey to `users.id`, ondelete="CASCADE")
  - `instrument_id`: UUID (ForeignKey to `instruments.id`, ondelete="CASCADE")
  - `headline`: String(255)
  - `summary`: Text (2-3 concise sentences)
  - `why_it_matters`: Text (Strategic/thesis implications)
  - `impact`: String (`POSITIVE`, `NEGATIVE`, `NEUTRAL`, `MIXED`)
  - `materiality`: String (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `time_horizon`: String (`SHORT`, `MEDIUM`, `LONG`)
  - `thesis_impact`: String (`STRONGER`, `UNCHANGED`, `WEAKER`, `INVALIDATED`, `NOT_EVALUATED`)
  - `review_required`: Boolean (True for High/Critical)
  - `category`: String (`EARNINGS`, `REGULATORY`, `MACRO`, `OPERATIONAL`, `COMPETITIVE`, `GENERAL`)
  - `source_metadata`: JSONB (Title, publisher, URL, source quality: `PRIMARY` | `PROFESSIONAL` | `RADAR_UNVERIFIED`)
  - `is_portfolio`: Boolean (Distinguishes owned holdings vs watchlist candidates)
  - `published_at`: DateTime(timezone=True)
  - `created_at`: DateTime(timezone=True)

### 3.3 Noise Reduction Principle
- `NEEDS ATTENTION`: `review_required=True` (Materiality High/Critical, thesis impact Weaker/Invalidated).
- `WORTH KNOWING`: `review_required=False` (Materiality Medium, relevant context).
- `FILTERED AS NOISE`: Materiality Low. Counted in `items_filtered` and excluded from the main feed.

### 3.4 Finance System Integration
- Uses Finance evidence adapters:
  - `GoogleNewsRSSProvider` for discovery radar.
  - `SECDisclosureProvider` for primary filings metadata.
  - Existing `news-monitoring` protocol definitions.
- Generates structured items through a dedicated briefing generator in PortfolioMind that leverages Finance records and categorizes them with verified sources.

---

## 4. API Endpoints

### Decisions API (`/api/decisions`)
- `GET /api/decisions`: List decision log entries (supports filtering by `event_type`, `instrument_id`, `asset_id`, pagination).
- `POST /api/decisions`: Create manual decision entry or attach user rationale.
- `PATCH /api/decisions/{id}/rationale`: Update user rationale, confidence, expectation on an existing entry.

### Briefing API (`/api/briefing`)
- `GET /api/briefing/latest`: Fetch latest briefing run and associated briefing items for current user.
- `POST /api/briefing/generate`: Trigger an on-demand briefing generation for owned + watchlist instruments.

---

## 5. UI Architecture & Navigation

### Navigation Hierarchy
```text
OVERVIEW
  Dashboard

PORTFOLIO
  Holdings
  Allocation
  Cash
  Liabilities

INTELLIGENCE
  Briefing (/briefing)       [NEW]
  Watchlist (/watchlist)
  Research (/research)
  Monitoring (/monitoring)

DECISIONS
  Decision Log (/decisions)  [RENAMED & UPGRADED from Journal]

SYSTEM
  Settings
```

### New Briefing Screen (`/briefing`)
- Header with "Briefing: Your portfolio-relevant intelligence digest" and "Generate / Refresh Briefing" button.
- Summary counter bar:
  - `X Need Attention` (amber/rose)
  - `Y Worth Knowing` (teal/sky)
  - `Z Filtered as Noise` (muted count)
- Filter tabs: All, Portfolio, Watchlist, High Impact, Earnings, Regulatory, Macro.
- Concise intelligence cards with badge tags (Portfolio/Watchlist, Category, Impact, Horizon, Thesis impact, Review required, Source link, link to Asset).
- Honest empty state: *"Nothing material was found for your portfolio or watchlist."*

### Upgraded Decision Log Screen (`/decisions`)
- Displays chronological timeline of decisions (position additions, trims, closes, thesis revisions, recommendation changes, and manual notes).
- Each entry displays:
  - Objective context pill (e.g. `BUY: 10 shares @ $150.00`, `Recommendation Changed: HOLD → REDUCE`).
  - Related review link if triggered by protocol review.
  - User rationale, confidence, and expectations.
  - Ability to add or edit user rationale directly inline.

---

## 6. Dashboard Integration

Connect the Dashboard directly to the new persistent models:
1. **Portfolio Pulse:**
   - `Material Events`: Count of unreviewed material briefing items (`review_required=True` from latest briefing).
   - `Thesis Alerts`: Count of active holdings with thesis status `WEAKER` or `INVALIDATED`.
2. **Needs Attention Card:**
   - Aggregates briefing items where `review_required=True` alongside thesis-breaking events.
3. **Recent Decisions Card:**
   - Displays real recent entries from `decision_log_entries` table.
4. **Quiet State:**
   - When no alerts exist, renders intentional quiet reassurance: *"Nothing important requires your attention today."*

---

## 7. Verification & Testing Plan

1. **Backend Tests:**
   - `test_decisions.py`: Manual decision creation, transaction auto-logging, intelligence review state transition auto-logging, no-duplicate transition suppression.
   - `test_briefing.py`: Briefing run generation, portfolio vs watchlist mapping, noise filtering, persistence, source references.
2. **Frontend Tests:**
   - Briefing page rendering, filtering, refresh button state.
   - Decision Log rendering, inline rationale editing.
   - Dashboard integration with real Briefing and Decision Log state.
3. **Full System Verification:**
   - `pytest backend/tests` (all 231+ tests passing).
   - `npm test -- --run` (all vitest suites passing).
   - `tsc && vite build` (clean production build).
