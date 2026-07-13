import pytest
from moss_ci.runner.base import MossRunner
from moss_ci.runner.cli_backend import CLIBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult


class TestCLIBackend:
    @pytest.mark.asyncio
    async def test_run_simple(self):
        backend = CLIBackend(moss_command="echo")
        spec = MossCallSpec(prompt="hello world")
        result = await backend.run(spec)
        assert "hello world" in result.output
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_run_with_env(self, tmp_path):
        # Verify spec.env is injected into the subprocess environment.
        # Use a tiny script that prints an env var (not bash -c, since the
        # backend now inserts `--` to stop flag parsing, which would make
        # bash treat -c as a filename).
        script = tmp_path / "echo_env.py"
        script.write_text("import os, sys; sys.stdout.write(os.environ.get('MY_VAR', ''))", encoding="utf-8")
        import sys
        backend = CLIBackend(moss_command=f"{sys.executable} {script}")
        spec = MossCallSpec(prompt="ignored", env={"MY_VAR": "testval"})
        result = await backend.run(spec)
        assert "testval" in result.output


class TestMossRunner:
    @pytest.mark.asyncio
    async def test_auto_detect_cli(self):
        runner = MossRunner()
        spec = MossCallSpec(prompt="echo hello")
        result = await runner.run(spec)
        assert isinstance(result, MossResult)
