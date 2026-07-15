import pytest
from moss_ci.evaluator.contains import ContainsEvaluator
from moss_ci.evaluator.tool_sequence import ToolSequenceEvaluator
from moss_ci.evaluator.tool_args import ToolArgsEvaluator
from moss_ci.evaluator.llm_judge import LLMJudgeEvaluator
from moss_ci.evaluator.side_effect import SideEffectEvaluator
from moss_ci.evaluator.registry import EvaluatorRegistry
from moss_ci.models.test import ContainsSpec, ToolSequenceSpec, ToolArgsSpec, LLMJudgeSpec, SideEffectSpec
from moss_ci.models.result import EvalResult


class TestContainsEvaluator:
    @pytest.mark.asyncio
    async def test_found(self):
        r = await ContainsEvaluator().evaluate(ContainsSpec(type="contains", value="hello"), "hello world", [])
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_not_found(self):
        r = await ContainsEvaluator().evaluate(ContainsSpec(type="contains", value="xyz"), "hello world", [])
        assert r.passed is False

    @pytest.mark.asyncio
    async def test_regex(self):
        r = await ContainsEvaluator().evaluate(ContainsSpec(type="contains", value=r"\d+", is_regex=True), "abc123def", [])
        assert r.passed is True


class TestToolSequenceEvaluator:
    @pytest.mark.asyncio
    async def test_strict_match(self):
        r = await ToolSequenceEvaluator().evaluate(
            ToolSequenceSpec(type="tool_sequence", expected=[{"tool": "A"}, {"tool": "B"}], order="strict"),
            "", [{"tool": "A"}, {"tool": "B"}])
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_strict_mismatch(self):
        r = await ToolSequenceEvaluator().evaluate(
            ToolSequenceSpec(type="tool_sequence", expected=[{"tool": "A"}, {"tool": "B"}], order="strict"),
            "", [{"tool": "B"}, {"tool": "A"}])
        assert r.passed is False


class TestToolArgsEvaluator:
    @pytest.mark.asyncio
    async def test_match(self):
        r = await ToolArgsEvaluator().evaluate(
            ToolArgsSpec(type="tool_args", tool="comment", contains={"body": "fix"}),
            "", [{"tool": "comment", "args": {"body": "please fix this"}}])
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_no_match(self):
        r = await ToolArgsEvaluator().evaluate(
            ToolArgsSpec(type="tool_args", tool="comment", contains={"body": "fix"}),
            "", [{"tool": "comment", "args": {"body": "looks good"}}])
        assert r.passed is False


