from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ToolSequenceSpec
from moss_ci.models.result import EvalResult

class ToolSequenceEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ToolSequenceSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        actual = [tc.get("tool", "") for tc in tool_calls]
        expected = [s.tool for s in spec.expected]
        if spec.order == "strict":
            if len(actual) < len(expected):
                return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": "Insufficient calls"})
            for i, e in enumerate(expected):
                if actual[i] != e:
                    return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": f"Pos {i}: expected {e}, got {actual[i]}"})
            return EvalResult(type="tool_sequence", passed=True, details={"expected": expected, "actual": actual[:len(expected)]})
        else:
            remaining = list(actual)
            for e in expected:
                if e in remaining:
                    remaining.remove(e)
                else:
                    return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": f"'{e}' not found"})
            return EvalResult(type="tool_sequence", passed=True, details={"expected": expected, "actual": actual})
