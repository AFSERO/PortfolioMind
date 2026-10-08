"""Market-Wide Discovery Engine v1 (DiscoveryService).

Performs bounded, staged market discovery:
1. Loads bounded universe (US_LARGE_CAP, US_TECH_GROWTH, BIST_LIQUID).
2. Cheaply excludes owned, watchlisted, and recently dismissed assets.
3. Applies deterministic market data filters & dislocation signals.
4. Ranks candidates and enriches a small shortlist with news/SEC disclosures.
5. Selectively invokes Finance DiscoveryReasoner for deep screening.
6. Persists DiscoveryRun and DiscoveryCandidate records.
7. Dispatches user actions (Add to Watchlist, Dismiss, Screen).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session_factory
from app.models.asset import Asset, AssetType
from app.models.discovery import (
    DiscoveryCandidate,
    DiscoveryCandidateState,
    DiscoveryConfidence,
    DiscoveryRun,
    DiscoveryRunStatus,
    DiscoveryStatus,
    DiscoverySuggestedNextStep,
    DiscoveryTriggerType,
    DiscoveryUniverse,
)
from app.models.instrument import Instrument
from app.models.opportunity import ResearchStage, WatchlistItem, WatchlistPriority
from app.models.user import User

logger = logging.getLogger(__name__)

_DEFAULT_REASONER = object()

# Discovery Universe definitions
UNIVERSE_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

TECH_SYMBOLS = {
    "NVDA", "AMD", "CRM", "ADBE", "QCOM", "AVGO", "CSCO", "INTC",
    "ORCL", "IBM", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NOW",
    "SNOW", "UBER", "TSM", "PLTR", "PANW", "CRWD", "DDOG", "NET",
}


def load_universe_symbols(universe: DiscoveryUniverse | str) -> List[Dict[str, str]]:
    """Load bounded universe symbols and names from repository data files."""
    u_str = universe.value if hasattr(universe, "value") else str(universe).upper()

    if u_str == DiscoveryUniverse.BIST_LIQUID.value or u_str == "BIST_LIQUID":
        path = UNIVERSE_DATA_DIR / "bist_stocks.json"
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                return [{"symbol": f"{d['symbol']}.IS", "name": d["name"], "exchange": "BIST", "currency": "TRY"} for d in data[:40]]
        return []

    elif u_str == DiscoveryUniverse.US_TECH_GROWTH.value or u_str == "US_TECH_GROWTH":
        path = UNIVERSE_DATA_DIR / "us_stocks.json"
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                res = []
                for d in data:
                    if d["symbol"] in TECH_SYMBOLS:
                        res.append({"symbol": d["symbol"], "name": d["name"], "exchange": "NASDAQ", "currency": "USD"})
                return res
        return []

    else:
        # Default: US_LARGE_CAP (top 45 liquid large caps)
        path = UNIVERSE_DATA_DIR / "us_stocks.json"
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                return [{"symbol": d["symbol"], "name": d["name"], "exchange": "NYSE/NASDAQ", "currency": "USD"} for d in data[:45]]
        return []


def _fetch_fast_market_snapshot(symbol: str) -> Optional[Dict[str, Any]]:
    """Synchronous worker function to fetch yfinance fast_info snapshot."""
    import yfinance as yf

    clean_sym = symbol.replace(".", "-") if not symbol.endswith(".IS") else symbol
    try:
        t = yf.Ticker(clean_sym)
        info = t.fast_info
        last_price = getattr(info, "last_price", None)
        if last_price is None or last_price <= 0:
            return None

        year_high = getattr(info, "year_high", None)
        year_low = getattr(info, "year_low", None)
        fifty_day_avg = getattr(info, "fifty_day_average", None)
        two_hundred_day_avg = getattr(info, "two_hundred_day_average", None)
        market_cap = getattr(info, "market_cap", None)
        currency = getattr(info, "currency", None) or ("TRY" if symbol.endswith(".IS") else "USD")

        return {
            "last_price": round(float(last_price), 4),
            "year_high": round(float(year_high), 4) if year_high else None,
            "year_low": round(float(year_low), 4) if year_low else None,
            "fifty_day_average": round(float(fifty_day_avg), 4) if fifty_day_avg else None,
            "two_hundred_day_average": round(float(two_hundred_day_avg), 4) if two_hundred_day_avg else None,
            "market_cap": float(market_cap) if market_cap else None,
            "currency": currency,
        }
    except Exception as e:
        logger.debug("Fast market snapshot failed for %s: %s", symbol, e)
        return None


async def fetch_market_snapshots_batch(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """Batch fetch market data snapshots concurrently using thread pool."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    loop = asyncio.get_running_loop()

    def _batch_worker():
        batch_res = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            fut_map = {executor.submit(_fetch_fast_market_snapshot, s): s for s in symbols}
            for fut in as_completed(fut_map):
                s = fut_map[fut]
                try:
                    snap = fut.result()
                    if snap:
                        batch_res[s] = snap
                except Exception as e:
                    logger.debug("Fast market worker failed for %s: %s", s, e)
        return batch_res

    try:
        return await loop.run_in_executor(None, _batch_worker)
    except Exception as e:
        logger.warning("Batch market data fetch failed: %s", e)
        return {}


