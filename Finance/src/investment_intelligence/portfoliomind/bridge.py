"""PortfolioMind integration bridge — synchronizes Finance protocol outputs to PortfolioMind."""

import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from investment_intelligence.portfoliomind.client import PortfolioMindClient
from investment_intelligence.portfoliomind.config import PortfolioMindBridgeConfig
from investment_intelligence.portfoliomind.exceptions import PortfolioMindSyncError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    """Result envelope for a PortfolioMind synchronization attempt."""

    synced: bool
    instrument_id: Optional[UUID] = None
    review_id: Optional[UUID] = None
    state_updated: bool = False
    technical_plan_synced: bool = False
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


class PortfolioMindBridge:
    """Coordinates syncing validated Finance protocol runs to PortfolioMind."""

    def __init__(
        self,
        client: Optional[PortfolioMindClient] = None,
        config: Optional[PortfolioMindBridgeConfig] = None,
    ):
        self.config = config or (client.config if client else PortfolioMindBridgeConfig.from_env())
        self.client = client or PortfolioMindClient(self.config)

    def sync_protocol_run(
        self,
        run_record: Any,
        finance_instrument: Any,
        *,
        research_path: Optional[str] = None,
        auto_apply_state: bool = True,
        technical_plan: Optional[dict[str, Any]] = None,
        raise_on_error: bool = False,
    ) -> SyncResult:
        """Sync a completed Finance protocol run to PortfolioMind.

        Safety Invariant:
        - If PORTFOLIOMIND_SYNC_ENABLED is False, gracefully returns skipped.
        - If raise_on_error is False, persistence failures do NOT raise or corrupt
          the local run; they return a SyncResult with error diagnostics.
        """
        if not self.config.enabled:
            return SyncResult(
                synced=False,
                skipped_reason="PORTFOLIOMIND_SYNC_ENABLED is disabled",
            )

        try:
            # 1. Resolve Instrument
            pm_instrument_id = (
                getattr(finance_instrument, "id", None)
                or (finance_instrument.get("id") if isinstance(finance_instrument, dict) else None)
                or (finance_instrument.get("instrument_id") if isinstance(finance_instrument, dict) else None)
            )
            if pm_instrument_id:
                if isinstance(pm_instrument_id, str):
                    pm_instrument_id = UUID(pm_instrument_id)
            else:
                symbol = (
                    getattr(finance_instrument, "symbol", None)
                    or (finance_instrument.get("symbol") if isinstance(finance_instrument, dict) else None)
                )
                if not symbol:
                    raise PortfolioMindSyncError(
                        "Finance instrument has no symbol and no id; cannot resolve PortfolioMind instrument"
                    )

                asset_type = (
                    getattr(finance_instrument, "instrument_type", None)
                    or (finance_instrument.get("instrument_type") if isinstance(finance_instrument, dict) else None)
                )
                venue = (
                    getattr(finance_instrument, "venue", None)
                    or (finance_instrument.get("venue") if isinstance(finance_instrument, dict) else None)
                )
                currency = (
                    getattr(finance_instrument, "currency", None)
                    or (finance_instrument.get("currency") if isinstance(finance_instrument, dict) else None)
                )

                pm_instrument_id = self.client.resolve_instrument(
                    symbol=symbol,
                    asset_type=asset_type,
                    venue=venue,
                    currency=currency,
                )

            # 2. Extract run record details
            protocol_name = (
                getattr(run_record, "protocol_name", None)
                or (run_record.get("protocol_name") if isinstance(run_record, dict) else None)
            )
            status = (
                getattr(run_record, "status", None)
                or (run_record.get("status") if isinstance(run_record, dict) else "COMPLETED")
            )
            if hasattr(status, "value"):
                status = status.value

            machine_record = (
                getattr(run_record, "machine_record", None)
                or (run_record.get("machine_record") if isinstance(run_record, dict) else None)
            )
            human_brief = (
                getattr(run_record, "human_brief", None)
                or (run_record.get("human_brief") if isinstance(run_record, dict) else None)
            )
            confidence = (
                getattr(run_record, "confidence", None)
                or (run_record.get("confidence") if isinstance(run_record, dict) else None)
            )
            run_id = (
                getattr(run_record, "id", None)
                or (run_record.get("id") if isinstance(run_record, dict) else None)
            )
            source_run_id = str(run_id) if run_id else None
            is_synthetic = bool(
                getattr(run_record, "is_synthetic", False)
                or (run_record.get("is_synthetic", False) if isinstance(run_record, dict) else False)
            )

            # 3. Post review
            review_res = self.client.post_review(
                pm_instrument_id,
                protocol=protocol_name or "protocol_run",
                status=status or "COMPLETED",
                machine_record=machine_record,
                human_brief=human_brief,
                confidence=confidence,
                research_path=research_path,
                source_run_id=source_run_id,
                auto_apply_state=auto_apply_state,
                is_synthetic=is_synthetic,
            )
            review_id = UUID(review_res["id"]) if review_res and "id" in review_res else None

            # 4. Sync technical plan if present
            tech_plan_synced = False
            plan_payload = technical_plan
            if not plan_payload and machine_record and "technical_plan" in machine_record:
                plan_payload = machine_record["technical_plan"]

            if plan_payload:
                self.client.put_technical_plan(pm_instrument_id, plan_payload)
                tech_plan_synced = True

            state_updated = bool(review_res.get("state_updated", False)) if review_res else False
            return SyncResult(
                synced=True,
                instrument_id=pm_instrument_id,
                review_id=review_id,
                state_updated=state_updated,
                technical_plan_synced=tech_plan_synced,
            )

        except Exception as err:
            logger.error("Failed to sync protocol run to PortfolioMind: %s", err, exc_info=True)
            if raise_on_error:
                raise PortfolioMindSyncError(f"PortfolioMind sync failed: {err}") from err
            return SyncResult(
                synced=False,
                error=str(err),
            )

    async def async_sync_protocol_run(
        self,
        run_record: Any,
        finance_instrument: Any,
        *,
        research_path: Optional[str] = None,
        auto_apply_state: bool = True,
        technical_plan: Optional[dict[str, Any]] = None,
        raise_on_error: bool = False,
    ) -> SyncResult:
        """Asynchronously sync a completed Finance protocol run to PortfolioMind."""
        if not self.config.enabled:
            return SyncResult(
                synced=False,
                skipped_reason="PORTFOLIOMIND_SYNC_ENABLED is disabled",
            )

        try:
            pm_instrument_id = (
                getattr(finance_instrument, "id", None)
                or (finance_instrument.get("id") if isinstance(finance_instrument, dict) else None)
                or (finance_instrument.get("instrument_id") if isinstance(finance_instrument, dict) else None)
            )
            if pm_instrument_id:
                if isinstance(pm_instrument_id, str):
                    pm_instrument_id = UUID(pm_instrument_id)
            else:
                symbol = (
                    getattr(finance_instrument, "symbol", None)
                    or (finance_instrument.get("symbol") if isinstance(finance_instrument, dict) else None)
                )
                if not symbol:
                    raise PortfolioMindSyncError(
                        "Finance instrument has no symbol and no id; cannot resolve PortfolioMind instrument"
                    )

                asset_type = (
                    getattr(finance_instrument, "instrument_type", None)
                    or (finance_instrument.get("instrument_type") if isinstance(finance_instrument, dict) else None)
                )
                venue = (
                    getattr(finance_instrument, "venue", None)
                    or (finance_instrument.get("venue") if isinstance(finance_instrument, dict) else None)
                )
                currency = (
                    getattr(finance_instrument, "currency", None)
                    or (finance_instrument.get("currency") if isinstance(finance_instrument, dict) else None)
                )

                pm_instrument_id = await self.client.resolve_instrument(
                    symbol=symbol,
                    asset_type=asset_type,
                    venue=venue,
                    currency=currency,
                )

            protocol_name = (
                getattr(run_record, "protocol_name", None)
                or (run_record.get("protocol_name") if isinstance(run_record, dict) else None)
            )
            status = (
                getattr(run_record, "status", None)
                or (run_record.get("status") if isinstance(run_record, dict) else "COMPLETED")
            )
            if hasattr(status, "value"):
                status = status.value

            machine_record = (
                getattr(run_record, "machine_record", None)
                or (run_record.get("machine_record") if isinstance(run_record, dict) else None)
            )
            human_brief = (
                getattr(run_record, "human_brief", None)
                or (run_record.get("human_brief") if isinstance(run_record, dict) else None)
            )
            confidence = (
                getattr(run_record, "confidence", None)
                or (run_record.get("confidence") if isinstance(run_record, dict) else None)
            )
            run_id = (
                getattr(run_record, "id", None)
                or (run_record.get("id") if isinstance(run_record, dict) else None)
            )
            source_run_id = str(run_id) if run_id else None
            is_synthetic = bool(
                getattr(run_record, "is_synthetic", False)
                or (run_record.get("is_synthetic", False) if isinstance(run_record, dict) else False)
            )

            review_res = await self.client.post_review(
                pm_instrument_id,
                protocol=protocol_name or "protocol_run",
                status=status or "COMPLETED",
                machine_record=machine_record,
                human_brief=human_brief,
                confidence=confidence,
                research_path=research_path,
                source_run_id=source_run_id,
                auto_apply_state=auto_apply_state,
                is_synthetic=is_synthetic,
            )
            review_id = UUID(review_res["id"]) if review_res and "id" in review_res else None

            tech_plan_synced = False
            plan_payload = technical_plan
            if not plan_payload and machine_record and "technical_plan" in machine_record:
                plan_payload = machine_record["technical_plan"]

            if plan_payload:
                await self.client.put_technical_plan(pm_instrument_id, plan_payload)
                tech_plan_synced = True

            state_updated = bool(review_res.get("state_updated", False)) if review_res else False
            return SyncResult(
                synced=True,
                instrument_id=pm_instrument_id,
                review_id=review_id,
                state_updated=state_updated,
                technical_plan_synced=tech_plan_synced,
            )

        except Exception as err:
            logger.error("Failed to sync protocol run to PortfolioMind: %s", err, exc_info=True)
            if raise_on_error:
                raise PortfolioMindSyncError(f"PortfolioMind sync failed: {err}") from err
            return SyncResult(
                synced=False,
                error=str(err),
            )

