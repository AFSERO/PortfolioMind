# PortfolioMind Main Dashboard Operating Model (Product & UI/UX Concept)

**Document Type:** Candidate Product Direction / Design Manifesto  
**Date:** 2026-09-16  
**Status:** PROPOSED CONCEPT (NOT IMPLEMENTED / NO CODE CHANGES)  
**Reference Baseline:** `PORTFOLIOMIND_INTEGRATION_CONTEXT.md`

> [!IMPORTANT]
> **Status:** We are NOT implementing anything yet. This document is purely product/UI/UX ideation and conceptual documentation. No components, routes, database models, or APIs are modified. It records an approved candidate product direction for continued discussion and challenge.

---

## Executive Context

PortfolioMind is evolving from the existing NetWorth application.

- **NetWorth** primarily answers:  
  *“What do I own?”*
- **PortfolioMind** should eventually answer:  
  *“What do I own?”*  
  *“Why do I own it?”*  
  *“What changed?”*  
  *“Does anything require my attention?”*  
  *“Is my investment thesis still valid?”*  
  *“What am I researching?”*  
  *“What risks exist across my portfolio?”*  
  *“What important events are coming?”*  
  *“Is my portfolio still aligned with my intended allocation?”*

PortfolioMind should therefore feel less like a traditional net-worth tracker and more like a **personal investment intelligence / decision-support system**.

The dashboard should remain visually connected to the existing NetWorth product:
- Dark theme
- Left sidebar
- Restrained card-based layout
- Clean typography
- Premium financial application feel

**The Key Principle:**  
The dashboard should not try to show everything. It should show the user:
1. Current portfolio state
2. What changed
3. What deserves attention
4. What is coming next
5. What research is in progress
6. Whether portfolio structure is drifting
7. Whether there is anything the user actually needs to do

The dashboard should **reduce noise rather than create more market-monitoring behavior**.

---

## 1. Core Dashboard Philosophy

The PortfolioMind dashboard should behave like a **personal investment control center**.

### What it should NOT be:
- A Bloomberg clone
- A TradingView clone
- A scrolling news feed
- A list of daily gainers and losers
- A screen full of market prices
- A trading terminal
- An AI chatbot homepage

### What it should instead be:
- Portfolio-aware
- Thesis-aware
- Research-aware
- Event-aware
- Risk-aware
- Action-oriented
- Low-noise
- Decision-support focused

The main question the dashboard should answer every time it opens is:  
> **“Is there anything important in my portfolio that deserves my attention?”**

Ideally, the user should be able to understand the answer within a few seconds.

### The Critical Separation:
The dashboard intentionally separates:
$$\text{INFORMATION} \quad \neq \quad \text{ATTENTION} \quad \neq \quad \text{ACTION}$$

- A market event may be interesting without being actionable.
- A price move may be large without being material.
- A portfolio alert may require research without requiring a trade.
The product should reflect that distinction.

---

## 2. Main Navigation Concept

The left sidebar should evolve from the existing NetWorth navigation.

```
PORTFOLIOMIND
Investment Intelligence

OVERVIEW
- Dashboard

PORTFOLIO
- Holdings
- Allocation
- Cash

INTELLIGENCE
- Watchlist
- Research
- Monitoring

DECISIONS
- Journal

SYSTEM
- Settings
```

> [!NOTE]
> This is a conceptual navigation model only. Do not implement or finalize routes yet.

**The Navigation Hierarchy:**
- **Portfolio** = what I own
- **Intelligence** = what I am evaluating or monitoring
- **Decisions** = why I acted

The user should naturally understand the distinction without needing documentation.

---

## 3. Global Top Bar

The dashboard may contain a compact global top bar.

**Possible elements:**
- **Search:** *“Search for a ticker, company or topic…”*  
  Eventually acts as a universal entry point for:
  - Owned assets
  - Watchlist assets
  - Researched assets
  - Companies, funds, cryptocurrencies
  - Research records
- **Right-side utilities:**
  - Display currency (TRY, USD, EUR)
  - Notifications
  - Theme
  - User account

The top bar should remain visually quiet and not compete with dashboard content.

---

## 4. Dashboard Header

**Example:**  
**Dashboard**  
*“Your portfolio at a glance. Smarter insights for better decisions.”*

- *Optional:* Current date & greeting (e.g. `Tue, Sep 16, 2026 — Good morning, User`).
- The greeting is not a critical feature; the header should remain compact.

---

## 5. Portfolio Pulse / Attention Summary

Directly below the header should be a very compact portfolio status layer: **PORTFOLIO PULSE**.