class TestLLMJudgeEvaluator:
    @pytest.mark.asyncio
    async def test_not_configured_returns_error(self, monkeypatch):
        # No judge URL/key set: the eval must fail loudly, NOT fake a 3.0 pass.
        monkeypatch.delenv("MOSS_CI_JUDGE_API_URL", raising=False)
        monkeypatch.delenv("MOSS_CI_JUDGE_API_KEY", raising=False)
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "output", [])
        assert r.type == "llm_judge"
        assert r.passed is False
        assert r.score is None  # no phantom score pollutes the diff engine
        assert r.error and "not configured" in r.error

    @pytest.mark.asyncio
    async def test_judge_success(self, monkeypatch):
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": '{"score": 4.0}'}]})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "good review", [])
        assert r.passed is True
        assert r.score == 4.0

    @pytest.mark.asyncio
    async def test_judge_below_threshold_fails(self, monkeypatch):
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": '{"score": 2.0}'}]})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "weak review", [])
        assert r.passed is False
        assert r.score == 2.0

    @pytest.mark.asyncio
    async def test_judge_markdown_fence(self, monkeypatch):
        # Judges often wrap JSON in ```json fences — must still parse.
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": '```json\n{"score": 4.5}\n```'}]})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.score == 4.5
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_judge_prose_fallback(self, monkeypatch):
        # Non-JSON prose like "The score is 4" — regex fallback extracts it.
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": 'The review is solid. The score is 4 out of 5.'}]})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.score == 4.0

    @pytest.mark.asyncio
    async def test_judge_unparseable_score_fails(self, monkeypatch):
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": "I cannot score this."}]})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.passed is False
        assert r.score is None
        assert r.error and "non-numeric" in r.error

    @pytest.mark.asyncio
    async def test_judge_http_error(self, monkeypatch):
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch, status=500, body={"error": "boom"})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.passed is False
        assert r.error and "500" in r.error

    @pytest.mark.asyncio
    async def test_bearer_auth_for_gateway(self, monkeypatch):
        # Non-anthropic host (horizon gateway) must send Authorization: Bearer.
        captured = self._stub_post(monkeypatch,
                                   body={"content": [{"type": "text", "text": '{"score": 4.0}'}]})
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        headers = captured["headers"]
        assert headers.get("Authorization") == "Bearer test-key"
        assert "x-api-key" not in headers

    @pytest.mark.asyncio
    async def test_apikey_auth_for_official_anthropic(self, monkeypatch):
        # Official api.anthropic.com keeps x-api-key, no Bearer.
        captured = self._stub_post(monkeypatch,
                                   body={"content": [{"type": "text", "text": '{"score": 4.0}'}]})
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://api.anthropic.com")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        headers = captured["headers"]
        assert headers.get("x-api-key") == "test-key"
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_dimension_with_min_enforced(self, monkeypatch):
        # A dimension with min>0 gates the overall pass.
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch,
                        body={"content": [{"type": "text", "text": '{"score": 3.0}'}]})
        from moss_ci.models.test import LLMJudgeDimension
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="x", threshold=3.0,
                         dimensions=[LLMJudgeDimension(name="clarity", min=4.0)]), "x", [])
        # score 3.0 meets threshold but fails the clarity(min=4) dimension.
        assert r.passed is False

    @staticmethod
    def _stub_post(monkeypatch, body: dict, status: int = 200) -> dict:
        """Replace httpx.AsyncClient.post with a stub that returns `body`.

        Returns a dict that captures the headers sent, so a test can assert on
        the auth scheme (Bearer vs x-api-key).
        """
        captured: dict = {}

        class _Resp:
            def __init__(self):
                self.status_code = status
                self.text = "stub"
            def json(self):
                return body

        class _Client:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def post(self, url, headers=None, json=None, timeout=None):
                captured["url"] = url
                captured["headers"] = headers or {}
                captured["json"] = json
                return _Resp()

        import moss_ci.evaluator.llm_judge as mod
        monkeypatch.setattr(mod.httpx, "AsyncClient", lambda: _Client())
        return captured

    @staticmethod
    def _stub_post_raises(monkeypatch, exc):
        """Make the judge's httpx call raise `exc` (a network/transport error)."""
        class _Client:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def post(self, url, headers=None, json=None, timeout=None):
                raise exc
        import moss_ci.evaluator.llm_judge as mod
        monkeypatch.setattr(mod.httpx, "AsyncClient", lambda: _Client())

    @pytest.mark.asyncio
    async def test_judge_network_error_skips(self, monkeypatch):
        # An unreachable endpoint (connect/timeout) is environmental — the eval
        # is skipped, not failed, so it can't turn a green suite red. CI uses
        # this path when the runner can't reach the judge host.
        import httpx
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        # httpx ConnectTimeout has an empty str() — this also guards _fmt_error
        # leads with the type name rather than producing an unreadable "".
        self._stub_post_raises(monkeypatch, httpx.ConnectTimeout(""))
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.skipped is True
        assert r.passed is False
        assert r.score is None
        assert r.error and "ConnectTimeout" in r.error  # readable, not ""

    @pytest.mark.asyncio
    async def test_judge_http_error_not_skipped(self, monkeypatch):
        # A non-network failure (HTTP 401/500, bad score) must NOT skip — it's a
        # real problem and should fail loudly. Only the network path skips.
        monkeypatch.setenv("MOSS_CI_JUDGE_API_URL", "https://llmapi.horizon.auto")
        monkeypatch.setenv("MOSS_CI_JUDGE_API_KEY", "test-key")
        self._stub_post(monkeypatch, status=401, body={"error": "bad key"})
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "x", [])
        assert r.skipped is False
        assert r.passed is False
        assert r.error and "401" in r.error



class TestSideEffectEvaluator:
    @pytest.mark.asyncio
    async def test_exit_code(self):
        r = await SideEffectEvaluator().evaluate(
            SideEffectSpec(type="side_effect", check="exit_code"), "", [], exit_code=0)
        assert r.passed is True

    @pytest.mark.asyncio
    async def test_tests_pass_case_insensitive(self):
        # Moss says "4 tests pass" / "all passed", not pytest's "PASSED" banner.
        ev = SideEffectEvaluator()
        r1 = await ev.evaluate(SideEffectSpec(type="side_effect", check="tests_pass"),
                               "All 4 tests pass now.", [])
        r2 = await ev.evaluate(SideEffectSpec(type="side_effect", check="tests_pass"),
                               "tests passed", [])
        r3 = await ev.evaluate(SideEffectSpec(type="side_effect", check="tests_pass"),
                               "still broken", [])
        assert r1.passed is True
        assert r2.passed is True
        assert r3.passed is False

    @pytest.mark.asyncio
    async def test_tests_fail_case_insensitive(self):
        ev = SideEffectEvaluator()
        r = await ev.evaluate(SideEffectSpec(type="side_effect", check="tests_fail"),
                              "the tests failed", [])
        assert r.passed is True


class TestEvaluatorRegistry:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        r = await EvaluatorRegistry().evaluate(ContainsSpec(type="contains", value="hi"), "hi there", [])
        assert r.passed is True
        assert r.type == "contains"
