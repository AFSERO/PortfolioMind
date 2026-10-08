"""Scheduled Daily Briefing Service.

Provides in-process automated intelligence gathering on a configured daily schedule,
running safely within the FastAPI application lifespan.

Invariants:
- Automated collection and filtering only: NO automatic formal reviews, NO automatic trading.
- Zero state mutations: InstrumentIntelligenceState and transactions remain untouched.
- Fault isolation: Failures for one user or provider do not crash the scheduler or other users.
- Lightweight: Zero external queue infrastructure (no Celery, Redis, Kafka).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Set
from uuid import UUID
import zoneinfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_session_factory
from app.models.briefing import BriefingItem, BriefingRun, BriefingTriggerType
from app.models.user import User
from app.schemas.briefing import BriefingRunResponse
from app.services import briefing as briefing_service

logger = logging.getLogger(__name__)


async def run_scheduled_briefing_for_user(
    db: AsyncSession,
    user_id: UUID,
    evidence_since: Optional[datetime] = None,
    reasoner: Optional[Any] = None,
) -> Optional[BriefingRunResponse]:
    """Execute a scheduled briefing cycle for a single user.

    Uses SCHEDULED trigger provenance, calculates incremental evidence window,
    checks cross-process DB at-most-once constraint, and isolates exceptions.
    """
    try:
        tz = zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)
    except Exception:
        tz = timezone.utc

    now_local = datetime.now(tz)
    today_start_utc = datetime(
        now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=tz
    ).astimezone(timezone.utc)

    # 1. Cross-process at-most-once check
    existing_sched_stmt = (
        select(BriefingRun)
        .options(
            selectinload(BriefingRun.items).selectinload(BriefingItem.instrument)
        )
        .where(
            BriefingRun.user_id == user_id,
            BriefingRun.trigger_type == BriefingTriggerType.SCHEDULED,
            BriefingRun.generated_at >= today_start_utc,
        )
        .order_by(BriefingRun.generated_at.desc())
        .limit(1)
    )
    existing_sched_res = await db.execute(existing_sched_stmt)
    existing_sched_run = existing_sched_res.scalar_one_or_none()
    if existing_sched_run is not None:
        logger.info(
            "Scheduled briefing already executed today (%s) for user %s (run_id=%s); skipping duplicate execution.",
            now_local.date().isoformat(),
            user_id,
            existing_sched_run.id,
        )
        return briefing_service._run_to_response(existing_sched_run)

    logger.info("Executing scheduled briefing run for user %s", user_id)
    try:
        run = await briefing_service.generate_briefing_run(
            db=db,
            user_id=user_id,
            scope="PORTFOLIO_AND_WATCHLIST",
            force_refresh=True,
            trigger_type=BriefingTriggerType.SCHEDULED,
            evidence_since=evidence_since,
            reasoner=reasoner,
        )
        logger.info(
            "Scheduled briefing completed for user %s: run_id=%s, items_shown=%d, items_filtered=%d",
            user_id,
            run.id,
            run.items_shown,
            run.items_filtered,
        )

        # Opportunity Evaluation Cycle (isolated failure domain)
        try:
            from app.services import opportunity as opportunity_service
            opp_summary = await opportunity_service.evaluate_user_opportunities(
                db=db,
                user_id=user_id,
                force_refresh=False,
                reasoner=reasoner,
            )
            logger.info(
                "Scheduled opportunity evaluation completed for user %s: evaluated=%d, opportunities_found=%d (now=%d, soon=%d)",
                user_id,
                opp_summary.evaluated,
                opp_summary.opportunities_found,
                opp_summary.research_now_count,
                opp_summary.research_soon_count,
            )
        except Exception as opp_err:
            logger.error(
                "Scheduled opportunity evaluation failed for user %s; briefing run preserved: %s",
                user_id,
                opp_err,
                exc_info=True,
            )

        # Discovery Scan Cycle (isolated failure domain)
        try:
            from app.models.discovery import DiscoveryTriggerType, DiscoveryUniverse
            from app.services import discovery as discovery_service
            disc_run = await discovery_service.run_discovery_scan_for_user(
                db=db,
                user_id=user_id,
                universe=DiscoveryUniverse.US_LARGE_CAP,
                trigger_type=DiscoveryTriggerType.SCHEDULED,
                force_refresh=False,
                reasoner=reasoner,
            )
            logger.info(
                "Scheduled discovery scan completed for user %s: scanned=%d, surfaced=%d",
                user_id,
                disc_run.instruments_scanned,
                disc_run.candidates_surfaced,
            )
        except Exception as disc_err:
            logger.error(
                "Scheduled discovery scan failed for user %s; briefing run preserved: %s",
                user_id,
                disc_err,
                exc_info=True,
            )

        return run
    except Exception as e:
        logger.error(
            "Scheduled briefing run failed for user %s: %s",
            user_id,
            e,
            exc_info=True,
        )
        return None


async def run_scheduled_briefing_cycle(
    session_factory: Optional[async_sessionmaker] = None,
    target_user_id: Optional[UUID] = None,
    reasoner: Optional[Any] = None,
) -> List[BriefingRunResponse]:
    """Execute a scheduled briefing cycle across all active users (or a specific target user).

    Yields a list of successfully created BriefingRunResponse objects.
    Each user runs in its own isolated DB transaction session.
    """
    factory = session_factory or get_session_factory()
    user_ids: List[UUID] = []

    if target_user_id is not None:
        user_ids = [target_user_id]
    else:
        try:
            async with factory() as db:
                result = await db.execute(select(User.id))
                user_ids = list(result.scalars().all())
        except Exception as e:
            logger.error("Failed to query users for scheduled briefing cycle: %s", e)
            return []

    if not user_ids:
        logger.info("No users found for scheduled briefing cycle.")
        return []

    logger.info(
        "Starting scheduled briefing cycle for %d user(s)", len(user_ids)
    )
    completed_runs: List[BriefingRunResponse] = []

    for uid in user_ids:
        try:
            async with factory() as db:
                run = await run_scheduled_briefing_for_user(
                    db=db,
                    user_id=uid,
                    reasoner=reasoner,
                )
                if run is not None:
                    completed_runs.append(run)
        except Exception as e:
            logger.error(
                "Unhandled error in scheduled briefing cycle for user %s: %s",
                uid,
                e,
                exc_info=True,
            )

    logger.info(
        "Scheduled briefing cycle completed: %d/%d users processed successfully",
        len(completed_runs),
        len(user_ids),
    )
    return completed_runs


class BriefingScheduler:
    """In-process background scheduler for automated daily briefings.

    Runs within the FastAPI application lifespan, waking periodically to evaluate
    configured schedule trigger conditions.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._last_run_dates: Dict[UUID, date] = {}
        self._last_cycle_date: Optional[date] = None

    @property
    def is_running(self) -> bool:
        return self._is_running and self._task is not None and not self._task.done()

    def get_schedule_info(self) -> Dict[str, Any]:
        """Compute human and machine-readable schedule metadata."""
        tz_str = settings.BRIEFING_SCHEDULE_TIMEZONE
        try:
            tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            tz = timezone.utc
            tz_str = "UTC"

        now_local = datetime.now(tz)
        target_hour = settings.BRIEFING_SCHEDULE_HOUR
        target_minute = settings.BRIEFING_SCHEDULE_MINUTE

        candidate_today = datetime(
            now_local.year,
            now_local.month,
            now_local.day,
            target_hour,
            target_minute,
            0,
            tzinfo=tz,
        )

        if candidate_today > now_local:
            next_local = candidate_today
        else:
            next_local = candidate_today + timedelta(days=1)

        next_utc = next_local.astimezone(timezone.utc)
        target_utc_sample = candidate_today.astimezone(timezone.utc)

        return {
            "timezone": tz_str,
            "local_target": f"{target_hour:02d}:{target_minute:02d} {tz_str}",
            "utc_target": f"{target_utc_sample.strftime('%H:%M')} UTC",
            "next_local_execution": next_local.isoformat(),
            "next_utc_execution": next_utc.isoformat(),
        }

    def start(self, session_factory: Optional[async_sessionmaker] = None) -> None:
        """Start the background scheduling loop if not already running."""
        if self.is_running:
            logger.warning("BriefingScheduler is already running.")
            return

        self._is_running = True
        self._task = asyncio.create_task(
            self._scheduler_loop(session_factory),
            name="briefing-scheduler-task",
        )
        info = self.get_schedule_info()
        logger.info(
            "BriefingScheduler started [Timezone: %s | Local Target: %s | UTC Target: %s | Next Local: %s | Next UTC: %s | Check interval: %ds]",
            info["timezone"],
            info["local_target"],
            info["utc_target"],
            info["next_local_execution"],
            info["next_utc_execution"],
            settings.BRIEFING_SCHEDULE_CHECK_INTERVAL_SECONDS,
        )

    async def stop(self) -> None:
        """Gracefully stop the background scheduling loop."""
        if not self._is_running:
            return

        logger.info("Stopping BriefingScheduler...")
        self._is_running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("BriefingScheduler stopped successfully.")

    def _get_tz(self) -> timezone:
        try:
            return zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)  # type: ignore[return-value]
        except Exception:
            return timezone.utc

    def should_trigger(self, current_dt: datetime) -> bool:
        """Determine if current time matches the scheduled hour/minute and hasn't fired today.
        
        Evaluates current_dt converted explicitly to BRIEFING_SCHEDULE_TIMEZONE.
        """
        try:
            tz = zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)
        except Exception:
            tz = timezone.utc

        if current_dt.tzinfo is None:
            current_local = current_dt.replace(tzinfo=timezone.utc).astimezone(tz)
        else:
            current_local = current_dt.astimezone(tz)

        target_hour = settings.BRIEFING_SCHEDULE_HOUR
        target_minute = settings.BRIEFING_SCHEDULE_MINUTE
        current_date = current_local.date()

        if self._last_cycle_date == current_date:
            return False

        if current_local.hour == target_hour and current_local.minute == target_minute:
            return True

        return False

    async def _scheduler_loop(
        self, session_factory: Optional[async_sessionmaker] = None
    ) -> None:
        """Periodic background evaluation loop."""
        try:
            tz = zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)
        except Exception:
            tz = timezone.utc

        while self._is_running:
            try:
                now_local = datetime.now(tz)
                if self.should_trigger(now_local):
                    logger.info(
                        "Briefing schedule condition met at %s (%s). Triggering daily briefing cycle.",
                        now_local.isoformat(),
                        settings.BRIEFING_SCHEDULE_TIMEZONE,
                    )
                    self._last_cycle_date = now_local.date()
                    await run_scheduled_briefing_cycle(session_factory=session_factory)

                await asyncio.sleep(settings.BRIEFING_SCHEDULE_CHECK_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in BriefingScheduler loop: %s", e, exc_info=True)
                await asyncio.sleep(settings.BRIEFING_SCHEDULE_CHECK_INTERVAL_SECONDS)


# Global singleton instance
scheduler = BriefingScheduler()
