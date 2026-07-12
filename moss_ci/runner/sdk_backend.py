from __future__ import annotations
import asyncio, time, structlog
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class SDKBackend(MossBackend):
    def __init__(self):
        self._available: bool | None = None

    def _check(self) -> bool:
        if self._available is None:
            try:
                import moss
                self._moss = moss
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not self._check():
            return MossResult(output="Error: Moss SDK not available", exit_code=-1)
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(asyncio.to_thread(self._moss.run, spec.prompt or spec.task or ""), timeout=timeout)
            return MossResult(output=result.get("output", ""), tool_calls=result.get("tool_calls", []),
                              exit_code=0, duration=time.monotonic() - start, raw_log=result.get("output", ""))
        except asyncio.TimeoutError:
            return MossResult(output=f"Timeout after {timeout}s", exit_code=-1, duration=time.monotonic() - start)

    async def run_task(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not self._check():
            return MossResult(output="Error: Moss SDK not available", exit_code=-1)
        start = time.monotonic()
        try:
            if hasattr(self._moss, "run_task"):
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._moss.run_task, spec.task, workdir=spec.workdir), timeout=timeout)
                return MossResult(output=result.get("output", ""), tool_calls=result.get("tool_calls", []),
                                  files_modified=result.get("files_modified", []), exit_code=0,
                                  duration=time.monotonic() - start, raw_log=result.get("output", ""))
            return await self.run(spec, timeout=timeout)
        except asyncio.TimeoutError:
            return MossResult(output=f"Timeout after {timeout}s", exit_code=-1, duration=time.monotonic() - start)
