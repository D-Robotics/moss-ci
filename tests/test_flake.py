import pytest
from moss_ci.engine.flake import FlakeDetector
from moss_ci.models.test import FlakeDetection, TestConfig, MossCallSpec, ContainsSpec
from moss_ci.models.result import TestResult, EvalResult
from moss_ci.engine.scheduler import TestPlan


class MockExecutor:
    async def _execute_test(self, plan):
        return TestResult(test_name=plan.test.name, status="pass", duration=0.1, evals=[EvalResult(type="contains", passed=True)])


class TestFlakeDetector:
    @pytest.mark.asyncio
    async def test_all_pass(self):
        detector = FlakeDetector()
        flake_config = FlakeDetection(runs=3, pass_threshold=2, consensus="majority")
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"), eval=[ContainsSpec(type="contains", value="hi")], flake_detection=flake_config)
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)
        executor = MockExecutor()
        result = await detector.detect(plan, executor)
        assert result.status == "pass"
        assert result.flake_runs is not None
        assert len(result.flake_runs) == 3

    @pytest.mark.asyncio
    async def test_majority_consensus(self):
        detector = FlakeDetector()
        flake_config = FlakeDetection(runs=3, pass_threshold=2, consensus="majority")
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"), eval=[ContainsSpec(type="contains", value="hi")], flake_detection=flake_config)
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)

        class MixedExecutor:
            call_count = 0
            async def _execute_test(self, plan):
                self.call_count += 1
                status = "pass" if self.call_count <= 2 else "fail"
                return TestResult(test_name=plan.test.name, status=status, duration=0.1, evals=[EvalResult(type="contains", passed=status=="pass")])

        result = await detector.detect(plan, MixedExecutor())
        # 2 pass / 1 fail meets pass_threshold (2) but is not unanimous ->
        # the detector flags this as a flake (inconsistent but passing).
        assert result.status == "flake"
        assert result.flake_runs is not None
        assert len(result.flake_runs) == 3
