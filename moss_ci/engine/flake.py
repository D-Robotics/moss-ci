import structlog
from moss_ci.engine.scheduler import TestPlan
from moss_ci.models.result import TestResult

logger = structlog.get_logger(__name__)


class FlakeDetector:
    async def detect(self, plan: TestPlan, executor) -> TestResult:
        flake = plan.test.flake_detection
        runs: list[TestResult] = []
        # Call the single-run path, NOT _execute_test — otherwise re-running
        # a flake test re-enters the flake branch and recurses infinitely.
        run_once = getattr(executor, "_run_test_once", executor._execute_test)
        for i in range(flake.runs):
            result = await run_once(plan)
            runs.append(result)
        # A run that was skipped (e.g. judge endpoint unreachable from this
        # host) is environmental, not a verdict. If EVERY run skipped, the
        # whole test is skipped; otherwise skipped runs are excluded from the
        # pass/fail consensus so a reachable-then-not host can't flunk it.
        non_skipped = [r for r in runs if r.status != "skipped"]
        if not non_skipped:
            final_status = "skipped"
            passed_count = 0
        else:
            passed_count = sum(1 for r in non_skipped if r.status == "pass")
            if flake.consensus == "unanimous":
                final_status = "pass" if passed_count == len(non_skipped) else "fail"
            else:
                final_status = "pass" if passed_count >= flake.pass_threshold else "fail"
            if passed_count < len(non_skipped) and passed_count >= flake.pass_threshold:
                final_status = "flake"
        return TestResult(
            test_name=plan.test.name, status=final_status,
            duration=sum(r.duration for r in runs),
            moss_output=runs[0].moss_output,
            moss_tool_calls=runs[0].moss_tool_calls,
            evals=runs[0].evals,
            flake_runs=runs,
        )
