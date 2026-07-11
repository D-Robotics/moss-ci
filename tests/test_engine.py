import pytest
from moss_ci.engine.scheduler import Scheduler, ExecutionPlan, SuitePlan, TestPlan
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import RunStatus


TWO_SUITES_YAML = """
name: "suite-a"
version: "1.0"
tests:
  - name: "a-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
  - name: "a-2"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""


class TestScheduler:
    def test_plan_single_suite(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.suites) == 1
        assert len(plan.suites[0].tests) == 2

    def test_plan_resolves_timeout(self):
        yaml = """
name: "config-suite"
version: "1.0"
config:
  moss:
    timeout: 120
    retry: 3
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert plan.suites[0].tests[0].timeout == 120
        assert plan.suites[0].tests[0].retry == 3

    def test_plan_skips_disabled_tests(self):
        yaml = """
name: "skip-suite"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
  - name: "t2"
    skip: true
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert len(plan.suites[0].tests) == 1
        assert plan.suites[0].tests[0].test.name == "t1"


class TestPipelineEngine:
    @pytest.mark.asyncio
    async def test_engine_creates_result(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        engine = PipelineEngine(PipelineConfig(fail_fast=False))
        result = await engine.run([suite])
        assert result.pipeline_name == "pipeline"
        assert result.status in (RunStatus.SUCCESS, RunStatus.FAILED)
        assert len(result.suites) == 1
        assert result.suites[0].total == 2

    @pytest.mark.asyncio
    async def test_engine_fail_fast(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        engine = PipelineEngine(PipelineConfig(fail_fast=True))
        result = await engine.run([suite])
        assert result.status in (RunStatus.SUCCESS, RunStatus.FAILED)
