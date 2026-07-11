from __future__ import annotations
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


class MossConfig(BaseModel):
    """Configuration for Moss invocation.

    Uses None sentinels (not the default value) so the Scheduler can
    distinguish "user set this explicitly" from "use the global default".
    A previous version used ``timeout: int = 300`` and detected overrides
    with ``!= 300`` — that broke when a user explicitly set ``timeout: 300``.
    """
    model: str = Field(default="", description="Model to use")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds; None = inherit global default")
    retry: Optional[int] = Field(default=None, description="Retry count on network error; None = inherit global default")


class EvalConfig(BaseModel):
    """Configuration for evaluation."""
    judge_model: str = Field(default="claude-opus-4-8", description="Model for LLM-as-Judge")


class FlakeDetection(BaseModel):
    """Flake detection configuration."""
    runs: int = Field(default=3, ge=2, description="Number of runs")
    pass_threshold: int = Field(default=2, ge=1, description="Minimum passes required")
    consensus: Literal["majority", "unanimous"] = Field(default="majority")


class ConversationTurn(BaseModel):
    """A single turn in a multi-turn conversation."""
    role: Literal["user", "assistant"]
    content: Optional[str] = Field(default=None, description="Null means Moss generates this")


class MossCallSpec(BaseModel):
    """Specification for how to call Moss.

    Per-test ``timeout``/``retry`` use the same None-sentinel pattern as
    :class:`MossConfig`: ``None`` means "inherit the global config default",
    letting the Scheduler distinguish an explicit per-test override from an
    unset field.
    """
    prompt: Optional[str] = Field(default=None, description="Single prompt")
    task: Optional[str] = Field(default=None, description="End-to-end task description")
    conversation: Optional[list[ConversationTurn]] = Field(default=None, description="Multi-turn conversation")
    context: Optional[str] = Field(default=None, description="Additional context for the prompt")
    workdir: Optional[str] = Field(default=None, description="Working directory for task execution")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout: Optional[int] = Field(default=None, description="Timeout in seconds; None = inherit global config")
    retry: Optional[int] = Field(default=None, description="Retry count on network error; None = inherit global config")


class ContainsSpec(BaseModel):
    """Evaluate if output contains expected text."""
    type: Literal["contains"]
    value: str = Field(description="Expected string or regex pattern")
    mode: Literal["all", "any"] = Field(default="all", description="all=must match all, any=at least one")
    is_regex: bool = Field(default=False, description="Treat value as regex pattern")


class ToolSequenceStep(BaseModel):
    """Expected tool call in a sequence."""
    tool: str = Field(description="Tool name")


class ToolSequenceSpec(BaseModel):
    """Evaluate if tool calls match expected sequence."""
    type: Literal["tool_sequence"]
    expected: list[ToolSequenceStep] = Field(description="Expected tool call sequence")
    order: Literal["strict", "any"] = Field(default="strict", description="strict=exact order, any=any order")


class ToolArgsSpec(BaseModel):
    """Evaluate if a tool call's arguments contain expected values."""
    type: Literal["tool_args"]
    tool: str = Field(description="Target tool name")
    contains: dict[str, Any] = Field(description="Expected key-value pairs in args")


class LLMJudgeDimension(BaseModel):
    """A scoring dimension for LLM-as-Judge."""
    name: str = Field(description="Dimension name")
    min: float = Field(default=0.0, description="Minimum score for this dimension")


class LLMJudgeSpec(BaseModel):
    """Evaluate using an LLM as judge."""
    type: Literal["llm_judge"]
    rubric: str = Field(description="Scoring rubric")
    threshold: float = Field(default=4.0, ge=1.0, le=5.0, description="Overall score threshold")
    dimensions: list[LLMJudgeDimension] = Field(default_factory=list, description="Per-dimension thresholds")
    compare_to: Optional[str] = Field(default=None, description="Compare against a previous round")
    model: Optional[str] = Field(default=None, description="Override judge model for this eval")


class SideEffectSpec(BaseModel):
    """Evaluate side effects of Moss execution."""
    type: Literal["side_effect"]
    check: Literal["file_modified", "file_created", "tests_pass", "tests_fail", "exit_code"]
    target: Optional[str] = Field(default=None, description="Target file or test name")


EvalSpec = ContainsSpec | ToolSequenceSpec | ToolArgsSpec | LLMJudgeSpec | SideEffectSpec


class TestConfig(BaseModel):
    """A single test case definition."""
    name: str = Field(description="Test name")
    description: str = Field(default="", description="Test description")
    moss: MossCallSpec = Field(description="How to call Moss")
    eval: list[EvalSpec] = Field(description="Evaluation criteria")
    flake_detection: Optional[FlakeDetection] = Field(default=None, description="Flake detection config")
    skip: bool = Field(default=False, description="Skip this test")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering")
