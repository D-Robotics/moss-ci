from abc import ABC, abstractmethod
from typing import Any
from moss_ci.models.result import EvalResult

class BaseEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, spec: Any, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult: ...
