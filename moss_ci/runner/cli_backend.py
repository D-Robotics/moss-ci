from __future__ import annotations
import asyncio, json, os, shlex, time, structlog
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

    @staticmethod
    def _session_dir(cwd: str | None) -> Path | None:
        # Moss writes one .jsonl per invocation under <cwd>/.moss/sessions/.
        d = Path(cwd) / ".moss" / "sessions" if cwd else Path(".moss") / "sessions"
        return d if d.is_dir() else None

    @staticmethod
    def _list_sessions(d: Path) -> set[str]:
        return {p.name for p in d.glob("*.jsonl")} if d.is_dir() else set()

    @staticmethod
    def _parse_tool_calls(session_path: Path) -> list[dict]:
        """Extract tool calls from a Moss session jsonl, in call order.

        Moss records assistant turns with Anthropic-style content blocks:
        {"type":"tool_use","name":"read_file","input":{"path":"x"}}.
        moss-ci's evaluators expect {"tool": <name>, "args": <input>}.
        Returns [] if the session can't be parsed (e.g. Moss wrote no session).
        """
        tool_calls: list[dict] = []
        try:
            with open(session_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    messages = rec.get("messages", [])
                    if not isinstance(messages, list):
                        continue
                    for msg in messages:
                        content = msg.get("content")
                        if not isinstance(content, list):
                            continue
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tool_calls.append({
                                    "tool": block.get("name", ""),
                                    "args": block.get("input", {}) or {},
                                })
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("session.parse_failed", path=str(session_path), error=str(e))
        return tool_calls

    def _extract_tool_calls(self, cwd: str | None, before: set[str]) -> list[dict]:
        # Find session jsonl(s) that appeared during this Moss invocation and
        # parse the newest one. Moss typically writes exactly one new file.
        d = self._session_dir(cwd)
        if d is None:
            return []
        new_sessions = sorted(self._list_sessions(d) - before)
        if not new_sessions:
            return []
        return self._parse_tool_calls(d / new_sessions[-1])

    # Tools that modify files — their input.path tells us what Moss changed.
    _FILE_WRITE_TOOLS = {"write_file", "edit_file", "apply_patch", "move_file"}

    def _extract_files_modified(self, tool_calls: list[dict]) -> list[str]:
        """Derive files_modified from tool calls. Moss's session jsonl records
        every tool_use with its input; for write/edit/patch/move the input
        carries a `path` (move_file also has `destination`). Collect those so
        the side_effect evaluator (file_modified) has something to check.
        """
        modified: list[str] = []
        for tc in tool_calls:
            if tc.get("tool") not in self._FILE_WRITE_TOOLS:
                continue
            args = tc.get("args") or {}
            path = args.get("path") or args.get("file_path")
            if path:
                modified.append(path)
            # move_file moves to a destination too
            dest = args.get("destination") or args.get("to")
            if dest:
                modified.append(dest)
        return modified

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        start = time.monotonic()
        prompt = spec.prompt or spec.task or ""
        # Insert `--` so prompt text isn't parsed as Moss flags. A prompt
        # containing e.g. `python -m pytest` would otherwise treat `-m` as
        # Moss's --model short flag ("model=pytest" → HTTP 400). Everything
        # after `--` is positional argv, which Moss concatenates into the
        # prompt. (bash -c 'echo $X' still tokenizes correctly via shlex.)
        cmd = [*self._cmd_prefix, "--", *shlex.split(prompt)]
        env = {**os.environ, **spec.env}
        cwd = str(Path(spec.workdir).resolve()) if spec.workdir else None
        # Snapshot existing sessions so we can find the NEW one Moss writes.
        sessions_before = self._list_sessions(self._session_dir(cwd)) if self._session_dir(cwd) else set()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            raw_log = output + ("\n[stderr]\n" + stderr.decode("utf-8", errors="replace") if stderr else "")
            tool_calls = self._extract_tool_calls(cwd, sessions_before)
            files_modified = self._extract_files_modified(tool_calls)
            return MossResult(output=output.strip(), tool_calls=tool_calls, exit_code=process.returncode or 0,
                              duration=time.monotonic() - start, workdir=spec.workdir or "",
                              files_modified=files_modified, raw_log=raw_log)
        except asyncio.TimeoutError:
            return MossResult(output="", exit_code=-1, duration=time.monotonic() - start,
                              raw_log=f"Timeout after {timeout}s")
        except FileNotFoundError:
            return MossResult(output=f"Error: '{self.moss_command}' not found", exit_code=127,
                              duration=time.monotonic() - start, raw_log=f"Command not found: {self.moss_command}")
