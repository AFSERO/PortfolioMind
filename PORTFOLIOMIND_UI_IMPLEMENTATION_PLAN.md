# PortfolioMind UI Implementation Plan & Roadmap

**Created:** 2026-09-16  
**Status:** READY FOR IMPLEMENTATION  
**Primary Reference Documents:**
- `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md`
- `UI_UX_DESIGN_DECISIONS.md`
- `PORTFOLIOMIND_INTEGRATION_CONTEXT.md`

---

## 1. Executive Summary & Core Product Direction

PortfolioMind is evolving from a net-worth tracker into an **AI-powered investment intelligence and decision-support platform**.

### The Main Product Hierarchy
```text
Portfolio   → What do I own?
Intelligence → What requires my attention?
Decisions   → Why did I make this decision?
```

### Key Principles
1. **Noise Reduction:**
   $$\text{Information} \neq \text{Attention} \neq \text{Action}$$
   The application is comfortable telling the user: *"Nothing important requires your attention today."*
2. **Contextual & Quiet AI:**
   No giant AI chatbot homepage hero box. AI is contextual, specialized, and quiet.
3. **Preserve the Financial Core:**
   Assets, transactions, cash, liabilities, P&L, multi-currency conversion, pricing, and auth remain 100% operational. Evolve rather than rewrite.
4. **Leverage Existing Backend:**
   The backend already has Instrument identity, `InstrumentIntelligenceState`, `IntelligenceReview`, `TechnicalPlan`, and Finance bridge persistence. We connect to these existing models rather than reinventing them.

---

## 2. Progress Tracker

- [x] **Phase 1:** Application Shell, Navigation & Visual Foundation (COMPLETE)
- [x] **Phase 2:** PortfolioMind Decision Dashboard (COMPLETE)
- [x] **Phase 3:** Asset & Instrument Detail Experience (COMPLETE)
- [x] **Phase 4:** Intelligence / Needs Attention & Monitoring Experience (COMPLETE)
- [/] **Phase 5:** Research & Watchlist Experience (IN PROGRESS)
- [ ] **Phase 6:** Decisions / Journal Experience
- [ ] **Phase 7:** Polish, Responsiveness & Reassuring Empty States

---

## 3. Phase-by-Phase Plan

---

### Phase 1: Application Shell, Navigation & Visual Foundation

- **Objective:** Establish the PortfolioMind brand identity, quiet global top bar, and multi-tier navigation hierarchy (`Overview`, `Portfolio`, `Intelligence`, `Decisions`, `System`) while keeping all existing routes functional.
- **Screens / Components Affected:**
  - `frontend/src/components/layout/AppShell.tsx`
  - `frontend/src/components/layout/Sidebar.tsx`
  - `frontend/src/components/layout/TopBar.tsx` (NEW)
  - `frontend/src/App.tsx`
  - `frontend/index.html` (title: PortfolioMind)
- **Existing Components Reused:**
  - `Button`, `Avatar`, `Sheet`, `ToggleGroup`, `useAuthStore`, `useDashboardStore`, `sonner`.
- **New Components:**
  - `TopBar.tsx`: Global search input placeholder, display currency selector (TRY/USD/EUR), notifications indicator, user avatar.
  - Route placeholders for `/allocation`, `/watchlist`, `/research`, `/monitoring`, `/journal`.
- **API Dependencies:**
  - Existing auth and user endpoints.
- **Backend Changes:** None.
- **Tests:**
  - Vitest test suite (`npm test -- --run`)
  - TypeScript check (`npx tsc --noEmit`)
- **Completion Criteria:**
  - Sidebar displays "PortfolioMind / Investment Intelligence" with clean dark styling.
  - Navigation accurately groups `OVERVIEW` (Dashboard), `PORTFOLIO` (Holdings, Allocation, Cash, Liabilities), `INTELLIGENCE` (Watchlist, Research, Monitoring), `DECISIONS` (Journal), and `SYSTEM` (Settings).
  - Existing pages (`/dashboard`, `/assets`, `/cash`, `/liabilities`, `/settings`) navigate without error.
  - Responsive mobile drawer reflects the same hierarchy.

---

