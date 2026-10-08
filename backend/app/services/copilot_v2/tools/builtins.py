"""Built-in safe READ_ONLY tools for Copilot V2.

Implements the four foundational tools required for Phase 1:
1. get_portfolio_summary()
2. get_holdings()
3. get_asset_context(symbol)
4. get_briefing(scope?, symbol?, period?)

Invariants:
- All tools are strictly user-scoped (filtered by user_id).
- No raw SQL access or database mutation.
- Outputs are bounded and structured to avoid overflowing context windows.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.briefing import BriefingItem, BriefingRun
from app.models.decision_log import DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, IntelligenceReview
from app.models.user import User
from app.services.asset import list_assets_with_stats
from app.services.briefing import get_latest_briefing_run, resolve_item_attention_states
from app.services.copilot.holding_resolver import HoldingResolver
from app.services.copilot_v2.entity_resolver import EntityResolver
from app.services.copilot_v2.tools.registry import (
    ToolClassification,
    ToolDefinition,
    ToolRegistry,
)
from app.services.copilot_v2.tools.web_research import (
    fetch_web_page_handler,
    search_news_handler,
    search_web_handler,
)
from app.services.dashboard import get_summary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: get_portfolio_summary
# ---------------------------------------------------------------------------


async def get_portfolio_summary_handler(
    db: AsyncSession,
    user_id: UUID,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve high-level portfolio totals, allocation overview, and performance metrics."""
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    base_currency = getattr(user, "base_currency", "TRY") if user else "TRY"

    summary = await get_summary(db, user_id, base_currency=base_currency)

    # Return bounded, compact representation
    by_type = []
    for item in summary.get("by_type_summary", []):
        by_type.append({
            "asset_type": str(item.get("asset_type")),
            "value": float(item.get("value", 0.0)),
            "percentage": float(item.get("percentage", 0.0)),
        })

    best = summary.get("best_performer")
    worst = summary.get("worst_performer")

    return {
        "status": "success",
        "base_currency": summary.get("base_currency", base_currency),
        "total_value": float(summary.get("total_value", 0.0)),
        "net_worth": float(summary.get("net_worth", 0.0)),
        "total_cost": float(summary.get("total_cost", 0.0)),
        "total_pl": float(summary.get("total_pl", 0.0)),
        "total_pl_pct": float(summary.get("total_pl_pct", 0.0)),
        "unrealized_pl": float(summary.get("unrealized_pl", 0.0)),
        "realized_pl": float(summary.get("realized_pl", 0.0)),
        "total_cash": float(summary.get("total_cash", 0.0)),
        "total_liabilities": float(summary.get("total_liabilities", 0.0)),
        "asset_count": int(summary.get("asset_count", 0)),
        "liability_count": int(summary.get("liability_count", 0)),
        "by_type_summary": by_type,
        "best_performer": {
            "symbol": best.get("symbol"),
            "name": best.get("name"),
            "pl": float(best.get("pl", 0.0)),
            "pl_pct": float(best.get("pl_pct", 0.0)),
        } if best else None,
        "worst_performer": {
            "symbol": worst.get("symbol"),
            "name": worst.get("name"),
            "pl": float(worst.get("pl", 0.0)),
            "pl_pct": float(worst.get("pl_pct", 0.0)),
        } if worst else None,
    }


# ---------------------------------------------------------------------------
# Tool 2: get_holdings
# ---------------------------------------------------------------------------


