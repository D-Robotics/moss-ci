from typing import Any
from moss_ci.evaluator.contains import ContainsEvaluator
from moss_ci.evaluator.tool_sequence import ToolSequenceEvaluator
from moss_ci.evaluator.tool_args import ToolArgsEvaluator
from moss_ci.evaluator.llm_judge import LLMJudgeEvaluator
from moss_ci.evaluator.side_effect import SideEffectEvaluator
from moss_ci.models.result import EvalResult

class EvaluatorRegistry:
    def __init__(self):
        self._evals = {"contains": ContainsEvaluator(), "tool_sequence": ToolSequenceEvaluator(),
                       "tool_args": ToolArgsEvaluator(), "llm_judge": LLMJudgeEvaluator(),
                       "side_effect": SideEffectEvaluator()}

    async def evaluate(self, spec: Any, moss_output: str, tool_calls: list[dict[str, Any]], files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        e = self._evals.get(spec.type)
        if e is None:
            return EvalResult(type=spec.type, passed=False, error=f"Unknown evaluator: {spec.type}")
        if spec.type == "side_effect":
            return await e.evaluate(spec, moss_output, tool_calls, files_modified=files_modified, exit_code=exit_code)
        return await e.evaluate(spec, moss_output, tool_calls)
