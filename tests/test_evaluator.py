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
    async def test_returns_result(self):
        r = await LLMJudgeEvaluator().evaluate(
            LLMJudgeSpec(type="llm_judge", rubric="score quality", threshold=3.0), "output", [])
        assert isinstance(r, EvalResult)
        assert r.type == "llm_judge"


class TestSideEffectEvaluator:
    @pytest.mark.asyncio
    async def test_exit_code(self):
        r = await SideEffectEvaluator().evaluate(
            SideEffectSpec(type="side_effect", check="exit_code"), "", [], exit_code=0)
        assert r.passed is True


class TestEvaluatorRegistry:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        r = await EvaluatorRegistry().evaluate(ContainsSpec(type="contains", value="hi"), "hi there", [])
        assert r.passed is True
        assert r.type == "contains"
