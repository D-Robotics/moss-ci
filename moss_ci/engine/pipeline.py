from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.result import PipelineResult
from moss_ci.engine.scheduler import Scheduler
from moss_ci.engine.executor import Executor


@dataclass
class PipelineConfig:
    fail_fast: bool = True
    # Global concurrency cap across all suites. None = no global cap, so each
    # suite's own ``max_concurrency`` (from YAML) is the real limit. A CLI
    # ``--concurrency N`` sets this to cap every suite at N regardless of YAML.
    max_concurrency: Optional[int] = None
    pipeline_name: str = "pipeline"


class PipelineEngine:
    def __init__(self, config: PipelineConfig | None = None, runner=None):
        self.config = config or PipelineConfig()
        self._scheduler = Scheduler()
        self._executor = Executor(max_concurrency=self.config.max_concurrency, runner=runner)

    async def run(self, suites: list[SuiteConfig]) -> PipelineResult:
        plan = self._scheduler.plan(suites)
        result = await self._executor.execute(plan)
        result.pipeline_name = self.config.pipeline_name
        return result