These are **NOT traditional financial KPI cards**. They represent: *“What changed or needs attention?”*

| Indicator | Metric | Context |
|---|---|---|
| **Material Events** | `3` | Require your attention |
| **Thesis Alerts** | `1` | A holding needs review |
| **Upcoming Earnings** | `2` | Within next 7 days |
| **Allocation Drift** | `4.2%` | Outside target range |

- Each item behaves as a **navigation shortcut** into deeper information.
- The objective is **fast situational awareness** in under 5 seconds.
- Restrained severity logic: `Neutral`, `Informational`, `Attention`, `Important`, `Critical`.
- Colors must be restrained; red is strictly reserved for genuinely important situations.

---

## 6. Main Portfolio Summary

Preserves NetWorth's strong total portfolio / net worth presentation, made more useful:

- **Large primary number:** e.g., `₺996,923.29`
- **Optional period change:** `+₺12,436 (+1.26%)`
- **Time selector:** `1W`, `1M`, `3M`, `6M`, `1Y`, `ALL`
- **Chart:** Portfolio value over time.
- **Compact statistics row below:**
  - Total Assets
  - Total Liabilities
  - Cash
  - Portfolio P/L

Avoid metric overload. The summary answers:
1. *How much is the portfolio worth?*
2. *How has it changed?*
3. *What are the major balance components?*

---

## 7. Portfolio Allocation

Donut or proportional visualization with high-level categories:
- Global Equities
- Turkish Equities
- Gold / Precious Metals
- Defensive
- Crypto
- Active / Opportunistic
- Cash

### Evolving Beyond Simple Allocation:
Conceptually supports **Current Allocation vs. Target Allocation**:
- Global Equities: `Current: 31% | Target: 40%`
- Gold: `Current: 27% | Target: 15%`
- Crypto: `Current: 8% | Target: 10%`

**Drift Detection:**
The system flags: *“Allocation drift detected”* or *“Portfolio allocation requires review.”*  
It does **NOT** dictate: *“Sell X / Buy Y”*. PortfolioMind is decision support, not automated algorithmic trading.

---

## 8. Needs Attention

**One of the most vital modules on the dashboard.**

This does NOT simply show biggest price drops or gains. Items appear only when something potentially relevant happened:

- **UBER:** New regulatory event may affect original thesis.
- **THF:** Latest holdings report materially changed portfolio exposure.
- **Portfolio:** Gold allocation moved significantly above target.
- **TSMC:** New earnings released and research is now stale.
- **BTC:** Volatility materially increased relative to normal range.

### Structure of an Attention Item:
- **Header:** Asset / Portfolio name
- **Headline:** What happened?
- **Short Reason:** Why might I care?
- **Severity Level:** Informational / Attention / Review / Important / Critical
- **Action Shortcut:** `Review`, `Read`, `Update research`, `Inspect allocation`

> [!IMPORTANT]
> **Avoid fake urgency.** A price decline alone is NOT an alert.  
> `“AAPL down 7%”` is not enough.  
> Supporting context is required: `“AAPL down 7%; no material company-specific event detected”` or `“AAPL down 7% after guidance revision.”` Distinguish price movement from thesis-changing information.

---

## 9. Research Queue

A concise dashboard summary of active research in progress.

**Rows may show:**
- **TSMC:** `Researching`
- **UBER:** `Waiting for Price`
- **Microsoft:** `Ready`
- **Bitcoin:** `Review`

**Possible States in the Pipeline:**
`DISCOVERED` → `SCREENING` → `RESEARCHING` → `VALUED` → `READY` → `WAITING FOR PRICE` → `OWNED` → `REVIEW` → `REJECTED`

The dashboard answers: *“What investment work am I currently doing?”* (not a list of every company ever looked at).

---

## 10. Upcoming Events

Prioritized list of highest-value upcoming portfolio / research events:
- **UBER Earnings:** in 3 days
- **TSMC Earnings:** in 8 days
- **THF Holdings Report:** Expected this month
- **Fed Interest Rate Decision:** Tomorrow

**Categories:** Earnings, Fund reports, Central bank meetings, Regulatory decisions, Investor days, Product launches, Research/Thesis review dates.  
**Rule:** Prioritized by portfolio relevance. Macro events that don't affect holdings should not dominate.

---

## 11. Watchlist Opportunities

A compact module answering: *“Which already-researched opportunities deserve attention?”*

- Avoid turning this into a noisy stock screener.
- **Examples:**
  - UBER: `Waiting for Price`
  - TSMC: `Researching`
  - Company X: `Valuation approaching desired entry range`
