import pytest
from datetime import datetime
from moss_ci.models.pipeline import SuiteConfig, TestConfig, MossConfig
from moss_ci.models.test import (
    EvalSpec, ContainsSpec, ToolSequenceSpec, ToolArgsSpec,
    LLMJudgeSpec, LLMJudgeDimension, SideEffectSpec,
    FlakeDetection, ConversationTurn, MossCallSpec,
)
from moss_ci.models.result import (
    EvalResult, TestResult, SuiteResult, PipelineResult, RunStatus,
)


class TestMossConfig:
    def test_defaults(self):
        cfg = MossConfig()
        # None sentinel = "inherit global default", resolved by Scheduler
        assert cfg.timeout is None
        assert cfg.retry is None

    def test_custom(self):
        cfg = MossConfig(model="claude-sonnet-5", timeout=120, retry=3)
        assert cfg.model == "claude-sonnet-5"
        assert cfg.timeout == 120
        assert cfg.retry == 3


class TestContainsSpec:
    def test_basic(self):
        spec = ContainsSpec(type="contains", value="hello")
        assert spec.value == "hello"
        assert spec.mode == "all"

    def test_any_mode(self):
        spec = ContainsSpec(type="contains", value="hello", mode="any")
        assert spec.mode == "any"


class TestToolSequenceSpec:
    def test_strict_order(self):
        spec = ToolSequenceSpec(
            type="tool_sequence",
            expected=[{"tool": "read_file"}, {"tool": "write_file"}],
            order="strict",
        )
        assert len(spec.expected) == 2
        assert spec.order == "strict"


class TestLLMJudgeSpec:
    def test_with_dimensions(self):
        spec = LLMJudgeSpec(
            type="llm_judge",
            rubric="评分标准",
            threshold=4.0,
            dimensions=[
                LLMJudgeDimension(name="具体性", min=3),
            ],
        )
        assert spec.threshold == 4.0
        assert len(spec.dimensions) == 1


class TestSuiteConfig:
    def test_parse_minimal(self):
        data = {
            "name": "test-suite",
            "version": "1.0",
            "tests": [
                {
                    "name": "test-1",
                    "moss": {"prompt": "hello"},
                    "eval": [{"type": "contains", "value": "world"}],
                }
            ],
        }
        suite = SuiteConfig(**data)
        assert suite.name == "test-suite"
        assert len(suite.tests) == 1
        assert suite.tests[0].moss.prompt == "hello"


class TestRunStatus:
    def test_status_values(self):
        assert RunStatus.PENDING == "pending"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.SUCCESS == "success"
        assert RunStatus.FAILED == "failed"


class TestTestResult:
    def test_create(self):
        result = TestResult(
            test_name="test-1",
            status="pass",
            duration=1.5,
            moss_output="hello world",
            evals=[],
        )
        assert result.status == "pass"
        assert result.duration == 1.5
