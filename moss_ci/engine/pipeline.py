from __future__ import annotations
from dataclasses import dataclass
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.result import PipelineResult
from moss_ci.engine.scheduler import Scheduler
from moss_ci.engine.executor import Executor


@dataclass
class PipelineConfig:
    fail_fast: bool = True
    max_concurrency: int = 10
    pipeline_name: str = "pipeline"


class PipelineEngine:
    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self._scheduler = Scheduler()
        self._executor = Executor(max_concurrency=self.config.max_concurrency)

    async def run(self, suites: list[SuiteConfig]) -> PipelineResult:
        plan = self._scheduler.plan(suites)
        result = await self._executor.execute(plan)
        result.pipeline_name = self.config.pipeline_name
        return result
