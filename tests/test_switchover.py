import pytest
from unittest.mock import AsyncMock, patch
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.engine.executor import Executor
from moss_ci.runner.base import MossRunner, MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult
from moss_ci.parser.yaml_parser import parse_suite_string


class StubBackend(MossBackend):
    """A fake Moss backend that returns deterministic output for tests."""
    def __init__(self):
        self.calls = []

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        self.calls.append(spec)
        # Echo the prompt so a `contains` eval on a known substring passes
        return MossResult(output=f"real-response: {spec.prompt or spec.task}", exit_code=0, duration=0.01)


class TestExecutorUsesRunner:
    @pytest.mark.asyncio
    async def test_executor_invokes_runner(self):
        # The executor must call the injected runner, not produce mock output.
        stub = StubBackend()
        runner = MossRunner(backend=stub)
        executor = Executor(runner=runner)
        from moss_ci.engine.scheduler import TestPlan
        from moss_ci.models.test import TestConfig, ContainsSpec
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"),
                          eval=[ContainsSpec(type="contains", value="real-response")])
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)
        result = await executor._execute_test(plan)
        assert len(stub.calls) == 1
        assert "real-response" in result.moss_output  # not "[mock]"
        assert result.status == "pass"


class TestPipelineAcceptsRunner:
    @pytest.mark.asyncio
    async def test_pipeline_injects_runner(self):
        stub = StubBackend()
        runner = MossRunner(backend=stub)
        engine = PipelineEngine(PipelineConfig(fail_fast=False), runner=runner)
        suite = parse_suite_string("""
name: "switchover-suite"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "real-response"
""")
        result = await engine.run([suite])
        assert len(stub.calls) == 1
        assert result.suites[0].passed == 1
        assert "real-response" in result.suites[0].tests[0].moss_output
