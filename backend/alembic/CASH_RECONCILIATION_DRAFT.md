# Cash Reconciliation Draft (Do Not Run Automatically)

This document is a reviewable migration/reconciliation design, not an Alembic
revision. No production data was changed while preparing it.

## Why reconciliation is needed

Two historical cases can exist:

1. The old frontend created a transaction and then sent a separate cash
   deposit/withdrawal. The backend also created its linked BUY/SELL movement,
   so the same economic event may have affected cash twice.
2. Revision `e5f6a7b8c9d0` marked pre-existing transactions as
   `affects_cash=true`, but did not backfill movements or account balances.
   Such rows may say they affect cash even though no effect was ever applied.

These cases cannot be distinguished with certainty from amounts alone. A
same-value manual deposit/withdrawal can be legitimate, so automatic deletion
or balance rewriting is unsafe.

## Read-only inventory

Run these queries on a restored staging copy first. They do not mutate data.

### Account balance versus ledger sum

```sql
SELECT
    ca.id AS cash_account_id,
    ca.user_id,
    ca.currency,
    ca.balance,
    COALESCE(SUM(cm.amount), 0) AS movement_sum,
    ca.balance - COALESCE(SUM(cm.amount), 0) AS unexplained_difference
FROM cash_accounts ca
LEFT JOIN cash_movements cm ON cm.cash_account_id = ca.id
GROUP BY ca.id, ca.user_id, ca.currency, ca.balance
HAVING ca.balance <> COALESCE(SUM(cm.amount), 0)
ORDER BY ca.user_id, ca.currency;
```

### Likely frontend/backend duplicate pairs

The old frontend movement was unlinked and followed the linked backend
movement. Treat this only as a candidate report; the time window and notes are
heuristics.

```sql
WITH linked AS (
    SELECT
        cm.id AS linked_movement_id,
        cm.cash_account_id,
        cm.related_transaction_id,
        cm.movement_type,
        cm.amount,
        cm.currency,
        cm.created_at,
        t.asset_id,
        a.user_id,
        a.name AS asset_name
    FROM cash_movements cm
    JOIN transactions t ON t.id = cm.related_transaction_id
    JOIN assets a ON a.id = t.asset_id
    WHERE cm.movement_type IN ('BUY', 'SELL')
)
SELECT
    l.user_id,
    l.asset_id,
    l.asset_name,
    l.related_transaction_id,
    l.linked_movement_id,
    manual.id AS suspected_duplicate_movement_id,
    l.movement_type AS transaction_movement_type,
    manual.movement_type AS manual_movement_type,
    l.amount,
    l.currency,
    l.created_at AS linked_created_at,
    manual.created_at AS manual_created_at,
    manual.notes
FROM linked l
JOIN cash_movements manual
  ON manual.cash_account_id = l.cash_account_id
 AND manual.related_transaction_id IS NULL
 AND manual.amount = l.amount
 AND manual.currency = l.currency
 AND manual.created_at >= l.created_at
 AND manual.created_at <= l.created_at + INTERVAL '10 minutes'
 AND manual.movement_type = CASE
       WHEN l.movement_type = 'BUY' THEN 'WITHDRAW'
       ELSE 'DEPOSIT'
     END
WHERE
    (l.movement_type = 'BUY' AND manual.notes LIKE 'BUY %')
 OR (l.movement_type = 'BUY' AND manual.notes LIKE 'Asset purchase:%')
 OR (l.movement_type = 'SELL' AND manual.notes LIKE 'SELL %')
ORDER BY l.created_at, manual.created_at;
```

### `affects_cash=true` transactions without a linked movement

This report includes legitimate historical/update cases and therefore also
requires review. `first_account_created_at` is useful for identifying rows that
predate the cash-ledger rollout.

```sql
SELECT
    t.id AS transaction_id,
    a.user_id,
    t.asset_id,
    t.transaction_type,
    t.total_amount,
    t.transaction_currency,
    t.created_at,
    MIN(ca.created_at) AS first_account_created_at,
    COUNT(cm.id) AS linked_movement_count
FROM transactions t
JOIN assets a ON a.id = t.asset_id
LEFT JOIN cash_accounts ca ON ca.user_id = a.user_id
LEFT JOIN cash_movements cm
  ON cm.related_transaction_id = t.id
 AND cm.movement_type IN ('BUY', 'SELL')
WHERE t.affects_cash = TRUE
GROUP BY
    t.id, a.user_id, t.asset_id, t.transaction_type,
    t.total_amount, t.transaction_currency, t.created_at
HAVING COUNT(cm.id) = 0
ORDER BY a.user_id, t.created_at;
```

## Proposed safe reconciliation

1. Take a database backup and restore it into an isolated staging database.
2. Export the three reports above with stable row IDs and ask the data owner to
   approve each suspected duplicate or legacy transaction policy.
3. Create a dedicated Alembic revision only after approval. The revision should
   create a small `cash_reconciliation_actions` audit table with a unique
   `source_movement_id`, reason, signed adjustment amount, execution timestamp,
   and operator/run identifier. The unique source ID makes reruns idempotent.
4. For every confirmed duplicate, preserve the historical movement and append
   one `ADJUSTMENT` equal to `-source_movement.amount`; update the corresponding
   account balance by the same adjustment in the same database transaction.
   Do not hard-delete audit history.
5. For pre-ledger transactions with no historical cash effect, choose one policy
   per approved dataset:
   - conservative: set `affects_cash=false`; or
   - ledger backfill: append the correct BUY/SELL movement and update the account
     balance atomically.
   Never infer this choice only from transaction amount.
6. Re-run all inventory queries. Require account balance minus movement sum to
   be zero and require every approved action to appear exactly once in the audit
   table.
7. Compare per-user cash and net-worth totals before/after, obtain sign-off,
   then rehearse restore/roll-forward before production execution.

## Rollback and operational notes

- Prefer a compensating adjustment over a destructive downgrade.
- Store the approved candidate CSV/hash with the deployment record; do not let
  the migration discover and mutate new candidates dynamically.
- Lock affected cash-account rows during the write phase to prevent concurrent
  balance changes.
- The transaction creation API currently has no idempotency key. Sending the
  same request twice intentionally creates two transactions and two cash
  effects; the regression suite documents this current behavior. Adding request
  idempotency belongs to a separate stabilization package.