- **Tone & State Philosophy:** Avoid shouting terms like `BUY NOW` or `STRONG BUY`. Prefer thoughtful states: `Researching`, `Watch`, `Waiting for Price`, `Ready for Review`, `Owned`.

---

## 12. Portfolio Context / Risk

Meaningful risk interpretation over finance-dashboard decoration:
- Largest position & concentration
- Largest asset class & country exposure
- Largest currency exposure
- Largest risk factor
- Volatility & maximum drawdown

*Rule:* Every metric must answer a real question. `Technology concentration: 38%` is far more actionable than displaying abstract raw statistical values like `Beta: 0.93`.

---

## 13. Investment Journal Summary

Shows recent meaningful investment activity and decision rationale:
- *Updated UBER thesis*
- *Added TSMC to research queue*
- *Reduced gold exposure*
- *Reviewed THF*
- *Closed research on Company X*

The journal records **WHY** decisions were made, not just the mechanical transaction.

---

## 14. Dashboard Information Priority (Visual Hierarchy)

The screen prioritizes information in this exact order:
1. **ATTENTION:** What requires inspection?
2. **PORTFOLIO STATE:** What do I currently own and what is it worth?
3. **STRUCTURE:** Is the portfolio aligned with intended allocation?
4. **RESEARCH:** What am I currently investigating?
5. **UPCOMING EVENTS:** What important events are coming?
6. **HISTORY:** What decisions or thesis changes were recently recorded?

> **Daily price movements should NOT outrank these categories.**

---

## 15. Noise Reduction Principle

PortfolioMind actively reduces the volume of financial noise:

$$\text{1,000 market events} \longrightarrow \text{100 potentially relevant} \longrightarrow \text{20 portfolio-related} \longrightarrow \text{5 material developments} \longrightarrow \text{1–2 requiring research} \longrightarrow \text{0–1 actions}$$

The dashboard displays the **filtered end of this pipeline**, never the raw stream.

---

## 16. “Nothing to Do” is a Valid (and Successful) Result

> [!TIP]
> Some days the correct dashboard state is:
> - No thesis-changing events
> - No allocation issues
> - No major upcoming portfolio events
> - No research action required
> - Everything operating normally
>
> This should feel like a **successful outcome**. The dashboard makes it psychologically comfortable to do nothing, which is essential for disciplined long-term investing.

---

## 17. Alert Design Philosophy

- **INFO:** Useful context, no action needed.
- **WATCH:** Worth knowing.
- **REVIEW:** Requires research or inspection.
- **IMPORTANT:** Material change.
- **CRITICAL:** Potentially thesis-changing.

*Severity does NOT mean trading:* `CRITICAL` does not mean `SELL`. It means the information may materially impact the thesis and warrants review.

---

## 18. Asset-Level Connection

Dashboard alerts are never dead ends:
- Clicking a dashboard alert (e.g. `UBER: Guidance changed`) drills directly into the asset's intelligence context (`Overview`, `Position`, `Thesis`, `Research`, `Valuation`, `Risks`, `Events`, `News`).

---

## 19. AI Philosophy

- AI does **NOT** dominate the dashboard.
- No giant "Ask AI" homepage hero box.
- AI is **contextual, specialized, and quiet**:
  - Dashboard level: *"What is the biggest shared risk across my holdings?"*
  - Asset level: *"Did the latest earnings change my original thesis?"*
  - Research level: *"Challenge my assumptions."*
- The product is 100% usable without chatting with AI.

---

## 20. Visual Direction

- **Theme:** Dark navy / charcoal interface, matching existing NetWorth aesthetic.
- **Cards:** Subtle borders, soft elevation, rounded corners, clean typography.
- **Density:** High information density without feeling crowded.
- **Accents:** PortfolioMind green / teal as primary.
- **Semantic Accents:**
  - `Blue`: Information
  - `Yellow`: Attention
  - `Red`: Genuinely important risk
  - `Purple`: Research / Alternative status
- Avoid excessive colors and rainbow charts. Clear visual hierarchy.

---

## 21. Data Freshness

Explicit freshness badges to prevent presenting stale research alongside live prices:
- *Prices updated:* 2 minutes ago
- *Portfolio calculated:* 10:42
- *THF holdings:* Report date Aug 31
- *Research:* Updated 47 days ago
- *Thesis:* Reviewed 12 days ago

---

## 22. Meaningful Empty States

No fake placeholders; clear, honest states:
- *No active research:* "Your research queue is empty."
- *No alerts:* "Nothing currently requires your attention."
- *No upcoming events:* "No major portfolio events in the next 7 days."
- *No target allocation:* "Target allocation has not been configured yet."

