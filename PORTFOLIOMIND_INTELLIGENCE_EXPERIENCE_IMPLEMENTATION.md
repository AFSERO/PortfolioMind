# PortfolioMind Intelligence Experience Implementation

## Overview
This document records the completed product increment:
> **Decision Log + Intelligence Briefing + Dashboard Integration**

The implementation establishes a cohesive, audit-grade loop answering the three central product questions:
1. **What happened?** &rarr; *Intelligence Briefing* (`/briefing`) continuously scans portfolio holdings and watched securities across live evidence providers.
2. **Does it matter to my portfolio/watchlist?** &rarr; The engine classifies items by category (`EARNINGS`, `REGULATORY`, `MACRO`, `OPERATIONAL`, `COMPETITIVE`), materiality (`HIGH`, `MEDIUM`, `LOW`), and thesis impact (`STRONGER`, `WEAKER`, `UNCHANGED`). Low-materiality noise is filtered out.
3. **What did I decide because of it?** &rarr; *Decision Log* (`/decisions`) records automated portfolio trade actions, intelligence status transitions, and user rationale with inline reflection capabilities.

---

## 1. Database & Persistence Layer

### Models
- **`DecisionLogEntry`** (`backend/app/models/decision_log.py`):
  - Primary audit trail entity with `user_id`, `instrument_id`, `asset_id`, `event_type`, `title`, `summary`, `user_rationale`, `confidence`, `expectation`, `related_review_id`, `related_transaction_id`, `metadata`, `occurred_at`, `created_at`, `updated_at`.
  - Indexes on `user_id`, `occurred_at`, `instrument_id`, `asset_id`, `event_type`.
- **`BriefingRun` & `BriefingItem`** (`backend/app/models/briefing.py`):
  - `BriefingRun`: stores execution metadata (`scope`, `status`, `items_found`, `items_shown`, `items_filtered`, `generated_at`).
  - `BriefingItem`: individual classified event with `headline`, `summary`, `why_it_matters`, `impact`, `materiality`, `time_horizon`, `thesis_impact`, `review_required`, `category`, `source_metadata`, `is_portfolio`, `published_at`.

### Migration
- **Revision `e6f7a8b9c0d1_decision_log_and_briefing.py`**:
  - Successfully applied via `alembic upgrade head` on top of `d5e6f7a8b9c0`.
  - Creates tables `decision_log_entries`, `briefing_runs`, and `briefing_items` with foreign key cascades and indexes.

---

## 2. Decision Log Engine & Auto-Logging Rules

### Auto-Logging Triggers
1. **Transactions (`backend/app/services/transaction.py`)**:
   - `POSITION_OPENED`: Initial BUY when previous quantity was 0.
   - `POSITION_ADDED`: Successive BUY when previous quantity > 0.
   - `POSITION_REDUCED`: Partial SELL when remaining quantity > 0.
   - `POSITION_CLOSED`: Full SELL when remaining quantity reaches 0.
   - Transaction notes are automatically populated into `user_rationale`. Execution price, quantity, and currency are preserved in `metadata`.
2. **Intelligence State Transitions (`backend/app/services/intelligence.py`)**:
   - Compares previous state against new review:
     - `RECOMMENDATION_CHANGED`: Logged only if recommendation actually changed.
     - `THESIS_CHANGED`: Logged only if thesis status changed (`STRONGER`, `WEAKER`, etc.).
     - `VALUATION_CHANGED`: Logged on valuation shift (`ATTRACTIVE`, `FAIR`, `EXPENSIVE`).
     - `TECHNICAL_PLAN_CHANGED`: Logged on new active plan activation.
   - **Noise Suppression**: Duplicate runs that do not transition state (e.g. routine `HOLD -> HOLD` monitoring runs) are suppressed and do NOT pollute the decision audit trail.
3. **Manual Decision Notes**:
   - Users can record standalone or asset-linked decision notes via `POST /api/decisions`.
   - Users can edit their rationale, confidence, or target expectations via `PATCH /api/decisions/{id}/rationale`.

---

## 3. Intelligence Briefing Engine

### Data Flow & Noise Filtering (`backend/app/services/briefing.py`)
- Scans user's owned portfolio assets (`is_portfolio = True`) and registered watchlist securities (`is_portfolio = False`).
- Leverages live providers:
  - `GoogleNewsRSSProvider` for discovery radar.
  - `SECDisclosureProvider` for corporate filings.
  - Historical internal `IntelligenceReview` protocol briefs.
- **Classification & Materiality**:
  - `LOW`: Filtered out as noise (incrementing `items_filtered`). Not displayed in feed.
  - `MEDIUM`: Digest developments ("Worth Knowing").
  - `HIGH` / `CRITICAL`: Urgent developments ("Needs Attention"), flagging `review_required = True`.
- **Honest Quiet State**:
  - When no material events occur, 0 developments require attention, providing a calm and reassuring indicator rather than invented noise.

---

## 4. Dashboard Integration

- **PortfolioPulse**:
  - "Material Events" connects to briefing attention count (`review_required = True`), directly linking to `/briefing`.
  - When 0: displays "Operating normally" and reassuring green state.
- **NeedsAttentionSection**:
  - Unifies asset thesis alerts and briefing items needing review.
  - Displays badges (`CRITICAL`, `IMPORTANT`) and direct action links (`Review Asset` or `Review Thesis`).
- **RecentJournalCard**:
  - Powered by real `DecisionLogEntry` records (`useDecisions({ limit: 5 })`).
  - Displays date calendar tile, symbol, decision action, and user rationale snippet.
  - Directly links to the full Decision Log (`/decisions`).

---

## 5. Navigation & Routes

- **Sidebar (`frontend/src/components/layout/Sidebar.tsx`)**:
  - Under `Intelligence`: added **Briefing** (`/briefing`).
  - Under `Decisions`: renamed Journal to **Decision Log** (`/decisions`).
- **Router (`frontend/src/App.tsx`)**:
  - Route `/briefing` &rarr; `<BriefingPage />`.
  - Route `/decisions` &rarr; `<DecisionsPage />`.
  - Route `/journal` &rarr; `<Navigate to="/decisions" replace />` (backward compatibility).

---

## 6. Verification & Test Suite Status

### Backend Tests
- **All 236 tests passed (1 skipped)**:
  - `tests/test_decisions.py`: Manual decision CRUD, transaction auto-logging (`POSITION_OPENED`, `POSITION_ADDED`, `POSITION_REDUCED`, `POSITION_CLOSED`), intelligence transition logging, and noise suppression.
  - `tests/test_briefing.py`: Initial empty state, briefing generation, item and noise counting, stats endpoint.
  - All existing 231 tests for assets, auth, cash, intelligence, liabilities, prices, and statements passing.

### Frontend Tests & Build
- **All 23 test files passed (61 total tests)**:
  - `src/pages/DecisionsBriefing.test.tsx`: Validates Decision Log headers, timeline, rationale, filter tabs, Briefing pulse metrics, and attention filtering.
  - `src/components/layout/Sidebar.test.tsx`: Validates updated navigation structure.
  - `src/components/dashboard/NeedsAttentionSection.test.tsx`: Validates quiet state and actionable alerts.
- **Production Build**:
  - `npm run build` (`tsc && vite build`) executes with **zero errors**.