def evaluate_deterministic_discovery_signals(
    symbol: str,
    name: str,
    snapshot: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], int, str]:
    """Evaluate deterministic discovery signals from market snapshot.

    Returns: (signals, score, score_band)
    """
    signals: List[Dict[str, Any]] = []
    score = 0

    price = snapshot.get("last_price")
    y_high = snapshot.get("year_high")
    y_low = snapshot.get("year_low")
    ma_50 = snapshot.get("fifty_day_average")
    ma_200 = snapshot.get("two_hundred_day_average")
    mcap = snapshot.get("market_cap")
    currency = snapshot.get("currency", "USD")

    curr_sym = "TRY" if currency == "TRY" else "$"

    if price is None or price <= 0:
        return signals, score, "LOW"

    # 1. Price Dislocation (15% to 50% pullback from 52-week high in large liquid asset)
    if y_high and y_high > 0:
        drawdown = (price - y_high) / y_high
        snapshot["drawdown_from_52w_high"] = round(drawdown, 4)
        if -0.50 <= drawdown <= -0.15:
            dd_pct = abs(round(drawdown * 100, 1))
            signals.append({
                "type": "PRICE_DISLOCATION",
                "label": f"Drawdown ({dd_pct}% from 52w High)",
                "detail": f"Price ({curr_sym}{price:,.2f}) pulled back {dd_pct}% from 52-week high ({curr_sym}{y_high:,.2f}).",
                "data": {"drawdown_pct": dd_pct, "year_high": y_high},
            })
            score += 3

    # 2. Support Proximity (trading within 10% of 52-week low)
    if y_low and y_low > 0:
        dist_low = (price - y_low) / y_low
        snapshot["distance_from_52w_low"] = round(dist_low, 4)
        if 0.0 <= dist_low <= 0.12 and snapshot.get("drawdown_from_52w_high", 0) <= -0.15:
            low_pct = round(dist_low * 100, 1)
            signals.append({
                "type": "SUPPORT_PROXIMITY",
                "label": f"Testing 52w Low (+{low_pct}%)",
                "detail": f"Price trading within {low_pct}% of 52-week support low ({curr_sym}{y_low:,.2f}).",
                "data": {"distance_pct": low_pct, "year_low": y_low},
            })
            score += 2

    # 3. Valuation Compression (trading > 18% below 200-day moving average)
    if ma_200 and ma_200 > 0:
        dist_200 = (price - ma_200) / ma_200
        snapshot["change_vs_200ma"] = round(dist_200, 4)
        if dist_200 <= -0.18:
            ma_pct = abs(round(dist_200 * 100, 1))
            signals.append({
                "type": "VALUATION_COMPRESSION",
                "label": f"Below 200-Day MA (-{ma_pct}%)",
                "detail": f"Price is compressed {ma_pct}% below long-term 200-day moving average ({curr_sym}{ma_200:,.2f}).",
                "data": {"below_200ma_pct": ma_pct, "ma_200": ma_200},
            })
            score += 2

    # 4. Momentum Breakout (Price > 50MA > 200MA)
    if ma_50 and ma_200 and ma_50 > 0 and ma_200 > 0:
        if price > ma_50 > ma_200:
            signals.append({
                "type": "MOMENTUM_BREAKOUT",
                "label": "Bullish Trend Alignment",
                "detail": f"Price ({curr_sym}{price:,.2f}) crossed above rising moving averages (50MA: {curr_sym}{ma_50:,.2f}, 200MA: {curr_sym}{ma_200:,.2f}).",
                "data": {"ma_50": ma_50, "ma_200": ma_200},
            })
            score += 2

    # Quality liquidity bonus (Market cap > 10B USD or > 20B TRY)
    if mcap:
        if (currency == "USD" and mcap >= 10_000_000_000) or (currency == "TRY" and mcap >= 20_000_000_000):
            score += 1

    score_band = "HIGH" if score >= 5 else ("MEDIUM" if score >= 3 else "LOW")
    return signals, score, score_band


