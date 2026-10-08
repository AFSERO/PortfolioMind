from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.cash import CashAccount
from app.models.financial_context import (
    CapitalAssignment,
    InvestmentMandate,
    ResourceAssignmentType,
)
from app.services.asset import list_assets_with_stats
from app.utils.currency import build_rate_map, convert


class AssignmentService:
    @staticmethod
    async def assign_capital(
        session: AsyncSession,
        user_id: uuid.UUID,
        mandate_id: uuid.UUID,
        resource_type: ResourceAssignmentType,
        asset_id: Optional[uuid.UUID] = None,
        cash_account_id: Optional[uuid.UUID] = None,
        assigned_quantity: Decimal = Decimal("0"),
        assigned_amount: Decimal = Decimal("0"),
        notes: Optional[str] = None,
    ) -> CapitalAssignment:
        # 1. Verify mandate ownership
        m_stmt = select(InvestmentMandate).where(
            InvestmentMandate.id == mandate_id,
            InvestmentMandate.user_id == user_id,
        )
        mandate = (await session.execute(m_stmt)).scalar_one_or_none()
        if not mandate:
            raise ValueError("Mandate not found or access denied")

        if resource_type == ResourceAssignmentType.ASSET:
            if not asset_id:
                raise ValueError("asset_id is required for ASSET assignment")
            # Verify asset ownership & total quantity
            assets_with_stats = await list_assets_with_stats(session, user_id)
            match = next((item for item in assets_with_stats if item[0].id == asset_id), None)
            if not match:
                raise ValueError("Asset not found or access denied")
            asset, stats = match
            total_qty = Decimal(str(stats["total_quantity"]))

            # Find existing assignment in this mandate if any
            existing_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == mandate_id,
                CapitalAssignment.asset_id == asset_id,
            )
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()

            # Sum assigned across other mandates
            all_assigned_stmt = select(CapitalAssignment).where(
                CapitalAssignment.user_id == user_id,
                CapitalAssignment.asset_id == asset_id,
            )
            all_assignments = (await session.execute(all_assigned_stmt)).scalars().all()
            assigned_other = sum(
                (a.assigned_quantity for a in all_assignments if a.mandate_id != mandate_id),
                Decimal("0"),
            )

            available_qty = max(Decimal("0"), total_qty - assigned_other)
            if assigned_quantity > available_qty:
                raise ValueError(
                    f"Cannot assign {assigned_quantity} units; only {available_qty} units available"
                )

            if existing:
                existing.assigned_quantity = assigned_quantity
                existing.notes = notes
                await session.flush()
                return existing
            else:
                assignment = CapitalAssignment(
                    user_id=user_id,
                    mandate_id=mandate_id,
                    resource_type=ResourceAssignmentType.ASSET,
                    asset_id=asset_id,
                    assigned_quantity=assigned_quantity,
                    assigned_amount=Decimal("0"),
                    notes=notes,
                )
                session.add(assignment)
                await session.flush()
                return assignment

        elif resource_type == ResourceAssignmentType.CASH_ACCOUNT:
            if not cash_account_id:
                raise ValueError("cash_account_id is required for CASH_ACCOUNT assignment")
            ca_stmt = select(CashAccount).where(
                CashAccount.id == cash_account_id,
                CashAccount.user_id == user_id,
            )
            cash_acc = (await session.execute(ca_stmt)).scalar_one_or_none()
            if not cash_acc:
                raise ValueError("Cash account not found or access denied")
            total_balance = max(Decimal("0"), cash_acc.balance)

            # Find existing assignment in this mandate
            existing_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == mandate_id,
                CapitalAssignment.cash_account_id == cash_account_id,
            )
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()

            # Sum assigned across other mandates
            all_assigned_stmt = select(CapitalAssignment).where(
                CapitalAssignment.user_id == user_id,
                CapitalAssignment.cash_account_id == cash_account_id,
            )
            all_assignments = (await session.execute(all_assigned_stmt)).scalars().all()
            assigned_other = sum(
                (a.assigned_amount for a in all_assignments if a.mandate_id != mandate_id),
                Decimal("0"),
            )

            available_cash = max(Decimal("0"), total_balance - assigned_other)
            if assigned_amount > available_cash:
                raise ValueError(
                    f"Cannot assign {assigned_amount}; only {available_cash} cash available"
                )

            if existing:
                existing.assigned_amount = assigned_amount
                existing.notes = notes
                await session.flush()
                return existing
            else:
                assignment = CapitalAssignment(
                    user_id=user_id,
                    mandate_id=mandate_id,
                    resource_type=ResourceAssignmentType.CASH_ACCOUNT,
                    cash_account_id=cash_account_id,
                    assigned_quantity=Decimal("0"),
                    assigned_amount=assigned_amount,
                    notes=notes,
                )
                session.add(assignment)
                await session.flush()
                return assignment
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")

    @staticmethod
    async def transfer_capital(
        session: AsyncSession,
        user_id: uuid.UUID,
        from_mandate_id: uuid.UUID,
        to_mandate_id: uuid.UUID,
        resource_type: ResourceAssignmentType,
        asset_id: Optional[uuid.UUID] = None,
        cash_account_id: Optional[uuid.UUID] = None,
        quantity: Optional[Decimal] = None,
        amount: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Virtual transfer between mandates.
        Modifies ONLY CapitalAssignment rows.
        Does NOT alter Asset, CashAccount, or Transaction tables.
        Net worth and cost basis remain 100% unchanged.
        """
        if from_mandate_id == to_mandate_id:
            raise ValueError("Source and destination mandates must be different")

        # Verify both mandates belong to user
        m_stmt = select(InvestmentMandate).where(
            InvestmentMandate.id.in_([from_mandate_id, to_mandate_id]),
            InvestmentMandate.user_id == user_id,
        )
        mandates = (await session.execute(m_stmt)).scalars().all()
        if len(mandates) != 2:
            raise ValueError("Both source and destination mandates must exist and belong to user")

        if resource_type == ResourceAssignmentType.ASSET:
            if not asset_id or quantity is None or quantity <= Decimal("0"):
                raise ValueError("asset_id and positive quantity are required")

            from_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == from_mandate_id,
                CapitalAssignment.asset_id == asset_id,
            )
            from_assign = (await session.execute(from_stmt)).scalar_one_or_none()
            if not from_assign or from_assign.assigned_quantity < quantity:
                avail = from_assign.assigned_quantity if from_assign else Decimal("0")
                raise ValueError(
                    f"Insufficient assigned quantity in source mandate. Required: {quantity}, Available: {avail}"
                )

            # Decrement from source
            from_assign.assigned_quantity -= quantity

            # Increment destination
            to_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == to_mandate_id,
                CapitalAssignment.asset_id == asset_id,
            )
            to_assign = (await session.execute(to_stmt)).scalar_one_or_none()
            if to_assign:
                to_assign.assigned_quantity += quantity
            else:
                to_assign = CapitalAssignment(
                    user_id=user_id,
                    mandate_id=to_mandate_id,
                    resource_type=ResourceAssignmentType.ASSET,
                    asset_id=asset_id,
                    assigned_quantity=quantity,
                    assigned_amount=Decimal("0"),
                )
                session.add(to_assign)

            await session.flush()
            return {
                "transferred_type": "ASSET",
                "asset_id": str(asset_id),
                "quantity": str(quantity),
                "from_mandate_id": str(from_mandate_id),
                "to_mandate_id": str(to_mandate_id),
            }

        elif resource_type == ResourceAssignmentType.CASH_ACCOUNT:
            if not cash_account_id or amount is None or amount <= Decimal("0"):
                raise ValueError("cash_account_id and positive amount are required")

            from_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == from_mandate_id,
                CapitalAssignment.cash_account_id == cash_account_id,
            )
            from_assign = (await session.execute(from_stmt)).scalar_one_or_none()
            if not from_assign or from_assign.assigned_amount < amount:
                avail = from_assign.assigned_amount if from_assign else Decimal("0")
                raise ValueError(
                    f"Insufficient assigned amount in source mandate. Required: {amount}, Available: {avail}"
                )

            from_assign.assigned_amount -= amount

            to_stmt = select(CapitalAssignment).where(
                CapitalAssignment.mandate_id == to_mandate_id,
                CapitalAssignment.cash_account_id == cash_account_id,
            )
            to_assign = (await session.execute(to_stmt)).scalar_one_or_none()
            if to_assign:
                to_assign.assigned_amount += amount
            else:
                to_assign = CapitalAssignment(
                    user_id=user_id,
                    mandate_id=to_mandate_id,
                    resource_type=ResourceAssignmentType.CASH_ACCOUNT,
                    cash_account_id=cash_account_id,
                    assigned_quantity=Decimal("0"),
                    assigned_amount=amount,
                )
                session.add(to_assign)

            await session.flush()
            return {
                "transferred_type": "CASH_ACCOUNT",
                "cash_account_id": str(cash_account_id),
                "amount": str(amount),
                "from_mandate_id": str(from_mandate_id),
                "to_mandate_id": str(to_mandate_id),
            }
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")

    @staticmethod
    async def reconcile_post_sell(
        session: AsyncSession,
        user_id: uuid.UUID,
        asset_id: uuid.UUID,
        mandate_id: Optional[uuid.UUID] = None,
        sold_quantity: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Reconciles capital assignments after a SELL transaction.
        Approved Product Rule:
        1. If SELL can be fully absorbed by UNASSIGNED units:
           - Reduce unassigned availability naturally
           - Mandate assignments remain completely unchanged
        2. If SELL exceeds unassigned units and transaction has NO explicit mandate attribution:
           - DO NOT proportionally alter mandate assignments!
           - DO NOT guess which mandate sold!
           - Preserve previous assignment state as inconsistent
           - Return ASSIGNMENT_REVIEW_REQUIRED state with available units, assigned units,
             over-assigned amount, and affected mandates.
        3. If transaction explicitly specifies the mandate:
           - Update that mandate assignment deterministically.
        """
        assets_with_stats = await list_assets_with_stats(session, user_id)
        match = next((item for item in assets_with_stats if item[0].id == asset_id), None)
        remaining_qty = Decimal(str(match[1]["total_quantity"])) if match else Decimal("0")

        assign_stmt = select(CapitalAssignment).where(
            CapitalAssignment.user_id == user_id,
            CapitalAssignment.asset_id == asset_id,
        )
        assignments = (await session.execute(assign_stmt)).scalars().all()
        total_assigned = sum((a.assigned_quantity for a in assignments), Decimal("0"))

        # Case 1: Explicit Mandate Attribution
        if mandate_id is not None and sold_quantity is not None and sold_quantity > Decimal("0"):
            target_assign = next((a for a in assignments if a.mandate_id == mandate_id), None)
            if target_assign:
                deducted = min(target_assign.assigned_quantity, sold_quantity)
                target_assign.assigned_quantity -= deducted
                await session.flush()
                new_total_assigned = sum((a.assigned_quantity for a in assignments), Decimal("0"))
                over_assigned = max(Decimal("0"), new_total_assigned - remaining_qty)
                return {
                    "reconciled": True,
                    "status": "CONSISTENT" if over_assigned == Decimal("0") else "ASSIGNMENT_REVIEW_REQUIRED",
                    "action": "MANDATE_ASSIGNMENT_DEDUCTED",
                    "mandate_id": str(mandate_id),
                    "deducted_quantity": str(deducted),
                    "available_units": str(remaining_qty),
                    "currently_assigned_units": str(new_total_assigned),
                    "over_assigned_amount": str(over_assigned),
                }

        # Case 2: Unattributed Sale - Fully absorbed by unassigned units
        if total_assigned <= remaining_qty:
            return {
                "reconciled": True,
                "status": "CONSISTENT",
                "action": "NONE",
                "available_units": str(remaining_qty),
                "currently_assigned_units": str(total_assigned),
                "unassigned_units": str(remaining_qty - total_assigned),
                "over_assigned_amount": "0.00",
                "affected_mandates": [],
            }

        # Case 3: Unattributed Sale - Exceeds unassigned units. DO NOT guess, DO NOT alter!
        over_assigned = total_assigned - remaining_qty
        affected_mandates = []
        for a in assignments:
            m = (await session.execute(select(InvestmentMandate).where(InvestmentMandate.id == a.mandate_id))).scalar_one_or_none()
            affected_mandates.append({
                "mandate_id": str(a.mandate_id),
                "mandate_name": m.name if m else "Unknown",
                "assigned_quantity": str(a.assigned_quantity),
            })

        return {
            "reconciled": False,
            "status": "ASSIGNMENT_REVIEW_REQUIRED",
            "action": "REVIEW_REQUIRED",
            "asset_id": str(asset_id),
            "available_units": str(remaining_qty),
            "currently_assigned_units": str(total_assigned),
            "over_assigned_amount": str(over_assigned),
            "affected_mandates": affected_mandates,
        }

    @staticmethod
    async def resolve_assignment_review(
        session: AsyncSession,
        user_id: uuid.UUID,
        asset_id: uuid.UUID,
        mandate_adjustments: Dict[str, Decimal],
    ) -> Dict[str, Any]:
        """User explicitly decides which mandate(s) absorb the over-assigned sold units."""
        assets_with_stats = await list_assets_with_stats(session, user_id)
        match = next((item for item in assets_with_stats if item[0].id == asset_id), None)
        remaining_qty = Decimal(str(match[1]["total_quantity"])) if match else Decimal("0")

        assign_stmt = select(CapitalAssignment).where(
            CapitalAssignment.user_id == user_id,
            CapitalAssignment.asset_id == asset_id,
        )
        assignments = (await session.execute(assign_stmt)).scalars().all()

        for m_id_str, new_qty in mandate_adjustments.items():
            m_uuid = uuid.UUID(str(m_id_str))
            target = next((a for a in assignments if a.mandate_id == m_uuid), None)
            if target:
                target.assigned_quantity = Decimal(str(new_qty))

        new_total_assigned = sum((a.assigned_quantity for a in assignments), Decimal("0"))
        if new_total_assigned > remaining_qty:
            raise ValueError(
                f"Total assigned ({new_total_assigned}) still exceeds available units ({remaining_qty})"
            )

        await session.flush()
        return {
            "status": "CONSISTENT",
            "action": "RESOLVED",
            "available_units": str(remaining_qty),
            "currently_assigned_units": str(new_total_assigned),
            "unassigned_units": str(remaining_qty - new_total_assigned),
            "over_assigned_amount": "0.00",
        }

    @staticmethod
    async def delete_assignment(
        session: AsyncSession,
        user_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> bool:
        stmt = delete(CapitalAssignment).where(
            CapitalAssignment.id == assignment_id,
            CapitalAssignment.user_id == user_id,
        )
        res = await session.execute(stmt)
        await session.flush()
        return res.rowcount > 0

    @staticmethod
    async def get_unassigned_resources(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Returns the unassigned capital breakdown for assets and cash accounts."""
        # Assets
        assets_with_stats = await list_assets_with_stats(session, user_id)
        assign_stmt = select(CapitalAssignment).where(CapitalAssignment.user_id == user_id)
        all_assignments = (await session.execute(assign_stmt)).scalars().all()

        asset_results = []
        for asset, stats in assets_with_stats:
            total_qty = Decimal(str(stats["total_quantity"]))
            assigned = sum(
                (a.assigned_quantity for a in all_assignments if a.asset_id == asset.id),
                Decimal("0"),
            )
            if assigned > total_qty:
                unassigned = Decimal("0")
                over_assigned = assigned - total_qty
                rec_status = "ASSIGNMENT_REVIEW_REQUIRED"
            else:
                unassigned = total_qty - assigned
                over_assigned = Decimal("0")
                rec_status = "CONSISTENT"

            asset_results.append({
                "asset_id": str(asset.id),
                "symbol": asset.symbol,
                "name": asset.name,
                "total_quantity": str(total_qty),
                "assigned_quantity": str(assigned),
                "unassigned_quantity": str(unassigned),
                "over_assigned_amount": str(over_assigned),
                "reconciliation_status": rec_status,
                "currency": asset.current_price_currency or "TRY",
            })

        # Cash Accounts
        cash_stmt = select(CashAccount).where(CashAccount.user_id == user_id)
        cash_accounts = (await session.execute(cash_stmt)).scalars().all()

        cash_results = []
        for cash in cash_accounts:
            total_bal = cash.balance
            assigned = sum(
                (a.assigned_amount for a in all_assignments if a.cash_account_id == cash.id),
                Decimal("0"),
            )
            if assigned > total_bal:
                unassigned = Decimal("0")
                over_assigned = assigned - total_bal
                rec_status = "ASSIGNMENT_REVIEW_REQUIRED"
            else:
                unassigned = total_bal - assigned
                over_assigned = Decimal("0")
                rec_status = "CONSISTENT"

            cash_results.append({
                "cash_account_id": str(cash.id),
                "currency": cash.currency,
                "total_balance": str(total_bal),
                "assigned_amount": str(assigned),
                "unassigned_amount": str(unassigned),
                "over_assigned_amount": str(over_assigned),
                "reconciliation_status": rec_status,
            })

        return {
            "assets": asset_results,
            "cash_accounts": cash_results,
        }
