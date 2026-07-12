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
    async def test_run_with_env(self):
        backend = CLIBackend(moss_command="bash")
        spec = MossCallSpec(prompt="-c 'echo $MY_VAR'", env={"MY_VAR": "testval"})
        result = await backend.run(spec)
        assert "testval" in result.output


class TestMossRunner:
    @pytest.mark.asyncio
    async def test_auto_detect_cli(self):
        runner = MossRunner()
        spec = MossCallSpec(prompt="echo hello")
        result = await runner.run(spec)
        assert isinstance(result, MossResult)
