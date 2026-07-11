from __future__ import annotations
from typing import Optional, Literal, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Status of a pipeline run."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


class EvalResult(BaseModel):
    """Result of a single evaluator."""
    type: str = Field(description="Evaluator type")
    passed: bool = Field(description="Whether the evaluation passed")
    score: Optional[float] = Field(default=None, description="Score (for llm_judge)")
    details: dict[str, Any] = Field(default_factory=dict, description="Detailed results")
    error: Optional[str] = Field(default=None, description="Error message if evaluation failed")


class TestResult(BaseModel):
    """Result of a single test case."""
    test_name: str
    status: Literal["pass", "fail", "error", "flake", "skipped"]
    duration: float = Field(default=0.0, description="Duration in seconds")
    moss_output: str = Field(default="", description="Raw Moss output")
    moss_tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tool calls made by Moss")
    evals: list[EvalResult] = Field(default_factory=list, description="Evaluation results")
    flake_runs: Optional[list[TestResult]] = Field(default=None, description="Individual flake detection runs")
    error: Optional[str] = Field(default=None, description="Error message if status is error")


class SuiteResult(BaseModel):
    """Result of a test suite run."""
    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    flake: int = 0
    error: int = 0
    skipped: int = 0
    duration: float = 0.0
    tests: list[TestResult] = Field(default_factory=list)


class DiffItem(BaseModel):
    """A single regression/fix item."""
    test_name: str
    change: Literal["new_failure", "fixed", "improved", "degraded"]
    previous_status: Optional[str] = None
    current_status: Optional[str] = None
    previous_score: Optional[float] = None
    current_score: Optional[float] = None


class DiffResult(BaseModel):
    """Regression analysis result."""
    run_id: str
    previous_run_id: str
    new_failures: list[DiffItem] = Field(default_factory=list)
    fixed: list[DiffItem] = Field(default_factory=list)
    improved: list[DiffItem] = Field(default_factory=list)
    degraded: list[DiffItem] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Result of a complete pipeline run."""
    run_id: str = Field(default="", description="Unique run ID")
    pipeline_name: str
    status: RunStatus = RunStatus.PENDING
    suites: list[SuiteResult] = Field(default_factory=list)
    summary: str = Field(default="", description="Human-readable summary")
    diff: Optional[DiffResult] = Field(default=None, description="Regression diff")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    total_duration: float = Field(default=0.0)
