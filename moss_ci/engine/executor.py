from __future__ import annotations
import asyncio
import time
import structlog
from moss_ci.engine.scheduler import SuitePlan, TestPlan, ExecutionPlan
from moss_ci.models.result import (
    SuiteResult, TestResult, PipelineResult, RunStatus, EvalResult,
)

logger = structlog.get_logger(__name__)


class Executor:
    """Executes test plans with concurrency control."""

    def __init__(self, max_concurrency: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrency)

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
                async with self._semaphore:
                    return await self._execute_test(tp)

        tasks = [run_with_limit(tp) for tp in suite.tests]
        test_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[TestResult] = []
        passed = failed = error_cnt = 0
        for i, result in enumerate(test_results):
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
            results.append(tr)
            if suite.fail_fast and tr.status in ("fail", "error"):
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break

        duration = time.monotonic() - start
        return SuiteResult(
            suite_name=suite.suite_name,
            total=len(suite.tests),
            passed=passed, failed=failed, error=error_cnt,
            skipped=suite.skipped_count,
            duration=duration, tests=results,
        )

    async def _execute_test(self, test_plan: TestPlan) -> TestResult:
        if test_plan.test.flake_detection is not None:
            from moss_ci.engine.flake import FlakeDetector
            return await FlakeDetector().detect(test_plan, self)
        # SCAFFOLD: Moss output is mocked here. The real MossRunner (built in
        # Tasks 5-6) is NOT yet wired in — that switchover is Task 16.
        # Until then, contains/tool_sequence/tool_args evaluators are
        # exercised against synthetic output, and llm_judge returns a
        # hardcoded score (see evaluator/llm_judge.py). This is deliberate:
        # it lets the whole pipeline run and pass tests before a real Moss
        # instance is available.
        start = time.monotonic()
        test = test_plan.test
        try:
            moss_output = f"[mock] Moss: {test.moss.prompt or test.moss.task}"
            moss_tool_calls: list[dict] = []

            eval_results: list[EvalResult] = []
            for eval_spec in test.eval:
                er = await self._evaluate(eval_spec, moss_output, moss_tool_calls)
                eval_results.append(er)

            all_passed = all(er.passed for er in eval_results)
            status = "pass" if all_passed else "fail"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return TestResult(test_name=test.name, status="error", duration=time.monotonic() - start, error=str(e))

        return TestResult(
            test_name=test.name, status=status, duration=time.monotonic() - start,
            moss_output=moss_output, moss_tool_calls=moss_tool_calls, evals=eval_results,
        )

    async def _evaluate(self, eval_spec, moss_output: str, moss_tool_calls: list[dict]) -> EvalResult:
        from moss_ci.evaluator.registry import EvaluatorRegistry
        return await EvaluatorRegistry().evaluate(eval_spec, moss_output, moss_tool_calls)