async def get_user_exclusion_symbols(db: AsyncSession, user_id: UUID) -> Tuple[Set[str], Set[UUID]]:
    """Collect symbols and instrument IDs owned, watchlisted, or recently dismissed by user."""
    # 1. Owned assets
    asset_stmt = select(Instrument.symbol, Instrument.id).join(
        Asset, Asset.instrument_id == Instrument.id
    ).where(Asset.user_id == user_id)
    asset_res = await db.execute(asset_stmt)
    owned_rows = asset_res.all()
    owned_symbols = {r[0].upper() for r in owned_rows if r[0]}
    owned_inst_ids = {r[1] for r in owned_rows if r[1]}

    # 2. Watchlist items
    wl_stmt = select(Instrument.symbol, Instrument.id).join(
        WatchlistItem, WatchlistItem.instrument_id == Instrument.id
    ).where(WatchlistItem.user_id == user_id)
    wl_res = await db.execute(wl_stmt)
    wl_rows = wl_res.all()
    wl_symbols = {r[0].upper() for r in wl_rows if r[0]}
    wl_inst_ids = {r[1] for r in wl_rows if r[1]}

    # 3. Recently dismissed candidates (within 30 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    dismissed_stmt = select(Instrument.symbol, Instrument.id).join(
        DiscoveryCandidate, DiscoveryCandidate.instrument_id == Instrument.id
    ).where(
        DiscoveryCandidate.user_id == user_id,
        DiscoveryCandidate.candidate_state == DiscoveryCandidateState.DISMISSED,
        DiscoveryCandidate.dismissed_at >= cutoff,
    )
    d_res = await db.execute(dismissed_stmt)
    d_rows = d_res.all()
    dismissed_symbols = {r[0].upper() for r in d_rows if r[0]}
    dismissed_inst_ids = {r[1] for r in d_rows if r[1]}

    all_symbols = owned_symbols | wl_symbols | dismissed_symbols
    all_inst_ids = owned_inst_ids | wl_inst_ids | dismissed_inst_ids
    return all_symbols, all_inst_ids


async def ensure_canonical_instrument(
    db: AsyncSession,
    symbol: str,
    name: str,
    exchange: Optional[str] = None,
    currency: Optional[str] = None,
) -> Instrument:
    """Find or create canonical Instrument entity."""
    clean_sym = symbol.upper().strip()
    stmt = select(Instrument).where(Instrument.symbol == clean_sym).limit(1)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if inst is None:
        inst = Instrument(
            id=uuid.uuid4(),
            symbol=clean_sym,
            name=name,
            asset_type=AssetType.STOCK,
            exchange=exchange or ("BIST" if clean_sym.endswith(".IS") else "NASDAQ"),
            currency=currency or ("TRY" if clean_sym.endswith(".IS") else "USD"),
        )
        db.add(inst)
        await db.flush()

    return inst


