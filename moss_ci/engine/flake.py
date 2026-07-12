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
        passed_count = sum(1 for r in runs if r.status == "pass")
        if flake.consensus == "unanimous":
            final_status = "pass" if passed_count == flake.runs else "fail"
        else:
            final_status = "pass" if passed_count >= flake.pass_threshold else "fail"
        if passed_count < flake.runs and passed_count >= flake.pass_threshold:
            final_status = "flake"
        return TestResult(
            test_name=plan.test.name, status=final_status,
            duration=sum(r.duration for r in runs),
            moss_output=runs[0].moss_output,
            moss_tool_calls=runs[0].moss_tool_calls,
            evals=runs[0].evals,
            flake_runs=runs,
        )
