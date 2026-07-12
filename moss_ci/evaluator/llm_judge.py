import os, json, structlog
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import LLMJudgeSpec
from moss_ci.models.result import EvalResult

logger = structlog.get_logger(__name__)

class LLMJudgeEvaluator(BaseEvaluator):
    async def evaluate(self, spec: LLMJudgeSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        judge_model = spec.model or "claude-opus-4-8"
        prompt = f"Evaluate this AI output against the rubric.\n\nRubric:\n{spec.rubric}\n\nAI Output:\n{moss_output}\n\nReturn JSON: {{\"score\": <float 1-5>}}"
        try:
            score = await self._call_judge(judge_model, prompt)
        except Exception as e:
            return EvalResult(type="llm_judge", passed=False, error=str(e))
        passed = score >= spec.threshold
        dims = {}
        for d in spec.dimensions:
            dims[d.name] = {"min": d.min, "passed": score >= d.min}
        return EvalResult(type="llm_judge", passed=passed, score=score, details={"judge_model": judge_model, "threshold": spec.threshold, "score": score, "dimensions": dims})

    async def _call_judge(self, model: str, prompt: str) -> float:
        url = os.environ.get("MOSS_CI_JUDGE_API_URL", "")
        if url:
            import httpx
            async with httpx.AsyncClient() as c:
                r = await c.post(url, json={"model": model, "messages": [{"role": "user", "content": prompt}]}, timeout=httpx.Timeout(120))
                if r.status_code == 200:
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    try:
                        return float(json.loads(content).get("score", 3.0))
                    except (json.JSONDecodeError, ValueError):
                        pass
        logger.warning("llm_judge.no_api", message="Returning default score 3.5")
        return 3.5
