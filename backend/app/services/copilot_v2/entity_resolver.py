"""Canonical Entity and Instrument Resolver for Copilot V2.

Guarantees the core data-integrity invariant:
  symbol / query
        ↓
  single canonical instrument_id
        ↓
  all downstream context (asset holding, intelligence, briefing, decision logs, web enrichment)

Invariants:
1. User-owned asset priority:
   - When user_id is provided, search user's Asset records first.
   - If owned and Asset.instrument_id is present, THAT instrument_id is the sole canonical identity.
2. Unowned fallback:
   - If not owned, query Instrument table by exact symbol (or .IS suffix).
   - If exactly 1 match, resolve as canonical instrument.
   - If multiple duplicate instruments match (ambiguous), do NOT silently pick an arbitrary
     row via .limit(1). Mark is_ambiguous=True with candidate details.
3. Downstream consistency:
   - All tools (get_asset_context, get_briefing, search_news, research) consume the same canonical entity.
4. Generic: No hardcoded symbols (works for THF, AAPL, BTC, THYAO, KCV, HALF, etc.).
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.instrument import Instrument
from app.services.copilot.holding_resolver import COMMODITY_ALIASES, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class ResolvedEntity:
    """Structured result of canonical entity resolution."""

    query: str
    symbol: str
    canonical_instrument_id: Optional[UUID] = None
    canonical_instrument: Optional[Instrument] = None
    canonical_name: Optional[str] = None
    asset: Optional[Asset] = None
    is_owned: bool = False
    is_ambiguous: bool = False
    ambiguous_candidates: List[Dict[str, Any]] = field(default_factory=list)
    match_type: str = "NONE"
    warning: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """True if a single non-ambiguous canonical instrument or asset was found."""
        return not self.is_ambiguous and (
            self.canonical_instrument_id is not None or self.asset is not None
        )


class EntityResolver:
    """Centralized, deterministic entity resolver for Copilot V2."""

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        query: str,
        user_id: Optional[UUID] = None,
    ) -> ResolvedEntity:
        """Execute deterministic, invariant-backed entity resolution."""
        raw_query = query.strip()
        clean_symbol = raw_query.upper()
        norm_query = normalize_text(raw_query)

        # ---------------------------------------------------------------------
        # Stage 1: Authenticated User Asset Lookup (Highest Priority)
        # ---------------------------------------------------------------------
        if user_id is not None:
            user_assets_res = await db.execute(
                select(Asset)
                .options(selectinload(Asset.instrument))
                .where(Asset.user_id == user_id)
            )
            user_assets = list(user_assets_res.scalars().all())

            matched_asset: Optional[Asset] = None

            # 1a. Exact symbol match on user's Asset
            for a in user_assets:
                if a.symbol and a.symbol.upper() == clean_symbol:
                    matched_asset = a
                    break

            # 1b. Symbol with .IS suffix match on user's Asset
            if not matched_asset:
                is_suffix = f"{clean_symbol}.IS"
                for a in user_assets:
                    if a.symbol and a.symbol.upper() == is_suffix:
                        matched_asset = a
                        break

            # 1c. Commodity / Gold alias match on user's Asset
            if not matched_asset:
                # Check COMMODITY_ALIASES (e.g. "yarim altin" -> "HALF")
                matched_alias_symbol: Optional[str] = None
                sorted_aliases = sorted(
                    COMMODITY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
                )
                for alias_key, target_sym in sorted_aliases:
                    if re.search(r"\b" + re.escape(alias_key) + r"\b", norm_query):
                        matched_alias_symbol = target_sym
                        break

                if matched_alias_symbol:
                    for a in user_assets:
                        if (a.symbol and a.symbol.upper() == matched_alias_symbol) or (
                            matched_alias_symbol.lower() in normalize_text(a.name)
                        ):
                            matched_asset = a
                            break

            # 1d. Exact name match on user's Asset
            if not matched_asset:
                for a in user_assets:
                    if a.name and normalize_text(a.name) == norm_query:
                        matched_asset = a
                        break

            # If user owns the asset, determine canonical instrument
            if matched_asset:
                resolved_sym = matched_asset.symbol or clean_symbol

                # 1. Asset has explicit instrument_id
                if matched_asset.instrument_id:
                    inst = matched_asset.instrument
                    if not inst:
                        inst = await db.get(Instrument, matched_asset.instrument_id)

                    inst_name = inst.name if inst else matched_asset.name
                    return ResolvedEntity(
                        query=raw_query,
                        symbol=resolved_sym,
                        canonical_instrument_id=matched_asset.instrument_id,
                        canonical_instrument=inst,
                        canonical_name=inst_name,
                        asset=matched_asset,
                        is_owned=True,
                        match_type="OWNED_ASSET_INSTRUMENT",
                    )

                # 2. Asset exists but instrument_id is NULL -> fallback to instrument symbol lookup
                inst_res = await db.execute(
                    select(Instrument).where(
                        (Instrument.symbol.ilike(resolved_sym))
                        | (Instrument.symbol.ilike(f"{resolved_sym}.IS"))
                    )
                )
                matching_insts = list(inst_res.scalars().all())

                if len(matching_insts) == 1:
                    inst = matching_insts[0]
                    return ResolvedEntity(
                        query=raw_query,
                        symbol=resolved_sym,
                        canonical_instrument_id=inst.id,
                        canonical_instrument=inst,
                        canonical_name=inst.name,
                        asset=matched_asset,
                        is_owned=True,
                        match_type="OWNED_ASSET_SYMBOL_FALLBACK",
                    )
                elif len(matching_insts) > 1:
                    candidates = [
                        {
                            "id": str(i.id),
                            "symbol": i.symbol,
                            "name": i.name,
                            "exchange": i.exchange,
                            "asset_type": str(i.asset_type),
                        }
                        for i in matching_insts
                    ]
                    return ResolvedEntity(
                        query=raw_query,
                        symbol=resolved_sym,
                        asset=matched_asset,
                        is_owned=True,
                        is_ambiguous=True,
                        ambiguous_candidates=candidates,
                        match_type="AMBIGUOUS",
                        warning=(
                            f"Owned asset '{resolved_sym}' has NULL instrument_id and "
                            f"{len(matching_insts)} conflicting instruments exist in database."
                        ),
                    )
                else:
                    return ResolvedEntity(
                        query=raw_query,
                        symbol=resolved_sym,
                        asset=matched_asset,
                        canonical_name=matched_asset.name,
                        is_owned=True,
                        match_type="OWNED_ASSET_WITHOUT_INSTRUMENT",
                    )

        # ---------------------------------------------------------------------
        # Stage 2: Global Instrument Lookup (Unowned Fallback)
        # ---------------------------------------------------------------------
        # Check commodity alias first
        target_lookup_symbol = clean_symbol
        sorted_aliases = sorted(
            COMMODITY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
        )
        for alias_key, target_sym in sorted_aliases:
            if re.search(r"\b" + re.escape(alias_key) + r"\b", norm_query):
                target_lookup_symbol = target_sym
                break

        # Query Instrument table
        inst_stmt = select(Instrument).where(
            (Instrument.symbol.ilike(target_lookup_symbol))
            | (Instrument.symbol.ilike(f"{target_lookup_symbol}.IS"))
        )
        inst_res = await db.execute(inst_stmt)
        matched_instruments = list(inst_res.scalars().all())

        # Exact match single instrument
        if len(matched_instruments) == 1:
            inst = matched_instruments[0]
            return ResolvedEntity(
                query=raw_query,
                symbol=inst.symbol or target_lookup_symbol,
                canonical_instrument_id=inst.id,
                canonical_instrument=inst,
                canonical_name=inst.name,
                is_owned=False,
                match_type="INSTRUMENT_EXACT",
            )

        # Multiple instruments matched: check if exact symbol disambiguates (e.g. THF vs THF.IS)
        if len(matched_instruments) > 1:
            exact_symbol_insts = [
                i for i in matched_instruments
                if i.symbol and i.symbol.upper() == target_lookup_symbol
            ]
            if len(exact_symbol_insts) == 1:
                inst = exact_symbol_insts[0]
                return ResolvedEntity(
                    query=raw_query,
                    symbol=inst.symbol or target_lookup_symbol,
                    canonical_instrument_id=inst.id,
                    canonical_instrument=inst,
                    canonical_name=inst.name,
                    is_owned=False,
                    match_type="INSTRUMENT_EXACT",
                )

            # Still multiple instruments (true duplicate records in database)
            # DO NOT silently pick an arbitrary row with .limit(1)!
            candidates = [
                {
                    "id": str(i.id),
                    "symbol": i.symbol,
                    "name": i.name,
                    "exchange": i.exchange,
                    "asset_type": str(i.asset_type),
                }
                for i in matched_instruments
            ]
            return ResolvedEntity(
                query=raw_query,
                symbol=target_lookup_symbol,
                is_owned=False,
                is_ambiguous=True,
                ambiguous_candidates=candidates,
                match_type="AMBIGUOUS",
                warning=(
                    f"Ambiguous symbol: {len(matched_instruments)} instruments match symbol "
                    f"'{target_lookup_symbol}' without user ownership to resolve canonical identity."
                ),
            )

        # ---------------------------------------------------------------------
        # Stage 3: Global Name Match (Last Fallback)
        # ---------------------------------------------------------------------
        name_stmt = select(Instrument).where(Instrument.name.ilike(f"%{raw_query}%")).limit(10)
        name_res = await db.execute(name_stmt)
        name_matches = list(name_res.scalars().all())

        if len(name_matches) == 1:
            inst = name_matches[0]
            return ResolvedEntity(
                query=raw_query,
                symbol=inst.symbol or clean_symbol,
                canonical_instrument_id=inst.id,
                canonical_instrument=inst,
                canonical_name=inst.name,
                is_owned=False,
                match_type="INSTRUMENT_NAME",
            )
        elif len(name_matches) > 1:
            candidates = [
                {
                    "id": str(i.id),
                    "symbol": i.symbol,
                    "name": i.name,
                    "exchange": i.exchange,
                    "asset_type": str(i.asset_type),
                }
                for i in name_matches
            ]
            return ResolvedEntity(
                query=raw_query,
                symbol=clean_symbol,
                is_owned=False,
                is_ambiguous=True,
                ambiguous_candidates=candidates,
                match_type="AMBIGUOUS",
                warning=f"Multiple instruments matched name query '{raw_query}'.",
            )

        # ---------------------------------------------------------------------
        # Stage 4: Unrecognized / Not Found
        # ---------------------------------------------------------------------
        return ResolvedEntity(
            query=raw_query,
            symbol=clean_symbol,
            is_owned=False,
            match_type="NOT_FOUND",
            warning=f"No asset or instrument found matching '{raw_query}'.",
        )
