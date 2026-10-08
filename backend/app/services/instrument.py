"""Instrument service — manage canonical investment instrument identities.

Encapsulates instrument lookup, resolution, deduplication, and creation.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetType
from app.models.instrument import Instrument


async def find_or_create_instrument(
    db: AsyncSession,
    *,
    asset_type: AssetType,
    name: str,
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
    currency: Optional[str] = None,
    country: Optional[str] = None,
    isin: Optional[str] = None,
    provider: Optional[str] = None,
    provider_id: Optional[str] = None,
    instrument_id: Optional[UUID] = None,
) -> Instrument:
    """Find an existing Instrument if safe to deduplicate, otherwise create a new one.

    Rules:
    1. If explicit instrument_id provided and exists, use it.
    2. CUSTOM and REAL_ESTATE or assets without symbol are NEVER shared across positions.
    3. For standard market assets (STOCK, CRYPTO, FUND, PRECIOUS_METALS, FOREX):
       - Exact match on asset_type and uppercase symbol.
       - Candidate must not have conflicting exchange, currency, or ISIN.
       - If multiple candidates match (ambiguous), do not merge — create a new instrument.
       - If exactly one candidate matches safely, reuse and enrich any missing metadata.
    """
    if instrument_id is not None:
        inst = await get_instrument(db, instrument_id)
        if inst is not None:
            return inst

    clean_symbol = symbol.strip().upper() if symbol and symbol.strip() else None

    # Custom/real estate or missing symbols are never deduplicated
    if asset_type in (AssetType.CUSTOM, AssetType.REAL_ESTATE) or not clean_symbol:
        inst = Instrument(
            symbol=clean_symbol,
            name=name,
            asset_type=asset_type,
            exchange=exchange,
            currency=currency,
            country=country,
            isin=isin,
            provider=provider,
            provider_id=provider_id,
        )
        db.add(inst)
        await db.flush()
        return inst

    # Infer metadata where not provided
    inferred_exchange = exchange
    inferred_currency = currency
    inferred_provider = provider
    inferred_provider_id = provider_id

    if asset_type == AssetType.STOCK:
        if not inferred_exchange:
            if clean_symbol.endswith(".IS"):
                inferred_exchange = "BIST"
                inferred_currency = inferred_currency or "TRY"
            else:
                inferred_exchange = "NASDAQ"
                inferred_currency = inferred_currency or "USD"
        if not inferred_provider:
            inferred_provider = "yfinance"
    elif asset_type == AssetType.CRYPTO:
        if not inferred_exchange:
            inferred_exchange = "Crypto"
        if not inferred_provider:
            inferred_provider = "CoinGecko"
        inferred_currency = inferred_currency or "USD"
    elif asset_type == AssetType.FUND:
        if not inferred_exchange:
            inferred_exchange = "TEFAS"
        if not inferred_provider:
            inferred_provider = "TEFAS"
        inferred_currency = inferred_currency or "TRY"
    elif asset_type == AssetType.PRECIOUS_METALS:
        if not inferred_exchange:
            inferred_exchange = "Precious Metals"
        if not inferred_provider:
            inferred_provider = "yfinance"
        inferred_currency = inferred_currency or "USD"
    elif asset_type == AssetType.FOREX:
        if not inferred_exchange:
            inferred_exchange = "Forex"
        if not inferred_provider:
            inferred_provider = "ExchangeRate-API"
        if not inferred_currency and "/" in clean_symbol:
            inferred_currency = clean_symbol.split("/")[1]

    # Query existing candidates with matching asset_type and symbol
    stmt = select(Instrument).where(
        Instrument.asset_type == asset_type,
        func.upper(Instrument.symbol) == clean_symbol,
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    viable_matches: list[Instrument] = []
    for cand in candidates:
        # Check exchange conflict
        if (
            inferred_exchange
            and cand.exchange
            and inferred_exchange.upper() != cand.exchange.upper()
        ):
            continue
        # Check currency conflict
        if (
            inferred_currency
            and cand.currency
            and inferred_currency.upper() != cand.currency.upper()
        ):
            continue
        # Check ISIN conflict
        if isin and cand.isin and isin.upper() != cand.isin.upper():
            continue
        viable_matches.append(cand)

    # Exactly 1 safe candidate found -> reuse and enrich
    if len(viable_matches) == 1:
        matched = viable_matches[0]
        changed = False
        if not matched.exchange and inferred_exchange:
            matched.exchange = inferred_exchange
            changed = True
        if not matched.currency and inferred_currency:
            matched.currency = inferred_currency
            changed = True
        if not matched.country and country:
            matched.country = country
            changed = True
        if not matched.isin and isin:
            matched.isin = isin
            changed = True
        if not matched.provider and inferred_provider:
            matched.provider = inferred_provider
            changed = True
        if not matched.provider_id and inferred_provider_id:
            matched.provider_id = inferred_provider_id
            changed = True
        if changed:
            await db.flush()
        return matched

    # 0 matches or >1 matches (ambiguous) -> create a new distinct Instrument
    new_inst = Instrument(
        symbol=clean_symbol,
        name=name,
        asset_type=asset_type,
        exchange=inferred_exchange,
        currency=inferred_currency,
        country=country,
        isin=isin,
        provider=inferred_provider,
        provider_id=inferred_provider_id,
    )
    db.add(new_inst)
    await db.flush()
    return new_inst


async def get_instrument(
    db: AsyncSession, instrument_id: UUID
) -> Optional[Instrument]:
    stmt = select(Instrument).where(Instrument.id == instrument_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_instruments(
    db: AsyncSession,
    q: Optional[str] = None,
    asset_type: Optional[AssetType] = None,
    limit: int = 50,
) -> list[Instrument]:
    stmt = select(Instrument).order_by(Instrument.created_at.desc()).limit(limit)
    if asset_type is not None:
        stmt = stmt.where(Instrument.asset_type == asset_type)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Instrument.symbol).like(term),
                func.lower(Instrument.name).like(term),
                func.lower(Instrument.isin).like(term),
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())
