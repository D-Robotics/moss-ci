import re
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ContainsSpec
from moss_ci.models.result import EvalResult

class ContainsEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ContainsSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        if spec.is_regex:
            m = re.search(spec.value, moss_output, re.IGNORECASE | re.DOTALL)
            return EvalResult(type="contains", passed=m is not None, details={"matched": m.group(0) if m else None, "pattern": spec.value})
        passed = spec.value in moss_output
        return EvalResult(type="contains", passed=passed, details={"expected": spec.value, "matched": spec.value if passed else None})
