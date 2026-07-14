import os, json, re, structlog
from typing import Any
from urllib.parse import urlparse
import httpx
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import LLMJudgeSpec
from moss_ci.models.result import EvalResult

logger = structlog.get_logger(__name__)

# Anthropic's official API uses x-api-key auth; every other Anthropic-protocol
# gateway we've seen (horizon at llmapi.horizon.auto, custom proxies) uses
# Authorization: Bearer. Detect by host so the judge works against both.
_ANTHROPIC_OFFICIAL_HOST = "api.anthropic.com"


class LLMJudgeEvaluator(BaseEvaluator):
    async def evaluate(self, spec: LLMJudgeSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        judge_model = spec.model or os.environ.get("MOSS_CI_JUDGE_MODEL", "HORIZON-GLM")
        prompt = f"Evaluate this AI output against the rubric.\n\nRubric:\n{spec.rubric}\n\nAI Output:\n{moss_output}\n\nReturn JSON: {{\"score\": <float 1-5>}}"
        try:
            score = await self._call_judge(judge_model, prompt)
        except Exception as e:
            # Includes "not configured" — a misconfigured judge must NOT show as
            # a silent pass. passed=False makes F1 fail loudly instead of faking
            # a score. score stays None so DiffEngine skips it (no bogus
            # improved/degraded from a phantom number).
            return EvalResult(type="llm_judge", passed=False, score=None, error=str(e))
        # Per-dimension pass: only enforce dims whose min was set explicitly
        # (>0). A dimension with min==0 (the default) carries no threshold, so
        # it would let any score through — recording it without enforcing avoids
        # "no min set = always passes" silently masking a bad dimension.
        dims = {}
        dims_pass = True
        for d in spec.dimensions:
            enforced = d.min > 0
            ok = (score >= d.min) if enforced else True
            dims[d.name] = {"min": d.min, "enforced": enforced, "passed": ok}
            if enforced and not ok:
                dims_pass = False
        passed = (score >= spec.threshold) and dims_pass
        return EvalResult(type="llm_judge", passed=passed, score=score,
                          details={"judge_model": judge_model, "threshold": spec.threshold, "score": score, "dimensions": dims})

    async def _call_judge(self, model: str, prompt: str) -> float:
        url = os.environ.get("MOSS_CI_JUDGE_API_URL", "")
        api_key = os.environ.get("MOSS_CI_JUDGE_API_KEY", "")
        if not url or not api_key:
            # Not configured: do not synthesize a fake score. Returning here
            # raises → evaluate() marks the eval failed with this message, so a
            # missing judge is visible rather than masked by a phantom 3.0.
            raise RuntimeError(
                "llm_judge not configured: set MOSS_CI_JUDGE_API_URL and "
                "MOSS_CI_JUDGE_API_KEY (Anthropic-protocol endpoint, Bearer auth)"
            )

        endpoint = self._messages_endpoint(url)
        headers = self._auth_headers(url, api_key)
        headers["content-type"] = "application/json"
        headers["anthropic-version"] = "2023-06-01"
        payload = {"model": model, "max_tokens": 1024,
                   "messages": [{"role": "user", "content": prompt}]}

        async with httpx.AsyncClient() as c:
            r = await c.post(endpoint, headers=headers, json=payload,
                             timeout=httpx.Timeout(120))
        if r.status_code != 200:
            raise RuntimeError(f"Judge API returned {r.status_code}: {r.text[:200]}")
        data = r.json()
        text = self._extract_text(data)
        return self._parse_score(text)

    @staticmethod
    def _messages_endpoint(url: str) -> str:
        # Accept base URLs with or without a trailing /v1:
        #   https://llmapi.horizon.auto        -> /v1/messages
        #   https://llmapi.horizon.auto/v1     -> /v1/messages
        base = url.rstrip("/")
        if base.endswith("/v1"):
            return base + "/messages"
        return base + "/v1/messages"

    @staticmethod
    def _auth_headers(url: str, api_key: str) -> dict[str, str]:
        # Mirror the Moss fork's host-based Bearer detection: official Anthropic
        # keeps x-api-key; any other host (horizon gateways, custom proxies)
        # uses Authorization: Bearer.
        host = (urlparse(url).hostname or "").lower()
        if host == _ANTHROPIC_OFFICIAL_HOST:
            return {"x-api-key": api_key}
        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def _extract_text(data: dict) -> str:
        # Anthropic /v1/messages returns content as a list of blocks; the judge
        # reply is a single text block. Tolerate minor shape variation rather
        # than hard-indexing.
        content = data.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")
                # Some gateways flatten to {"text": "..."} without a type tag.
                if isinstance(block, dict) and "text" in block:
                    return block["text"]
        if isinstance(content, str):
            return content
        raise RuntimeError(f"Judge response had no text content: {str(data)[:200]}")

    @staticmethod
    def _parse_score(text: str) -> float:
        # Judges don't always reply clean JSON — they wrap in ```json fences or
        # add prose. Try strict JSON first, then fenced JSON, then a regex that
        # pulls the number after "score". Last resort raises so the eval fails
        # loudly rather than guessing.
        text = text.strip()

        def _try_json(s: str) -> float | None:
            try:
                return float(json.loads(s).get("score"))
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                return None

        # 1. Plain JSON.
        score = _try_json(text)
        if score is not None:
            return score

        # 2. ```json ... ``` fenced.
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            score = _try_json(fence.group(1))
            if score is not None:
                return score

        # 3. Bare {...} object anywhere.
        obj = re.search(r"\{[^{}]*\"score\"[^{}]*\}", text, re.DOTALL)
        if obj:
            score = _try_json(obj.group(0))
            if score is not None:
                return score

        # 4. "score: 4" / "score is 4" prose fallback.
        m = re.search(r"score[\"']?\s*[:=is]+\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        raise RuntimeError(f"Judge returned non-numeric/unparseable score: {text!r}")