### Phase 2: PortfolioMind Decision Dashboard

- **Objective:** Transform the dashboard from a purely financial overview into a decision-support dashboard matching `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md` (4-row wireframe grid).
- **Screens / Components Affected:**
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/components/dashboard/PortfolioPulse.tsx` (NEW)
  - `frontend/src/components/dashboard/NeedsAttentionSection.tsx` (NEW)
  - `frontend/src/components/dashboard/ResearchQueueCard.tsx` (NEW)
  - `frontend/src/components/dashboard/UpcomingEventsCard.tsx` (NEW)
  - `frontend/src/components/dashboard/WatchlistCard.tsx` (NEW)
  - `frontend/src/components/dashboard/PortfolioRiskCard.tsx` (NEW)
  - `frontend/src/components/dashboard/RecentJournalCard.tsx` (NEW)
  - `frontend/src/components/dashboard/SummaryCards.tsx` (MODIFIED)
  - `frontend/src/components/dashboard/AllocationChart.tsx` (MODIFIED)
  - `frontend/src/components/dashboard/TimelineChart.tsx`
- **Existing Components Reused:**
  - `TimelineChart`, `PerformersSection`, `AllocationChart`, `SummaryCards`, `FinancialValue`.
- **New Components:**
  - `PortfolioPulse`: 4 counters (Material Events, Thesis Alerts, Upcoming Events, Allocation Drift).
  - `NeedsAttentionSection`: Displays actionable items if a holding has `WEAKER`/`INVALIDATED` thesis or `REVIEW_REQUIRED`/`SELL` recommendation. When clean, displays the intentional quiet state: *"✓ Nothing currently requires your attention. N positions monitored, 0 thesis-breaking events, 0 technical deviations."*
  - `ResearchQueueCard`: Active research status summary.
  - `UpcomingEventsCard`: Upcoming earnings, reports, review cadences.
  - `WatchlistCard`: Researched opportunities approaching entry range.
  - `PortfolioRiskCard`: Actionable concentration and asset-class metrics.
  - `RecentJournalCard`: Summary of latest thesis reviews and rationale.
- **API Dependencies:**
  - Existing `/api/dashboard/summary`, `/api/dashboard/allocation`, `/api/dashboard/timeline`, `/api/assets`.
- **Backend Changes:** None.
- **Tests:**
  - Dashboard component tests, empty-state tests, Vitest + TypeScript checks.
- **Completion Criteria:**
  - Dashboard exhibits the 4-row layout from Section 27 wireframe grid.
  - Portfolio Pulse displays accurate status counts.
  - "Needs Attention" displays contextual alerts or the reassuring empty state.
  - Financial summary and timeline charts remain responsive and accurate.

---

### Phase 3: Asset & Instrument Detail Experience

- **Objective:** Evolve `/assets/:id` into an investment decision workstation combining position economics with Investment Intelligence state, Technical Plan zones, review audit trail, and TradingView charts.
- **Screens / Components Affected:**
  - `frontend/src/pages/AssetDetailPage.tsx`
  - `frontend/src/services/intelligenceService.ts` (NEW)
  - `frontend/src/hooks/useIntelligence.ts` (NEW)
  - `frontend/src/components/assets/VerdictCard.tsx` (NEW)
  - `frontend/src/components/assets/TechnicalPlanZones.tsx` (NEW)
  - `frontend/src/components/assets/IntelligenceTimeline.tsx` (NEW)
  - `frontend/src/components/assets/ContextualAIActions.tsx` (NEW)
- **Existing Components Reused:**
  - `TradingViewChart`, `AssetTypeBadge`, `TransactionDialog`, `AssetFormDialog`, `DeleteConfirmDialog`.
- **New Components:**
  - `VerdictCard`: Recommendation badge (`HOLD`, `ADD`, `REDUCE`, `SELL`, `REVIEW_REQUIRED`), Thesis status, Valuation status, Technical status, human brief, freshness timestamp.
  - `TechnicalPlanZones`: Visual scale showing Invalidation < Entry < Current Price < Profit-taking zones from `TechnicalPlan`.
  - `IntelligenceTimeline`: Chronological audit trail of protocol reviews with expandable machine records.
  - `ContextualAIActions`: Quiet prompts tailored to the specific asset.
- **API Dependencies:**
  - Existing `/api/assets/{id}`, `/api/instruments/{id}/intelligence`, `/api/instruments/{id}/reviews`, `/api/instruments/{id}/technical-plan`.
- **Backend Changes:** None.
- **Tests:**
  - Asset detail and intelligence component tests.
- **Completion Criteria:**
  - Detail page renders the Decision Box (Verdict), Strategy Zones (Technical Plan), and Review Timeline when available.
  - Assets without intelligence display clean, honest empty state.
  - All existing transaction CRUD and P/L calculations continue to function.

---

### Phase 4: Intelligence / Needs Attention & Monitoring Experience

- **Objective:** Provide a dedicated `/monitoring` command center for multi-asset thesis health, technical deviations, review cadences, and alert filtering.
- **Screens / Components Affected:**
  - `frontend/src/pages/MonitoringPage.tsx` (NEW)
  - `frontend/src/components/monitoring/MonitoringTable.tsx` (NEW)
- **Existing Components Reused:**
  - `AppShell`, `PageHeader`, `AssetTypeBadge`, `Skeleton`.
- **New Components:**
  - `MonitoringTable`: Filterable by Thesis Status (`STRONGER`, `UNCHANGED`, `WEAKER`, `INVALIDATED`), Technical Status, Recommendation. Direct links into asset detail.
- **API Dependencies:**
  - Existing `/api/assets` (which loads instruments and intelligence states).
- **Backend Changes:** None.
- **Tests:**
  - Page render tests and filter tests.
- **Completion Criteria:**
  - `/monitoring` route displays monitored assets with thesis and technical health.
  - Filter by alert severity.

---

### Phase 5: Research & Watchlist Experience [COMPLETED]

- **Objective:** Dedicated `/watchlist` and `/research` pages to track unowned candidates and research pipeline stages (`DISCOVERED` → `SCREENING` → `RESEARCHING` → `VALUED` → `READY` → `WAITING FOR PRICE`).
- **Screens / Components Affected:**
  - `frontend/src/pages/WatchlistPage.tsx` (NEW)
  - `frontend/src/pages/ResearchPage.tsx` (NEW)
  - `frontend/src/services/instrumentService.ts` (NEW)
- **Existing Components Reused:**
  - `AppShell`, `PageHeader`, `Card`, `Badge`, `Button`.
- **New Components:**
  - Pipeline board / list of research items.
  - Watchlist cards with entry price targets.
- **API Dependencies:**
  - Existing `/api/instruments` (search & list).
- **Backend Changes:** None.
- **Tests:**
  - Watchlist and Research page tests.
- **Completion Criteria:**
  - Non-held instruments can be viewed and tracked on `/watchlist` and `/research`.

---

### Phase 6: Decisions / Journal Experience [COMPLETED]

- **Objective:** Dedicated `/journal` page answering *"Why did I make this decision?"* by combining historical protocol reviews, transaction notes, and manual decision logs.
- **Screens / Components Affected:**
  - `frontend/src/pages/JournalPage.tsx` (NEW)
  - `frontend/src/components/journal/JournalTimeline.tsx` (NEW)
- **Existing Components Reused:**
  - `AppShell`, `PageHeader`, `Card`.
- **New Components:**
  - `JournalTimeline`: Displays decision records with rationale, timestamps, and linked assets.
- **API Dependencies:**
  - Aggregates reviews and transaction notes across portfolio instruments.
- **Backend Changes:** None.
- **Tests:**
  - Journal page tests.
- **Completion Criteria:**
  - Timeline of investment decisions and thesis reviews displayed chronologically.

---

### Phase 7: Polish, Responsiveness & Reassuring Empty States [COMPLETED]

- **Objective:** Ensure dark theme consistency, loading skeletons, error resilience, mobile viewports, and quiet empty states meet the design manifesto.
- **Verification:**
  - Full Vitest suite run (`npm test -- --run`).
  - Full backend pytest suite run (`.venv\Scripts\python -m pytest backend/tests`).
  - Strict TypeScript check (`npx tsc --noEmit`).
  - Manual end-to-end check.
