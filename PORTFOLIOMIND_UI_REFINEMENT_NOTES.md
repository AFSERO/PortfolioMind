# PortfolioMind UI Refinement Notes

**Reference Baseline:** Visual Reference Screenshot (`media_1789558866032.png`)  
**Operating Models:** `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md` & `UI_UX_DESIGN_DECISIONS.md`  
**Date:** September 16, 2026

---

## 1. Main UI Problems Diagnosed in the Initial Implementation

Before this refinement pass, the application possessed the correct conceptual entities (pulse metrics, attention alerts, research candidates, and journal entries), but felt visually unconvincing compared to the reference design:

1. **Vertical Financial Clutter vs. Unified Hero:**
   - The dashboard previously placed `SummaryCards` (4 separate boxes in a row), then `AllocationChart` & `RightPanel` (2 stacked blocks), and then `TimelineChart` (full-width area chart) into three separate vertical rows.
   - This forced the user to scroll through three full tiers of financial numbers before reaching any Investment Intelligence.
2. **Structural Imbalance in Rows 3 & 4:**
   - `NeedsAttentionSection` spanned 2 columns while `ResearchQueue` and `UpcomingEvents` were vertically stacked into a single column. This created jarring height mismatches and erratic whitespace.
   - Row 4 (`WatchlistCard`, `PortfolioRiskCard`, `RecentJournalCard`) had mismatched padding, unstyled lists, and raw empty states.
3. **Severe Sparse-Data Collapse:**
   - When real data was sparse (e.g. 0 active alerts, no pending earnings in the next 7 days, or empty journal notes), cards collapsed into tiny 60px boxes with simple sentences, making the dashboard look unfinished and hollow.
4. **Weak Metric Card Composition:**
   - The top pulse metrics used vertical number stacks that lacked the horizontal rhythm, colored badge icons, and interactive chevrons seen in modern premium finance interfaces.

---

## 2. Refinements Implemented

### A. Dashboard Header & Greeting
- Replaced the raw currency toggle in the page header with a bespoke financial header:
  - **Left:** Bold `Dashboard` title with subtitle *"Your portfolio at a glance. Smarter insights for better decisions."*
  - **Right:** Localized date string (`Tue, Sep 16, 2026`) paired with a personalized time-of-day greeting (`Good morning, {name}.`).
  - Currency toggle remains universally accessible in the top bar.

### B. Row 1: Portfolio Pulse Metric Cards (`PortfolioPulse.tsx`)
- Restructured into 4 horizontal cards with colored badge icon containers:
  - **Card 1 (Material Events):** Amber Bell badge, bold count (`X material events`), subtitle (`Require attention` / `Operating normally`), right chevron.
  - **Card 2 (Thesis Alerts):** Rose Document badge, bold count (`X thesis alerts`), subtitle (`Holdings need review` / `Theses intact`), right chevron.
  - **Card 3 (Upcoming Events):** Blue Calendar badge, bold count (`X upcoming events`), subtitle (`In the next 7 days` / `In next 14 days`), right chevron.
  - **Card 4 (Allocation Drift):** Gold Target/Compass badge, title (`Allocation drift X%` / `Target aligned`), subtitle (`Outside target range` / `Target band aligned`), right chevron.

### C. Row 2: Master Financial Hero + Portfolio Allocation (`SummaryCards.tsx` & `AllocationChart.tsx`)
- **Master Financial Hero Card (Left ~60-65%):**
  - Combined `Total Portfolio Value` (prominent font-mono text-3xl/4xl), balance visibility toggle (eye icon), and 24h change pill with directional arrow (`+12,436.82 (+1.26%) Today`).
  - Embedded the historical area chart with a smooth emerald gradient wave directly in the upper-right quadrant.
  - Added interactive timeframe pills (`1W`, `1M`, `3M`, `6M`, `1Y`, `ALL`) driving real timeline queries.
  - Integrated the 4 core balance pillars into a structured bottom row: **Total Assets**, **Total Liabilities**, **Cash (% of portfolio)**, and **Portfolio P/L (+% all time)**.
- **Portfolio Allocation Card (Right ~35-40%):**
  - Card header: `Portfolio Allocation` with `View details →` linking to `/allocation`.
  - Balanced side-by-side layout: Donut chart on left with `Total` and formatted portfolio value in the center hole, paired with asset class rows on the right featuring icons, mini progress bars, and percentage tags.
  - Reassuring empty state with a dotted ring placeholder and "+ Add first asset" action.

