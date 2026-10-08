# PortfolioMind Copilot Write Safety Model

> [!NOTE]
> **Status:** Phase 4 Implemented & Verified  
> **Implementation Scope:** Full write engine with action proposals, narrow write executors, atomic pre-commit state revalidation, strict idempotency, durable audit logging, interactive proposal preview UI, Level 3 Portfolio Import & Opening Position Engine, and Level 2 Investor Profile & Personalization Governance.


Core principle:

AI may read broadly, but it should write narrowly.

Codex/PortfolioMind Copilot may use broad context across:
- investor profile
- investment policy
- portfolio
- holdings
- research
- thesis
- watchlist
- decision history
- conversation context

But write operations must be tightly scoped, explicit, validated, and auditable.

## Write permission levels

### Level 1 — Low-risk writes
May be allowed with minimal friction, but still logged.

Examples:
- watchlist add/remove
- research status updates
- notes
- tags
- journal entries
- thesis draft notes
- non-financial metadata

### Level 2 — Confirmation required
Must show a proposal/preview before writing.

Examples:
- adding a transaction
- editing a transaction
- opening position / migrated holding
- target allocation changes
- risk profile changes
- investment policy changes
- portfolio rules / limits

Required flow:

User request  
→ interpret intent  
→ resolve target  
→ validate current state  
→ create proposed change  
→ show old vs new  
→ explain impact  
→ user confirms  
→ revalidate current state  
→ write once  
→ audit log  

### Level 3 — Strong confirmation
Use stronger confirmation for destructive/high-impact changes.

Examples:
- deleting transactions
- changing historical cost basis
- bulk portfolio imports
- overwriting existing holdings
- cash balance corrections
- liability corrections
- destructive reconciliation
- large historical data changes

These actions should have extra friction and very clear impact previews.

### Level 4 — Not allowed for now
Copilot should not directly execute:

- real broker buy/sell orders
- money transfers
- withdrawals
- account deletion
- destructive bulk financial cleanup

Copilot may analyze or prepare these actions, but not execute them.

## Financial integrity principles

Never directly overwrite a holding quantity without understanding the accounting meaning.

Example:

“Change UBER from 10 shares to 15”

must first determine whether this means:

- BUY 5
- opening-position correction
- import reconciliation
- historical correction

Historical transactions, cost basis, cash balances, and delete operations are especially sensitive because they can alter portfolio P/L and historical reporting.

Do not guess financial data.

Missing:
- price
- quantity
- cost basis
- transaction date
- currency

must be resolved explicitly when required.

## Policy changes vs portfolio changes

Investment Policy changes and actual portfolio changes must be separate action classes.

Example:

“I want to take more risk.”

should not automatically alter holdings.

Possible flow:

Update risk policy  
→ analyze portfolio against new policy  
→ show resulting drift / implications  
→ user separately decides whether to change holdings  

## Revalidation before commit

A proposed change may become stale between preview and confirmation.

Before any confirmed write:

- reload current state
- confirm the expected old state still matches
- reject or re-preview if state changed

## Idempotency

Every write action should have an idempotency key or equivalent protection.

Double clicks, retries, network retries, or repeated confirmations must not create duplicate transactions or duplicate writes.

## Auditability

Every meaningful AI-triggered write should be traceable.

Record at minimum:

- user request
- interpreted intent
- proposed action
- affected records
- old value/state
- new value/state
- source/context used
- confirmation timestamp
- acting user
- final executed result
- action/idempotency identifier

Copilot should never silently mutate financial state.

## Tool design principle

Avoid broad mutation tools such as:

`update_everything()`

Prefer narrow, explicit tools such as:

`add_transaction()`  
`update_transaction()`  
`append_thesis_note()`  
`update_target_allocation()`  
`update_risk_profile()`  
`add_watchlist_item()`  

Each tool should have clear:
- permission level
- validation rules
- input schema
- side effects
- audit behavior

## Final principle

AI can propose.  
User decides.  
System validates.  
System writes narrowly.  
Everything important is logged.  

## Implementation Architecture (Phase 2)

- **Database Models (`app/models/copilot.py`):**
  - `CopilotActionProposal`: Persistent proposal table storing parameters, expected impact, current snapshot, and lifecycle status (`DRAFT`, `NEEDS_INPUT`, `READY_FOR_CONFIRMATION`, `CONFIRMED`, `APPLIED`, `CANCELLED`, `EXPIRED`, `FAILED`).
  - `CopilotAuditLog`: Immutable audit trail recording user request, interpreted intent, affected resource type/ID, old/new states, execution status, and idempotency key. Survives conversation deletion.
- **Narrow Write Executor (`app/services/copilot/executor.py`):**
  - Dispatches narrow mutations only via existing domain services (`transaction.py`, `opportunity.py`, `decision_log.py`).
  - Atomically validates state (e.g. non-negative holdings for SELL, instrument/asset ownership).
  - Enforces strict idempotency (double-clicking confirm returns cached result with 0 duplicate mutations).
- **Proposal Lifecycle Service (`app/services/copilot/proposal_service.py`):**
  - Creates, retrieves, and cancels user-scoped proposals with expiration handling.
- **REST Endpoints (`app/routers/copilot.py`):**
  - `GET /api/copilot/proposals/{proposal_id}`
  - `POST /api/copilot/proposals/{proposal_id}/confirm`
  - `POST /api/copilot/proposals/{proposal_id}/cancel`
