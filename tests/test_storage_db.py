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
