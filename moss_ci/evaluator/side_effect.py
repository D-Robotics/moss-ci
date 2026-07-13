from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import SideEffectSpec
from moss_ci.models.result import EvalResult

class SideEffectEvaluator(BaseEvaluator):
    async def evaluate(self, spec: SideEffectSpec, moss_output: str, tool_calls: list[dict[str, Any]], files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        if spec.check == "file_modified":
            mods = files_modified or []
            passed = len(mods) > 0 if not spec.target else spec.target in mods
            return EvalResult(type="side_effect", passed=passed, details={"check": "file_modified", "files": mods})
        elif spec.check == "file_created":
            passed = len(files_modified or []) > 0
            return EvalResult(type="side_effect", passed=passed, details={"check": "file_created"})
        elif spec.check == "tests_pass":
            # Case-insensitive: Moss says "4 tests pass" / "all passed",
            # not pytest's "PASSED" banner. Match "pass" (covers pass/passed/
            # passing). Don't match "ok" alone — it appears as a substring
            # in words like "broken", causing false positives.
            lowered = moss_output.lower()
            passed = "pass" in lowered
            return EvalResult(type="side_effect", passed=passed, details={"check": "tests_pass"})
        elif spec.check == "tests_fail":
            lowered = moss_output.lower()
            passed = ("fail" in lowered) or ("error" in lowered)
            return EvalResult(type="side_effect", passed=passed, details={"check": "tests_fail"})
        elif spec.check == "exit_code":
            return EvalResult(type="side_effect", passed=exit_code == 0, details={"check": "exit_code", "exit_code": exit_code})
        return EvalResult(type="side_effect", passed=False, error=f"Unknown check: {spec.check}")
