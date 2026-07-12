from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ToolArgsSpec
from moss_ci.models.result import EvalResult

class ToolArgsEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ToolArgsSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        # NOTE: matching is string-substring based (str(expected) in str(arg)).
        # This is deliberately permissive for the scaffold — it lets YAML
        # authors write `contains: {body: "fix"}` without worrying about
        # exact types. Known limitation: bool/number coercion is lossy
        # (True matches "True" never "true"), so prefer string-valued
        # `contains` specs. Structured equality matching is a future task.
        targets = [tc for tc in tool_calls if tc.get("tool") == spec.tool]
        if not targets:
            return EvalResult(type="tool_args", passed=False, details={"tool": spec.tool, "error": "Tool not called"})
        for call in targets:
            args = call.get("args", {})
            if all(str(expected_val) in str(args.get(key, "")) for key, expected_val in spec.contains.items()):
                return EvalResult(type="tool_args", passed=True, details={"tool": spec.tool, "matched_args": args})
        return EvalResult(type="tool_args", passed=False, details={"tool": spec.tool, "expected": spec.contains, "actual": [c.get("args", {}) for c in targets]})
