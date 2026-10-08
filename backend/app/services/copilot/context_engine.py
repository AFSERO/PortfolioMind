"""Dedicated Context Engine for PortfolioMind Copilot.

Selects bounded, relevant, high-precedence structured context based on intent and entities,
enforcing strict source-of-truth precedence and tracking detailed provenance for every item.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.briefing import BriefingItem
from app.models.copilot import CopilotMessage
from app.models.decision_log import DecisionLogEntry
from app.models.discovery import DiscoveryCandidate
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, IntelligenceReview
from app.models.opportunity import WatchlistItem
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.copilot import (
    ContextGroup,
    ContextProvenanceItem,
    IntentResult,
    IntentType,
)
from app.services.copilot.holding_resolver import HoldingResolver
from app.services.dashboard import _load_assets_with_stats, get_summary


@dataclass
class ContextItem:
    """An individual piece of structured evidence or state."""

    source_type: str
    source_id: Optional[str]
    title: str
    content: dict[str, Any]
    precedence: int  # 1 = highest (database state), 6 = lowest (legacy docs)
    updated_at: Optional[str] = None
    freshness: Optional[str] = None  # e.g. "CURRENT", "RECENT", "HISTORICAL", "STALE"

    def to_provenance(self) -> ContextProvenanceItem:
        return ContextProvenanceItem(
            source_type=self.source_type,
            source_id=self.source_id,
            title=self.title,
            updated_at=self.updated_at,
            freshness=self.freshness,
        )


@dataclass
class ContextBundle:
    """Bounded, ordered context payload delivered to Copilot Prompt Orchestrator."""

    items: List[ContextItem] = field(default_factory=list)
    provenance: List[ContextProvenanceItem] = field(default_factory=list)

    def add(self, item: ContextItem) -> None:
        self.items.append(item)
        self.provenance.append(item.to_provenance())

    def sort_by_precedence(self) -> None:
        """Enforce canonical source-of-truth precedence (lower rank number = higher precedence)."""
        self.items.sort(key=lambda x: x.precedence)

    def to_context_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary partitioned by source type."""
        result: dict[str, Any] = {}
        for it in self.items:
            key = it.source_type.lower()
            if key not in result:
                result[key] = []
            result[key].append({
                "title": it.title,
                "source_id": it.source_id,
                "freshness": it.freshness,
                "updated_at": it.updated_at,
                "data": it.content,
            })
        return result


