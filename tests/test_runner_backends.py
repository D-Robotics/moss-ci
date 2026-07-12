import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from moss_ci.runner.api_backend import APIBackend
from moss_ci.runner.sdk_backend import SDKBackend
from moss_ci.models.test import MossCallSpec, ConversationTurn


class TestAPIBackend:
    @pytest.mark.asyncio
    async def test_run_sends_request(self):
        # Response is a plain MagicMock: httpx Response.json() is synchronous,
        # so .json() must return a dict, not a coroutine. Only post() is async.
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"output": "API response", "tool_calls": []}
        mock_resp.text = '{"output": "API response"}'
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            backend = APIBackend(base_url="http://localhost:8000")
            result = await backend.run(MossCallSpec(prompt="test"), timeout=30)
        assert result.output == "API response"

    @pytest.mark.asyncio
    async def test_run_handles_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            backend = APIBackend(base_url="http://localhost:8000")
            result = await backend.run(MossCallSpec(prompt="test"), timeout=30)
        assert result.exit_code == 500


class TestSDKBackend:
    @pytest.mark.asyncio
    async def test_run_with_mock_moss(self):
        mock_moss = MagicMock()
        mock_moss.run.return_value = {"output": "SDK output", "tool_calls": [{"tool": "read_file", "args": {}}]}
        with patch.dict("sys.modules", {"moss": mock_moss}):
            backend = SDKBackend()
            result = await backend.run(MossCallSpec(prompt="test"))
        assert result.output == "SDK output"
        assert len(result.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_run_sdk_not_available(self):
        with patch.dict("sys.modules", {}, clear=True):
            backend = SDKBackend()
            result = await backend.run(MossCallSpec(prompt="test"))
        assert result.exit_code == -1
