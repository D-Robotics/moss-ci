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

    @pytest.mark.asyncio
    async def test_yaml_max_concurrency_serializes(self):
        # Without a CLI --concurrency (None global cap), the suite's own YAML
        # max_concurrency must be the real limit. max_concurrency: 1 → strictly
        # serial, so peak in-flight Moss calls never exceeds 1.
        import asyncio
        from moss_ci.runner.base import MossBackend
        from moss_ci.models.test import MossCallSpec
        from moss_ci.models.result import MossResult

        yaml = """
name: "serial-suite"
version: "1.0"
config:
  max_concurrency: 1
  fail_fast: false
tests:
  - name: "t-1"
    moss: {prompt: "hi"}
    eval: [{type: contains, value: "ok"}]
  - name: "t-2"
    moss: {prompt: "hi"}
    eval: [{type: contains, value: "ok"}]
  - name: "t-3"
    moss: {prompt: "hi"}
    eval: [{type: contains, value: "ok"}]
"""
        state = {"in_flight": 0, "peak": 0}

        class _CountingBackend(MossBackend):
            async def run(self, spec: MossCallSpec, timeout: int = 300):
                state["in_flight"] += 1
                state["peak"] = max(state["peak"], state["in_flight"])
                await asyncio.sleep(0.05)
                state["in_flight"] -= 1
                return MossResult(output="ok", exit_code=0)

        from moss_ci.runner.base import MossRunner
        runner = MossRunner(backend=_CountingBackend())
        suite = parse_suite_string(yaml)
        engine = PipelineEngine(PipelineConfig(fail_fast=False), runner=runner)
        await engine.run([suite])
        assert state["peak"] == 1  # max_concurrency: 1 → strictly serial


class TestWorkdirIsolation:
    @pytest.mark.asyncio
    async def test_source_workdir_not_mutated(self, tmp_path):
        # A test that "creates a file" must not leave it in the source workdir.
        # The executor stages a throwaway copy; Moss writes to the copy, so the
        # source stays clean across runs (no hello.txt residue breaking the
        # next run's create-file test).
        import asyncio
        from moss_ci.runner.base import MossBackend, MossRunner
        from moss_ci.models.test import MossCallSpec
        from moss_ci.models.result import MossResult

        src = tmp_path / "fixtures"
        src.mkdir()
        (src / "existing.txt").write_text("keep me", encoding="utf-8")

        class _FileCreatingBackend(MossBackend):
            async def run(self, spec: MossCallSpec, timeout: int = 300):
                # Simulate Moss creating a file in its workdir (the staged copy).
                import os
                if spec.workdir:
                    with open(os.path.join(spec.workdir, "created.txt"), "w", encoding="utf-8") as f:
                        f.write("new")
                return MossResult(output="done", exit_code=0,
                                  files_modified=["created.txt"])

        suite_yaml = f"""
name: "iso-suite"
version: "1.0"
config:
  max_concurrency: 1
  fail_fast: false
tests:
  - name: "creates-file"
    moss:
      prompt: "create a file"
      workdir: {str(src).replace(chr(92), '/')}
    eval:
      - type: contains
        value: "done"
"""
        runner = MossRunner(backend=_FileCreatingBackend())
        suite = parse_suite_string(suite_yaml)
        engine = PipelineEngine(PipelineConfig(fail_fast=False), runner=runner)

        await engine.run([suite])
        # Source must NOT have the created file — it went to the staged copy.
        assert not (src / "created.txt").exists()
        assert (src / "existing.txt").read_text() == "keep me"

        # Run again — still clean (each run gets a fresh copy).
        await engine.run([suite])
        assert not (src / "created.txt").exists()

    @pytest.mark.asyncio
    async def test_stage_workdir_none_when_no_dir(self):
        from moss_ci.engine.executor import Executor
        assert await Executor._stage_workdir(None) is None
        assert await Executor._stage_workdir("/does/not/exist/xyz") is None