async def run_discovery_scan_for_user(
    db: AsyncSession,
    user_id: UUID,
    universe: DiscoveryUniverse | str = DiscoveryUniverse.US_LARGE_CAP,
    trigger_type: DiscoveryTriggerType = DiscoveryTriggerType.MANUAL,
    force_refresh: bool = False,
    reasoner: Any = _DEFAULT_REASONER,
) -> DiscoveryRun:
    """Execute end-to-end Market-Wide Discovery Scan."""
    now_utc = datetime.now(timezone.utc)
    u_val = universe.value if hasattr(universe, "value") else str(universe).upper()

    # 1. Initialize DiscoveryRun record
    run = DiscoveryRun(
        id=uuid.uuid4(),
        user_id=user_id,
        universe=u_val,
        trigger_type=trigger_type,
        status=DiscoveryRunStatus.RUNNING,
        started_at=now_utc,
        diagnostics={"universe": u_val, "trigger": trigger_type.value},
    )
    db.add(run)
    await db.flush()

    try:
        # 2. Load universe members
        universe_items = load_universe_symbols(u_val)
        run.instruments_scanned = len(universe_items)

        if not universe_items:
            run.status = DiscoveryRunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.diagnostics["message"] = f"Universe {u_val} returned 0 configured members."
            await db.commit()
            return run

        # 3. Collect exclusion set
        excluded_symbols, _ = await get_user_exclusion_symbols(db, user_id)
        candidates_to_screen = [
            item for item in universe_items
            if item["symbol"].upper() not in excluded_symbols
            and item["symbol"].replace(".IS", "").upper() not in excluded_symbols
        ]
        run.candidates_filtered = len(universe_items) - len(candidates_to_screen)

        if not candidates_to_screen:
            run.status = DiscoveryRunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.diagnostics["message"] = "All universe members excluded as already owned, watchlisted, or recently dismissed."
            await db.commit()
            return run

        # 4. Batch market data fetching
        symbols_to_fetch = [c["symbol"] for c in candidates_to_screen]
        snapshots = await fetch_market_snapshots_batch(symbols_to_fetch)

        # 5. Deterministic signal evaluation & scoring
        scored_candidates = []
        for cand in candidates_to_screen:
            sym = cand["symbol"]
            snap = snapshots.get(sym)
            if not snap or not snap.get("last_price"):
                continue

            signals, score, band = evaluate_deterministic_discovery_signals(
                symbol=sym,
                name=cand["name"],
                snapshot=snap,
            )

            # Only retain candidates with at least one meaningful signal
            if signals:
                scored_candidates.append({
                    "meta": cand,
                    "snapshot": snap,
                    "signals": signals,
                    "score": score,
                    "score_band": band,
                })

        # Sort by score descending and take top shortlist (maximum 6 candidates)
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        shortlist = scored_candidates[:6]

        # 6. Evidence enrichment & selective Codex screening
        from investment_intelligence.discovery_reasoner import (
            DiscoveryAssessment,
            DiscoveryReasoner,
        )

        surfaced_records = []
        if reasoner is _DEFAULT_REASONER:
            try:
                ai_reasoner = DiscoveryReasoner()
            except Exception:
                ai_reasoner = None
        else:
            ai_reasoner = reasoner

        for idx, item in enumerate(shortlist):
            cand_meta = item["meta"]
            snap = item["snapshot"]
            signals = item["signals"]
            band = item["score_band"]
            sym = cand_meta["symbol"]
            clean_sym = sym.replace(".IS", "")

            # Ensure canonical instrument
            inst = await ensure_canonical_instrument(
                db=db,
                symbol=sym,
                name=cand_meta["name"],
                exchange=cand_meta.get("exchange"),
                currency=snap.get("currency"),
            )

            # Check for existing surfaced candidate in recent run (idempotency check)
            if not force_refresh:
                prev_cand_stmt = select(DiscoveryCandidate).where(
                    DiscoveryCandidate.user_id == user_id,
                    DiscoveryCandidate.instrument_id == inst.id,
                    DiscoveryCandidate.candidate_state == DiscoveryCandidateState.SURFACED,
                ).order_by(DiscoveryCandidate.created_at.desc()).limit(1)
                prev_cand_res = await db.execute(prev_cand_stmt)
                prev_cand = prev_cand_res.scalar_one_or_none()

                if prev_cand is not None:
                    # Check if price changed meaningfully (>12%)
                    prev_price = float(prev_cand.current_price) if prev_cand.current_price else None
                    curr_price = snap.get("last_price")
                    if prev_price and curr_price:
                        price_shift = abs(curr_price - prev_price) / prev_price
                        if price_shift < 0.12:
                            logger.debug("Idempotent discovery: candidate %s unchanged. Reusing.", sym)
                            surfaced_records.append(prev_cand)
                            continue

            # Enrich with news / SEC disclosures (if available)
            recent_news: List[Dict[str, Any]] = []
            sec_filings: List[Dict[str, Any]] = []
            try:
                from investment_intelligence.live_providers import GoogleNewsRSSProvider
                from investment_intelligence.records import InstrumentRecord
                inst_rec = InstrumentRecord(
                    id=inst.id,
                    symbol=clean_sym,
                    name=cand_meta["name"],
                    asset_type="STOCK",
                    exchange=cand_meta.get("exchange") or "NASDAQ",
                    currency=snap.get("currency") or "USD",
                )
                np = GoogleNewsRSSProvider([inst_rec])
                news_items = np.get_recent_news(inst_rec, limit=3)
                recent_news = [{"headline": n.title, "source": n.source, "published_at": n.published_at.isoformat()} for n in news_items]
            except Exception as e:
                logger.debug("News enrichment failed for %s: %s", sym, e)

            # Selective Codex reasoning: only top 3 candidates reach Codex!
            assessment: Optional[DiscoveryAssessment] = None
            if idx < 3 and ai_reasoner is not None:
                run.candidates_reasoned += 1
                try:
                    assessment = ai_reasoner.assess_candidate(
                        instrument={
                            "symbol": sym,
                            "name": cand_meta["name"],
                            "asset_type": "STOCK",
                            "exchange": cand_meta.get("exchange"),
                            "currency": snap.get("currency"),
                        },
                        market_data=snap,
                        signals=signals,
                        recent_news=recent_news,
                        portfolio_context={"owned_symbols": list(excluded_symbols)},
                    )
                except Exception as ai_err:
                    logger.warning("Codex discovery screening failed for %s; using deterministic fallback: %s", sym, ai_err)
                    assessment = None

            # Fallback deterministic assessment if Codex was not run or failed
            if assessment is None:
                primary_sig = signals[0]["detail"] if signals else "Deterministic opportunity criteria satisfied."
                assessment = DiscoveryAssessment(
                    discovery_status="HIGH_PRIORITY_SCREEN" if band == "HIGH" else "SCREEN",
                    primary_reason=primary_sig,
                    signal_summary=", ".join(s["label"] for s in signals),
                    key_question="Does this price dislocation represent temporary market overreaction or structural thesis risk?",
                    key_risk="Potential value trap if margin pressures or revenue deceleration persist.",
                    suggested_next_step="PRELIMINARY_SCREENING" if band == "HIGH" else "ADD_TO_WATCHLIST",
                    confidence="MEDIUM",
                    raw_machine_record={},
                )

            # Do not surface candidates marked IGNORE by Codex
            if assessment.discovery_status == "IGNORE":
                continue

            # Persist DiscoveryCandidate
            cand_record = DiscoveryCandidate(
                id=uuid.uuid4(),
                run_id=run.id,
                user_id=user_id,
                instrument_id=inst.id,
                status=DiscoveryStatus(assessment.discovery_status),
                candidate_state=DiscoveryCandidateState.SURFACED,
                primary_reason=assessment.primary_reason,
                signals=signals,
                key_question=assessment.key_question,
                key_risk=assessment.key_risk,
                suggested_next_step=DiscoverySuggestedNextStep(assessment.suggested_next_step),
                confidence=DiscoveryConfidence(assessment.confidence),
                score_band=band,
                current_price=Decimal(str(snap["last_price"])),
                current_price_currency=snap.get("currency"),
                market_data_snapshot=snap,
                source_metadata={
                    "recent_news": recent_news,
                    "signal_summary": assessment.signal_summary,
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(cand_record)
            surfaced_records.append(cand_record)

        run.candidates_surfaced = len(surfaced_records)
        run.status = DiscoveryRunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        res = await db.execute(
            select(DiscoveryRun)
            .options(selectinload(DiscoveryRun.candidates).selectinload(DiscoveryCandidate.instrument))
            .where(DiscoveryRun.id == run.id)
        )
        return res.scalar_one()

    except Exception as e:
        logger.error("Discovery run failed for user %s: %s", user_id, e, exc_info=True)
        run.status = DiscoveryRunStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        run.diagnostics["error"] = str(e)
        await db.commit()
        return run


async def get_latest_discovery_run(
    db: AsyncSession,
    user_id: UUID,
) -> Optional[DiscoveryRun]:
    """Retrieve the latest discovery run for user with populated candidates."""
    stmt = (
        select(DiscoveryRun)
        .options(
            selectinload(DiscoveryRun.candidates).selectinload(DiscoveryCandidate.instrument)
        )
        .where(DiscoveryRun.user_id == user_id)
        .order_by(DiscoveryRun.started_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def add_candidate_to_watchlist(
    db: AsyncSession,
    user_id: UUID,
    candidate_id: UUID,
) -> WatchlistItem:
    """Convert a discovery candidate into an active WatchlistItem (preserving provenance)."""
    cand_stmt = select(DiscoveryCandidate).where(
        DiscoveryCandidate.id == candidate_id,
        DiscoveryCandidate.user_id == user_id,
    )
    cand_res = await db.execute(cand_stmt)
    cand = cand_res.scalar_one_or_none()
    if cand is None:
        raise ValueError(f"Discovery candidate {candidate_id} not found.")

    # Check if already watchlisted
    wl_stmt = select(WatchlistItem).where(
        WatchlistItem.user_id == user_id,
        WatchlistItem.instrument_id == cand.instrument_id,
    )
    wl_res = await db.execute(wl_stmt)
    wl_item = wl_res.scalar_one_or_none()

    if wl_item is None:
        wl_item = WatchlistItem(
            id=uuid.uuid4(),
            user_id=user_id,
            instrument_id=cand.instrument_id,
            discovery_candidate_id=cand.id,
            research_stage=ResearchStage.DISCOVERED,
            priority=WatchlistPriority.HIGH if cand.status == DiscoveryStatus.HIGH_PRIORITY_SCREEN else WatchlistPriority.MEDIUM,
            why_interesting=cand.primary_reason,
            key_risk=cand.key_risk,
        )
        db.add(wl_item)

    # Mark candidate as watchlisted
    cand.candidate_state = DiscoveryCandidateState.WATCHLISTED
    cand.watchlisted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wl_item)
    return wl_item


async def dismiss_discovery_candidate(
    db: AsyncSession,
    user_id: UUID,
    candidate_id: UUID,
) -> DiscoveryCandidate:
    """Dismiss and suppress a discovery candidate."""
    cand_stmt = select(DiscoveryCandidate).where(
        DiscoveryCandidate.id == candidate_id,
        DiscoveryCandidate.user_id == user_id,
    )
    cand_res = await db.execute(cand_stmt)
    cand = cand_res.scalar_one_or_none()
    if cand is None:
        raise ValueError(f"Discovery candidate {candidate_id} not found.")

    cand.candidate_state = DiscoveryCandidateState.DISMISSED
    cand.dismissed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cand)
    return cand


async def screen_discovery_candidate(
    db: AsyncSession,
    user_id: UUID,
    candidate_id: UUID,
    ai_provider: Optional[Any] = None,
) -> Tuple[DiscoveryCandidate, Any]:
    """Execute formal preliminary screening protocol on the discovery candidate."""
    cand_stmt = select(DiscoveryCandidate).where(
        DiscoveryCandidate.id == candidate_id,
        DiscoveryCandidate.user_id == user_id,
    )
    cand_res = await db.execute(cand_stmt)
    cand = cand_res.scalar_one_or_none()
    if cand is None:
        raise ValueError(f"Discovery candidate {candidate_id} not found.")

    from app.services import formal_review as formal_review_service
    review_res = await formal_review_service.execute_instrument_formal_review(
        db=db,
        instrument_id=cand.instrument_id,
        protocol_name="preliminary-screening",
        user_id=user_id,
        ai_provider=ai_provider,
    )

    cand.candidate_state = DiscoveryCandidateState.SCREENED
    await db.commit()
    await db.refresh(cand)
    return cand, review_res


# Alias for test compatibility
run_candidate_preliminary_screen = screen_discovery_candidate
