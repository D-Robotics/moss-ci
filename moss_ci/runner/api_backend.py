from __future__ import annotations
import time, structlog, httpx
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class APIBackend(MossBackend):
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=httpx.Timeout(300),
        )

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        start = time.monotonic()
        payload = {"prompt": spec.prompt or spec.task or "", "context": spec.context}
        if spec.env:
            payload["env"] = spec.env
        try:
            resp = await self._client.post("/chat", json=payload, timeout=httpx.Timeout(timeout))
            d = time.monotonic() - start
            if resp.status_code == 200:
                data = resp.json()
                return MossResult(output=data.get("output", ""), tool_calls=data.get("tool_calls", []),
                                  exit_code=0, duration=d, raw_log=resp.text)
            return MossResult(output=f"API error: {resp.status_code}", exit_code=resp.status_code, duration=d, raw_log=resp.text)
        except httpx.TimeoutException:
            return MossResult(output=f"Timeout after {timeout}s", exit_code=-1, duration=time.monotonic() - start)
        except Exception as e:
            return MossResult(output=f"Error: {e}", exit_code=-1, duration=time.monotonic() - start, raw_log=str(e))
