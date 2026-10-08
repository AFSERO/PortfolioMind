from datetime import datetime, timedelta, timezone
from dataclasses import asdict
import json

import pytest
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError

from investment_intelligence.models import ThesisSnapshot, ProtocolRun
from investment_intelligence.repositories import InstrumentRepository, IntelligenceStateRepository
from investment_intelligence.services import ProtocolRunService
from investment_intelligence.thesis import ThesisSnapshotRepository, compact_snapshot
from investment_intelligence.context import build_asset_context
from investment_intelligence.bootstrap_uber_thesis import bootstrap_uber
from investment_intelligence.providers import StaticMarketDataProvider, StaticNewsProvider, StaticPortfolioProvider, NewsItemRecord
from investment_intelligence.execution import StaticAIProvider
from investment_intelligence.workflows import ThesisReviewWorkflow

pytestmark = pytest.mark.postgres
BASE = datetime(2026, 9, 14, tzinfo=timezone.utc)


def instrument(session, symbol="UBER"):
    return InstrumentRepository(session).create(symbol=symbol, name=symbol, instrument_type="equity", currency="USD")


def snapshot(session, iid, when=BASE, rationale="Compact rationale"):
    return ThesisSnapshotRepository(session).create(iid, as_of=when, core_investment_rationale=rationale, key_assumptions=["Durable contribution"])


def test_persistence_history_latest_context_and_isolation(session):
    with session.begin():
        a, b = instrument(session), instrument(session, "OTHER")
        first = snapshot(session, a.id)
        latest = snapshot(session, a.id, BASE + timedelta(hours=1), "Latest")
        snapshot(session, a.id, BASE - timedelta(days=1), "Late insertion of old thesis")
        snapshot(session, a.id, datetime.now(timezone.utc) + timedelta(days=1), "Future")
        snapshot(session, b.id, BASE + timedelta(hours=2), "Other")
    with session.begin():
        repo = ThesisSnapshotRepository(session)
        assert repo.latest(a.id).id == latest.id
        assert repo.latest(a.id, applicable_at=BASE).id == first.id
        assert session.scalar(select(func.count()).select_from(ThesisSnapshot).where(ThesisSnapshot.instrument_id == a.id)) == 4
        context = build_asset_context(session, a.id)
        assert context["thesis_snapshot"]["core_investment_rationale"] == "Latest"
        assert context["thesis_snapshot"]["key_assumptions"] == ["Durable contribution"]
        assert "Other" not in json.dumps(context)
        repo.latest(a.id).key_assumptions.append("Detached change")
        assert repo.latest(a.id).key_assumptions == ["Durable contribution"]


def test_missing_snapshot(session):
    with session.begin():
        inst = instrument(session)
        assert build_asset_context(session, inst.id)["thesis_snapshot"] is None


@pytest.mark.parametrize("operation", [update, delete])
def test_snapshot_history_immutable(session, operation):
    with session.begin():
        inst = instrument(session)
        row = snapshot(session, inst.id)
    statement = operation(ThesisSnapshot).where(ThesisSnapshot.id == row.id)
    if operation is update:
        statement = statement.values(core_investment_rationale="Overwrite")
    with pytest.raises(IntegrityError, match="immutable"), session.begin():
        session.execute(statement)


def test_utc_bounds_and_source_run_isolation(session):
    with session.begin():
        a, b = instrument(session), instrument(session, "OTHER")
        row = snapshot(session, a.id, BASE.astimezone(timezone(timedelta(hours=3))))
        assert row.as_of == BASE and row.as_of.utcoffset() == timedelta(0)
        with pytest.raises(ValueError, match="Timezone-aware"):
            snapshot(session, a.id, BASE.replace(tzinfo=None))
        with pytest.raises(ValueError, match="12000"):
            snapshot(session, a.id, rationale="X" * 12001)
        run = ProtocolRunService(session).start("thesis-review", instrument_id=b.id)
        with pytest.raises(ValueError, match="match instrument"):
            ThesisSnapshotRepository(session).create(a.id, as_of=BASE, core_investment_rationale="x", source_protocol_run_id=run.id)


@pytest.mark.parametrize("state_baseline,has_snapshot,expected_source", [
    (BASE + timedelta(hours=2), True, "last_review_at"),
    (None, True, "thesis_snapshot"), (None, False, "fallback_30_days"),
])
def test_change_window_provider_and_context(session, state_baseline, has_snapshot, expected_source):
    with session.begin():
        inst = instrument(session)
        if has_snapshot:
            snapshot(session, inst.id)
        IntelligenceStateRepository(session).create_initial(inst.id)
        if state_baseline:
            IntelligenceStateRepository(session).update(inst.id, last_review_at=state_baseline)

    class UnfilteredNews(StaticNewsProvider):
        def get_recent_news(self, iid, *, since=None, until=None, limit=10):
            assert not session.in_transaction()
            self.since, self.until = since, until
            return [
                NewsItemRecord(title="Old event", published_at=since-timedelta(seconds=1), source="fake", instrument_id=iid),
                NewsItemRecord(title="New filing about old event", published_at=since+timedelta(seconds=1), source="fake", instrument_id=iid),
                NewsItemRecord(title="Future", published_at=until+timedelta(seconds=1), source="fake", instrument_id=iid),
            ]
    news = UnfilteredNews()
    ai = StaticAIProvider()
    workflow = ThesisReviewWorkflow(session, ai, StaticMarketDataProvider(), news, StaticPortfolioProvider())
    workflow.run(inst.id)
    supp = ai.recorded_requests[0].supplemental_context
    assert supp["baseline_source"] == expected_source
    assert supp["evidence_window_start"] == news.since.isoformat()
    assert supp["baseline_review_at"] == (state_baseline.isoformat() if state_baseline else None)
    assert supp["thesis_snapshot_as_of"] == (BASE.isoformat() if has_snapshot else None)
    if state_baseline or has_snapshot:
        assert news.since == (state_baseline or BASE)
    else:
        assert news.until-news.since == timedelta(days=30)
    assert [item["title"] for item in supp["recent_news"]] == ["New filing about old event"]
    assert "republished" in supp["change_window_guidance"]
    with session.begin():
        assert IntelligenceStateRepository(session).get(inst.id).last_review_at == state_baseline


def test_bootstrap_repeatable_state_and_terminal_run_unchanged(session):
    with session.begin():
        inst = instrument(session)
        state = IntelligenceStateRepository(session).create_initial(inst.id)
        svc = ProtocolRunService(session)
        run = svc.start("thesis-review", instrument_id=inst.id)
        terminal = svc.complete(run.id, machine_record={"recommendation": "REVIEW_REQUIRED"}, human_brief="Original low-context run", confidence="LOW")
        first, created = bootstrap_uber(session, inst.id)
        second, repeated = bootstrap_uber(session, inst.id)
        assert created and not repeated and first.id == second.id
        assert first.confidence == "MEDIUM" and first.source_protocol_run_id is None
        assert len(json.dumps(compact_snapshot(first)).encode()) < 12000
        assert IntelligenceStateRepository(session).get(inst.id) == state
        assert svc.get(run.id) == terminal
    with pytest.raises(IntegrityError), session.begin():
        session.execute(update(ProtocolRun).where(ProtocolRun.id == run.id).values(human_brief="Changed"))
