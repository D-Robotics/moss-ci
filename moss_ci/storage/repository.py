from __future__ import annotations
from moss_ci.storage.db import Database
from moss_ci.storage.models import RunRecord, SuiteResultRecord, TestResultRecord, EvalResultRecord
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, EvalResult, RunStatus
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class RunRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save(self, result: PipelineResult) -> PipelineResult:
        async with self.db.get_session() as session:
            run = RunRecord(
                run_id=result.run_id, pipeline_name=result.pipeline_name,
                status=result.status.value, summary=result.summary,
                total_duration=result.total_duration, completed_at=result.completed_at,
            )
            for suite in result.suites:
                sr = SuiteResultRecord(
                    suite_name=suite.suite_name, total=suite.total,
                    passed=suite.passed, failed=suite.failed, flake=suite.flake,
                    error=suite.error, skipped=suite.skipped, duration=suite.duration,
                )
                for test in suite.tests:
                    tr = TestResultRecord(
                        test_name=test.test_name, status=test.status, duration=test.duration,
                        moss_output=test.moss_output, moss_tool_calls=test.moss_tool_calls,
                        flake_runs=self._dump_flake_runs(test.flake_runs),
                        error=test.error,
                    )
                    for ev in test.evals:
                        tr.evals.append(EvalResultRecord(
                            type=ev.type, passed=1 if ev.passed else 0,
                            score=ev.score,
                            details=self._eval_details(ev),
                            error=ev.error,
                        ))
                    sr.tests.append(tr)
                run.suites.append(sr)
            session.add(run)
            await session.commit()
        return result

    async def get(self, run_id: str) -> PipelineResult | None:
        async with self.db.get_session() as session:
            # Eager-load suites -> tests -> evals. Async sessions cannot lazy
            # load relationships (raises MissingGreenlet), and _to_domain walks
            # the full nested graph, so everything must be loaded up front.
            stmt = (
                select(RunRecord)
                .where(RunRecord.run_id == run_id)
                .options(
                    selectinload(RunRecord.suites)
                    .selectinload(SuiteResultRecord.tests)
                    .selectinload(TestResultRecord.evals)
                )
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._to_domain(record)

    async def list(self, limit: int = 20, offset: int = 0) -> list[PipelineResult]:
        async with self.db.get_session() as session:
            stmt = (
                select(RunRecord)
                .order_by(RunRecord.created_at.desc())
                .limit(limit)
                .offset(offset)
                .options(
                    selectinload(RunRecord.suites)
                    .selectinload(SuiteResultRecord.tests)
                    .selectinload(TestResultRecord.evals)
                )
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [self._to_domain(r) for r in records]

    def _to_domain(self, record: RunRecord) -> PipelineResult:
        suites = []
        for sr in record.suites:
            tests = []
            for tr in sr.tests:
                evals = [self._eval_to_domain(er) for er in tr.evals]
                tests.append(TestResult(test_name=tr.test_name, status=tr.status, duration=tr.duration,
                                        moss_output=tr.moss_output, moss_tool_calls=tr.moss_tool_calls,
                                        evals=evals, error=tr.error,
                                        flake_runs=self._load_flake_runs(tr.flake_runs)))
            suites.append(SuiteResult(suite_name=sr.suite_name, total=sr.total, passed=sr.passed,
                                  failed=sr.failed, flake=sr.flake, error=sr.error, skipped=sr.skipped,
                                  duration=sr.duration, tests=tests))
        return PipelineResult(run_id=record.run_id, pipeline_name=record.pipeline_name,
                              status=RunStatus(record.status), summary=record.summary,
                              suites=suites, total_duration=record.total_duration,
                              created_at=record.created_at, completed_at=record.completed_at)

    @staticmethod
    def _dump_flake_runs(flake_runs) -> list | None:
        # Serialize each flake run's TestResult to a plain dict. Flake runs are
        # single-shot results, so their own flake_runs is None — no recursion.
        if not flake_runs:
            return None
        return [r.model_dump(mode="json") for r in flake_runs]

    @staticmethod
    def _load_flake_runs(data) -> list[TestResult] | None:
        if not data:
            return None
        return [TestResult.model_validate(d) for d in data]

    @staticmethod
    def _eval_details(ev) -> dict:
        # Persist `skipped` inside the JSON details column rather than adding a
        # new DB column (avoids another migration). The flag is popped on load.
        d = dict(ev.details or {})
        if ev.skipped:
            d["_skipped"] = True
        return d

    @staticmethod
    def _eval_to_domain(er) -> EvalResult:
        # Restore skipped from details (written by _eval_details). Old rows
        # without the flag simply read skipped=False.
        d = dict(er.details or {})
        skipped = bool(d.pop("_skipped", False))
        return EvalResult(type=er.type, passed=bool(er.passed), score=er.score,
                         details=d, error=er.error, skipped=skipped)
