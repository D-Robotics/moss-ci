import pytest
from moss_ci.storage.db import Database, get_db
from moss_ci.storage.models import RunRecord, TestResultRecord
from moss_ci.storage.repository import RunRepository
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, RunStatus, EvalResult


class TestDatabase:
    @pytest.mark.asyncio
    async def test_init_and_create_tables(self):
        db = Database(url="sqlite+aiosqlite:///:memory:")
        await db.init()
        async with db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        await db.close()

    @pytest.mark.asyncio
    async def test_get_db_singleton(self):
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2


class TestRunRepository:
    @pytest.fixture
    async def repo(self):
        db = Database(url="sqlite+aiosqlite:///:memory:")
        await db.init()
        repo = RunRepository(db)
        yield repo
        await db.close()

    @pytest.mark.asyncio
    async def test_save_and_get(self, repo):
        result = PipelineResult(
            run_id="run-001", pipeline_name="test-pipeline",
            status=RunStatus.SUCCESS, summary="all passed",
            suites=[SuiteResult(suite_name="suite-a", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", duration=0.5,
                                      evals=[EvalResult(type="contains", passed=True)])])]
        )
        saved = await repo.save(result)
        assert saved.run_id == "run-001"
        loaded = await repo.get("run-001")
        assert loaded is not None
        assert loaded.status == RunStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_list_runs(self, repo):
        for i in range(3):
            await repo.save(PipelineResult(run_id=f"run-{i:03d}", pipeline_name="test", status=RunStatus.SUCCESS))
        runs = await repo.list(limit=2)
        assert len(runs) == 2

    @pytest.mark.asyncio
    async def test_flake_runs_roundtrip(self, repo):
        # A flake test stores N individual run verdicts; they must survive a
        # save→get cycle so `status`/`logs` can show which runs passed.
        flake_run = TestResult(test_name="t1", status="pass", duration=0.1,
                               moss_output="READY",
                               evals=[EvalResult(type="contains", passed=True)])
        result = PipelineResult(
            run_id="run-flake", pipeline_name="test", status=RunStatus.FAILED,
            summary="1 flake",
            suites=[SuiteResult(suite_name="suite-a", total=1, flake=1,
                    tests=[TestResult(test_name="t1", status="flake", duration=0.3,
                                      moss_output="READY",
                                      evals=[EvalResult(type="contains", passed=True)],
                                      flake_runs=[flake_run])])]
        )
        await repo.save(result)
        loaded = await repo.get("run-flake")
        assert loaded is not None
        test = loaded.suites[0].tests[0]
        assert test.status == "flake"
        assert test.flake_runs is not None and len(test.flake_runs) == 1
        assert test.flake_runs[0].status == "pass"
        assert test.flake_runs[0].moss_output == "READY"
        assert test.flake_runs[0].evals[0].passed is True
