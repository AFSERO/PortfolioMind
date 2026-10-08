"""Pure stats calculation over an asset's transactions.

Convention (per spec):
  avg_cost          = Σ(buy_qty × buy_price) / Σ(buy_qty)            across ALL BUYs
  total_quantity    = Σ(BUY qty) − Σ(SELL qty)
  total_cost        = avg_cost × total_quantity                      (remaining cost basis)
  realized_pl       = Σ over SELLs of (sell_price − running_avg_at_sale) × sell_qty
  avg_cost_currency = currency of the FIRST BUY (chronological)
  has_mixed_currencies = True if any transaction uses a different currency
                         than the first BUY's currency

All arithmetic in Decimal; callers convert to float at the JSON boundary.
"""

from decimal import Decimal
from typing import Any, Iterable, Optional

from app.models.transaction import Transaction, TransactionType

ZERO = Decimal("0")


def _sorted(transactions: Iterable[Transaction]) -> list[Transaction]:
    # created_at is None on unsaved objects (server default not yet applied).
    # Normalise the tiebreaker to date so (date, date) tuples are always comparable.
    return sorted(
        transactions,
        key=lambda t: (
            t.transaction_date,
            t.created_at.date() if t.created_at is not None else t.transaction_date,
        ),
    )


def compute_stats(
    transactions: Iterable[Transaction],
    opening_position: Optional[Any] = None,
) -> dict:
    txns = _sorted(transactions)

    op_qty = ZERO
    op_cost = None
    op_currency = None
    cost_basis_known = True
    has_incomplete_history = False

    if opening_position is not None:
        op_qty = getattr(opening_position, "quantity", ZERO)
        has_incomplete_history = getattr(opening_position, "has_incomplete_history", True)
        cost_basis_known = getattr(opening_position, "cost_basis_known", True)
        op_currency = getattr(opening_position, "cost_currency", None)
        avg_cost_val = getattr(opening_position, "average_cost", None)
        if cost_basis_known and avg_cost_val is not None:
            op_cost = op_qty * avg_cost_val
        else:
            cost_basis_known = False

    if not txns:
        avg_cost = None
        total_cost = ZERO if cost_basis_known else None
        if opening_position is not None and cost_basis_known and op_cost is not None:
            avg_cost = getattr(opening_position, "average_cost", None)
            total_cost = op_cost

        return {
            "total_quantity": op_qty,
            "avg_cost": avg_cost,
            "avg_cost_currency": op_currency,
            "total_cost": total_cost,
            "realized_pl": ZERO,
            "unrealized_pl": ZERO if cost_basis_known else None,
            "has_mixed_currencies": False,
            "cost_basis_known": cost_basis_known,
            "has_incomplete_history": has_incomplete_history,
        }

    # First BUY determines the avg_cost currency (falling back to opening position currency)
    first_buy: Optional[Transaction] = next(
        (t for t in txns if t.transaction_type == TransactionType.BUY), None
    )
    avg_cost_currency = op_currency or (first_buy.transaction_currency if first_buy else None)

    has_mixed = False
    if avg_cost_currency is not None:
        has_mixed = any(
            t.transaction_currency != avg_cost_currency for t in txns
        )

    # Weighted avg over ALL buys (and opening position if cost basis known)
    total_buy_qty = ZERO
    total_buy_cost = ZERO

    if cost_basis_known and op_cost is not None:
        total_buy_qty += op_qty
        total_buy_cost += op_cost

    for t in txns:
        if t.transaction_type == TransactionType.BUY:
            total_buy_qty += t.quantity
            total_buy_cost += t.quantity * t.price_per_unit

    avg_cost = (
        (total_buy_cost / total_buy_qty) if total_buy_qty > 0 else None
    )

    # Running avg for realized P/L at each SELL
    running_qty = op_qty
    running_cost = op_cost if (cost_basis_known and op_cost is not None) else ZERO
    realized_pl = ZERO
    total_sell_qty = ZERO
    for t in txns:
        if t.transaction_type == TransactionType.BUY:
            running_qty += t.quantity
            running_cost += t.quantity * t.price_per_unit
        else:  # SELL
            running_avg = (running_cost / running_qty) if running_qty > 0 else ZERO
            realized_pl += (t.price_per_unit - running_avg) * t.quantity
            # Reduce running pool at current avg (sells don't change avg)
            running_cost -= running_avg * t.quantity
            running_qty -= t.quantity
            total_sell_qty += t.quantity

    actual_buy_tx_qty = sum(
        (t.quantity for t in txns if t.transaction_type == TransactionType.BUY), ZERO
    )
    total_quantity = op_qty + actual_buy_tx_qty - total_sell_qty
    total_cost = (avg_cost * total_quantity) if avg_cost is not None else ZERO
    if opening_position is not None:
        # Opening positions use the remaining moving-average pool after later trades.
        avg_cost = running_cost / running_qty if running_qty > 0 else None
        total_cost = running_cost
        if not cost_basis_known or has_mixed:
            avg_cost = total_cost = None
            realized_pl = None if total_sell_qty else ZERO

    return {
        "total_quantity": total_quantity,
        "avg_cost": avg_cost,
        "avg_cost_currency": avg_cost_currency,
        "total_cost": total_cost,
        "realized_pl": realized_pl,
        "unrealized_pl": ZERO if cost_basis_known else None,  # filled in by dashboard/asset layer with current price
        "has_mixed_currencies": has_mixed,
        "cost_basis_known": cost_basis_known,
        "has_incomplete_history": has_incomplete_history,
    }

