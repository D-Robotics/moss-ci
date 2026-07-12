from __future__ import annotations
import asyncio, os, shlex, time, structlog
from pathlib import Path
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class CLIBackend(MossBackend):
    def __init__(self, moss_command: str = "moss"):
        # moss_command may be a bare command ("moss") OR a command with leading
        # args ("node /abs/path/cli.js --config-file C:/..."). Tokenize so
        # MOSS_CLI_COMMAND can point at an interpreter + script, not just a
        # PATH-resolved binary. Use posix=False on Windows so backslashes in
        # Windows paths (C:\Users\...) aren't eaten as shell escapes —
        # posix=True turns 'C:\Users\t' into 'C:Userst', corrupting the path.
        self.moss_command = moss_command
        self._cmd_prefix = shlex.split(moss_command, posix=not os.name == "nt")

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        start = time.monotonic()
        prompt = spec.prompt or spec.task or ""
        # shlex.split so that ``bash -c 'echo $X'`` parses into the right
        # argv ([bash, -c, echo $X]) instead of one arg. create_subprocess_exec
        # does not invoke a shell, so prompt text must be tokenized here.
        # (For real Moss, multi-word prompts split into several argv — Moss
        # concatenates argv back into one prompt, verified empirically.)
        cmd = [*self._cmd_prefix, *shlex.split(prompt)]
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
