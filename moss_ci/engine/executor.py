from __future__ import annotations
import asyncio
import shutil
import tempfile
import time
from pathlib import Path
import structlog
from moss_ci.engine.scheduler import SuitePlan, TestPlan, ExecutionPlan
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import (
    SuiteResult, TestResult, PipelineResult, RunStatus, EvalResult,
)

logger = structlog.get_logger(__name__)


class Executor:
    """Executes test plans with concurrency control."""

    def __init__(self, max_concurrency: int | None = None, runner=None):
        # Outer (cross-suite) semaphore. None means no global cap — each suite's
        # own max_concurrency (from YAML) is then the sole limit. A non-None
        # value (set via CLI --concurrency) caps every suite at that many.
        self._semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency else None
        self._runner = runner  # Optional[MossRunner]; None = scaffold mock output

    async def execute(self, plan: ExecutionPlan) -> PipelineResult:
        suite_tasks = [self._execute_suite(suite) for suite in plan.suites]
        suite_results = await asyncio.gather(*suite_tasks, return_exceptions=True)

        results: list[SuiteResult] = []
        for i, result in enumerate(suite_results):
            if isinstance(result, Exception):
                logger.error("suite.error", suite=plan.suites[i].suite_name, error=str(result))
                results.append(SuiteResult(
                    suite_name=plan.suites[i].suite_name,
                    total=len(plan.suites[i].tests),
                    error=len(plan.suites[i].tests),
                ))
            else:
                results.append(result)

        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        total_error = sum(r.error for r in results)
        overall_status = RunStatus.SUCCESS if total_failed == 0 and total_error == 0 else RunStatus.FAILED

        return PipelineResult(
            pipeline_name="pipeline",
            status=overall_status,
            suites=results,
            summary=f"{total_passed} passed, {total_failed} failed, {total_error} error",
        )

    async def _execute_suite(self, suite: SuitePlan) -> SuiteResult:
        start = time.monotonic()
        semaphore = asyncio.Semaphore(suite.max_concurrency)

        async def run_with_limit(tp: TestPlan) -> TestResult:
            async with semaphore:
                if self._semaphore is not None:
                    async with self._semaphore:
                        return await self._execute_test(tp)
                return await self._execute_test(tp)

        # Schedule as real Tasks so fail_fast can cancel pending ones.
        # (Calling .done()/.cancel() on bare coroutines raises AttributeError,
        #  which the old gather-only path never hit because suites passed.)
        results_by_index: dict[int, TestResult | Exception] = {}
        pending: set[asyncio.Task] = set()
        index_by_task: dict[asyncio.Task, int] = {}
        for i, tp in enumerate(suite.tests):
            t = asyncio.ensure_future(run_with_limit(tp))
            index_by_task[t] = i
            pending.add(t)

        stopped = False
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                i = index_by_task[t]
                exc = t.exception()
                if exc is not None:
                    if isinstance(exc, asyncio.CancelledError):
                        results_by_index[i] = TestResult(
                            test_name=suite.tests[i].test.name, status="error", error="cancelled")
                    else:
                        results_by_index[i] = exc
                else:
                    results_by_index[i] = t.result()
                if suite.fail_fast and not stopped:
                    tr = results_by_index[i]
                    is_fail = isinstance(tr, Exception) or (
                        isinstance(tr, TestResult) and tr.status in ("fail", "error"))
                    if is_fail:
                        stopped = True
                        for p in pending:
                            p.cancel()
            if stopped:
                # Drain the cancelled tasks so their results are recorded.
                if pending:
                    cancelled_done, _ = await asyncio.wait(pending)
                    for t in cancelled_done:
                        i = index_by_task[t]
                        exc = t.exception()
                        if isinstance(exc, asyncio.CancelledError):
                            results_by_index[i] = TestResult(
                                test_name=suite.tests[i].test.name, status="error", error="cancelled")
                        elif exc is not None:
                            results_by_index[i] = exc
                        else:
                            results_by_index[i] = t.result()
                    pending = set()

        results: list[TestResult] = []
        passed = failed = error_cnt = skipped_cnt = 0
        for i in range(len(suite.tests)):
            result = results_by_index.get(i)
            if isinstance(result, Exception):
                tr = TestResult(test_name=suite.tests[i].test.name, status="error", error=str(result))
                error_cnt += 1
            else:
                tr = result
                if tr.status == "pass":
                    passed += 1
                elif tr.status == "fail":
                    failed += 1
                elif tr.status == "error":
                    error_cnt += 1
                elif tr.status == "skipped":
                    skipped_cnt += 1
            results.append(tr)

        duration = time.monotonic() - start
        return SuiteResult(
            suite_name=suite.suite_name,
            total=len(suite.tests),
            passed=passed, failed=failed, error=error_cnt,
            skipped=suite.skipped_count + skipped_cnt,
            duration=duration, tests=results,
        )

    async def _execute_test(self, test_plan: TestPlan) -> TestResult:
        if test_plan.test.flake_detection is not None:
            from moss_ci.engine.flake import FlakeDetector
            return await FlakeDetector().detect(test_plan, self)
        return await self._run_test_once(test_plan)

    async def _run_test_once(self, test_plan: TestPlan) -> TestResult:
        # Single non-flake execution. FlakeDetector calls THIS (not
        # _execute_test) so re-running a flake test doesn't re-trigger the
        # flake branch → infinite recursion.
        start = time.monotonic()
        test = test_plan.test
        try:
            if self._runner is not None:
                # Isolate workdir: copy the test's workdir to a fresh temp dir
                # so Moss mutates a throwaway copy, not the source fixtures.
                # Without this, a run that creates hello.txt leaves it behind
                # and the next run's "create hello.txt" test sees it already
                # exists → Moss does nothing → tool_sequence fails. Each call
                # (including each flake run) gets its own clean copy.
                workdir = await self._stage_workdir(test.moss.workdir)
                moss_spec = MossCallSpec(
                    prompt=test.moss.prompt,
                    task=test.moss.task,
                    conversation=test.moss.conversation,
                    context=test.moss.context,
                    workdir=workdir,
                    env=test.moss.env,
                )
                if test.moss.task:
                    moss_result = await self._runner.run_task(moss_spec)
                elif test.moss.conversation:
                    moss_result = await self._runner.run_conversation(moss_spec)
                else:
                    moss_result = await self._runner.run(moss_spec)
                moss_output = moss_result.output
                moss_tool_calls = list(moss_result.tool_calls)
                files_modified = list(moss_result.files_modified)
                exit_code = moss_result.exit_code
            else:
                # SCAFFOLD fallback — no real runner wired in.
                moss_output = f"[mock] Moss: {test.moss.prompt or test.moss.task}"
                moss_tool_calls: list[dict] = []
                files_modified = []
                exit_code = 0

            eval_results: list[EvalResult] = []
            for eval_spec in test.eval:
                er = await self._evaluate(
                    eval_spec, moss_output, moss_tool_calls,
                    files_modified=files_modified, exit_code=exit_code,
                )
                eval_results.append(er)

            # A skipped eval (e.g. judge unreachable from this host) is neither
            # pass nor fail — exclude it from the verdict. If every eval was
            # skipped, the test is skipped; if the non-skipped ones all pass,
            # the test passes; any non-skipped fail fails it.
            decisive = [er for er in eval_results if not er.skipped]
            if not decisive:
                status = "skipped"
            else:
                status = "pass" if all(er.passed for er in decisive) else "fail"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return TestResult(test_name=test.name, status="error", duration=time.monotonic() - start, error=str(e))

        return TestResult(
            test_name=test.name, status=status, duration=time.monotonic() - start,
            moss_output=moss_output, moss_tool_calls=moss_tool_calls, evals=eval_results,
        )

    async def _evaluate(self, eval_spec, moss_output: str, moss_tool_calls: list[dict],
                        files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        from moss_ci.evaluator.registry import EvaluatorRegistry
        return await EvaluatorRegistry().evaluate(
            eval_spec, moss_output, moss_tool_calls,
            files_modified=files_modified, exit_code=exit_code,
        )

    @staticmethod
    async def _stage_workdir(workdir: str | None) -> str | None:
        """Copy the test's workdir to a fresh temp dir, return that path.

        Moss runs against the copy, so mutations (created/edited files, pytest
        runs) never touch the source fixtures and never leak into the next run.
        Returns None when there's no workdir to stage. The temp dir is left in
        place for the process lifetime (the OS / runner reaps it); we don't
        clean up eagerly because a flake run's later inspection (logs/status)
        may want to read what Moss produced.
        """
        if not workdir:
            return None
        src = Path(workdir)
        if not src.is_dir():
            return None
        # Skip Moss's own runtime state when copying — sessions/history are per-
        # invocation and must not carry over between isolated runs.
        def _copy() -> str:
            dst = Path(tempfile.mkdtemp(prefix="moss-ci-wd-"))
            ignore = shutil.ignore_patterns(".moss", "__pycache__")
            shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
            return str(dst)
        return await asyncio.to_thread(_copy)
