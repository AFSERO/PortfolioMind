# PortfolioMind Phase 4 — Investor Profile & Assessment

Status: **DESIGN DRAFT — requires product approval before implementation**  
Date: 2026-09-29. Scope: product specification only. No production code, migrations, providers or automation changed.

## 1. Decision and architecture baseline

Offer one optional **Investor Profile**, containing Goals & Financial Context, Risk Profile, Investment Policy, and Preferences. Keep experience and involvement inside Preferences, but expose them separately in interpretation. Keep provenance, completeness and revision metadata alongside these sections. A profile describes the investor's circumstances, intentions and constraints; it never contains positions, transactions, account balances or calculated portfolio exposure.

Risk tolerance is psychological willingness; risk capacity is ability to absorb losses without compromising needs. Neither substitutes for the other. Capacity is a bounded assessment of self-reported facts, not an independently verified financial diagnosis. Knowledge, goals and capacity warrant separate treatment; this distinction is consistent with the [FCA's suitability overview](https://www.fca.org.uk/firms/assessing-suitability). Goal horizons also matter to allocation interpretation, as described by [Investor.gov](https://www.investor.gov/glossary-term-categories/asset-allocation). These are design references, not a claim of regulatory compliance. All thresholds and completeness weights below are proposed product heuristics, not validated psychometrics or externally prescribed rules.

### Inspected checkout, not roadmap assumptions

| Evidence inspected | Current source-backed finding | Phase 4 implication |
| --- | --- | --- |
| [Integration context](../PORTFOLIOMIND_INTEGRATION_CONTEXT.md), [SPEC](../SPEC.md), [AGENTS](../AGENTS.md) | Older NetWorth phases coexist with newer Copilot Phase 2/3 work. Integration context's original inspection is dated September 16, with subsequent additions. | Use current code for seams. This specification concerns Investor Profile Phase 4, not the old Gemini chatbot roadmap. |
| [User model](../backend/app/models/user.py) | User has ID, email, password hash, display name, base currency (default TRY), timestamps. No investor assessment/profile model found in the model inventory. | Link a new conceptual profile to authenticated user ID; do not turn account settings into a risk model or assume TRY is spending currency. |
| [Asset](../backend/app/models/asset.py), [cash](../backend/app/models/cash.py), [liability](../backend/app/models/liability.py), [snapshots](../backend/app/models/portfolio_snapshot.py), [opening positions](../backend/app/models/opening_position.py) | Holdings belong to user-owned Asset records linked to canonical Instruments; cash, liabilities, snapshots and opening balances are separate models. No standalone Portfolio model was found in this inventory. | Initially scope profile to the user's tracked investments; goal IDs are planning scopes, not invented portfolio IDs. Financial context answers do not duplicate financial ledgers. |
| [Context engine](../backend/app/services/copilot/context_engine.py) | USER_PROFILE currently emits display name/base currency. Its documented precedence places structured profile/policy after current portfolio state. | Extend the existing context seam with confirmed profile fields, versions, uncertainty and applicability. Holdings establish actual exposure; policy establishes intended exposure. Neither overwrites the other. |
| [Prompt orchestrator](../backend/app/services/copilot/prompt_orchestrator.py), [classifier](../backend/app/services/copilot/intent_classifier.py), [service](../backend/app/services/copilot/service.py) | USER_PROFILE and INVESTMENT_POLICY context names exist; POLICY_CHANGE is recognized. Service's UPDATE_POLICY branch returns an action intent with AUTO_APPLY metadata but explicitly says no database write occurs. | This is partial scaffolding, not working policy persistence. Phase 4 must replace this route with confirmation semantics; do not inherit AUTO_APPLY for profile/policy. |
| [Copilot architecture](copilot_architecture.md), [proposal/audit models](../backend/app/models/copilot.py), [executor](../backend/app/services/copilot/executor.py) | Persistent proposals/audit and narrow executors exist. Executor dispatch has transactions, watchlist, journal and import, but no investor-profile/policy executor. | Reuse proposal lifecycle and add narrowly scoped profile confirmation later. Documentation's general write guarantees are not fresh runtime certification here. |
| [Import architecture](portfolio_import_architecture.md), [import router](../backend/app/routers/copilot.py) | CSV/chat converge on Phase 3 import. Screenshot upload currently returns 501 because extraction is unconfigured. Import confirmation requires IMPORT. | Reuse import and accounting semantics; gate screenshot by actual capability. Profile confirmation never confirms import. |

Inspection was read-only against a working tree containing existing changes. No application tests, database migrations or live provider checks were run for this documentation task. Historical “verified” statements in other documents are not validation performed here.

## 2. Experience and assessment structure

Create account → invitation → optional assessment → Investor Profile Draft → review/edit → confirm → optional Portfolio Setup → dashboard. “Skip for now” at the invitation goes directly to the dashboard; an independent portfolio-setup entry remains available there.

Invitation copy: **“Help PortfolioMind understand your goals and preferences. Start with 12 short questions. You can skip anything and change it later.”** Buttons: “Start”, “Skip for now”. Explain that draft answers are saved privately to resume and become active personalization only after confirmation. No repeated blocking invitations on login.

| Layer | Questions | Presentation and estimated effort |
| --- | --- | --- |
| Core | C01–C12 | Four short sections: goals/needs, resilience, comfort/experience, approach/constraints. 12 cards, roughly 7–10 minutes including a brief review; not 12 single clicks. One initial goal; up to three conditional cards usually add 2–4 minutes. |
| Extended | E01–E12 | Optional modules from review/settings: context, preferences, research/monitoring. Usually 4–6 relevant cards, 3–6 minutes; never auto-chain all of them after core. |
| Advanced IPS | A01–A08 | User-invoked policy editor. 8 cards with repeatable rule rows; around 5–10 minutes for users who already know their rules, longer for complex policies. |
| Conditional | F01–F04 | Only when relevant; same skip controls. F01 withdrawal details, F02 restrictions, F03 leverage scope, F04 custom alert details. |

Estimates are hypotheses to validate with usability testing across language and experience levels. A normal user should obtain a useful, bounded profile after approximately 10–12 core answers, not need all 36 question definitions. Seven well-chosen answers may support some explanations; no answer count unlocks a blanket “suitable” result.

All screens support “Skip question”, “Skip section”, back/edit, and “Save and leave”. Section skip records unanswered members as skipped without deleting answered members. Resume returns to the saved position. Progress means cards visited in this session, distinct from meaningful profile completeness. Additional goals can be added later by repeating C01/C02 and linking F01; no artificial limit of three lifetime goals.

“Essential” below means essential to a particular personalization capability, **never mandatory to enter the app or confirm an incomplete profile**. Recommended answers improve usefulness. Optional means specialist/detail input. Numeric inputs can always be left blank. A user declining financial disclosures is not penalized with more reminders or assigned low risk.

## 3. Questionnaire conventions

The English text below is canonical product copy, to be localized without changing stable IDs or option semantics. No answer is preselected. Each question additionally offers **“I don't know yet”**, **“Prefer not to say”**, and skip. These create distinct missing states, not substantive enums. “None”, “no restriction” and zero are affirmative answers, not missingness. On multiple choice, “none”, “no preference” and missing-state controls are exclusive.

Each card specifies section/layer, priority, answer type, exact substantive choices, purpose, mapping, affected dimensions, dependencies and checks. “Other: yes” adds the exact **“Other / My answer”** option with an optional text box, up to 2,000 characters; an empty custom answer stays unresolved. No forced interpretation. “Other: no” applies to bounded numeric questions where custom numbers already fit. A free-text escape is allowed for any question via an accessible “Explain my answer” note; it does not override a selection.

Dimension keys: **T** risk tolerance; **C** risk capacity; **I** IPS; **P** preferences; **G** goals/context. Field paths refer to §4. Rule IDs refer to §6. Every substantive answer is draft until confirmed. Fields may be unknown unless the dictionary explicitly says otherwise.

### Core assessment

#### C01 — Main goal

- Section: Goals & Financial Context; core; **essential**. Text: **“What is the main job you want this money to do?”**
- Type: single choice. Options: `PRESERVE` “Preserve purchasing power”; `GROW` “Build long-term wealth”; `INCOME` “Support regular spending”; `RETIREMENT` “Fund retirement”; `PURCHASE` “Pay for a major purchase”; `EDUCATION` “Fund education”; `LEGACY` “Leave money to others”; `EXPLORING` “I am still deciding”. Other: yes (`OTHER`).
- Why: anchors relevance and priorities without assuming every user wants maximum return. Fields: `goals.items[].kind`; system creates stable goal ID. Dimensions: G, I.
- Dependencies: C02 refers to this goal. “Add another goal” repeats C01/C02; E02 prioritizes them. Checks: X01, X06; EXPLORING does not imply an established objective.

#### C02 — Horizon and flexibility

- Section: Goals & Financial Context; core; **essential**. Text: **“When will you first need money for this goal, and could you delay it?”**
- Type: single choice for horizon and single choice for flexibility. Horizon options: `LT_1Y` “Under 1 year”; `Y1_3` “1 to under 3 years”; `Y3_5` “3 to under 5 years”; `Y5_10` “5 to under 10 years”; `GE_10Y` “10 years or more”; `ONGOING` “I need it now and regularly”; `NO_DATE` “No planned date”. Flexibility: `FIXED` “Cannot delay”; `SOME` “Can delay somewhat”; `FLEXIBLE` “Can substantially delay or reduce this goal”. Other: yes; optional exact date/month input retains precision.
- Why: separates timing from willingness to delay. Fields: `goals.items[].horizon`, `.target_date`, `.flexibility`. Dimensions: G, C, I.
- Dependencies: repeat per goal; C03/F01 identifies withdrawals rather than assuming all goal capital is needed on the first date. Checks: X01, X02, X06.

#### C03 — Withdrawals

- Section: Goals & Financial Context; core; **essential**. Text: **“Will you need to take money from these investments in the next three years?”**
- Type: single choice. Options: `NONE` “No planned withdrawals”; `ONE_OFF` “One or more one-off withdrawals”; `REGULAR` “Regular withdrawals”; `BOTH` “Both one-off and regular withdrawals”; `POSSIBLE` “Possibly, but I cannot estimate yet”. Other: yes.
- Why: identifies capital that cannot be treated as fully long term. Field: `goals.withdrawal_pattern`. Dimensions: G, C, I.
- Dependencies: ONE_OFF/REGULAR/BOTH → F01; POSSIBLE offers F01 but permits unknown quantities. Checks: X01, X02, X06, X09.

#### C04 — Accessible reserves

- Section: Financial resilience; core; **essential**. Text: **“Outside the money planned for these goals, how long could accessible savings cover essential expenses if your usual income stopped?”**
- Type: single choice. Options: `NONE` “No separate reserve”; `LT_1M` “Under 1 month”; `M1_3` “1 to under 3 months”; `M3_6` “3 to under 6 months”; `M6_12` “6 to under 12 months”; `GE_12M` “12 months or more”. Other: yes.
- Why: measures financial buffer without asking exact income, bank balances or counting goal money twice. Field: `goals.reserve_months_band`. Dimensions: C, G.
- Dependencies: help text defines accessible as usable when needed, not locked pension/property or available borrowing. Checks: X03, X09.

#### C05 — Cash flow and reliability

- Section: Financial resilience; core; **essential**. Text: **“After essential expenses and required payments, what best describes your usual cash flow and how reliable it is?”**
- Type: two single-choice parts. Cash flow: `SURPLUS` “Usually money left to save”; `BREAK_EVEN` “Usually about enough”; `DEFICIT` “Often need savings or borrowing”; `VARIABLE` “Varies too much to summarize”. Reliability: `RELIABLE` “Fairly predictable”; `VARIABLE` “Changes substantially”; `AT_RISK` “Likely to reduce or stop”; `NO_OUTSIDE_INCOME` “I mainly live from investments”. Other: yes, separately per part.
- Why: captures ability to replenish capital without privileging salaried employment over pensions or irregular work. Fields: `goals.cashflow`, `goals.income_reliability`. Dimensions: C, G.
- Dependencies: NO_OUTSIDE_INCOME offers C03/F01 if skipped. Checks: X03, X06, X09. Retirement or variable income alone is not a low-capacity classification.

#### C06 — Obligations

- Section: Financial resilience; core; **recommended**. Text: **“Could required payments or financial support commitments put pressure on your ability to keep investing?”**
- Type: single choice. Options: `NONE` “No material commitments”; `MANAGEABLE` “Commitments are comfortably covered”; `PRESSURE` “They sometimes strain my finances”; `ARREARS` “I am behind or expect difficulty paying”; `CHANGE_EXPECTED` “A significant new commitment is expected”. Other: yes.
- Why: debt/support burden matters more here than lender names, family status or exact debt balances. Field: `goals.obligation_pressure`. Dimensions: C, G.
- Dependencies: CHANGE_EXPECTED optionally opens E03 for timing/context. Checks: X03. Do not ask who is supported or for medical details.

#### C07 — Consequences of loss

- Section: Financial resilience; core; **essential**. Text: **“If this goal's investment money permanently lost 20% of its value, what would the financial effect be?”** Helper: “Think about what you could afford, separately from how upsetting it would feel.”
- Type: single choice. Options: `ESSENTIALS` “Essential spending or required payments would be at risk”; `GOAL_UNAFFORDABLE` “The goal would no longer be affordable”; `ADJUST_GOAL` “I could delay or reduce the goal”; `LITTLE_EFFECT` “No material change to essentials or this goal”. Other: yes.
- Why: direct loss-bearing consequence, distinct from a temporary drawdown. Field: `goals.items[].loss_consequence`. Dimensions: C, G.
- Dependencies: asked for initial goal; offered for every additional goal. Checks: X01, X03. The scenario is not a forecast or a claim that 20% is a maximum loss.

#### C08 — Drawdown comfort

- Section: Risk Profile; core; **essential**. Text: **“For money you do not need soon, which fall from a previous high could you tolerate without feeling you must change your plan?”** Helper: “Recovery is uncertain and may take years; some losses may be permanent.”
- Type: single choice. Options: `NONE` “I would not be comfortable with a loss”; `P5` “About 5%”; `P10` “About 10%”; `P20` “About 20%”; `P30` “About 30%”; `P40_PLUS` “40% or more”. Other: yes; any supplied custom percentage must be 0–100 and explicitly confirmed.
- Why: stated psychological comfort, never a capacity estimate or automatic stop-loss instruction. Fields: `risk.drawdown_comfort`, `risk.custom_drawdown_pct`. Dimensions: T.
- Dependencies: show both percent and a normalized 100-unit example, not an invented portfolio balance. Checks: X01, X04, X10.

#### C09 — Reaction under stress

- Section: Risk Profile; core; **recommended**. Text: **“Imagine your long-term investments fall 20% in six months. Your needs are unchanged, but recovery is uncertain. What would you most likely do?”**
- Type: single choice. Options: `EXIT` “Sell most or all”; `REDUCE` “Reduce risk”; `REVIEW` “Pause and review before deciding”; `HOLD` “Keep the plan”; `ADD_IF_FUNDED` “Consider adding only if spare money and my plan permit”. Other: yes.
- Why: provides a second tolerance signal; buying the dip is not rewarded with capacity points. Field: `risk.stress_response`. Dimensions: T.
- Dependencies: E04 offers actual prior behavior. Checks: X04, X05; changed circumstances can explain differences.

#### C10 — Product experience

- Section: Preferences / Experience; core; **recommended**. Text: **“Which investments have you used, and how comfortable are you explaining their risks?”**
- Type: multiple choice of product families, with a single-choice experience level per selected family. Families: `CASH` “Cash/deposits”; `BONDS` “Bonds”; `FUNDS` “Funds/ETFs”; `STOCKS` “Individual shares”; `FX` “Foreign currency”; `METALS` “Precious metals”; `PROPERTY` “Property”; `CRYPTO` “Cryptoassets”; `DERIVATIVES` “Options/futures”; `PRIVATE` “Private/illiquid investments”; `NONE` “None yet”. Levels: `LEARNING` “Learning, have not used”; `USED_BASIC` “Used, need explanations”; `UNDERSTAND` “Used and understand main risks”. Other: yes, custom family.
- Why: adjusts explanations and flags complex-product discussions; self-assessed familiarity is not a suitability license. Field: `preferences.experience[]` (family, level); NONE is an explicit empty set. Dimensions: P.
- Dependencies: unfamiliar products → educational explanation when discussed, not an extra quiz at signup. Checks: X05, X08.

#### C11 — Desired involvement

- Section: Preferences; core; **recommended**. Text: **“How would you like to manage investment decisions?”**
- Type: single choice. Options: `LOW_MAINTENANCE` “Keep a simple plan with occasional reviews”; `PERIODIC` “Research and adjust from time to time”; `ACTIVE` “Research and make decisions frequently”; `MIXED` “A simple core plus some active decisions”; `LEARNING` “Help me learn before choosing an approach”. Other: yes.
- Why: adapts workflow and research burden without equating activity with risk. Field: `preferences.involvement`. Dimensions: P.
- Dependencies: E05/E06 optional. Checks: X07.

#### C12 — Important restrictions

- Section: Investment Policy; core; **recommended**. Text: **“Are there investments or practices PortfolioMind should avoid when showing ideas?”**
- Type: multiple choice. Options: `NONE` “No restrictions I want to set now”; `BORROWING` “Borrowing to invest”; `COMPLEX` “Complex/leveraged products”; `ILLIQUID` “Money being locked up”; `ASSETS` “Specific asset classes or products”; `MARKETS` “Specific markets/countries”; `VALUES` “Activities or products for personal, ethical or religious reasons”; `ACCESS` “Investments I cannot access”. Other: yes.
- Why: elicits constraints voluntarily without asking identity or beliefs. Fields: `policy.restriction_topics`, then `policy.constraints[]` through F02. Dimensions: I, P.
- Dependencies: non-NONE choices → F02. BORROWING pre-fills a draft prohibition for review; does not silently activate it. Checks: X08, X10, X11.

### Conditional detail cards

#### F01 — Withdrawal detail

- Section: Goals & Financial Context; conditional; **essential when withdrawals apply**. Text: **“For this withdrawal, when is it needed and how much of the investment money does it use?”**
- Type: repeatable numeric/range plus choices. Timing: “Now”, “Under 12 months”, “12 to under 36 months”, “36 months or later”, or month/date. Size mode: “Percentage of the investment money covered by this profile” (0–100), “Amount and currency” (nonnegative decimal + currency), or “Not sure”. Recurrence: `ONCE`, `MONTHLY`, `QUARTERLY`, `YEARLY`; for recurrent rows ask optional end month. Coverage: `INVESTMENTS` “From these investments”; `OUTSIDE` “Already covered outside them”; `PARTIAL` “Partly covered outside”; `UNKNOWN`. For PARTIAL, same size modes for uncovered portion. Other: yes.
- Why: quantifies affected capital, timing and recurring needs without demanding holdings. Fields: `goals.withdrawals[]` including optional linked `goal_id`; details in §4. Dimensions: G, C, I.
- Dependencies: C03 or goal-specific need; optional link to an existing goal avoids entering the same need twice. Each row can be skipped. Checks: X01, X02, X06, X09. Never convert amounts to portfolio percentages without a separate, current, user-scoped portfolio denominator.

#### F02 — Constraint detail

- Section: Investment Policy; conditional; **recommended**. Text: **“What exactly should be excluded or limited, and is this a firm rule or a preference?”**
- Type: multiple choice plus optional text. Scope: `ALL` “All tracked investments” or `GOAL` “A selected goal”. Strength: `HARD` “Do not suggest”; `SOFT` “Prefer alternatives”. Rule: `EXCLUDE`, `LIMIT`, `REQUIRE_REVIEW`. Subject: selected C12 topic plus a named product/category/market/activity. LIMIT optionally takes 0–100% with denominator “investments in this scope”; vague limit stays unresolved. Other: yes.
- Why: “ethical” alone cannot identify exclusions or attest compliance. Fields: `policy.constraints[]` (scope, goal_id, topic, subject, strength, rule, max_pct). Dimensions: I, P.
- Dependencies: topic-specific editable draft; “requires certification” can be preserved as subject text, never inferred from religion. Checks: X08, X10, X11.

#### F03 — Leverage detail

- Section: Investment Policy; conditional; **optional**. Text: **“Which uses of borrowing or derivatives, if any, are within your policy?”**
- Type: multiple choice plus numeric/range. Uses: `HEDGING` “Hedging existing exposure”; `BORROWED_INVESTING` “Investing borrowed money”; `LEVERAGED_PRODUCTS` “Leveraged funds/products”; `SPECULATION` “Speculative derivatives”. Optional gross-exposure limit: 100–1,000% of net investment equity; preserve other metrics as text for review. Other: yes.
- Why: separates hedging, leverage and speculation. Fields: `policy.leverage_uses`, `policy.gross_exposure_limit_pct`. Dimensions: I.
- Dependencies: A03 conditional/allowed. Checks: X03, X05, X08, X10. A number outside this UI range may be retained as custom text, not silently clipped or deemed safe.

#### F04 — Alert detail

- Section: Preferences / Monitoring; conditional; **optional**. Text: **“What should trigger this alert?”**
- Type: single choice metric plus numeric input and choices. Metrics: `DRAWDOWN` “Fall from a previous high”; `PRICE_MOVE` “Price move”; `ALLOCATION_DRIFT` “Difference from my target”. Threshold: >0 to 100 percent for price/drawdown, >0 to 100 percentage points for drift. Window: `DAY`, `WEEK`, `MONTH`, `SINCE_REVIEW`; direction for PRICE_MOVE: `UP`, `DOWN`, `EITHER`; scope: `ALL`, `GOAL`, or user-selected instrument reference from existing instrument search. Other: yes.
- Why: avoids ambiguous “alert at 10%”. Fields: `preferences.custom_alerts[]` (metric, threshold, unit, window, direction, scope, goal_id, instrument_id). Dimensions: P.
- Dependencies: E09 threshold topic; drift requires A01 and observable allocation. Checks: X10, X12. This is an alert request, not a stop-loss or trade order.

### Extended profile

#### E01 — Spending and jurisdiction context

- Section: Goals & Financial Context; extended; **recommended**. Text: **“Which currencies will you spend this money in, and is country-specific context relevant?”**
- Type: multiple choice searchable ISO 4217 currency list, optional country selection (ISO 3166-1 alpha-2), optional free text for cross-border context. Country prompt: “Country whose market or tax context you want considered”; not nationality. Options for jurisdiction intent: `NONE` “No country-specific context”; `SUPPLY` “I want to supply it”. Other: yes.
- Why: identifies spending-currency mismatch and relevance without inferring residence from IP, UI language or TRY account default. Fields: `goals.spending_currencies`, `goals.jurisdiction_mode`, `goals.jurisdictions`, `goals.jurisdiction_note`. Dimensions: G, I.
- Dependencies: optional per-goal currency via E02. Checks: X13. No automatic tax conclusion from country alone; multi-jurisdiction analysis may remain unavailable.

#### E02 — Goal priority and size

- Section: Goals & Financial Context; extended; **recommended for multiple goals**. Text: **“Which goals take priority, and do you have a target amount?”**
- Type: per-goal single choice `ESSENTIAL`, `IMPORTANT`, `ASPIRATIONAL`; optional numeric amount/currency or target percentage of the defined investment scope (0–100). Other: yes.
- Why: distinguishes negotiable aspirations from capital that must be available. Fields: `goals.items[].priority`, `.target_size`. Dimensions: G, C, I.
- Dependencies: one or more goals. Checks: X01, X02, X06. A goal target and its linked withdrawal are not two separate liabilities.

#### E03 — Material change ahead

- Section: Goals & Financial Context; extended; **optional**. Text: **“Is a known change likely to affect your ability to save or withdraw money?”**
- Type: multiple choice `NONE`, `INCOME_CHANGE`, `RETIREMENT`, `LARGE_EXPENSE`, `RELOCATION`, `SUPPORT_COMMITMENT`; optional timing “Under 1 year”, “1–3 years”, “Later”, and optional note. Other: yes.
- Why: identifies review triggers without ages, employers, diagnoses or dependants' identities. Fields: `goals.expected_changes[]` (kind, timing, note). Dimensions: C, G.
- Dependencies: C06 may offer it; material cash needs link back to F01. Checks: X03, X06.

#### E04 — Lived downturn experience

- Section: Risk Profile; extended; **optional**. Text: **“Have you held investments through a substantial market fall, and what did you do?”**
- Type: single choice `NO_EXPERIENCE` “Not yet”; `SOLD` “Sold because of discomfort”; `NEEDS_SALE` “Sold because I needed money”; `HELD` “Held”; `ADDED` “Added”; `MIXED` “Different actions at different times”. Optional free text for circumstances. Other: yes.
- Why: contextualizes hypothetical tolerance without judging necessities as psychological weakness. Field: `risk.observed_response`. Dimensions: T; NEEDS_SALE flags a capacity clarification, not a lower tolerance score.
- Dependencies: none. Checks: X04, X05.

#### E05 — Investing philosophy

- Section: Preferences; extended; **optional**. Text: **“Which approaches would you like research and explanations to emphasize?”**
- Type: multiple choice `BROAD_PASSIVE` “Broad diversified/passive”; `VALUE`; `QUALITY`; `GROWTH`; `INCOME`; `MACRO`; `TECHNICAL`; `THEMATIC`; `NO_PREFERENCE`. Other: yes.
- Why: prioritizes research lenses, never proves strategy skill or expected returns. Field: `preferences.styles`. Dimensions: P.
- Dependencies: none. Checks: X07; multiple styles are allowed and not inherently inconsistent.

#### E06 — Available attention

- Section: Preferences; extended; **optional**. Text: **“How much time would you like to spend reviewing investments?”**
- Type: single choice `MONTHLY_SHORT` “A short monthly review”; `WEEKLY_SHORT` “A short weekly review”; `WEEKLY_HOURS` “Several hours each week”; `DAILY` “Most days”; `EVENT_ONLY` “Only when something material changes”. Other: yes.
- Why: calibrates workload separately from desired investment style. Field: `preferences.attention`. Dimensions: P.
- Dependencies: none. Checks: X07.

#### E07 — Asset and market interests

- Section: Preferences; extended; **optional**. Text: **“Which investment areas should we prioritize learning about or researching?”**
- Type: multiple choice of C10 product families excluding NONE, plus `NO_PREFERENCE`; optional searchable countries/regions with `GLOBAL` “Global” or `SELECTED` “Selected markets”. Other: yes.
- Why: relevance ranking, separate from F02 exclusions or actual holdings. Fields: `preferences.asset_interests`, `preferences.market_mode`, `preferences.markets`. Dimensions: P.
- Dependencies: selected markets require country/region names. Checks: X08, X13. Interest in an asset is not permission to own it.

#### E08 — Research priorities

- Section: Preferences; extended; **recommended**. Text: **“Which questions should research answer first for you?”**
- Type: multiple choice, up to three: `BUSINESS_QUALITY`, `VALUATION`, `DOWNSIDE`, `INCOME_SAFETY`, `DIVERSIFICATION`, `FEES`, `CATALYSTS`, `TECHNICAL_TIMING`, `POLICY_FIT`, `LEARNING`. Other: yes.
- Why: ranks bounded research work and opportunity relevance. Field: `preferences.research_priorities`. Dimensions: P.
- Dependencies: none. Checks: X07, X08. Preference never suppresses material risk evidence.

#### E09 — Monitoring topics

- Section: Preferences; extended; **recommended**. Text: **“What would you like PortfolioMind to bring to your attention?”**
- Type: multiple choice `THESIS_CHANGE`, `MATERIAL_DISCLOSURE`, `POLICY_BREACH`, `ALLOCATION_DRIFT`, `GOAL_LIQUIDITY`, `PRICE_MOVE`, `DRAWDOWN`, `RESEARCH_OPPORTUNITY`, or exclusive `NONE` “No proactive investment alerts”. Other: yes.
- Why: personalizes attention without equating volatility with an action. Field: `preferences.monitor_topics`. Dimensions: P.
- Dependencies: PRICE_MOVE/DRAWDOWN offers F04; ALLOCATION_DRIFT requires A01 for a numeric alert; unknown goal details limit GOAL_LIQUIDITY. Checks: X12. Unsupported topics are saved as requested, with “not active” status, never advertised as operational.

#### E10 — Delivery preferences

- Section: Preferences; extended; **optional**. Text: **“How often and where would you like available investment alerts?”**
- Type: single cadence `ON_DEMAND`, `DAILY_DIGEST`, `WEEKLY_DIGEST`, `MATERIAL_ONLY`; multiple channels `IN_APP`, `EMAIL`, `PUSH`, displayed only if implemented; optional local quiet-hours start/end and IANA timezone. Other: yes.
- Why: controls interruptions, not analytical risk. Fields: `preferences.alert_cadence`, `.alert_channels`, `.quiet_hours`. Dimensions: P.
- Dependencies: if no proactive topics, show on-demand summaries only; timezone required to activate quiet hours. Checks: X12. Selecting email here cannot authorize marketing or connect an unconfigured delivery system.

#### E11 — Copilot explanations

- Section: Preferences; extended; **optional**. Text: **“How should Copilot explain its analysis?”**
- Type: single depth `BRIEF`, `STEP_BY_STEP`, `TECHNICAL`; language: searchable supported BCP 47 language tags; stance `EXPLAIN_OPTIONS` “Explain options and trade-offs” or `CHALLENGE` “Also challenge my reasoning”. Other: yes.
- Why: changes presentation, not evidence standards or financial permissions. Fields: `preferences.explanation_depth`, `.language`, `.copilot_stance`. Dimensions: P.
- Dependencies: supported language list is a capability catalogue, not restricted to Turkish/English by investor identity. Checks: none beyond validity.

#### E12 — Desired outcomes

- Section: Goals & Financial Context; extended; **optional**. Text: **“Do you have a return or income expectation you want us to use when discussing this goal?”**
- Type: single choice `NO_TARGET`, `PRESERVE_PURCHASING_POWER`, `ENTER_RETURN`, `ENTER_INCOME`; optional annual return decimal >−100%, with `NOMINAL`/`REAL` and currency; or annual income Money (nonnegative). Other: yes.
- Why: reveals aspiration/constraint tensions; targets are not forecasts. Fields: `goals.items[].expectation` (mode, annual_return_pct, return_basis, currency, annual_income). Dimensions: G, I.
- Dependencies: select goal. Checks: X10. Unclear nominal/real basis leaves numeric interpretation unresolved. No arbitrary return target is required to finish.

### Advanced Investment Policy

#### A01 — Target allocation

- Section: Investment Policy; advanced; **optional**. Text: **“Do you already have a target allocation you want PortfolioMind to compare against?”**
- Type: single choice `NONE` “No target yet”; `ENTER` “Enter my target”; `DRAFT_HELP` “Help me prepare a draft later”. ENTER: repeatable rows of non-overlapping product family/custom bucket with target 0–100% and optional min/max 0–100%; scope ALL or selected GOAL. Other: yes.
- Why: distinguishes user policy from current exposure. Fields: `policy.allocation_mode`, `policy.allocations[]` (scope, goal_id, buckets). Dimensions: I.
- Dependencies: targets within each scope total 100%; custom bucket definitions need review. Checks: X08, X10, X11, X13. No risk-label-to-allocation auto-fill.

#### A02 — Concentration limits

- Section: Investment Policy; advanced; **optional**. Text: **“Which concentration limits, if any, should we compare your investments with?”**
- Type: multiple choice `NO_LIMIT_SET`, `ISSUER`, `SECTOR`, `COUNTRY`, `ASSET_FAMILY`, `ILLIQUID`; for each selected dimension numeric maximum >0–100% and ALL/GOAL scope. Other: yes.
- Why: makes diversification preferences measurable without imposing universal limits. Field: `policy.concentration_limits[]` (dimension, max_pct, scope, goal_id). Dimensions: I.
- Dependencies: denominator is scoped investment market value; issuer/sector look-through unavailable → check unavailable, never “within limit”. Checks: X11.

#### A03 — Leverage stance

- Section: Investment Policy; advanced; **recommended before leverage discussions**. Text: **“What is your policy on borrowing to invest and leveraged products?”**
- Type: single choice `PROHIBITED` “Exclude both”; `CONDITIONAL` “Only for specified purposes and limits”; `CONSIDER` “Open to considering them after review”; `UNDECIDED` “No policy decided”. Other: yes.
- Why: explicitly distinguishes openness from authorization. Field: `policy.leverage_stance`. Dimensions: I.
- Dependencies: CONDITIONAL/CONSIDER → F03. Checks: X03, X05, X08. Unknown stance never implies allowed leverage.

#### A04 — Rebalancing approach

- Section: Investment Policy; advanced; **optional**. Text: **“When would you want to review rebalancing?”**
- Type: multiple choice `CALENDAR`, `DRIFT`, `CONTRIBUTIONS` “Prefer using new contributions/withdrawals”, or exclusive `MANUAL` “Only when I request it”. CALENDAR: `QUARTERLY`, `HALF_YEARLY`, `YEARLY`; DRIFT: >0–100 percentage points from target. Other: yes.
- Why: separates review triggers from automatic transactions. Fields: `policy.rebalance_triggers`, `.rebalance_interval`, `.rebalance_drift_pp`. Dimensions: I.
- Dependencies: numeric drift requires A01; calendar and contributions may coexist. Checks: X07, X12.

#### A05 — Liquidity floor

- Section: Investment Policy; advanced; **optional**. Text: **“Do you want a minimum amount kept readily accessible for these investments?”**
- Type: single choice `NO_RULE` “No separate rule”; `ENTER` “Set a minimum”; ENTER accepts Money or 0–100% of scoped investments, plus access deadline `SAME_DAY`, `WITHIN_WEEK`, `WITHIN_MONTH`. Other: yes.
- Why: separates a chosen policy floor from reported outside emergency reserves. Fields: `policy.liquidity_floor` (mode, size, access, scope, goal_id). Dimensions: I, C.
- Dependencies: F01 overlap explained; a floor may cover a known need, not be automatically added to it. Checks: X01, X09, X11.

#### A06 — Costs, turnover and tax considerations

- Section: Investment Policy; advanced; **optional**. Text: **“Which implementation frictions should analysis consider?”**
- Type: multiple choice `NO_RULE`, `LOW_FEES`, `LOW_TURNOVER`, `TAX_REVIEW` “Review tax implications before suggesting changes”, `ACCESS_LIMITS`, `CURRENCY_CONVERSION`; optional text describing a specific rule. Other: yes.
- Why: prevents naive rebalancing interpretations ignoring frictions. Fields: `policy.implementation_priorities`, `policy.implementation_note`. Dimensions: I.
- Dependencies: TAX_REVIEW may offer E01 but does not demand tax returns. Checks: X07, X13; no tax calculation from questionnaire alone.

#### A07 — Review schedule

- Section: Investment Policy; advanced; **optional**. Text: **“When should we ask whether this profile and policy still fit?”**
- Type: single choice `SIX_MONTHS`, `YEARLY`, `ON_REQUEST`; multiple event triggers `GOAL_CHANGE`, `INCOME_CHANGE`, `MAJOR_WITHDRAWAL`, `LIFE_CHANGE`. Other: yes.
- Why: keeps profile current without interpreting market price moves as changes in investor personality. Fields: `policy.review_cadence`, `policy.review_events`. Dimensions: I.
- Dependencies: future reminder activation is separate from saving a preference. Checks: none beyond validity.

#### A08 — Success benchmark

- Section: Investment Policy; advanced; **optional**. Text: **“How would you like to judge progress?”**
- Type: multiple choice `GOAL_PROGRESS`, `PURCHASING_POWER`, `INCOME_RELIABILITY`, `POLICY_ADHERENCE`, `BENCHMARK`; BENCHMARK requires user-selected existing index/reference and comparison currency. Other: yes.
- Why: sets evaluation context without assuming index outperformance is everyone's objective. Fields: `policy.success_measures`, `policy.benchmark_reference`, `policy.benchmark_currency`. Dimensions: I, G.
- Dependencies: comparison requires compatible data/currency/period. Checks: X10, X13. Missing history or unknown import cost basis remains a Portfolio analytics limitation.

### Exact display labels for compact option lists

Where cards above list a code without a quoted label, use the following copy. Stable codes are never displayed as technical identifiers in the questionnaire. Reused choices inherit the originating card's wording; numeric entry shows unit, currency and scope next to the input.

| Question(s) | Code → user-facing answer copy |
| --- | --- |
| F01 | ONCE → “Once”; MONTHLY → “Every month”; QUARTERLY → “Every three months”; YEARLY → “Every year” |
| F02 | EXCLUDE → “Exclude it”; LIMIT → “Keep it below a limit”; REQUIRE_REVIEW → “Discuss it with me before suggesting it” |
| F04 | DAY → “One day”; WEEK → “One week”; MONTH → “One month”; SINCE_REVIEW → “Since my last review”; UP → “Up”; DOWN → “Down”; EITHER → “Either direction” |
| E02 | ESSENTIAL → “Essential”; IMPORTANT → “Important”; ASPIRATIONAL → “Nice to achieve” |
| E03 | NONE → “No known change”; INCOME_CHANGE → “Income changing”; RETIREMENT → “Retirement”; LARGE_EXPENSE → “A major expense”; RELOCATION → “Moving country or home”; SUPPORT_COMMITMENT → “A new financial support commitment” |
| E05 | VALUE → “Value investing”; QUALITY → “Business quality”; GROWTH → “Growth investing”; INCOME → “Investment income”; MACRO → “Economic trends”; TECHNICAL → “Price and technical analysis”; THEMATIC → “Investment themes”; NO_PREFERENCE → “No preference yet” |
| E07 | NO_PREFERENCE → “No particular asset preference”; GLOBAL → “Global”; SELECTED → “Selected markets” |
| E08 | BUSINESS_QUALITY → “Business quality”; VALUATION → “Valuation”; DOWNSIDE → “What could go wrong”; INCOME_SAFETY → “Reliability of investment income”; DIVERSIFICATION → “Diversification”; FEES → “Fees and costs”; CATALYSTS → “Events that could change the outlook”; TECHNICAL_TIMING → “Price-based timing”; POLICY_FIT → “Fit with my policy”; LEARNING → “Understanding the investment” |
| E09 | THESIS_CHANGE → “Changes to the investment case”; MATERIAL_DISCLOSURE → “Important company or fund disclosures”; POLICY_BREACH → “An investment outside my policy”; ALLOCATION_DRIFT → “Allocation moving away from my target”; GOAL_LIQUIDITY → “Money needed for my goals”; PRICE_MOVE → “Price changes”; DRAWDOWN → “Falls from previous highs”; RESEARCH_OPPORTUNITY → “Ideas relevant to my research interests” |
| E10 | ON_DEMAND → “Only when I ask”; DAILY_DIGEST → “A daily digest”; WEEKLY_DIGEST → “A weekly digest”; MATERIAL_ONLY → “When something material changes”; IN_APP → “In the app”; EMAIL → “Email”; PUSH → “Push notification” |
| E11 | BRIEF → “Brief”; STEP_BY_STEP → “Step by step”; TECHNICAL → “Technical detail” |
| E12 | NO_TARGET → “No return or income target”; PRESERVE_PURCHASING_POWER → “Keep up with inflation”; ENTER_RETURN → “Enter an annual return aspiration”; ENTER_INCOME → “Enter an annual income goal”; NOMINAL → “Before adjusting for inflation”; REAL → “After adjusting for inflation” |
| A02 | NO_LIMIT_SET → “No concentration limits set”; ISSUER → “One issuer”; SECTOR → “One sector”; COUNTRY → “One country”; ASSET_FAMILY → “One asset class”; ILLIQUID → “Investments that are hard to sell” |
| A04 | CALENDAR → “At regular review dates”; DRIFT → “When allocation moves away from target”; QUARTERLY → “Every three months”; HALF_YEARLY → “Every six months”; YEARLY → “Every year” |
| A05 | SAME_DAY → “The same day”; WITHIN_WEEK → “Within one week”; WITHIN_MONTH → “Within one month” |
| A06 | NO_RULE → “No particular rule”; LOW_FEES → “Keep fees low”; LOW_TURNOVER → “Avoid frequent trading”; ACCESS_LIMITS → “Consider account or product access limits”; CURRENCY_CONVERSION → “Consider currency conversion costs” |
| A07 | SIX_MONTHS → “Every six months”; YEARLY → “Every year”; ON_REQUEST → “Only when I ask”; GOAL_CHANGE → “When my goals change”; INCOME_CHANGE → “When my income changes”; MAJOR_WITHDRAWAL → “When I plan a major withdrawal”; LIFE_CHANGE → “When I report a major life change” |
| A08 | GOAL_PROGRESS → “Progress toward my goals”; PURCHASING_POWER → “Maintaining purchasing power”; INCOME_RELIABILITY → “Reliable investment income”; POLICY_ADHERENCE → “Staying within my policy”; BENCHMARK → “Comparison with a benchmark I choose” |

All remaining custom categorical answers use the same “Other / My answer” copy and envelope rules. A custom answer that does not fit a supported operational enum remains a reviewed narrative constraint/preference, with machine enforcement explicitly unavailable.

## 4. Structured Investor Profile contract

This is a logical data dictionary, not a database migration or API commitment. One user-facing profile can be stored across separately versioned records internally.

```text
InvestorProfile (owned by User)
├── goals: GoalsAndContext
│   ├── items[]: goal-specific timing, consequence, priority and expectations
│   ├── withdrawals[]: stated future needs, not ledger movements
│   └── resilience/context answers
├── risk: RiskProfile (stated tolerance evidence + derived dimensions)
├── policy: InvestmentPolicy (intentions and reviewed rules)
├── preferences: InvestorPreferences (experience, approach, research, delivery)
└── metadata: raw answers, provenance, confirmations, versions, completeness

Portfolio domain ── current facts ──► comparison/analysis ◄── confirmed profile
```

### Common types and metadata rules

- `Money = {amount, currency}`: `amount` is a nonnegative DECIMAL(18,6), serialized as a decimal string; `currency` is ISO 4217. No binary floating point for money. Amount is explicit, currency must be supplied or explicitly accepted, never silently borrowed from TRY account defaults.
- `Size = {mode, amount, currency, percentage}`: mode `AMOUNT`/`PERCENT`/`UNKNOWN`. AMOUNT uses Money fields; PERCENT uses decimal 0–100 and means a share of investments covered by the chosen scope **as stated at answer time**, not a stored live balance. Inactive members are null. Percentage and amount are alternative representations, not additive.
- For a future withdrawal, preserve the percentage's answer-time basis; do not silently turn “half of today's investments” into half of a later balance. If a historical denominator was never available, the corresponding monetary amount remains unknown. Policy percentages (allocation targets, caps and floors) instead describe ongoing shares of the stated scope; previews explicitly identify this difference. Zero/negative portfolio denominator makes percentage comparisons unavailable.
- `Scope = {scope, goal_id}`: scope `ALL`/`GOAL`; goal_id required only for GOAL and must belong to this profile. Goals do not partition actual holdings unless a separate future portfolio mapping exists. No per-goal exposure assertion without that mapping.
- Product-family options are the C10 taxonomy, not the ORM AssetType enum. In this checkout PRECIOUS_METALS, not GOLD, is the actual asset enum; cash is separate; funds may wrap bonds/equities. Future allocation analysis needs an explicit classification adapter and non-overlapping buckets. Do not modify AssetType as part of this design.
- Optional date is `{value, precision}` with ISO `YYYY-MM`/`YYYY-MM-DD` and precision `MONTH`/`DAY`. Bands are never silently converted to exact dates or midpoints.
- Arrays use stable item IDs (system-generated UUID) to preserve history across edits. “No items” is only authoritative after explicit NONE; an unanswered array is null, not `[]`.

Every substantive leaf is a `ProfileValue<T>` with the following envelope. The tables below inherit these rules so that every leaf has source, confidence, missingness and history semantics:

| Envelope field | Meaning / type / allowed values | Source; unknown; history |
| --- | --- | --- |
| `value` | Typed value from the dictionary below, or null | Explicit or interpreted as marked; may be unknown; history according to V/P/D below |
| `knowledge_state` | `KNOWN`, `UNKNOWN`, `NOT_ASKED`, `SKIPPED`, `DECLINED`, `NOT_APPLICABLE` | Explicit controls or deterministic session state; never null; preserved with answer revision |
| `source_kind` | `EXPLICIT`, `AI_INTERPRETED`, `CALCULATED` | Deterministically records origin; never null; immutable per revision |
| `answer_refs` | UUID[] pointing to preserved answer records; empty for system-only values | Calculated; never null; immutable per revision |
| `confidence` | `HIGH`, `MEDIUM`, `LOW`, `UNASSESSED`; confidence in interpretation, not honesty or predictive accuracy | Exact mapping HIGH; ambiguous AI LOW/UNASSESSED; derived per §5; never null |
| `review_state` | `DRAFT`, `NEEDS_REVIEW`, `CONFIRMED`, `REJECTED` | Explicit confirmation or calculated lifecycle; never null; logged |
| `confirmed_at` | UTC timestamp or null | Calculated from explicit confirmation; unknown before approval; immutable |
| `as_of` | Time the answer describes, UTC timestamp (default answer time disclosed) | Explicit if user supplies earlier date, otherwise calculated; never null for known answer |
| `freshness` | `CURRENT`, `REVIEW_DUE`, `STALE`, `UNKNOWN` | Calculated using §9; unknown permitted as enum; derived evaluation history |
| `interpretation_reason` | Optional short text with quote/span references; no hidden chain of thought | AI_INTERPRETED or CALCULATED explanation; may be null; retained with interpretation |

Source codes in the following tables: **E/A** = direct explicit selections/numbers, or an AI interpretation of supplied text awaiting user review. AI may propose only supported values; confirmation keeps the AI origin. **D** = deterministic derivation. History codes: **V** = confirmed change creates next material profile version; **P** = explicit save creates a lightweight preference revision; **D** = derived evaluation revision pinned to source version/ruleset, not a new user answer. All substantive E/A fields permit unknown; no defaulting unknown to a favorable or adverse answer. Rule prerequisites distinguish not applicable from unknown.

### GoalsAndContext fields

| Field under `goals` | Meaning and type | Allowed values / constraints | Source; history |
| --- | --- | --- | --- |
| `items[].id` | Stable goal UUID | Generated; cannot be unknown | D; V |
| `items[].kind` | Goal purpose enum | C01 options including OTHER | E/A; V |
| `items[].horizon` | First need timing enum | C02 horizon options + OTHER | E/A; V |
| `items[].target_date` | Optional exact first-need date | Date type above; reconciled with horizon | E/A; V |
| `items[].flexibility` | Ability to postpone/reduce enum | C02 flexibility + OTHER | E/A; V |
| `items[].priority` | Goal importance enum | E02: ESSENTIAL/IMPORTANT/ASPIRATIONAL + OTHER | E/A; V |
| `items[].target_size` | Desired goal amount/share | Size; not current holdings | E/A; V |
| `items[].loss_consequence` | Impact of permanent 20% loss enum | C07 options + OTHER | E/A; V |
| `items[].expectation.mode` | Desired outcome enum | E12 modes + OTHER | E/A; V |
| `items[].expectation.annual_return_pct` | Annual desired return decimal | >−100; not forecast; null unless ENTER_RETURN | E/A; V |
| `items[].expectation.return_basis` | Return basis enum | NOMINAL/REAL | E/A; V |
| `items[].expectation.currency` | Return purchasing/comparison currency | ISO 4217 | E/A; V |
| `items[].expectation.annual_income` | Desired annual income | Money; null unless ENTER_INCOME | E/A; V |
| `withdrawal_pattern` | Expected three-year withdrawals enum | C03 options + OTHER | E/A; V |
| `withdrawals[].id` | Stable need UUID | Generated; cannot be unknown | D; V |
| `withdrawals[].goal_id` | Optional goal link | Owned goal UUID or null; no duplicate goal obligation | E/A; V |
| `withdrawals[].timing_band` | First withdrawal timing enum | NOW/LT_12M/M12_36/GE_36M/OTHER | E/A; V |
| `withdrawals[].date` | Optional exact first need | Date type above | E/A; V |
| `withdrawals[].size` | Size of each occurrence | Size; percentage denominator fixed at answer time | E/A; V |
| `withdrawals[].recurrence` | Frequency enum | ONCE/MONTHLY/QUARTERLY/YEARLY/OTHER | E/A; V |
| `withdrawals[].end_date` | Last recurring need date | Date or null (end unknown, not infinite) | E/A; V |
| `withdrawals[].coverage` | Funding source enum | INVESTMENTS/OUTSIDE/PARTIAL/UNKNOWN | E/A; V |
| `withdrawals[].uncovered_size` | Portion still funded by investments | Size; only PARTIAL; same unit/currency as total before comparison | E/A; V |
| `reserve_months_band` | Outside accessible buffer enum | C04 options + OTHER | E/A; V |
| `cashflow` | Ordinary cash-flow balance enum | C05 cash-flow options + OTHER | E/A; V |
| `income_reliability` | Income continuity enum | C05 reliability options + OTHER | E/A; V |
| `obligation_pressure` | Required payment burden enum | C06 options + OTHER | E/A; V |
| `expected_changes[].kind` | Known change category enum | E03 except NONE, plus OTHER; NONE gives confirmed empty list | E/A; V |
| `expected_changes[].timing` | Change horizon enum | LT_1Y/Y1_3/LATER/OTHER | E/A; V |
| `expected_changes[].note` | Optional user explanation text | Up to 2,000 characters | E/A; V |
| `spending_currencies` | Expected spending currency set | ISO 4217[] | E/A; V |
| `jurisdiction_mode` | Whether specific context is requested | NONE/SUPPLY/OTHER | E/A; V |
| `jurisdictions` | Countries relevant to requested context | ISO 3166-1 alpha-2[]; no inferred residence | E/A; V |
| `jurisdiction_note` | Optional cross-border context | Text up to 2,000 characters | E/A; V |

### RiskProfile fields

| Field under `risk` | Meaning and type | Allowed values | Source; history |
| --- | --- | --- | --- |
| `drawdown_comfort` | Stated psychological loss threshold enum | C08 + OTHER | E/A; V |
| `custom_drawdown_pct` | Custom stated threshold decimal | 0–100; only custom input | E/A; V |
| `stress_response` | Hypothetical behavior enum | C09 + OTHER | E/A; V |
| `observed_response` | Past self-reported downturn behavior enum | E04 + OTHER | E/A; V |
| `tolerance_summary` | Psychological summary enum | LOW/MODERATE/HIGH/MIXED/UNKNOWN | D; D |
| `capacity_by_goal[].goal_id` | Goal evaluated | Owned goal UUID; cannot be unknown | D; D |
| `capacity_by_goal[].status` | Capacity constraints enum | CONSTRAINED/CONDITIONAL/LESS_CONSTRAINED/UNKNOWN | D; D |
| `capacity_by_goal[].reason_codes` | Applicable rule/prerequisite IDs | Ordered string[] from §5/§6; never null | D; D |
| `capacity_by_goal[].affected_size` | Capital to which constraint applies | Referenced withdrawal Size, otherwise unknown; not inferred remainder | D; D |
| `liquidity_summary` | Withdrawal requirements enum | NONE_PLANNED/KNOWN_NEEDS/UNQUANTIFIED_NEEDS/UNKNOWN | D; D |
| `resilience_summary` | Buffer/continuity summary enum | VULNERABLE/BUFFERED/MIXED/UNKNOWN | D; D |
| `horizon_by_goal` | Goal IDs + recorded horizon/date view | No averaged horizon; unknown goal timing preserved | D; D |

Do not ship a global conservative/balanced/growth/aggressive badge in initial Phase 4. “High stated tolerance; capacity constrained for the home goal” is more useful. Optional future labels must be reversible summaries with visible contributing dimensions, never stored as authoritative risk inputs.

### InvestmentPolicy fields

| Field under `policy` | Meaning and type | Allowed values / constraints | Source; history |
| --- | --- | --- | --- |
| `restriction_topics` | Topics the user wishes to restrict | C12 set incl OTHER; NONE gives confirmed empty set | E/A; V |
| `constraints[].scope`, `.goal_id` | Applicability | Scope type; goal-specific constraint does not automatically cover unrelated goals | E/A; V |
| `constraints[].topic` | Restriction category | C12 non-NONE topic | E/A; V |
| `constraints[].subject` | Exact thing to exclude/limit/review | Text up to 2,000; named taxonomy/reference where available; unresolved text not executable | E/A; V |
| `constraints[].strength` | Firm constraint or preference | HARD/SOFT | E/A; V |
| `constraints[].rule` | Desired restriction | EXCLUDE/LIMIT/REQUIRE_REVIEW | E/A; V |
| `constraints[].max_pct` | Limit within scoped investment value | Decimal 0–100; only LIMIT | E/A; V |
| `allocation_mode` | Whether user has a target | NONE/ENTER/DRAFT_HELP/OTHER | E/A; V |
| `allocations[].scope`, `.goal_id` | Target applicability | Scope type | E/A; V |
| `allocations[].buckets[].family` | Non-overlapping allocation bucket | C10 family/custom identifier with reviewed definition | E/A; V |
| `allocations[].buckets[].definition` | Explicit inclusion boundaries | Text, required for custom/ambiguous classifications | E/A; V |
| `allocations[].buckets[].target_pct` | Desired share decimal | 0–100; per-scope sum exactly 100 | E/A; V |
| `allocations[].buckets[].min_pct`, `.max_pct` | Optional tolerated bounds decimals | 0 ≤ min ≤ target ≤ max ≤ 100; feasible combined bounds | E/A; V |
| `concentration_limits[].dimension` | Exposure aggregation | A02 except NO_LIMIT_SET, plus OTHER | E/A; V |
| `concentration_limits[].max_pct` | Largest allowed share decimal | >0–100 | E/A; V |
| `concentration_limits[].scope`, `.goal_id` | Denominator scope | Scope type | E/A; V |
| `leverage_stance` | Consideration policy enum | A03 options + OTHER | E/A; V |
| `leverage_uses` | Purposes under consideration | F03 set + OTHER | E/A; V |
| `gross_exposure_limit_pct` | Gross exposure / net equity cap decimal | 100–1,000; undefined if net equity ≤0; never permission to trade | E/A; V |
| `rebalance_triggers` | Conditions to review rebalancing | A04 set + OTHER; MANUAL exclusive | E/A; V |
| `rebalance_interval` | Calendar frequency | QUARTERLY/HALF_YEARLY/YEARLY | E/A; V |
| `rebalance_drift_pp` | Absolute target drift decimal | >0–100 percentage points, not relative percent | E/A; V |
| `liquidity_floor.mode` | Whether rule exists | NO_RULE/ENTER/OTHER | E/A; V |
| `liquidity_floor.size` | Minimum accessible amount/share | Size | E/A; V |
| `liquidity_floor.access` | Availability deadline enum | SAME_DAY/WITHIN_WEEK/WITHIN_MONTH | E/A; V |
| `liquidity_floor.scope`, `.goal_id` | Rule applicability | Scope type | E/A; V |
| `implementation_priorities` | Frictions to consider | A06 set + OTHER; NO_RULE exclusive | E/A; V |
| `implementation_note` | Specific user rule | Text up to 2,000 | E/A; V |
| `review_cadence` | Profile reassessment preference | SIX_MONTHS/YEARLY/ON_REQUEST/OTHER | E/A; V |
| `review_events` | Requested event triggers | A07 set + OTHER | E/A; V |
| `success_measures` | Preferred evaluation axes | A08 set + OTHER | E/A; V |
| `benchmark_reference` | Named reference, not invented data | Existing benchmark ID or unresolved text | E/A; V |
| `benchmark_currency` | Comparison currency | ISO 4217 | E/A; V |

### Preferences fields

| Field under `preferences` | Meaning and type | Allowed values / constraints | Source; history |
| --- | --- | --- | --- |
| `experience[].family` | Product family | C10 except NONE, plus OTHER | E/A; V |
| `experience[].level` | Self-assessed familiarity | LEARNING/USED_BASIC/UNDERSTAND | E/A; V |
| `involvement` | Desired decision activity | C11 + OTHER | E/A; P |
| `styles` | Research approaches | E05 set + OTHER | E/A; P |
| `attention` | Desired time commitment | E06 + OTHER | E/A; P |
| `asset_interests` | Areas for research | E07 set + OTHER | E/A; P |
| `market_mode` | Market preference | GLOBAL/SELECTED/OTHER | E/A; P |
| `markets` | Research regions | Country codes or explicit region names | E/A; P |
| `research_priorities` | Up to three research lenses | E08 set + OTHER | E/A; P |
| `monitor_topics` | Requested monitoring subjects | E09 set + OTHER | E/A; P |
| `custom_alerts[].metric` | Trigger kind | DRAWDOWN/PRICE_MOVE/ALLOCATION_DRIFT/OTHER | E/A; P |
| `custom_alerts[].threshold` | Trigger magnitude decimal | F04 bounds; cannot activate without valid unit | E/A; P |
| `custom_alerts[].unit` | Trigger unit | PERCENT/PERCENTAGE_POINTS | D from selected metric; P |
| `custom_alerts[].window` | Observation window | DAY/WEEK/MONTH/SINCE_REVIEW | E/A; P |
| `custom_alerts[].direction` | Price direction | UP/DOWN/EITHER; null for other metrics | E/A; P |
| `custom_alerts[].scope` | Alert target enum | ALL/GOAL/INSTRUMENT | E/A; P |
| `custom_alerts[].goal_id`, `.instrument_id` | Target references | Applicable owned goal or accessible canonical instrument UUID; others null | E/A; P |
| `alert_cadence` | Interruption frequency | E10 cadence + OTHER | E/A; P |
| `alert_channels` | Requested available channels | Capability-filtered subset of IN_APP/EMAIL/PUSH | E/A; P |
| `quiet_hours.start`, `.end` | Local wall-clock times | HH:mm 24-hour format; overnight ranges allowed | E/A; P |
| `quiet_hours.timezone` | Time interpretation | IANA timezone; required for activation | E/A; P |
| `explanation_depth` | Answer detail | BRIEF/STEP_BY_STEP/TECHNICAL/OTHER | E/A; P |
| `language` | Explanation language | Supported BCP 47 tag or unresolved custom request | E/A; P |
| `copilot_stance` | Explanation/challenge style | EXPLAIN_OPTIONS/CHALLENGE/OTHER | E/A; P |

Experience is intentionally V despite living under Preferences: changing claimed product understanding can affect decision support. Any preference edit that changes a hard constraint, financial trigger rule or policy threshold becomes V. E09/F04 delivery alerts alone remain P, and cannot modify a policy limit of the same name.

### Record, answer and evaluation metadata

All system-generated fields below are CALCULATED, exact bookkeeping (confidence not applicable), non-null unless marked, and retained in their respective record history. User text/controls are EXPLICIT; AI output is AI_INTERPRETED. No hidden additional business fields are implied by these containers.

| Record / fields | Types, allowed values and purpose | Version behavior |
| --- | --- | --- |
| Profile identity: `id`, `user_id` | UUID; stable profile ID and authenticated owner; never supplied by AI | Immutable |
| Profile lifecycle: `active_version_id`, `active_preferences_revision_id` | UUID or null before confirmation | Pointers updated only by explicit save/confirm |
| Assessment: `id`, `user_id`, `base_version_id`, `questionnaire_version`, `status`, `resume_question_id`, `created_at`, `updated_at` | UUIDs; base nullable; version string; status DRAFT/READY/CONFIRMED/POSTPONED/DISCARDED; resume nullable; UTC timestamps | Draft autosave revisions, not material versions |
| Answer: `id`, `assessment_id`, `question_id`, `item_id`, `selected_options`, `numeric_inputs`, `raw_text`, `locale`, `answered_at`, `knowledge_state` | UUIDs (item nullable), stable Q ID, option-code array, typed decimals/Money/Date, exact original text nullable, BCP 47, UTC, envelope missing-state enum | Append answer revisions; never overwrite original text with normalized text |
| Interpretation: `id`, `answer_ids`, `proposed_fields`, `evidence_spans`, `alternatives`, `confidence`, `provider_model`, `prompt_version`, `created_at`, `review_state` | UUID, UUID[], typed field-path/value map, exact quoted spans/offsets, alternative value/reason list, confidence enum, strings, UTC, envelope review enum | New interpretation revision; optional AI failure leaves no interpretation rather than fabricated output |
| Material version: `id`, `sequence`, `previous_version_id`, `snapshot`, `confirmed_by`, `confirmed_at`, `change_reason`, `questionnaire_version` | UUID; positive integer; nullable previous; typed profile snapshot with source refs; owning user UUID; UTC; user text/system action descriptor; version string | Append on confirmation; immutable historical snapshot |
| Preference revision: `id`, `previous_revision_id`, `snapshot`, `saved_by`, `saved_at` | UUID, nullable UUID, typed preference snapshot, owning user UUID, UTC | Append on explicit save; retain pair with material version in analyses |
| Evaluation: `id`, `profile_version_id`, `preferences_revision_id`, `ruleset_version`, `evaluated_at`, `dimensions`, `completeness`, `issues`, `summary` | UUIDs (source nullable for draft); string; UTC; typed §5 dimensions; §7 values; issue records below; optional evidence-grounded text | Separate D history; summary AI-interpreted or deterministic fallback; never authoritative over fields |
| Issue: `id`, `rule_id`, `field_paths`, `severity`, `state`, `explanation`, `resolution_answer_ids` | UUID, X01–X13 or validation rule ID, string[], VALIDATION/CONFLICT/CLARIFY/LIMITATION, OPEN/ACKNOWLEDGED/RESOLVED, short text, UUID[] | Append resolution events; acknowledging does not erase the condition |
| Completeness: `overall_pct`, `domains`, `capability_status`, `missing_field_paths` | Decimal 0–100; keyed percentages from §7; keyed SUPPORTED/LIMITED/UNAVAILABLE; string[] | Recomputed D evaluation, not a user fact |

Question/option labels are stored with questionnaire version for later reproduction. Notes and OTHER text remain available through Answer records; a typed OTHER enum must link to its raw answer and cannot be treated as an operational policy rule without resolution. Confirming an answer as unknown is valid and distinct from confirming an inferred value.

## 5. Interpretation: separate dimensions, explicit interactions

The deterministic rules engine maps options, validates quantities and derives bounded dimensions; AI does not score the investor. Every derived result includes rule IDs, contributing answer IDs, missing prerequisites and confidence. No additive 1–5 risk score, age score, wealth score or score based on current holdings.

### Psychological tolerance

1. Map C08 NONE/P5 → LOW, P10/P20 → MODERATE, P30/P40_PLUS → HIGH. Reviewed custom numbers use ≤5, >5 to ≤20, >20 respectively. Preserve the exact threshold alongside the coarse label; the thresholds are provisional wording aids, not instrument risk classes.
2. C09 EXIT/REDUCE supplies a lower-comfort signal; HOLD/ADD_IF_FUNDED supplies a higher-comfort signal; REVIEW is neutral. It cannot raise C08's category.
3. If HIGH from C08 conflicts with EXIT/REDUCE, or LOW conflicts with HOLD/ADD_IF_FUNDED at the 20% scenario, return MIXED and X04. MODERATE with either reaction is not automatically contradictory. No C08 → UNKNOWN, even if C09 is answered.
4. C08 alone yields at most MEDIUM interpretation confidence. Clear C08 plus coherent C09 may yield HIGH confidence in interpreting the user's current report. E04 can add context but never prove future behavior. A mismatch with prior behavior prompts clarification; legitimate changed circumstances may resolve it.
5. A skipped C09 does not secretly default to “hold”. No confidence increase because a user chooses the largest loss or claims extensive experience.

### Capacity, liquidity and resilience

Capacity is evaluated per goal and associated capital, never averaged across goals. Evaluate known adverse facts first, even if other data is missing; unknowns must not suppress a known constraint.

| Rule | Condition | Derived result and limit |
| --- | --- | --- |
| CAP1 | C07 ESSENTIALS or GOAL_UNAFFORDABLE | CONSTRAINED for that goal; cite financial consequence. Missing reserve data still shown. |
| CAP2 | Fixed goal need within 36 months with nonzero investment-funded withdrawal | CONSTRAINED for the linked amount/share; no implied judgment about unassigned remainder. Approximate horizon bands spanning the boundary yield CONDITIONAL unless an exact date resolves it. |
| CAP3 | C06 ARREARS; or C05 DEFICIT with C04 below 3 months | CONSTRAINED for exposed investment capital; financial resilience VULNERABLE. Scope may be uncertain, which is explicitly reported. |
| CAP4 | C04 at least 6 months, C05 SURPLUS + RELIABLE, C06 NONE/MANAGEABLE | Resilience BUFFERED. Capacity still depends on goal timing, withdrawals and loss consequences. |
| CAP5 | Goal horizon ≥5 years, flexible/some flexibility, C07 ADJUST_GOAL/LITTLE_EFFECT, no uncovered needs in next 36 months, and CAP4 | LESS_CONSTRAINED for that goal; means fewer reported constraints, not capacity for any specific loss or product. |
| CAP6 | Required goal horizon, flexibility, C03/F01, C04, both C05 parts, C06 or C07 absent and no known hard constraint | UNKNOWN; list missing items. Sufficient but conflicting/middle-case evidence → CONDITIONAL. |

A fixed 18-month home purchase requiring half the portfolio plus 40% stated drawdown comfort produces **HIGH tolerance + CONSTRAINED capacity for the home-purchase capital**. Do not label the whole investor aggressive or automatically assign the other half to risky assets. Other goals, outside reserves and overlapping needs still matter.

Resilience output is VULNERABLE under CAP3, BUFFERED under CAP4, UNKNOWN if inputs needed for either assessment are missing without a known vulnerability, otherwise MIXED. NO_OUTSIDE_INCOME is not itself vulnerability: sufficient outside reserves and carefully described withdrawals may support a coherent retirement plan, but the simplified model can remain CONDITIONAL. Avoid inventing a safe withdrawal rate or using salary status as a proxy for means.

Liquidity output: C03 NONE → NONE_PLANNED for the stated three-year period; affirmative withdrawals with known timing/size/coverage → KNOWN_NEEDS; any affirmative but missing size/timing/coverage → UNQUANTIFIED_NEEDS; skipped C03 → UNKNOWN. No planned withdrawal does not establish the liquidity of actual holdings.

For recurrent withdrawals, show the recurrence and computable dated occurrences; if the end date is unknown, calculate only a disclosed finite analysis window. Convert to percentage only in a separately timestamped analysis with current Portfolio data and an explicit denominator. No live denominator at onboarding → amount retained, share unknown. No double counting linked goal target and withdrawal, overlapping needs, or outside reserves. If overlap is unclear, do not sum silently.

Capacity confidence is separate from status. HIGH means required inputs are explicit, current and internally coherent for this limited qualitative classification; it is still self-reported. MEDIUM means ranges/partial coverage limit precision; LOW means unresolved conflict or AI ambiguity. Missing evidence may leave status UNKNOWN while exact interpretation of individual answers remains HIGH confidence.

### Other dimensions and downstream use

| Dimension | Preserve separately | How it changes product behavior |
| --- | --- | --- |
| Goals/horizons | Goal-specific purpose, priority, dates/flexibility | Research and portfolio-fit discussion prioritize the relevant goal; no single averaged horizon. |
| Experience | Product-family familiarity | Explain unfamiliar mechanics; do not assume diversification, leverage knowledge or suitability from years investing. |
| Activity/attention | C11 and E06, independent of tolerance | Adjust research workload and review presentation; activity is not a risk multiplier. |
| Policy | Explicit rules with scope and confirmation | Compare intended vs actual only where portfolio classifications and scope are observable. Violations are findings, not orders. |
| Preferences | Interests, research lenses and alerts | Rank opportunities within confirmed hard constraints; unknown fit is displayed, not inferred positive relevance. |

Tension is not solved by choosing the largest or smallest score. Low capacity plus high tolerance limits the applicable risk discussion. Low tolerance plus buffered finances does not justify pushing risk upward. Hard exclusions constrain relevance; soft preferences rank alternatives. Allocation targets are user intent, not evidence that the target fits capacity. Actual concentrated holdings cannot teach the system that concentration is desired.

## 6. Contradiction and consistency rules

“Conflict” means information needs reconciliation or an intention has a trade-off; it does not mean the user is wrong. AI may suggest additional issues with quotes, but only deterministic validations or reviewed issues affect machine capability status. It may not silently resolve explicit answers.

| ID | Trigger across answers | Response / consequence |
| --- | --- | --- |
| X01 | High C08 tolerance or growth target with near-term fixed C02/F01 need or C07 severe consequences | Show tolerance/capacity separately and affected capital. Capacity constraints remain even if acknowledged. Offer goal clarification; do not alter goals or tolerance. |
| X02 | Percentages >100, negative amounts, end before start, recurrence without unit, incompatible date and band, or incompatible scopes | VALIDATION for affected field/rule. Permit saving rest with invalid input retained as unconfirmed raw text. Percent totals for sequential needs require common denominator/overlap clarification before calling a contradiction. |
| X03 | Low reserve, deficit/at-risk cash flow, arrears, or impending commitments alongside LITTLE_EFFECT or requested leverage | Explain financial-resilience concern and ask whether outside resources were omitted. Never assume extra wealth or force disclosure. |
| X04 | C08/C09 conflict per §5; E04 discomfort sale inconsistent with current high comfort | Show both reports and context. User may explain changed circumstances; keep history. An unexplained mismatch leaves tolerance MIXED. |
| X05 | Limited product understanding or no downturn experience with leverage/complex-product interest or very high stated comfort | Education/clarification, not automatically lower tolerance or reject the investor. No recommendation of complex products from this questionnaire alone. |
| X06 | Regular-income goal/ONGOING timing/no outside income with C03 NONE; fixed near-term goal but no withdrawal shown | Ask whether needs are funded elsewhere. May be coherent. Unresolved funding link → limited liquidity/fit analysis. |
| X07 | Low attention/maintenance with frequent tactical timing, active review or turnover-heavy policy; contribution-only preference but no surplus | Workflow tension; show workload/friction implications. Offer changes, never rewrite philosophy or contributions. |
| X08 | C12/F02 hard exclusion conflicts with E07 interest, A01 target or A03 leverage stance | Distinguish learning interest from intended ownership. Exclusion continues to filter ownership ideas until changed explicitly. Conflicting draft policy rules remain inactive until resolved or omitted. |
| X09 | Same reserve/goal capital counted twice; F01 outside coverage exceeds need; liquidity floor assumed to be additive to linked withdrawal | Ask which need/resource overlaps. Avoid aggregation until clarified. No asset/balance creation from reserve bands. |
| X10 | No-loss comfort with return aspiration; high return with fixed near-term goal; percent vs percentage-point ambiguity; stop-loss implied by alert | Surface trade-offs/units. Never promise returns or invent a feasible portfolio. Invalid unit blocks that rule; aspirations may remain recorded as aspirations. |
| X11 | Allocation totals not 100; overlapping buckets; min > target > max; sum(min)>100 or sum(max)<100; hard cap/exclusion conflicts with target | Validate per scope; reject activation of conflicting policy, preserve draft. Holdings breaching valid limits are an analysis finding, not a reason to rewrite the policy. |
| X12 | Drift alert without target, custom alert without threshold/window, quiet hours without timezone, channel/monitor unavailable, E09 NONE with proactive delivery | Keep requested preference; show pending prerequisite/unavailable activation. Do not silently enable automation or invent monitoring coverage. |
| X13 | Spending/goal/benchmark currency differs from assets, access restrictions conflict with selected markets, tax context insufficient | Mark currency/access uncertainty and seek relevant context. Currency mismatch is exposure to analyze, not automatically an error. No inferred tax residency. |

Each issue card says: what answers triggered it, why it matters, affected capability, and choices **“Edit answer”**, **“Explain”**, **“Keep both; show this limitation”**, **“Leave unresolved”**. Invalid or incompatible operational policy cannot be activated by “keep both”; it stays draft or is excluded from the confirmation. Users can still confirm the valid remainder or go to the dashboard. Missing knowledge never blocks account access.

## 7. Meaningful completeness and capability confidence

Display **“Investor Profile — 65% information coverage”**, with per-domain detail and separate analysis readiness. It is neither a safety grade nor AI accuracy. Confirmed incomplete profiles are valid. Optional communication/style questions cannot offset missing capacity information.

For each item below: confirmed, current, usable explicit/reviewed value = 1; known but REVIEW_DUE = 0.5; unknown/skipped/declined/unreviewed/STALE/unresolved value = 0. Fractional weights for dates/ranges are not guessed: a band receives full credit if it answers the qualitative item, while a dependent precise calculation remains limited. AI confidence cannot grant credit before confirmation. The draft preview shows projected coverage separately; active coverage uses only confirmed data.

| Domain / weight | Weighted information units (sum within row) |
| --- | --- |
| Goals/context — 20 | Defined main goal 5 (EXPLORING not yet defined); horizon 7; flexibility 4; spending currency 4 |
| Liquidity — 20 | Withdrawal pattern 5; applicable timing 5; size/recurrence 5; funding coverage 5 |
| Resilience/capacity — 25 | Outside reserve 6; cash-flow balance 4; reliability 4; obligation pressure 4; main-goal loss consequence 7 |
| Tolerance — 20 | Drawdown comfort 12; scenario reaction 8 |
| Policy boundaries — 10 | Restriction screening 4; actionable scope/strength/subject for supplied restrictions 6 |
| Experience/involvement — 5 | Product experience or explicit novice/no-experience 3; desired involvement 2 |

Overall coverage = sum(weight × usability). Round once to nearest integer for display, retain exact decimal internally. A confirmed C03 NONE gives all 20 liquidity points for **known absence of planned three-year needs**; it does not certify real liquidity. Confirmed C12 NONE gives all 10 boundary points for **explicit absence of chosen restrictions**. Do not give these credits to skip/unknown. If restrictions/needs are supplied, score dependent units by fraction of applicable rows with usable information. Additional goals do not inflate overall coverage: show separate per-goal readiness and use the least-supported goal in any all-goal fit claim.

Examples of arithmetic: valid main goal/horizon/flexibility = 16; explicit no withdrawals = 20; reserve/cash flow/reliability/obligations = 18; experience/involvement = 5 → 59%, even if every delivery preference is filled. A complete core without spending currency but no unresolved dependencies can reach 96%; absence of an advanced target allocation still makes target-drift analysis unavailable. Filling advanced policy is not necessary for 100% information coverage. If that seems too easily confused with analysis completeness, label it “Core profile coverage” in launch copy; recommend this label.

| Capability | Required information | Behavior if missing/conflicting |
| --- | --- | --- |
| Psychological risk interpretation | C08; C09 supports consistency | C08 absent → unavailable; C09 absent or X04 → limited, no single confident label. |
| Capacity-aware risk analysis | Per-goal C02/C07, C03/F01, C04–C06 | Known adverse facts still reported; missing inputs prevent LESS_CONSTRAINED. Show missing facts, not “safe”. |
| Target allocation analysis | Confirmed valid A01 plus current portfolio and classification coverage | No target → no drift verdict; targets can be displayed as user intent while suitability remains limited. Unknown classifications/scopes are reported. |
| Portfolio fit | Goal timing/priority as relevant, tolerance, capacity, restrictions and actual portfolio data | Assess supported dimensions only. No whole-portfolio fit badge if material goal/policy/capacity gaps remain. |
| Liquidity analysis | F01 details or explicit NONE, currency, accessible holdings/cash evidence and scope | Can summarize stated needs; cannot claim ability to meet them without financial-domain data. |
| Copilot decision support | Task-specific prerequisites above, experience for complex products, current confirmed profile version | Explain options and ask one decision-changing question. Avoid personalized sizing/allocation prescriptions where required context is missing. |
| Research/opportunity relevance | Stated goals/interests; hard restrictions if supplied | Partial ranking with reasons; unknown fit never represented as approval or recommendation. |

Coverage, interpretation confidence, source quality and portfolio-data availability are separate metadata. Do not multiply them into one opaque “AI confidence” number. Missing optional sensitive information affects only relevant capabilities. Redoing/skipping cannot manufacture completeness.

## 8. AI interpretation and draft review

### AI contract

1. Direct option and numeric mappings are deterministic. Preserve raw option IDs, original text, locale and answer time. Numerical parsing must respect locale; ambiguous “1,000” or currency symbols require review rather than guessing.
2. AI may extract text into candidate fields, summarize confirmed/selected facts, identify possible inconsistencies and suggest missing considerations. Every candidate supplies source answer and exact supporting span, confidence, alternatives if relevant and a concise interpretation explanation. It cannot overwrite an explicit answer or use portfolio transactions, age, name, writing style or a developer's Finance files to infer preferences.
3. Treat all raw answers as untrusted data in bounded context, including text stored in the database. The current orchestrator calls structured data current database state; Phase 4 must also distinguish field values from instructions and drafts from confirmed state. “Ignore previous instructions” in an answer is never executable authority.
4. “My income is now stable and I can take more risk” supports a draft reliability update and a request to revisit comfort. It does not imply surplus, higher reserves, no debt, a 40% tolerance, changed target allocation or permission to trade.
5. Material AI interpretations (money, dates, currency, capacity inputs, goal priority, restrictions, targets and risk thresholds) require explicit item-level acceptance or correction in review. Final confirmation covers only those accepted values plus direct mappings. Low-confidence interpretations may remain unknown; no bulk prechecked acceptance.
6. Unsupported inferences remain proposed considerations, never populated facts. Profile summaries cite fields and retain limitations. User approval confirms the chosen interpretation, not the truth of forecasts or missing facts.
7. AI failure must not block onboarding. Deterministic choices create a usable draft; free text is preserved as uninterpreted, with “Review interpretation later”. Retrying does not change active profile or overwrite prior interpretations.
8. Send only context required for the current task to the configured provider. Do not send passwords, email, whole ledgers, private personal notes or sensitive raw restriction narratives merely to generate a summary. For general analysis, send normalized constraints instead of belief labels. Preserve raw text in protected storage; explain provider use before text submission and allow structured-only completion.

### Review screen

Title: **“Your Investor Profile — draft”**. Subheading: **“Check what we understood. Missing answers can stay missing.”** Show estimated core coverage and relevant readiness limits; never a gamified risk score.

Cards: Main Goals (one row per goal); Time Horizon; Risk Tolerance; Risk Capacity by goal; Liquidity Needs; Investing Style & Experience; Constraints; Investment Policy; Monitoring & Research. Each shows the current value, where it came from (your selection / interpretation of your words / calculated), editable source question and uncertainty. Display a capacity constraint with at least as much prominence as high tolerance.

A review queue groups **missing essentials**, **interpretations to accept**, **inconsistencies**, and **assumptions or unresolved scope**. No factual assumption silently enters the profile. A deterministic interpretation such as “20% per monthly withdrawal” shows its denominator and recurrence for review. Missing items can remain blank with a capability explanation.

Actions: **“Edit”**, **“Confirm profile”**, **“Save draft and go to dashboard”**, **“Discard draft”**. All major interpreted values must be accepted/corrected/left unknown; confirmation remains possible for the remainder. Final confirmation lists accepted facts/rules and unresolved limitations. It does not authorize monitoring delivery, import, trading or changes to actual investments.

Confirmation produces v1 (or vN+1), with explicit acceptance time, owner and version checked against the preview. Incomplete is a completeness property, not a different authority tier: a confirmed unknown stays unknown. After confirmation show **“Profile saved. Would you like to add your current portfolio?”** The dashboard always provides “Investor Profile” to return later.

## 9. Future changes, versions and authority

| Change route | Proposal and confirmation behavior |
| --- | --- |
| Investor Profile settings | Edit draft → show old/new and affected analyses → explicit Save/Confirm. Direct controls are user-authored proposals; no extra chat step. |
| Repeat assessment | Start draft referencing active version; offer “Review existing answers” or “Answer again”. Existing answers remain active until replacement confirmed. Skip means leave unchanged in review mode, not delete. “Clear this answer” is explicit and previewed. In answer-again mode, show every difference and offer whether unanswered fields are retained or explicitly cleared. |
| Copilot conversation | Prepare narrow profile-change proposal with evidence and old/new diff; Level 2 confirmation for V changes. Revalidate current version before applying atomically, once, with audit. No profile state update from a passing hypothetical remark. |

V changes: goals, timing/needs, financial resilience, tolerance, product experience, investment rules/constraints, allocation targets, tax/access context. One confirmed batch of such edits creates one version (v1 → v2); typing/autosave does not. All drafts reference their base version. A stale preview requires a refreshed diff; repeated confirmation returns the same result. A changeset spanning V and P commits its version pair atomically.

P changes: language, explanation depth, research ordering, interest/style preferences, delivery cadence/topics and advisory alert thresholds. Explicit settings Save is sufficient and logged; Copilot proposes before save, without silently turning a casual statement into a preference. Retain revision history without inflating major version numbers. Hard constraints or policy thresholds always remain V even when edited from a preferences screen.

Store the active pair `(material_version, preference_revision)` plus evaluation ruleset version on each personalized analysis/proposal. History shows date, before/after, source, rationale and actor. Restore copies an old version into a new draft to confirm; never rewinds/deletes history. A semantic algorithm change produces a new evaluation and visible explanation, not rewritten historical answers. If it would alter active policy, require a new proposal.

Suggested freshness: ask for optional review at six/twelve months according to A07; when A07 absent, display a non-blocking review-due indicator at twelve months. Time-sensitive inputs become REVIEW_DUE then, not automatically false. A known material change or passed withdrawal date marks affected projections STALE until clarified; passing the date does not prove withdrawal occurred. Preserve historical as-of facts. ON_REQUEST suppresses proactive prompts, not uncertainty metadata. Do not downgrade all preferences just because a goal date passed. Never create an automation solely by saving a requested cadence in Phase 4.

User ownership must be checked on profile, assessment, answers, goal references, versions, proposals and imports. All summaries/caches/provider context must be user scoped; two users with the same instrument can have different fit conclusions. Instrument research remains shared factual context where appropriate; personal fit/policy stays user-scoped. Do not load the repository owner's personal investment context as a product default.

Raw answers are sensitive profile data. Recommend preserving confirmed answer provenance while the profile/history is retained; expire abandoned drafts after a proposed 90-day retention window with notice and an earlier explicit discard action. Provider payloads and operational logs should avoid duplicating raw text. Final retention, export and erasure behavior requires product/security approval before persistence work; version history must not imply indefinite retention after an authorized erasure. Audit provenance should reference protected answer records rather than copy optional sensitive narratives everywhere.

## 10. Portfolio Setup handoff

Keep assessment/profile state and portfolio-import state independent. Confirming a profile succeeds even if setup is skipped, cancelled or fails. Portfolio setup never increases profile coverage merely by creating holdings.

| Choice | Route using existing Phase 3 |
| --- | --- |
| “Yes, enter it now” | Proposed structured entry presentation feeding the existing normalized import service/batch contract. This entry surface is new; do not imply it is already implemented. No direct Asset writes from onboarding. |
| “Import CSV” | Existing conversation import/upload flow → batch preview → reconciliation → existing confirmation. |
| “Upload screenshot” | Show only when runtime extraction capability is actually enabled; today the inspected router returns 501. If unavailable, explain and offer CSV/chat without a fake successful parse. |
| “Tell PortfolioMind in chat” | Existing natural-language import route and multi-turn missing-field completion, with explicit portfolio-import intent. |
| “Skip for now” | Dashboard; no empty import batch required. Resume setup later. |

Reuse [Phase 3 architecture](portfolio_import_architecture.md), `PortfolioImportService`, `PortfolioImportBatch`/items, resolution UI and `CopilotWriteExecutor` import executor. Preserve existing Level 3 `IMPORT` confirmation, ownership, stale-state checks, idempotency and audit. Import uses opening positions and never fabricates BUY transactions or cash movements. Unknown cost basis remains unknown; current implementation/documentation uses zero P/L as a sentinel in some paths, which must not be described by Copilot as proof of actual zero gains.

Transfer only authenticated user context, entry-channel intent, a reference to confirmed profile version if needed for explanations, and user-supplied portfolio input. Never infer quantities/currencies/cost basis from goals, reserve bands or targets. A policy edit after preview does not authorize a changed import. An import mismatch with policy may prompt a later analysis; it does not rewrite either holdings or policy during onboarding.

## 11. Questions deliberately excluded

| Do not require | Reason / narrower alternative |
| --- | --- |
| Exact age, date of birth, gender, marital status, nationality | Not reliable substitutes for capacity or horizon; ask goal dates and obligations. Identity/eligibility checks, if needed for another product, are a separate flow. |
| Exact salary, employer, household income, net worth, portfolio balance or full debt inventory | Core decisions can start from surplus, reliability, reserves and burden. Financial records belong in their own domains; exact target/withdrawal Money is optional when useful. |
| Family members' identities, medical diagnoses, political views, religious affiliation | Ask only voluntary investment restrictions or anonymous financial commitments; no identity inference. |
| Broker passwords, account numbers, government identifiers, tax returns | Not required for personalization. Import/security flows must not be duplicated here. |
| “What is your portfolio?” / individual holdings, quantities, purchase prices | Explicitly outside Investor Profile; Phase 3 setup owns these. |
| A forced expected return or “How rich do you want to be?” | Encourages false precision; E12 makes aspirations optional and clearly separates them from forecasts. |
| “Choose conservative/balanced/aggressive” as primary input | Hides different meanings and mixes tolerance/capacity. |
| Repeated near-identical loss questions or arbitrary market trivia quizzes | Adds fatigue without enough information; use one comfort question, one scenario and optional actual experience. |
| Years investing as a risk multiplier | Time in markets does not establish product understanding; ask family-specific familiarity. |
| Mandatory target allocation, position limits or benchmark at signup | Users can be useful participants without an existing IPS; keep advanced rules optional. |

Optional context should justify a concrete capability; avoid expanding into budgeting, KYC, tax advice, or family profiling to make the form look complete.

## 12. Example profiles and expected product behavior

Fictional examples illustrate behavior, not investment recommendations. Ages and account sizes are deliberately unnecessary. Different currencies/countries are user-supplied, not inferred. All fields not listed remain unknown.

### Example A — Near-term home buyer, psychologically risk tolerant

- Confirmed answers: C01 PURCHASE; C02 exact date 18 months ahead, FIXED; C03 ONE_OFF; F01 50% of covered investment money, investment-funded, linked to home goal; C04 M3_6; C05 SURPLUS/RELIABLE; C06 MANAGEABLE; C07 GOAL_UNAFFORDABLE; C08 P40_PLUS; C09 HOLD; C10 STOCKS/UNDERSTAND; C11 PERIODIC; C12 BORROWING + reviewed hard exclusion; E01 EUR, country context Germany supplied. No allocation target.
- Derived: HIGH tolerance; CONSTRAINED home-goal capacity via CAP1/CAP2; known 50% liquidity need; MIXED resilience under deliberately limited rules. X01 remains visible, not “resolved” by accepting high tolerance.
- Draft: “You report comfort with large falls, but losing money allocated to the home purchase could prevent the purchase.” No risk classification for the unassigned half. Portfolio-fit analysis needs actual portfolio evidence; target drift unavailable.
- Expected personalization: prioritize home-goal liquidity/currency exposure and downside research; no automatic risk increase or portfolio change. Core coverage can be 100% while suitability tension remains open.

### Example B — Beginner, long horizon, stable surplus, prefers simplicity

- Confirmed answers: C01 RETIREMENT; C02 GE_10Y/FLEXIBLE; C03 NONE; C04 M6_12; C05 SURPLUS/RELIABLE; C06 NONE; C07 ADJUST_GOAL; C08 P20; C09 REVIEW; C10 NONE; C11 LOW_MAINTENANCE; C12 BORROWING and COMPLEX with reviewed hard exclusions. E01 CAD; E05 BROAD_PASSIVE; E06 MONTHLY_SHORT; E08 FEES/DIVERSIFICATION/LEARNING; E11 STEP_BY_STEP; no target allocation yet.
- Derived: MODERATE tolerance; LESS_CONSTRAINED capacity for retirement under CAP5; BUFFERED resilience; NONE_PLANNED liquidity in three-year window. Novice status remains separate from financial capacity.
- Draft: “Your reported finances leave more flexibility for this long-term goal. You prefer simple explanations and have not yet chosen an allocation.” No automatic 60/40 or equity-heavy template.
- Expected personalization: explanatory research with costs/diversification emphasis; minimal review burden; unknown target means no drift alerts. A01 DRAFT_HELP can invite a later policy proposal, not set policy now.

### Example C — Experienced investor living from investments

- Confirmed answers: C01 INCOME; C02 ONGOING/FIXED; C03 REGULAR; F01 monthly 2,000 GBP from investments, starting now, end date unknown; C04 GE_12M explicitly outside this income goal; C05 BREAK_EVEN/NO_OUTSIDE_INCOME; C06 MANAGEABLE; C07 ESSENTIALS; C08 P10; C09 REDUCE; C10 BONDS and FUNDS/UNDERSTAND; C11 PERIODIC; C12 ILLIQUID reviewed hard exclusion for spending needs. E01 GBP; E08 INCOME_SAFETY/DOWNSIDE; E09 GOAL_LIQUIDITY/MATERIAL_DISCLOSURE; A06 TAX_REVIEW.
- Derived: MODERATE stated tolerance (not automatically low because retired), CONSTRAINED capacity for essential spending; known recurrent need, affected portfolio percentage unknown without denominator; resilience MIXED under simplified rules, not automatically VULNERABLE for lack of salary.
- Draft: “Regular investment withdrawals support essential spending. The share of your portfolio needed for them is not yet known.” Cannot infer a sustainable withdrawal rate from the amount and reserve band.
- Expected personalization: explain income reliability, liquidity timing and relevant risks. Do not invent nominal returns, tax rates or safe income. Imported holdings and their data quality remain necessary for portfolio fit.

### Example D — Variable-income investor declining financial disclosures

- Confirmed answers: C01 GROW; C02 GE_10Y/SOME; C03 POSSIBLE with F01 skipped; C04/C06/C07 DECLINED; C05 VARIABLE/VARIABLE; C08 P30; C09 REVIEW; C10 CRYPTO/USED_BASIC; C11 ACTIVE; C12 VALUES with free text “avoid businesses earning from gambling”, specific subject accepted as hard exclusion. E01 skipped; E08 BUSINESS_QUALITY/DOWNSIDE.
- Derived: HIGH stated tolerance; capacity UNKNOWN; UNQUANTIFIED_NEEDS; resilience UNKNOWN. Do not infer religious identity or copy an entire religious product standard from the one exclusion.
- Core coverage: goals 16 + liquidity 5 + capacity inputs 8 + tolerance 20 + boundaries 10 + experience/involvement 5 = **64%**. Other answered preferences add no points. Capacity remains unknown despite relatively high coverage.
- Expected personalization: explain research and the explicit exclusion; disclose missing capacity/liquidity context. No pressure to disclose, no automatic conservative label, and no confident personalized sizing recommendation.

## 13. Phase 4 implementation boundaries and acceptance criteria

### Recommended implementation slices, after approval

1. **Profile foundation and deterministic assessment:** user-owned drafts/raw answers, core questions, dependencies, field validation, review/confirmation, version history and return-later behavior. Extended/advanced field contracts can be reserved without forcing their entire editor into the first release.
2. **Dimensions and read integration:** versioned interpretation rules, per-goal capacity, capability-based completeness; confirmed USER_PROFILE/INVESTMENT_POLICY context in the existing Copilot engine. Copy must distinguish general analysis, profile intent and actual holdings.
3. **AI interpretation and change proposals:** constrained text extraction, provenance, review queue, narrow Level 2 profile executor, replace current AUTO_APPLY policy intent behavior, stale-version revalidation and audit. Structured-only onboarding remains available throughout.
4. **Optional extended/advanced editors and import handoff:** same profile domain and confirmation contract; reuse Phase 3. Show monitoring requests separately from implemented capabilities. Future monitoring activation needs its own explicit flow.

Included: multi-user ownership, optional onboarding, editing/redo, scoped goals, both risk dimensions, confirmed policy intent, preferences, history and bounded Copilot personalization. Excluded: broker execution, automatic rebalance/asset changes, automatic policy creation from a score, new import engine, new OCR provider, full tax/KYC engine, certified suitability decisions, autonomous alerts/research jobs, new portfolio accounting or a Finance bridge redesign.

Do not implement SQLAlchemy models, migration files, routes, React screens, provider wiring or automation in this design task. Later implementation should follow repository service-layer and decimal conventions, perform ownership checks, and run migrations/tests appropriate to those changes. Existing working-tree modifications are not part of this deliverable.

### Acceptance scenarios for later implementation

| Scenario | Required observable result |
| --- | --- |
| Skip all / a section / one answer | Dashboard accessible; missingness recorded correctly; no defaults inferred; resume available. |
| Incomplete confirmation | Known valid fields active, others unknown; missing capability limitations remain. |
| 40% tolerance + 50% home withdrawal in 18 months | Separate tolerance/capacity; capital-specific issue; no global aggressive label. |
| Two goals with conflicting horizons | No averaging; no allocation/coverage claim without capital scope; goal-specific results. |
| AI proposes unsupported income/reserve facts | Reject extraction or keep unknown; preserve original text; no silent promotion. |
| AI unavailable / ambiguous decimal/currency | Structured assessment still works; free text preserved; unresolved quantities not guessed. |
| Injection text in answer or stored profile | Treated as data; no tools/state mutation or instruction precedence. |
| Change from Copilot / duplicate confirm / concurrent edit | Preview required; apply once; stale base gets refreshed review; owning-user audit entry. |
| Repeat assessment and skip existing answer | Existing active value retained unless explicit clear/replacement confirmed. |
| Invalid allocation / conflicting hard rules | Save remainder allowed; invalid rule cannot become operative merely by acknowledging warning. |
| 100% core coverage with no target or holdings | No target drift or whole-portfolio-fit claim; readiness remains task-specific. |
| Alert preference saved but feature unavailable | Requested/not active shown; no claim that a monitor is running. |
| Import skipped/failed or screenshot unconfigured | Profile retained; dashboard usable; truthful alternative import choices. |
| User A requests User B's profile or version | No leakage through endpoints, IDs, caches, prompt context or proposal references. |
| Exact same asset held by different users | Personal fit differs by confirmed user profile; shared asset facts not rewritten. |
| Re-evaluate under new ruleset | Historical answers/analyses reproducible; no silent policy rewrite. |

These are acceptance requirements, not tests executed in this documentation-only task. Before launch, run comprehension/length testing with novices, experienced investors, users with irregular income, different countries/currencies and accessibility needs; specifically check whether C07 permanent loss and C08 drawdown are understood as different questions.

## 14. Human decisions required before implementation

1. **Approve the launch scope and friction:** 12 core cards, optional extensions, 7–10 minute hypothesis, universal skipping and incomplete confirmation; decide whether all advanced editors ship in Phase 4 or a later slice.
2. **Approve the interpretation model:** separate tolerance/capacity, goal-scoped constraints, proposed band thresholds and no global risk badge. Calibrate wording/rules with domain review and user testing; do not market this as validated suitability scoring.
3. **Approve authority and history:** every material change uses reviewed Level 2 confirmation, atomic version check and audit; lightweight preference revisions remain separate. Replace the existing AUTO_APPLY policy-intent metadata before enabling policy writes.
4. **Approve coverage/readiness presentation:** weighted core coverage, explicit NONE handling, independent capability gates and freshness reductions; completeness cannot imply suitability.
5. **Approve data handling:** raw-text preservation, minimal provider context, voluntary sensitive constraints, proposed 90-day abandoned-draft retention, and concrete export/erasure/security requirements before database design.
6. **Approve scope and capability semantics:** ALL vs goal scopes, explicit allocation classification/denominators, requested versus active monitoring, and reuse of Phase 3 setup with screenshot unavailable until genuinely configured.

No production implementation is authorized by this document's creation or by confirmation of an example profile.