- **Frontend Proposal Cards (`frontend/src/pages/CopilotPage.tsx`):**
  - Displays diff preview, position delta, cash impact, warnings, and [Onayla ve Uygula] / [İptal Et] buttons with loading guards.

## Implementation Architecture (Phase 3 — Portfolio Import & Opening Position Engine)

- **Input Channels Converged into Common Import Model:**
  - **Natural Language Chat:** Multi-holding extraction with Turkish/English entity resolution, distinguish quantity from market value, cost statements association.
  - **CSV File Upload:** Auto-detects delimiters (`,`, `;`, `\t`), European/Turkish comma decimals, flags ambiguous generic cost headers.
  - **Screenshot / Image Upload:** Validates file size (<10MB) and magic bytes (PNG, JPEG, WEBP). Explicitly returns HTTP 501 when external multimodal OCR provider is unconfigured (strict non-faking). Downstream structured vision parser, prompt-injection defense, and reconciliation layer are fully tested via controlled fixtures.
- **Database Models (`app/models/opening_position.py`, `app/models/portfolio_import.py`):**
  - `OpeningPosition`: Pure historical balance model (`quantity`, `average_cost`, `cost_basis_known`, `has_incomplete_history`, `opened_at`).
  - `PortfolioImportBatch` and `PortfolioImportItem`: Tracks import lifecycle (`DRAFT`, `READY_FOR_CONFIRMATION`, `APPLIED`, `CANCELLED`, `FAILED`), item intended actions (`CREATE_OPENING_POSITION`, `UPDATE_EXISTING_OPENING_POSITION`, `ADD_TO_EXISTING_OPENING_POSITION`, `SKIP`, `NEEDS_REVIEW`, `AMBIGUOUS`, `INVALID`).
- **Accounting & Portfolio Stats Integration:**
  - **Zero Fabricated Transactions:** Opening positions are never converted into fake `BUY` transactions.
  - **Cost Basis Known vs Unknown:** When cost basis is omitted/unknown (`cost_basis_known=False`), `unrealized_pl` is strictly set to 0.00 (no artificial 10,000% gain distortions).
  - **Running Balance Continuity:** `portfolio_stats.py` and `transaction.py` evaluate non-negative holdings starting from `OpeningPosition.quantity`.
- **Level 3 Strong Confirmation & Reconciliation:**
  - Ambiguous existing holdings are flagged as `NEEDS_REVIEW` / `AMBIGUOUS`.
  - Inline resolution controls allow user to choose REPLACE, ADD, SKIP, or edit quantity/cost before confirmation.
  - Execution requires explicit Strong Confirmation (`confirmation_text == "IMPORT"`).
  - Double confirmation is strictly idempotent and creates a durable `CopilotAuditLog`.

## Implementation Architecture (Phase 4.1 — Financial Context, Goals & Financial Intelligence)

- **Context Engine Groups & Loaders:**
  - `FINANCIAL_CONTEXT`: Monthly net income, essential expenses, discretionary expenses, income stability, planning currency.
  - `FINANCIAL_GOALS`: Goals list, modes, target amounts, currencies, target dates, priorities, funding status assessments (`FUNDED_NOW`, `ON_TRACK`, `SHORTFALL`, `UNASSIGNED`).
  - `MANDATES`: Scoped investment sleeves, types (`PRESERVATION`, `GROWTH`, `INCOME`, `RESERVE`, `SPECULATIVE`), risk capacities, and assigned capital.
  - `FINANCIAL_INTELLIGENCE`: Deterministic calculator metrics including Net Worth, Liquid Net Worth, Monthly Surplus, Savings Rate, Emergency Runway (months), Debt-to-Income, Speculative Exposure Cap.
- **Intent Classifier Expansion:**
  - `FINANCIAL_ANALYSIS`: Triggers holistic financial overview without requiring mutation. Formats calculated intelligence into structured Turkish response.
  - `UPDATE_FINANCIAL_CONTEXT`: Detects natural language income/expense updates, stages Level 2 proposal.
  - `CREATE_GOAL`: Detects conversational goal intentions (home purchase, retirement, emergency fund), stages Level 2 proposal.
  - `TRANSFER_CAPITAL`: Detects requests to reassign or move units/cash between mandates, stages Level 2 proposal.
- **Write Executor Handlers (`app/services/copilot/executor.py`):**
  - `_execute_financial_context_update`: Atomically updates `FinancialContext`.
  - `_execute_create_goal` & `_execute_update_goal`: Creates or updates `FinancialGoal`.
  - `_execute_create_mandate` & `_execute_update_mandate`: Creates or updates `InvestmentMandate` with policy inheritance validation.
  - `_execute_assign_capital`: Assigns fixed units or cash to a mandate, enforcing capital conservation.
  - `_execute_transfer_capital`: Performs virtual transfer between mandates (modifies only `CapitalAssignment`, zero new `Transaction` rows, zero cash movements, zero cost basis change).
- **Audit & Governance:**
  - All Level 2 proposals require explicit confirmation via `/api/copilot/proposals/{proposal_id}/confirm`.
  - Every confirmed action persists an immutable `CopilotAuditLog` entry with `execution_status = "SUCCESS"`.


