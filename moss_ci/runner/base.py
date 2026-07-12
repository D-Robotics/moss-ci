from __future__ import annotations
import asyncio, os, time, structlog
from abc import ABC, abstractmethod
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class MossBackend(ABC):
    @abstractmethod
    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult: ...

    async def run_conversation(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not spec.conversation:
            raise ValueError("No conversation turns defined")
        all_outputs: list[str] = []
        all_tool_calls: list[dict] = []
        for turn in spec.conversation:
            if turn.role == "user":
                turn_spec = MossCallSpec(prompt=turn.content or "", env=spec.env, workdir=spec.workdir)
                result = await self.run(turn_spec, timeout=timeout)
                all_outputs.append(f"[{turn.role}]: {result.output}")
                all_tool_calls.extend(result.tool_calls)
        return MossResult(output="\n".join(all_outputs), tool_calls=all_tool_calls)

    async def run_task(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not spec.task:
            raise ValueError("No task defined")
        return await self.run(spec, timeout=timeout)


class MossRunner:
    def __init__(self, backend: MossBackend | None = None, default_timeout: int = 300):
        self.default_timeout = default_timeout
        self.backend = backend if backend is not None else self._detect_backend()

    def _detect_backend(self) -> MossBackend:
        try:
            import moss
            from moss_ci.runner.sdk_backend import SDKBackend
            logger.info("backend.auto_detect", selected="sdk")
            return SDKBackend()
        except ImportError:
            pass
        api_url = os.environ.get("MOSS_API_URL", "")
        if api_url:
            from moss_ci.runner.api_backend import APIBackend
            api_key = os.environ.get("MOSS_API_KEY", "")
            logger.info("backend.auto_detect", selected="api", url=api_url)
            return APIBackend(base_url=api_url, api_key=api_key or None)
        from moss_ci.runner.cli_backend import CLIBackend
        moss_cmd = os.environ.get("MOSS_CLI_COMMAND", "moss")
        logger.info("backend.auto_detect", selected="cli", command=moss_cmd)
        return CLIBackend(moss_command=moss_cmd)

    async def run(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run(spec, timeout=self.default_timeout)

    async def run_conversation(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run_conversation(spec, timeout=self.default_timeout)

    async def run_task(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run_task(spec, timeout=self.default_timeout)