---

## 23. Future Personalization

Priorities dynamically adjust based on user's portfolio weights, watchlist, thesis status, risk profile, and review cadence.

---

## 24. What Should NOT Be on the Main Dashboard

The dashboard is for **orientation and attention management**, not storage. The following belong deeper in the app:
- Full transaction history
- Full research documents & thesis texts
- Full DCF / valuation models
- Full financial statements
- Raw news feeds
- Full screener & macroeconomic databases
- Full tax calculations & trading terminals

---

## 25. The 30-Second vs. Deep Research Experience

When opening PortfolioMind, the ideal user journey:
1. **Step 1:** Immediately see total portfolio state.
2. **Step 2:** Immediately understand whether anything important happened.
3. **Step 3:** See whether portfolio allocation or risk needs review.
4. **Step 4:** See active research and upcoming events.
5. **Step 5:** If something matters, drill down.
6. **Step 6:** If nothing matters, close the application with peace of mind.

---

## 26. Long-Term Product Identity

PortfolioMind is a coherent single workspace:
$$\text{Personal Portfolio Tracker} + \text{Investment Research Workspace} + \text{Thesis Database} + \text{Monitoring Engine} + \text{Decision Journal} + \text{AI Analytical Layer}$$

The user never feels like they are switching between six disjointed tools. The portfolio is the center of gravity.

### 26.1 Future Direction: Multi-User Support & Personalized Investment Policy

> [!NOTE]
> **Roadmap Idea / Future Direction Only:** This is a future product requirement / roadmap idea. Do not design or implement it yet. Recorded here so future sessions are aware of it.

PortfolioMind should eventually support multiple users.

Each user should be able to define their own:
- investment goals
- time horizon
- risk tolerance and risk capacity
- target asset allocation
- investment philosophy
- preferred asset classes
- liquidity needs
- portfolio constraints
- position/concentration limits
- research priorities
- monitoring preferences
- alert thresholds
- level of active vs passive investing

PortfolioMind should then adapt its:
- portfolio analysis
- allocation logic
- research priorities
- monitoring
- alerts
- risk interpretation
- AI context
- decision-support behavior

to that user's own investment policy/profile.

**Conceptual model:**
$$\text{User Profile} \longrightarrow \text{Investment Policy} \longrightarrow \text{Portfolio Rules} \longrightarrow \text{Research Priorities} \longrightarrow \text{Monitoring Rules} \longrightarrow \text{AI Context}$$

---

## 27. Proposed Dashboard Wireframe Grid

```
+-------------------------------------------------------------------------------+
| TOP BAR: Global Search (Ticker/Company/Topic)   |  TRY/USD  | Alerts | User   |
+-------------------------------------------------------------------------------+
| HEADER: Dashboard - "Your portfolio at a glance."                             |
+-------------------------------------------------------------------------------+
| PORTFOLIO PULSE:                                                              |
| [ 3 Material Events ]  [ 1 Thesis Alert ]  [ 2 Upcoming ]  [ Drift 4.2% ]     |
+-------------------------------------------------------+-----------------------+
| PRIMARY ROW:                                          | PORTFOLIO ALLOCATION: |
| TOTAL PORTFOLIO VALUE (Large Number + P/L + Timeline) | Current vs. Target    |
| [ Assets | Liabilities | Cash | Net P/L ]             | Drift status          |
+-------------------------------------------------------+-----------------------+
| SECONDARY ROW:                                                                |
| [ NEEDS ATTENTION (Filter-first) ] | [ RESEARCH QUEUE ] | [ UPCOMING EVENTS ] |
+-------------------------------------------------------------------------------+
| TERTIARY ROW:                                                                 |
| [ WATCHLIST OPPORTUNITIES ]    | [ PORTFOLIO RISK ]     | [ RECENT JOURNAL ]  |
+-------------------------------------------------------------------------------+
```

---

## 28. Guiding Mantra

> **NetWorth asked:** *“What do I own?”*  
> **PortfolioMind asks:**  
> *“What do I own?”*  
> *“Why do I own it?”*  
> *“What changed?”*  
> *“What matters?”*  
> *“What am I researching?”*  
> *“What should I review?”*  
> **“What can I safely ignore?”**

---

## 29. Next Steps for Collaborative Challenge

Before any line of UI code is written, future discussions should challenge:
1. Navigation structure & taxonomy
2. Priority and sizing of the proposed dashboard modules
3. Asset Detail deep-dive experience (Verdict, Buy/Sell zones, Review timeline)
4. Research and monitoring workflows
5. Journal entry format
6. Alert threshold rules and notifications
