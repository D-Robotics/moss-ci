import pytest
from typer.testing import CliRunner
from moss_ci.cli.main import app

runner = CliRunner()


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout

    def test_init(self, tmp_path):
        import os
        os.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "moss-ci.yaml").exists()

    def test_validate_valid(self, tmp_path):
        import os
        os.chdir(tmp_path)
        suite_dir = tmp_path / "suites"
        suite_dir.mkdir()
        (suite_dir / "test.yaml").write_text("""
name: "test"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
""")
        result = runner.invoke(app, ["validate", str(suite_dir)])
        assert result.exit_code == 0

    def test_validate_invalid(self, tmp_path):
        import os
        os.chdir(tmp_path)
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("invalid: [")
        result = runner.invoke(app, ["validate", str(bad_file)])
        assert result.exit_code != 0
