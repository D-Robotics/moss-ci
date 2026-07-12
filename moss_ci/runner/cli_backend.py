from __future__ import annotations
import asyncio, os, shlex, time, structlog
from pathlib import Path
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class CLIBackend(MossBackend):
    def __init__(self, moss_command: str = "moss"):
        self.moss_command = moss_command

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        start = time.monotonic()
        prompt = spec.prompt or spec.task or ""
        # shlex.split so that ``bash -c 'echo $X'`` parses into the right
        # argv ([bash, -c, echo $X]) instead of being passed as one arg.
        # create_subprocess_exec does not invoke a shell, so prompt text
        # must be tokenized here.
        cmd = [self.moss_command, *shlex.split(prompt)]
        env = {**os.environ, **spec.env}
        cwd = str(Path(spec.workdir).resolve()) if spec.workdir else None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            raw_log = output + ("\n[stderr]\n" + stderr.decode("utf-8", errors="replace") if stderr else "")
            return MossResult(output=output.strip(), exit_code=process.returncode or 0,
                              duration=time.monotonic() - start, workdir=spec.workdir or "", raw_log=raw_log)
        except asyncio.TimeoutError:
            return MossResult(output="", exit_code=-1, duration=time.monotonic() - start,
                              raw_log=f"Timeout after {timeout}s")
        except FileNotFoundError:
            return MossResult(output=f"Error: '{self.moss_command}' not found", exit_code=127,
                              duration=time.monotonic() - start, raw_log=f"Command not found: {self.moss_command}")