async def get_holdings_handler(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 50,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve the bounded list of active positions/holdings owned by the user."""
    pairs = await list_assets_with_stats(db, user_id=user_id)
    holdings = []

    for asset, stats in pairs[:limit]:
        qty = float(stats.get("total_quantity", 0.0))
        price = float(asset.current_price) if asset.current_price is not None else None
        avg_cost = float(stats.get("avg_cost")) if stats.get("avg_cost") is not None else None
        total_cost = float(stats.get("total_cost")) if stats.get("total_cost") is not None else None
        market_val = (price * qty) if (price is not None and qty is not None) else None
        unrealized_pl = float(stats.get("unrealized_pl")) if stats.get("unrealized_pl") is not None else None

        holdings.append({
            "asset_id": str(asset.id),
            "instrument_id": str(asset.instrument_id) if asset.instrument_id else None,
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
            "quantity": qty,
            "current_price": price,
            "currency": asset.current_price_currency or stats.get("avg_cost_currency"),
            "avg_cost": avg_cost,
            "total_cost": total_cost,
            "market_value": market_val,
            "unrealized_pl": unrealized_pl,
        })

    return {
        "status": "success",
        "holdings": holdings,
        "total_count": len(pairs),
        "returned_count": len(holdings),
    }


# ---------------------------------------------------------------------------
# Tool 3: get_asset_context
# ---------------------------------------------------------------------------


async def get_asset_context_handler(
    db: AsyncSession,
    user_id: UUID,
    symbol: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve bounded asset context including identity, user holding, intelligence, and decisions."""
    clean_symbol = symbol.strip().upper()
    entity = await EntityResolver.resolve(
        db=db,
        query=clean_symbol,
        user_id=user_id,
    )

    if entity.is_ambiguous:
        return {
            "status": "ambiguous",
            "query_symbol": clean_symbol,
            "message": entity.warning,
            "candidates": entity.ambiguous_candidates,
            "instrument": None,
            "user_holding": {"is_owned": False, "note": "Ambiguous instrument match."},
            "intelligence_state": None,
            "recent_reviews": [],
            "recent_decisions": [],
        }

    result_data: Dict[str, Any] = {
        "status": "success",
        "query_symbol": clean_symbol,
        "match_type": entity.match_type,
        "instrument": None,
        "user_holding": None,
        "intelligence_state": None,
        "recent_reviews": [],
        "recent_decisions": [],
    }

    inst: Optional[Instrument] = entity.canonical_instrument
    if inst:
        result_data["instrument"] = {
            "id": str(inst.id),
            "symbol": inst.symbol,
            "name": inst.name,
            "asset_type": inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            "currency": inst.currency,
            "exchange": inst.exchange,
        }

    user_asset: Optional[Asset] = entity.asset

    if user_asset and entity.is_owned:
        # Load user-specific stats
        from app.services.asset import get_asset_with_stats
        pair = await get_asset_with_stats(db, user_asset.id, user_id=user_id)
        if pair:
            _, stats = pair
            qty = float(stats.get("total_quantity", 0.0))
            price = float(user_asset.current_price) if user_asset.current_price is not None else None
            avg_cost = float(stats.get("avg_cost")) if stats.get("avg_cost") is not None else None
            total_cost = float(stats.get("total_cost")) if stats.get("total_cost") is not None else None
            market_val = (price * qty) if (price is not None and qty is not None) else None
            unreal_pl = float(stats.get("unrealized_pl")) if stats.get("unrealized_pl") is not None else None

            result_data["user_holding"] = {
                "asset_id": str(user_asset.id),
                "is_owned": True,
                "quantity": qty,
                "current_price": price,
                "avg_cost": avg_cost,
                "total_cost": total_cost,
                "market_value": market_val,
                "unrealized_pl": unreal_pl,
            }
    else:
        result_data["user_holding"] = {
            "is_owned": False,
            "note": "User does not currently hold this asset in their portfolio.",
        }

    # Attach intelligence state if instrument is known
    if inst:
        st_stmt = select(InstrumentIntelligenceState).where(
            InstrumentIntelligenceState.instrument_id == inst.id
        ).limit(1)
        st_res = await db.execute(st_stmt)
        state = st_res.scalar_one_or_none()
        if state:
            result_data["intelligence_state"] = {
                "thesis_status": state.thesis_status.value if state.thesis_status else None,
                "valuation_status": state.valuation_status.value if state.valuation_status else None,
                "technical_status": state.technical_status.value if state.technical_status else None,
                "recommendation": state.recommendation.value if state.recommendation else None,
                "human_brief": state.human_brief,
                "last_review_at": state.last_review_at.isoformat() if state.last_review_at else None,
            }

        # Attach top 2 recent formal reviews
        rev_stmt = (
            select(IntelligenceReview)
            .where(IntelligenceReview.instrument_id == inst.id)
            .order_by(IntelligenceReview.created_at.desc())
            .limit(2)
        )
        rev_res = await db.execute(rev_stmt)
        reviews = rev_res.scalars().all()
        for rev in reviews:
            rec_val = None
            if isinstance(rev.machine_record, dict):
                rec_val = rev.machine_record.get("recommendation")
            elif hasattr(rev, "recommendation"):
                rec_obj = getattr(rev, "recommendation")
                rec_val = rec_obj.value if hasattr(rec_obj, "value") else str(rec_obj) if rec_obj else None

            result_data["recent_reviews"].append({
                "id": str(rev.id),
                "protocol_name": getattr(rev, "protocol", getattr(rev, "protocol_name", "review")),
                "recommendation": rec_val,
                "human_brief": rev.human_brief,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            })

        # Attach recent user decision logs strictly for this user and instrument
        dl_stmt = (
            select(DecisionLogEntry)
            .where(
                DecisionLogEntry.user_id == user_id,
                DecisionLogEntry.instrument_id == inst.id,
            )
            .order_by(DecisionLogEntry.occurred_at.desc())
            .limit(3)
        )
        dl_res = await db.execute(dl_stmt)
        decisions = dl_res.scalars().all()
        for dl in decisions:
            result_data["recent_decisions"].append({
                "id": str(dl.id),
                "event_type": dl.event_type.value if hasattr(dl.event_type, "value") else str(dl.event_type),
                "occurred_at": dl.occurred_at.isoformat() if dl.occurred_at else None,
                "title": getattr(dl, "title", ""),
                "summary": getattr(dl, "summary", ""),
                "user_rationale": getattr(dl, "user_rationale", None),
                "confidence": getattr(dl, "confidence", None),
                "expectation": getattr(dl, "expectation", None),
            })

    return result_data


# ---------------------------------------------------------------------------
# Tool 4: get_briefing
# ---------------------------------------------------------------------------


async def get_briefing_handler(
    db: AsyncSession,
    user_id: UUID,
    scope: Optional[str] = None,
    symbol: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 10,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Retrieve bounded briefing items for the user, with optional symbol/scope filtering."""
    # Retrieve user's latest briefing run
    stmt = (
        select(BriefingRun)
        .options(
            selectinload(BriefingRun.items).selectinload(BriefingItem.instrument)
        )
        .where(BriefingRun.user_id == user_id)
        .order_by(BriefingRun.generated_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    latest_run = res.scalar_one_or_none()

    items: List[BriefingItem] = []
    run_info = None

    if latest_run:
        run_info = {
            "run_id": str(latest_run.id),
            "generated_at": latest_run.generated_at.isoformat() if latest_run.generated_at else None,
            "status": latest_run.status,
            "items_shown": latest_run.items_shown,
        }
        all_items = latest_run.items or []

        # Filter by symbol if specified
        if symbol:
            clean_sym = symbol.strip().upper()
            entity = await EntityResolver.resolve(db=db, query=clean_sym, user_id=user_id)
            if entity.canonical_instrument_id:
                all_items = [
                    it for it in all_items
                    if it.instrument_id == entity.canonical_instrument_id
                    or (it.instrument and it.instrument.symbol and it.instrument.symbol.upper() == clean_sym)
                ]
            else:
                all_items = [
                    it for it in all_items
                    if it.instrument and it.instrument.symbol and it.instrument.symbol.upper() == clean_sym
                ]

        # Filter by scope if specified
        if scope:
            clean_scope = scope.strip().upper()
            all_items = [
                it for it in all_items
                if (hasattr(it, "scope") and str(it.scope).upper() == clean_scope)
                or (latest_run.scope and latest_run.scope.upper() == clean_scope)
            ]

        items = all_items[:limit]

    # Dynamically resolve attention states for the returned items
    attention_map: Dict[UUID, str] = {}
    if items:
        attention_map = await resolve_item_attention_states(db, user_id, items)

    serialized_items = []
    for it in items:
        serialized_items.append({
            "id": str(it.id),
            "symbol": it.instrument.symbol if it.instrument else None,
            "headline": it.headline,
            "summary": it.summary,
            "category": it.category.value if hasattr(it.category, "value") else str(it.category),
            "materiality": it.materiality.value if hasattr(it.materiality, "value") else str(it.materiality),
            "review_required": it.review_required,
            "recommended_review": (it.source_metadata or {}).get("recommended_review") if it.source_metadata else None,
            "attention_state": attention_map.get(it.id, "NONE"),
            "created_at": it.created_at.isoformat() if it.created_at else None,
        })

    return {
        "status": "success",
        "run": run_info,
        "items": serialized_items,
        "returned_count": len(serialized_items),
    }


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in safe read tools into the provided ToolRegistry."""
    registry.register(
        ToolDefinition(
            name="get_portfolio_summary",
            description=(
                "Retrieve user portfolio overview: total value, net worth, total P&L, "
                "cash balances, asset count, allocations, and top performers."
            ),
            parameters_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            classification=ToolClassification.READ_ONLY,
            handler=get_portfolio_summary_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_holdings",
            description="Retrieve active portfolio holdings/positions for the authenticated user.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of holdings to return (default: 50)",
                        "default": 50,
                    }
                },
                "required": [],
            },
            classification=ToolClassification.READ_ONLY,
            handler=get_holdings_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_asset_context",
            description=(
                "Retrieve comprehensive, bounded context for an asset by symbol: "
                "instrument identity, user's holding details (if owned), current price, "
                "thesis intelligence state, recent reviews, and recent decision log notes."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Asset or instrument ticker symbol (e.g. 'BTC', 'THYAO', 'AAPL')",
                    }
                },
                "required": ["symbol"],
            },
            classification=ToolClassification.READ_ONLY,
            handler=get_asset_context_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="get_briefing",
            description=(
                "Retrieve latest user intelligence briefing items, filtered optionally "
                "by symbol or scope, including attention status and recommended reviews."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Optional ticker symbol filter (e.g. 'THYAO')",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional briefing scope filter (e.g. 'PORTFOLIO', 'WATCHLIST')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum items to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
            classification=ToolClassification.READ_ONLY,
            handler=get_briefing_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="search_news",
            description=(
                "Search current public news, market developments, and announcements for an asset, fund, or query. "
                "Use when internal portfolio or briefing data is insufficient to establish why an asset moved, "
                "or when recent developments, news, or regulatory events are needed."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query keywords (e.g. 'THF fonu neden düştü', 'Apple earnings', 'BIST düşüş')",
                    },
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional relevant asset or ticker symbols for canonical name enrichment (e.g. ['THF'])",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days in the past to search (default: 7)",
                        "default": 7,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum news items to return (default: 5, max: 8)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            classification=ToolClassification.READ_ONLY,
            handler=search_news_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="search_web",
            description=(
                "Perform broader public web search for company or fund background, regulatory disclosures, "
                "or market events when search_news yields insufficient evidence."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query keywords",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum search results to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            classification=ToolClassification.READ_ONLY,
            handler=search_web_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="fetch_web_page",
            description=(
                "Fetch and read extracted text from a specific public article or news URL "
                "(obtained from search_news results) when snippets are insufficient to establish verified facts. "
                "Protected against private/internal network addresses."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Public HTTP or HTTPS URL to read (e.g. from search_news link)",
                    }
                },
                "required": ["url"],
            },
            classification=ToolClassification.READ_ONLY,
            handler=fetch_web_page_handler,
        )
    )