class CopilotContextEngine:
    """Builds bounded ContextBundles tailored specifically to user queries."""

    @classmethod
    async def build_context(
        cls,
        db: AsyncSession,
        user_id: UUID,
        intent: IntentResult,
        entities: dict[str, Any],
        current_page_context: Optional[dict[str, Any]] = None,
        recent_messages: Optional[List[CopilotMessage]] = None,
        raw_user_message: Optional[str] = None,
    ) -> ContextBundle:
        bundle = ContextBundle()

        # ---------------------------------------------------------------------
        # Precedence Hierarchy (Lower number = Higher authority):
        # 1. Current Structured Database State (Holdings, Instrument, Stats)
        # 2. Structured Investment Policy / User Profile
        # 3. Current Research / Thesis State (InstrumentIntelligenceState, Reviews)
        # 4. Decision Log (DecisionLogEntry)
        # 5. Conversation Context (CopilotMessage)
        # 6. Legacy / Historical Documents
        # ---------------------------------------------------------------------

        req_groups = set(intent.requires_context)

        # 1. Load User Profile if requested or general
        user_res = await db.execute(select(User).where(User.id == user_id))
        current_user = user_res.scalar_one_or_none()
        base_currency = getattr(current_user, "base_currency", "TRY") if current_user else "TRY"

        # 1. Load User Profile & Investor Profile if requested
        from app.services.investor_profile.profile_service import InvestorProfileService
        profile_data = await InvestorProfileService.get_current_profile(db, user_id)

        if ContextGroup.USER_PROFILE.value in req_groups:
            profile_content = {
                "display_name": getattr(current_user, "display_name", None),
                "base_currency": base_currency,
                "has_investor_profile": bool(profile_data and profile_data.get("version_number")),
                "version_number": profile_data.get("version_number") if profile_data else None,
                "completeness_overall_pct": profile_data.get("completeness_overall_pct", 0.0) if profile_data else 0.0,
                "analysis_readiness": profile_data.get("analysis_readiness", {}) if profile_data else {},
                "goals": profile_data.get("goals", {}) if profile_data else {},
                "risk": profile_data.get("risk", {}) if profile_data else {},
                "preferences": profile_data.get("preferences", {}) if profile_data else {},
                "contradictions_and_issues": profile_data.get("issues", []) if profile_data else [],
            }
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.USER_PROFILE.value,
                    source_id=str(user_id),
                    title="User & Investor Profile",
                    content=profile_content,
                    precedence=2,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

        if ContextGroup.INVESTMENT_POLICY.value in req_groups:
            policy_content = {
                "has_policy": bool(profile_data and profile_data.get("policy")),
                "policy": profile_data.get("policy", {}) if profile_data else {},
                "restriction_topics": profile_data.get("policy", {}).get("restriction_topics", []) if profile_data else [],
                "constraints": profile_data.get("policy", {}).get("constraints", []) if profile_data else [],
                "allocations": profile_data.get("policy", {}).get("allocations", []) if profile_data else [],
                "leverage_stance": profile_data.get("policy", {}).get("leverage_stance") if profile_data else None,
                "rebalance_triggers": profile_data.get("policy", {}).get("rebalance_triggers", []) if profile_data else [],
            }
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.INVESTMENT_POLICY.value,
                    source_id=f"policy_{user_id}",
                    title="Investment Policy Statement (IPS)",
                    content=policy_content,
                    precedence=2,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )


        # 2. Portfolio Summary & Holdings
        load_portfolio = (
            ContextGroup.PORTFOLIO_SUMMARY.value in req_groups
            or ContextGroup.PORTFOLIO_HOLDINGS.value in req_groups
            or intent.intent == IntentType.PORTFOLIO_ANALYSIS
        )
        if load_portfolio:
            summary = await get_summary(db, user_id, base_currency=base_currency)
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.PORTFOLIO_SUMMARY.value,
                    source_id="portfolio_summary",
                    title="Current Portfolio Summary",
                    content=summary,
                    precedence=1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

            pairs = await _load_assets_with_stats(db, user_id)
            holdings_data = []
            owned_instrument_ids: list[UUID] = []
            for asset, stats in pairs:
                owned_instrument_ids.append(asset.instrument_id)
                holdings_data.append({
                    "asset_id": str(asset.id),
                    "instrument_id": str(asset.instrument_id) if asset.instrument_id else None,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_type": asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
                    "total_quantity": float(stats["total_quantity"]),
                    "current_price": float(asset.current_price) if asset.current_price is not None else None,
                    "currency": asset.current_price_currency or stats.get("avg_cost_currency"),
                    "avg_cost": float(stats["avg_cost"]) if stats["avg_cost"] is not None else None,
                    "total_cost": float(stats["total_cost"]) if stats["total_cost"] is not None else None,
                    "unrealized_pl": float(stats["unrealized_pl"]) if stats["unrealized_pl"] is not None else None,
                })

            bundle.add(
                ContextItem(
                    source_type=ContextGroup.PORTFOLIO_HOLDINGS.value,
                    source_id="portfolio_holdings",
                    title="Current Portfolio Holdings",
                    content={"holdings": holdings_data, "count": len(holdings_data)},
                    precedence=1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

            # If portfolio analysis, attach intelligence states for owned instruments
            if intent.intent == IntentType.PORTFOLIO_ANALYSIS and owned_instrument_ids:
                states_res = await db.execute(
                    select(InstrumentIntelligenceState, Instrument)
                    .join(Instrument, InstrumentIntelligenceState.instrument_id == Instrument.id)
                    .where(InstrumentIntelligenceState.instrument_id.in_(owned_instrument_ids))
                )
                for state, inst in states_res.all():
                    bundle.add(
                        ContextItem(
                            source_type=ContextGroup.INTELLIGENCE_STATE.value,
                            source_id=str(state.id),
                            title=f"{inst.symbol} Intelligence",
                            content={
                                "symbol": inst.symbol,
                                "thesis_status": state.thesis_status.value if state.thesis_status else None,
                                "valuation_status": state.valuation_status.value if state.valuation_status else None,
                                "technical_status": state.technical_status.value if state.technical_status else None,
                                "recommendation": state.recommendation.value if state.recommendation else None,
                                "human_brief": state.human_brief,
                                "last_review_at": state.last_review_at.isoformat() if state.last_review_at else None,
                            },
                            precedence=3,
                            updated_at=state.updated_at.isoformat() if state.updated_at else None,
                            freshness="CURRENT" if state.last_review_at else "RECENT",
                        )
                    )

        # ---------------------------------------------------------------------
        # 3. Targeted Asset / Holding Resolution (Strict filtering)
        # ---------------------------------------------------------------------
        resolved_holding = None
        if entities.get("symbol"):
            resolved_holding = await HoldingResolver.resolve(
                db=db,
                user_id=user_id,
                query=str(entities["symbol"]),
                current_page_context=current_page_context,
            )

        if not resolved_holding or not resolved_holding.is_resolved:
            search_query = (
                raw_user_message
                or (current_page_context.get("symbol") if current_page_context else "")
                or ""
            )
            if search_query:
                resolved_holding = await HoldingResolver.resolve(
                    db=db,
                    user_id=user_id,
                    query=search_query,
                    current_page_context=current_page_context,
                )

        if not resolved_holding:
            from app.services.copilot.holding_resolver import ResolvedHolding
            resolved_holding = ResolvedHolding(match_type="NONE", confidence=0.0)

        target_inst: Optional[Instrument] = None
        target_asset: Optional[Asset] = None

        if resolved_holding.is_resolved:
            target_inst = resolved_holding.instrument
            target_asset = resolved_holding.asset

            # 3a. If user owns this holding, attach EXISTING_HOLDING and PRICE_CONTEXT
            if target_asset and resolved_holding.stats:
                stats = resolved_holding.stats
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.EXISTING_HOLDING.value,
                        source_id=str(target_asset.id),
                        title=f"Existing Position: {target_asset.name} ({target_asset.symbol or 'N/A'})",
                        content={
                            "asset_id": str(target_asset.id),
                            "symbol": target_asset.symbol,
                            "name": target_asset.name,
                            "asset_type": target_asset.asset_type.value if hasattr(target_asset.asset_type, "value") else str(target_asset.asset_type),
                            "current_quantity": float(stats.quantity),
                            "current_price": float(stats.current_price) if stats.current_price is not None else None,
                            "currency": stats.currency,
                            "avg_cost": float(stats.avg_cost) if stats.avg_cost is not None else None,
                            "total_cost": float(stats.total_cost) if stats.total_cost is not None else None,
                            "unrealized_pl": float(stats.unrealized_pl) if stats.unrealized_pl is not None else None,
                        },
                        precedence=1,
                        updated_at=target_asset.updated_at.isoformat() if target_asset.updated_at else datetime.now(timezone.utc).isoformat(),
                        freshness="CURRENT",
                    )
                )

                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.PRICE_CONTEXT.value,
                        source_id=f"price_{target_asset.id}",
                        title=f"Price Context: {target_asset.name} ({target_asset.symbol or 'N/A'})",
                        content={
                            "current_unit_price": float(stats.current_price) if stats.current_price is not None else None,
                            "total_market_value": float(stats.current_value) if stats.current_value is not None else None,
                            "currency": stats.currency,
                            "price_per_unit_meaning": "Current market price per single unit / coin / share. NOT the total position value.",
                            "total_market_value_meaning": f"Total market valuation across all currently held {float(stats.quantity)} units.",
                            "semantic_breakdown": [v.model_dump(mode="json") for v in resolved_holding.semantic_values],
                            "is_manual_price": target_asset.is_manual_price,
                        },
                        precedence=1,
                        updated_at=datetime.now(timezone.utc).isoformat(),
                        freshness="CURRENT",
                    )
                )

                # Recent transactions for this asset
                tx_res = await db.execute(
                    select(Transaction)
                    .where(Transaction.asset_id == target_asset.id)
                    .order_by(desc(Transaction.transaction_date))
                    .limit(3)
                )
                recent_txns = tx_res.scalars().all()
                if recent_txns:
                    bundle.add(
                        ContextItem(
                            source_type=ContextGroup.ASSET.value,
                            source_id=f"txns_{target_asset.id}",
                            title=f"Recent Transactions: {target_asset.name}",
                            content={
                                "transactions": [
                                    {
                                        "id": str(t.id),
                                        "type": t.transaction_type.value if hasattr(t.transaction_type, "value") else str(t.transaction_type),
                                        "quantity": float(t.quantity),
                                        "price_per_unit": float(t.price_per_unit),
                                        "total_amount": float(t.total_amount),
                                        "currency": t.transaction_currency,
                                        "date": t.transaction_date.isoformat(),
                                        "affects_cash": t.affects_cash,
                                    }
                                    for t in recent_txns
                                ]
                            },
                            precedence=2,
                            freshness="RECENT",
                        )
                    )

            # 3b. Instrument Record
            if target_inst:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.INSTRUMENT.value,
                        source_id=str(target_inst.id),
                        title=f"{target_inst.symbol or target_inst.name} Instrument",
                        content={
                            "instrument_id": str(target_inst.id),
                            "symbol": target_inst.symbol,
                            "name": target_inst.name,
                            "asset_type": target_inst.asset_type.value if hasattr(target_inst.asset_type, "value") else str(target_inst.asset_type),
                            "currency": target_inst.currency,
                            "exchange": getattr(target_inst, "exchange", None),
                        },
                        precedence=1,
                        updated_at=target_inst.updated_at.isoformat() if target_inst.updated_at else None,
                        freshness="CURRENT",
                    )
                )
        elif resolved_holding.ambiguous_candidates:
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.EXISTING_HOLDING.value,
                    source_id="ambiguous_candidates",
                    title="Ambiguous Holding Candidates",
                    content={"candidates": resolved_holding.ambiguous_candidates},
                    precedence=1,
                    freshness="CURRENT",
                )
            )

        # Fallback to direct symbol lookup if HoldingResolver didn't resolve an instrument
        if not target_inst:
            sym_candidate = entities.get("symbol") or (current_page_context.get("symbol") if current_page_context else None)
            if sym_candidate:
                inst_res = await db.execute(
                    select(Instrument).where(Instrument.symbol == str(sym_candidate).upper())
                )
                target_inst = inst_res.scalar_one_or_none()
                if target_inst:
                    bundle.add(
                        ContextItem(
                            source_type=ContextGroup.INSTRUMENT.value,
                            source_id=str(target_inst.id),
                            title=f"{target_inst.symbol} Instrument",
                            content={
                                "symbol": target_inst.symbol,
                                "name": target_inst.name,
                                "asset_type": target_inst.asset_type.value if hasattr(target_inst.asset_type, "value") else str(target_inst.asset_type),
                                "currency": target_inst.currency,
                                "exchange": getattr(target_inst, "exchange", None),
                            },
                            precedence=1,
                            updated_at=target_inst.updated_at.isoformat() if target_inst.updated_at else None,
                            freshness="CURRENT",
                        )
                    )

        # 3c. If intelligence/research requested for this instrument, attach intelligence & reviews
        if target_inst and (
            ContextGroup.INTELLIGENCE_STATE.value in req_groups
            or intent.intent in (IntentType.ASSET_ANALYSIS, IntentType.RESEARCH_REQUEST)
        ):
            inst_id = target_inst.id

            # Watchlist status
            wl_res = await db.execute(
                select(WatchlistItem).where(
                    WatchlistItem.user_id == user_id,
                    WatchlistItem.instrument_id == inst_id,
                )
            )
            wl_item = wl_res.scalar_one_or_none()
            if wl_item:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.WATCHLIST.value,
                        source_id=str(wl_item.id),
                        title=f"{target_inst.symbol} Watchlist Entry",
                        content={
                            "research_stage": wl_item.research_stage.value if hasattr(wl_item.research_stage, "value") else str(wl_item.research_stage),
                            "priority": wl_item.priority.value if hasattr(wl_item.priority, "value") else str(wl_item.priority),
                            "why_interesting": wl_item.why_interesting,
                            "target_entry_min": float(wl_item.target_entry_min) if wl_item.target_entry_min else None,
                            "target_entry_max": float(wl_item.target_entry_max) if wl_item.target_entry_max else None,
                            "key_catalyst": wl_item.key_catalyst,
                            "key_risk": wl_item.key_risk,
                        },
                        precedence=2,
                        updated_at=datetime.now(timezone.utc).isoformat(),
                        freshness="CURRENT",
                    )
                )

            # Discovery Provenance
            disc_res = await db.execute(
                select(DiscoveryCandidate).where(
                    DiscoveryCandidate.user_id == user_id,
                    DiscoveryCandidate.instrument_id == inst_id,
                ).order_by(desc(DiscoveryCandidate.created_at)).limit(1)
            )
            disc_item = disc_res.scalar_one_or_none()
            if disc_item:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.DISCOVERY_PROVENANCE.value,
                        source_id=str(disc_item.id),
                        title=f"{target_inst.symbol} Discovery Provenance",
                        content={
                            "primary_reason": disc_item.primary_reason,
                            "score_band": disc_item.score_band,
                            "candidate_state": disc_item.candidate_state.value if hasattr(disc_item.candidate_state, "value") else str(disc_item.candidate_state),
                            "signals": disc_item.signals,
                        },
                        precedence=3,
                        updated_at=disc_item.created_at.isoformat() if disc_item.created_at else None,
                        freshness="RECENT",
                    )
                )

            # Instrument Intelligence State
            state_res = await db.execute(
                select(InstrumentIntelligenceState).where(
                    InstrumentIntelligenceState.instrument_id == inst_id
                )
            )
            intel_state = state_res.scalar_one_or_none()
            if intel_state:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.INTELLIGENCE_STATE.value,
                        source_id=str(intel_state.id),
                        title=f"{target_inst.symbol} Intelligence",
                        content={
                            "thesis_status": intel_state.thesis_status.value if intel_state.thesis_status else None,
                            "valuation_status": intel_state.valuation_status.value if intel_state.valuation_status else None,
                            "technical_status": intel_state.technical_status.value if intel_state.technical_status else None,
                            "recommendation": intel_state.recommendation.value if intel_state.recommendation else None,
                            "human_brief": intel_state.human_brief,
                            "last_review_at": intel_state.last_review_at.isoformat() if intel_state.last_review_at else None,
                        },
                        precedence=3,
                        updated_at=intel_state.updated_at.isoformat() if intel_state.updated_at else None,
                        freshness="CURRENT",
                    )
                )

            # Research History
            rev_res = await db.execute(
                select(IntelligenceReview).where(
                    IntelligenceReview.instrument_id == inst_id
                ).order_by(desc(IntelligenceReview.created_at)).limit(3)
            )
            reviews = rev_res.scalars().all()
            for rev in reviews:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.RESEARCH_HISTORY.value,
                        source_id=str(rev.id),
                        title=f"{target_inst.symbol} {rev.protocol.replace('-', ' ').title()}",
                        content={
                            "protocol": rev.protocol,
                            "run_type": rev.run_type,
                            "status": rev.status.value if hasattr(rev.status, "value") else str(rev.status),
                            "human_brief": rev.human_brief,
                            "confidence": rev.confidence,
                            "created_at": rev.created_at.isoformat() if rev.created_at else None,
                        },
                        precedence=3,
                        updated_at=rev.created_at.isoformat() if rev.created_at else None,
                        freshness="RECENT",
                    )
                )

            # Decision Log entries
            dec_res = await db.execute(
                select(DecisionLogEntry).where(
                    DecisionLogEntry.user_id == user_id,
                    DecisionLogEntry.instrument_id == inst_id,
                ).order_by(desc(DecisionLogEntry.occurred_at)).limit(5)
            )
            decisions = dec_res.scalars().all()
            if decisions:
                bundle.add(
                    ContextItem(
                        source_type=ContextGroup.DECISION_HISTORY.value,
                        source_id=f"decisions_{inst_id}",
                        title=f"{len(decisions)} relevant decision{'s' if len(decisions) > 1 else ''}",
                        content={
                            "count": len(decisions),
                            "entries": [
                                {
                                    "id": str(d.id),
                                    "title": d.title,
                                    "summary": d.summary,
                                    "user_rationale": d.user_rationale,
                                    "event_type": d.event_type.value if hasattr(d.event_type, "value") else str(d.event_type),
                                    "occurred_at": d.occurred_at.isoformat() if d.occurred_at else None,
                                }
                                for d in decisions
                            ],
                        },
                        precedence=4,
                        updated_at=decisions[0].occurred_at.isoformat() if decisions[0].occurred_at else None,
                        freshness="HISTORICAL",
                    )
                )

        # 3d. Financial Context, Goals, Mandates, and Financial Intelligence
        if (
            ContextGroup.FINANCIAL_CONTEXT.value in req_groups
            or intent.intent in (IntentType.FINANCIAL_ANALYSIS, IntentType.GOAL_PROGRESS, IntentType.FINANCIAL_DISCOVERY)
        ):
            from app.services.financial_context.context_service import FinancialContextService
            fc = await FinancialContextService.get_or_create(db, user_id)
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.FINANCIAL_CONTEXT.value,
                    source_id=str(fc.id),
                    title="User Financial Context",
                    content={
                        "financial_scope": fc.financial_scope.value if hasattr(fc.financial_scope, "value") else str(fc.financial_scope),
                        "planning_currency": fc.planning_currency,
                        "spending_currencies": fc.spending_currencies,
                        "monthly_net_income": float(fc.monthly_net_income) if fc.monthly_net_income is not None else None,
                        "income_sources": fc.income_sources,
                        "income_stability": fc.income_stability.value if hasattr(fc.income_stability, "value") else str(fc.income_stability),
                        "monthly_essential_expenses": float(fc.monthly_essential_expenses) if fc.monthly_essential_expenses is not None else None,
                        "monthly_discretionary_expenses": float(fc.monthly_discretionary_expenses) if fc.monthly_discretionary_expenses is not None else None,
                        "non_debt_obligations": fc.non_debt_obligations,
                        "dependents_count": fc.dependents_count,
                        "coverage_declarations": fc.coverage_declarations,
                        "last_confirmed_at": fc.last_confirmed_at.isoformat() if fc.last_confirmed_at else None,
                    },
                    precedence=2,
                    updated_at=fc.updated_at.isoformat() if fc.updated_at else None,
                    freshness="CURRENT",
                )
            )

        if (
            ContextGroup.FINANCIAL_GOALS.value in req_groups
            or ContextGroup.MANDATES.value in req_groups
            or intent.intent in (IntentType.FINANCIAL_ANALYSIS, IntentType.GOAL_PROGRESS, IntentType.FINANCIAL_DISCOVERY)
        ):
            from app.services.financial_context.goals_service import GoalsService
            goals_data = await GoalsService.list_goals(db, user_id)
            mandates_data = await GoalsService.list_mandates(db, user_id)

            def _serialize_dec(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, dict):
                    return {k: _serialize_dec(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_serialize_dec(x) for x in obj]
                return obj

            bundle.add(
                ContextItem(
                    source_type=ContextGroup.FINANCIAL_GOALS.value,
                    source_id=f"goals_{user_id}",
                    title="Financial Goals",
                    content=_serialize_dec({"goals": goals_data, "count": len(goals_data)}),
                    precedence=2,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

            bundle.add(
                ContextItem(
                    source_type=ContextGroup.MANDATES.value,
                    source_id=f"mandates_{user_id}",
                    title="Investment Mandates",
                    content=_serialize_dec({"mandates": mandates_data, "count": len(mandates_data)}),
                    precedence=2,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

        if (
            ContextGroup.FINANCIAL_INTELLIGENCE.value in req_groups
            or intent.intent in (IntentType.FINANCIAL_ANALYSIS, IntentType.FINANCIAL_DISCOVERY)
        ):
            from app.services.financial_context.intelligence_service import FinancialIntelligenceService
            intel_summary = await FinancialIntelligenceService.compute_financial_intelligence(db, user_id)

            def _serialize(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, dict):
                    return {k: _serialize(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_serialize(x) for x in obj]
                return obj

            bundle.add(
                ContextItem(
                    source_type=ContextGroup.FINANCIAL_INTELLIGENCE.value,
                    source_id=f"intelligence_{user_id}",
                    title="Derived Financial Intelligence",
                    content=_serialize(intel_summary),
                    precedence=1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

        # 4. Recent Conversation Context (Precedence 5)
        if recent_messages:
            conv_msgs = []
            for msg in recent_messages[-6:]:  # Keep recent context bounded
                conv_msgs.append({
                    "role": msg.role,
                    "content": msg.raw_content,
                })
            bundle.add(
                ContextItem(
                    source_type=ContextGroup.RECENT_CONVERSATION.value,
                    source_id="recent_conversation",
                    title="Recent Conversation",
                    content={"messages": conv_msgs},
                    precedence=5,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    freshness="CURRENT",
                )
            )

        # Sort bundle items by canonical precedence
        bundle.sort_by_precedence()
        return bundle

