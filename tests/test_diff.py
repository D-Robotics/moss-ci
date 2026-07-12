import pytest
from moss_ci.engine.diff import DiffEngine
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, EvalResult, RunStatus


def make_result(run_id: str, test_statuses: dict[str, str]) -> PipelineResult:
    tests = [TestResult(test_name=name, status=status) for name, status in test_statuses.items()]
    return PipelineResult(
        run_id=run_id, pipeline_name="test", status=RunStatus.SUCCESS,
        suites=[SuiteResult(suite_name="s1", total=len(tests), passed=sum(1 for t in tests if t.status=="pass"),
                            failed=sum(1 for t in tests if t.status=="fail"), tests=tests)]
    )


class TestDiffEngine:
    def test_new_failure(self):
        prev = make_result("r1", {"t1": "pass", "t2": "pass"})
        curr = make_result("r2", {"t1": "fail", "t2": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.new_failures) == 1
        assert diff.new_failures[0].test_name == "t1"

    def test_fixed(self):
        prev = make_result("r1", {"t1": "fail", "t2": "pass"})
        curr = make_result("r2", {"t1": "pass", "t2": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.fixed) == 1
        assert diff.fixed[0].test_name == "t1"

    def test_no_change(self):
        prev = make_result("r1", {"t1": "pass"})
        curr = make_result("r2", {"t1": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.new_failures) == 0
        assert len(diff.fixed) == 0

    def test_score_change(self):
        prev = PipelineResult(
            run_id="r1", pipeline_name="test", status=RunStatus.SUCCESS,
            suites=[SuiteResult(suite_name="s1", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", evals=[EvalResult(type="llm_judge", passed=True, score=4.5)])])]
        )
        curr = PipelineResult(
            run_id="r2", pipeline_name="test", status=RunStatus.SUCCESS,
            suites=[SuiteResult(suite_name="s1", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", evals=[EvalResult(type="llm_judge", passed=True, score=3.0)])])]
        )
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.degraded) == 1
