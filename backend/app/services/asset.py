"""Asset CRUD business logic — all queries filter by user_id for ownership.

An Asset is a position/holding, identified by (user_id, asset_type, symbol).
Quantity and cost basis live in the Transaction table; this module exposes
helpers that combine an Asset row with its computed stats.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.transaction import Transaction
from app.schemas.asset import AssetCreateRequest, AssetPriceUpdateRequest, AssetUpdateRequest
from app.services import instrument as instrument_service
from app.services import price as price_service
from app.services import transaction as tx_service
from app.services.portfolio_stats import compute_stats

# Asset types that support automatic price fetching on create/update
_AUTO_TYPES = {
    AssetType.STOCK,
    AssetType.FOREX,
    AssetType.PRECIOUS_METALS,
    AssetType.CRYPTO,
    AssetType.FUND,
}


async def list_assets(
    db: AsyncSession,
    user_id: UUID,
    asset_type: Optional[AssetType] = None,
) -> list[Asset]:
    query = (
        select(Asset)
        .options(
            selectinload(Asset.instrument),
            selectinload(Asset.opening_position),
        )
        .where(Asset.user_id == user_id)
        .order_by(Asset.created_at.desc())
    )
    if asset_type is not None:
        query = query.where(Asset.asset_type == asset_type)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_assets_with_stats(
    db: AsyncSession,
    user_id: UUID,
    asset_type: Optional[AssetType] = None,
) -> list[tuple[Asset, dict]]:
    """Return all user assets paired with their computed stats (single batch load)."""
    assets = await list_assets(db, user_id, asset_type)
    if not assets:
        return []

    asset_ids = [a.id for a in assets]
    result = await db.execute(
        select(Transaction).where(Transaction.asset_id.in_(asset_ids))
    )
    txns_by_asset: dict[UUID, list[Transaction]] = {aid: [] for aid in asset_ids}
    for tx in result.scalars().all():
        txns_by_asset[tx.asset_id].append(tx)

    return [
        (a, compute_stats(txns_by_asset[a.id], opening_position=a.opening_position))
        for a in assets
    ]


async def get_asset(
    db: AsyncSession, asset_id: UUID, user_id: UUID
) -> Optional[Asset]:
    result = await db.execute(
        select(Asset)
        .options(
            selectinload(Asset.instrument),
            selectinload(Asset.opening_position),
        )
        .where(Asset.id == asset_id, Asset.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_asset_with_stats(
    db: AsyncSession, asset_id: UUID, user_id: UUID
) -> Optional[tuple[Asset, dict]]:
    asset = await get_asset(db, asset_id, user_id)
    if asset is None:
        return None
    result = await db.execute(
        select(Transaction).where(Transaction.asset_id == asset_id)
    )
    stats = compute_stats(
        list(result.scalars().all()), opening_position=asset.opening_position
    )
    return asset, stats


async def create_asset(
    db: AsyncSession, user_id: UUID, data: AssetCreateRequest
) -> tuple[Asset, dict, Optional[str]]:
    """Insert a new asset (position). Optionally creates an initial BUY/SELL transaction.

    Returns (asset, stats, warning).  *warning* is a string when auto-price-fetch
    fails for an auto-type asset; otherwise None.
    """
    instrument = await instrument_service.find_or_create_instrument(
        db,
        asset_type=data.asset_type,
        name=data.name,
        symbol=data.symbol,
        exchange=data.exchange,
        currency=data.current_price_currency,
        instrument_id=data.instrument_id,
    )

    payload = data.model_dump(exclude={"initial_transaction", "exchange"})
    payload["instrument_id"] = instrument.id
    asset = Asset(user_id=user_id, **payload)
    db.add(asset)
    try:
        await db.flush()
        if data.initial_transaction is not None:
            await tx_service.stage_transaction(
                db, asset.id, data.initial_transaction, user_id=user_id
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Re-fetch asset with instrument relationship eagerly loaded
    loaded_asset = await get_asset(db, asset.id, user_id)
    if loaded_asset is not None:
        asset = loaded_asset

    warning = None
    if asset.asset_type in _AUTO_TYPES and asset.symbol:
        result = await price_service.refresh_single_asset(db, asset)
        if result["status"] == "failed":
            warning = f"Price fetch failed: {result.get('error', 'unknown error')}"

    # Load final stats
    tx_result = await db.execute(
        select(Transaction).where(Transaction.asset_id == asset.id)
    )
    stats = compute_stats(
        list(tx_result.scalars().all()), opening_position=asset.opening_position
    )
    return asset, stats, warning


async def update_asset(
    db: AsyncSession, asset: Asset, data: AssetUpdateRequest
) -> tuple[Asset, dict, Optional[str]]:
    symbol_or_type_changed = (
        "symbol" in data.model_fields_set
        or "asset_type" in data.model_fields_set
        or "instrument_id" in data.model_fields_set
    )
    if symbol_or_type_changed:
        new_type = data.asset_type if data.asset_type is not None else asset.asset_type
        new_symbol = data.symbol if "symbol" in data.model_fields_set else asset.symbol
        new_name = data.name if data.name is not None else asset.name
        new_currency = (
            data.current_price_currency
            if data.current_price_currency is not None
            else asset.current_price_currency
        )
        new_instrument = await instrument_service.find_or_create_instrument(
            db,
            asset_type=new_type,
            name=new_name,
            symbol=new_symbol,
            exchange=data.exchange,
            currency=new_currency,
            instrument_id=data.instrument_id,
        )
        asset.instrument_id = new_instrument.id

    for field, value in data.model_dump(
        exclude_unset=True, exclude={"exchange"}
    ).items():
        setattr(asset, field, value)
    await db.commit()
    loaded_asset = await get_asset(db, asset.id, asset.user_id)
    if loaded_asset is not None:
        asset = loaded_asset
    else:
        await db.refresh(asset)

    warning = None
    if symbol_or_type_changed and asset.asset_type in _AUTO_TYPES and asset.symbol:
        result = await price_service.refresh_single_asset(db, asset)
        if result["status"] == "failed":
            warning = f"Price fetch failed: {result.get('error', 'unknown error')}"

    tx_result = await db.execute(
        select(Transaction).where(Transaction.asset_id == asset.id)
    )
    stats = compute_stats(
        list(tx_result.scalars().all()), opening_position=asset.opening_position
    )
    return asset, stats, warning


async def update_asset_price(
    db: AsyncSession, asset: Asset, data: AssetPriceUpdateRequest
) -> tuple[Asset, dict]:
    asset.current_price = data.current_price
    asset.current_price_currency = data.current_price_currency
    asset.is_manual_price = True
    await db.commit()
    await db.refresh(asset)

    tx_result = await db.execute(
        select(Transaction).where(Transaction.asset_id == asset.id)
    )
    stats = compute_stats(
        list(tx_result.scalars().all()), opening_position=asset.opening_position
    )
    return asset, stats


async def delete_asset(db: AsyncSession, asset: Asset) -> None:
    await db.delete(asset)
    await db.commit()
