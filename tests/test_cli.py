import pytest
import asyncio
from typer.testing import CliRunner
from moss_ci.cli.main import app
from moss_ci.storage.db import Database
from moss_ci.storage.repository import RunRepository
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, RunStatus

runner = CliRunner()


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """A per-test SQLite DB that the CLI's get_db() will use.

    monkeypatch replaces the module-level get_db so export/diff read from
    this DB instead of the global moss_ci.db singleton.
    """
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/test.db")
    asyncio.run(db.init())

    def _fake_get_db(url: str = "") -> Database:
        return db

    monkeypatch.setattr("moss_ci.cli.main.get_db", _fake_get_db)
    yield db
    asyncio.run(db.close())


def _save_run(db, run_id, test_statuses):
    tests = [TestResult(test_name=n, status=s) for n, s in test_statuses.items()]
    result = PipelineResult(
        run_id=run_id, pipeline_name="test", status=RunStatus.SUCCESS,
        suites=[SuiteResult(suite_name="s1", total=len(tests),
                            passed=sum(1 for t in tests if t.status == "pass"),
                            failed=sum(1 for t in tests if t.status == "fail"),
                            tests=tests)],
    )
    asyncio.run(RunRepository(db).save(result))
    return result


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


class TestExportAndDiffFiles:
    def test_export_writes_valid_json(self, tmp_path, isolated_db):
        _save_run(isolated_db, "run-A", {"t1": "pass", "t2": "pass"})
        out = tmp_path / "run-A.json"
        result = runner.invoke(app, ["export", "run-A", "-o", str(out)])
        assert result.exit_code == 0
        # roundtrip: the exported JSON must deserialize back to a PipelineResult
        reloaded = PipelineResult.model_validate_json(out.read_text(encoding="utf-8"))
        assert reloaded.run_id == "run-A"

    def test_diff_files_no_changes(self, tmp_path, isolated_db):
        _save_run(isolated_db, "run-A", {"t1": "pass"})
        _save_run(isolated_db, "run-B", {"t1": "pass"})
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        runner.invoke(app, ["export", "run-A", "-o", str(a)])
        runner.invoke(app, ["export", "run-B", "-o", str(b)])
        result = runner.invoke(app, ["diff-files", str(a), str(b)])
        assert result.exit_code == 0
        assert "No changes" in result.stdout

    def test_diff_files_new_failure(self, tmp_path, isolated_db):
        # prev: t1 passes; curr: t1 fails -> new_failure
        _save_run(isolated_db, "run-prev", {"t1": "pass"})
        _save_run(isolated_db, "run-curr", {"t1": "fail"})
        p = tmp_path / "prev.json"
        c = tmp_path / "curr.json"
        runner.invoke(app, ["export", "run-prev", "-o", str(p)])
        runner.invoke(app, ["export", "run-curr", "-o", str(c)])
        result = runner.invoke(app, ["diff-files", str(p), str(c)])
        assert result.exit_code == 0
        assert "new failure" in result.stdout
        assert "t1" in result.stdout

    def test_diff_files_fixed(self, tmp_path, isolated_db):
        # prev: t1 fails; curr: t1 passes -> fixed
        _save_run(isolated_db, "run-prev", {"t1": "fail"})
        _save_run(isolated_db, "run-curr", {"t1": "pass"})
        p = tmp_path / "prev.json"
        c = tmp_path / "curr.json"
        runner.invoke(app, ["export", "run-prev", "-o", str(p)])
        runner.invoke(app, ["export", "run-curr", "-o", str(c)])
        result = runner.invoke(app, ["diff-files", str(p), str(c)])
        assert result.exit_code == 0
        assert "fixed" in result.stdout