### D. Row 3: Action & Attention Grid (3 Equal Columns, `min-h-[260px]`)
- **Needs Attention (`NeedsAttentionSection.tsx`):**
  - Active alerts feature circular colored status badges (Red AlertCircle, Amber AlertTriangle, Blue Info), bold titles, thesis excerpts, and chevrons.
  - **Intentional Quiet State:** When 0 alerts exist, renders a calm green/teal banner (*"Nothing currently requires your attention."*), status subtitle, and 3 structured checklist items (Theses intact, Strategy zones within bounds, Review cadence current) that preserve card height and structural balance.
- **Research Queue (`ResearchQueueCard.tsx`):**
  - Active items feature ticker, thesis focus, status pills (`Researching`, `Waiting for Price`, `Ready`, `Review`), and chevrons.
  - **Sparse State:** Renders a 4-stage pipeline guide (`1. Screening` $\rightarrow$ `2. Deep Research` $\rightarrow$ `3. Price Wait` $\rightarrow$ `4. Monitored`) with an inline `+ Add Research Candidate` button.
- **Upcoming Events (`UpcomingEventsCard.tsx`):**
  - Active reviews display date badges (`SEP 17`), review type, and chevrons.
  - **Sparse State:** Renders scheduled review cadences (`Q4 Thesis Review Cadence: Oct 01`, `Semi-Annual Rebalancing: Nov 15`) and a quiet reassurance that no volatile corporate earnings are scheduled in the next 7 days.

### E. Row 4: Watchlist, Context & Decisions Grid (3 Equal Columns, `min-h-[260px]`)
- **Watchlist Opportunities (`WatchlistCard.tsx`):**
  - Connects to real candidate instruments from `useInstruments()`.
  - Displays ticker, asset name, recommendation status badge, and chevron.
  - Sparse state features a clean placeholder with `+ Add Candidate Security`.
- **Portfolio Context (`PortfolioRiskCard.tsx`):**
  - Displays key risk and diversification characteristics:
    - `Beta (vs S&P 500)`: Value with volatility subtext.
    - `Sharpe Ratio`: Risk-adjusted return profile.
    - `Max Drawdown`: Peak-to-trough indicator (-12.6% YTD).
- **Recent Journal Entries (`RecentJournalCard.tsx`):**
  - Active entries feature formatted date badges (`SEP 14`), holding name, and rationale excerpt.
  - Sparse state features an explanatory prompt (*"Record the 'Why' behind every investment decision."*) and an inline `+ Record Decision Note` button linking directly to `/journal`.

---

## 3. Which Screens / Components Were Refined Most

1. **`frontend/src/pages/DashboardPage.tsx`**: Re-architected from an uneven, vertically fragmented layout into a balanced 4-row grid matching the reference composition.
2. **`frontend/src/components/dashboard/SummaryCards.tsx`**: Upgraded into a Master Financial Hero Card combining total value, 24h change, timeframe tabs, sparkline area chart, and 4 sub-metrics.
3. **`frontend/src/components/dashboard/AllocationChart.tsx`**: Refined with donut center value, category progress bars, and view details shortcut.
4. **`frontend/src/components/dashboard/PortfolioPulse.tsx`**: Converted to 4 horizontal metric cards with colored badge icons and chevrons.
5. **`frontend/src/components/dashboard/NeedsAttentionSection.tsx`, `ResearchQueueCard.tsx`, `UpcomingEventsCard.tsx`, `WatchlistCard.tsx`, `PortfolioRiskCard.tsx`, `RecentJournalCard.tsx`**: Standardized with consistent padding, headers, chevrons, and `min-h-[260px]` sparse-data layouts.

---

## 4. Design Tradeoffs

- **Removed `PerformersSection` and `RightPanel` from the Main Dashboard:**
  - *Rationale:* In the reference screenshot, the dashboard strictly adheres to the 4-row hierarchy without clutter. Top/worst performers are already visible in `/assets` (Holdings table with sorting) and the right panel metrics were redundant with the new Master Financial Hero.
- **Embedded Timeframe Sparkline in Financial Hero:**
  - *Rationale:* Eliminates the need for a separate full-width `TimelineChart` taking up half the dashboard viewport, allowing intelligence cards to be visible above the fold. Full detailed timeline analysis remains accessible in `/allocation` and `/assets`.

---

## 5. Verification Results

- **TypeScript Strictness:** Clean compilation (`npx tsc --noEmit` exited with code 0).
- **Vitest Unit & Integration Suite:** All 22 test files passed (57/57 tests passed, 0 failed).
- **Production Build:** `tsc && vite build` succeeded in 5.89s with clean minification.
