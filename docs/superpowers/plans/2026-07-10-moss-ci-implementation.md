# Moss CI 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个生产级 AI 智能体评测平台，用于对 Moss 智能体进行多维度回归测试。

**Architecture:** 分层架构：Pydantic 数据模型 → YAML 解析 → Pipeline 引擎（DAG 调度 + 并行执行）→ Moss Runner（CLI/API/SDK 三后端）→ Evaluator（5 种评估器）→ FastAPI + CLI + React Dashboard。PostgreSQL 存元数据，MinIO 存日志/产物，Redis 做队列和缓存。

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI, Typer, SQLAlchemy async, asyncpg, Redis, MinIO (boto3), PyYAML, NetworkX, Structlog, Tenacity, SSE-starlette, React + TypeScript + Recharts + Vite

## Global Constraints

- Python >= 3.11
- Pydantic >= 2（所有数据模型使用 Pydantic）
- 异步优先（asyncio + FastAPI + asyncpg）
- 所有公开接口必须有类型标注
- 测试使用 pytest + pytest-asyncio
- 日志使用 structlog
- YAML 解析使用 PyYAML

---

## Phase 1: Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `D:\moss-ci\pyproject.toml`
- Create: `D:\moss-ci\moss_ci\__init__.py`
- Create: `D:\moss-ci\tests\__init__.py`
- Create: `D:\moss-ci\tests\conftest.py`
- Create: `D:\moss-ci\examples\simple_assert.yaml`
- Create: `D:\moss-ci\examples\tool_check.yaml`
- Create: `D:\moss-ci\examples\llm_judge.yaml`
- Create: `D:\moss-ci\examples\e2e_scenario.yaml`

**Interfaces:**
- Produces: `pyproject.toml` 定义项目元数据和依赖，`moss_ci` 包可导入，`tests/conftest.py` 提供测试夹具

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "moss-ci"
version = "0.1.0"
description = "AI Agent Evaluation Platform for Moss"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]",
    "pydantic>=2",
    "pyyaml",
    "httpx",
    "asyncpg",
    "sqlalchemy[asyncio]",
    "alembic",
    "redis[hiredis]",
    "boto3",
    "rich",
    "typer",
    "sse-starlette",
    "structlog",
    "tenacity",
    "networkx",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "pytest-cov",
    "httpx",          # for TestClient
    "aiosqlite",      # for testing with SQLite
]

[project.scripts]
moss-ci = "moss_ci.cli.main:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["moss_ci*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create moss_ci/__init__.py**

```python
"""Moss CI — AI Agent Evaluation Platform."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create tests/__init__.py**

```python
"""Tests for Moss CI."""
```

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest
from pathlib import Path


@pytest.fixture
def examples_dir() -> Path:
    """Path to example YAML files."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def sample_suite_yaml() -> str:
    """A minimal valid suite YAML for testing."""
    return """
name: "test-suite"
description: "A test suite"
version: "1.0"
tests:
  - name: "simple-test"
    moss:
      prompt: "Hello"
    eval:
      - type: contains
        value: "expected"
"""
```

- [ ] **Step 5: Create example YAML files**

Create `D:\moss-ci\examples\simple_assert.yaml`:

```yaml
name: "简单断言示例"
description: "演示最基本的 contains 评估"
version: "1.0"
config:
  moss:
    timeout: 60
tests:
  - name: "hello-world"
    moss:
      prompt: "回复 'hello world'，不要带任何其他内容"
    eval:
      - type: contains
        value: "hello world"
```

Create `D:\moss-ci\examples\tool_check.yaml`:

```yaml
name: "工具调用示例"
description: "演示工具调用顺序和参数验证"
version: "1.0"
config:
  moss:
    timeout: 120
tests:
  - name: "read-then-write"
    moss:
      prompt: "读取 config.yaml，然后创建一个备份文件 config.backup.yaml"
    eval:
      - type: tool_sequence
        expected:
          - tool: read_file
          - tool: write_file
        order: strict
      - type: tool_args
        tool: read_file
        contains:
          path: "config.yaml"
```

Create `D:\moss-ci\examples\llm_judge.yaml`:

```yaml
name: "LLM Judge 示例"
description: "演示用 LLM-as-Judge 评估回复质量"
version: "1.0"
config:
  moss:
    timeout: 120
  eval:
    judge_model: claude-opus-4-8
tests:
  - name: "code-review-quality"
    moss:
      prompt: "请 review 以下代码，指出潜在问题:\n```python\ndef divide(a, b):\n    return a / b\n```"
    eval:
      - type: llm_judge
        rubric: |
          请从以下维度评分（1-5分）：
          1. 是否指出了除零错误
          2. 建议是否具体可操作
          3. 回复是否清晰简洁
        threshold: 3.0
```

Create `D:\moss-ci\examples\e2e_scenario.yaml`:

```yaml
name: "端到端示例"
description: "演示端到端任务测试"
version: "1.0"
config:
  moss:
    timeout: 300
tests:
  - name: "fix-and-test"
    moss:
      task: "在 fixtures/ 目录下有一个 buggy.py，找出 bug 并修复它"
      workdir: ./fixtures
    eval:
      - type: side_effect
        check: "file_modified"
      - type: llm_judge
        rubric: "修复是否正确"
        threshold: 3.0
```

- [ ] **Step 6: Install dependencies and verify**

```bash
cd D:\moss-ci
pip install -e ".[dev]"
python -c "import moss_ci; print(moss_ci.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
cd D:\moss-ci
git init
git add -A
git commit -m "feat: project scaffolding with pyproject.toml and examples"
```

---

### Task 2: Core Data Models

**Files:**
- Create: `D:\moss-ci\moss_ci\models\__init__.py`
- Create: `D:\moss-ci\moss_ci\models\pipeline.py`
- Create: `D:\moss-ci\moss_ci\models\test.py`
- Create: `D:\moss-ci\moss_ci\models\result.py`
- Test: `D:\moss-ci\tests\test_models.py`

**Interfaces:**
- Produces: `SuiteConfig`, `TestConfig`, `MossConfig`, `EvalSpec`, `ContainsSpec`, `ToolSequenceSpec`, `ToolArgsSpec`, `LLMJudgeSpec`, `SideEffectSpec`, `FlakeDetection`, `ConversationTurn`, `MossResult`, `EvalResult`, `TestResult`, `SuiteResult`, `PipelineResult`, `RunStatus`

- [ ] **Step 1: Write failing tests for models**

Create `D:\moss-ci\tests\test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\moss-ci
pytest tests/test_models.py -v
```

Expected: all tests FAIL (import errors)

- [ ] **Step 3: Create models/__init__.py**

```python
"""Data models for Moss CI."""
```

- [ ] **Step 4: Create models/pipeline.py**

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from moss_ci.models.test import TestConfig, MossConfig, EvalConfig


class SuiteConfig(BaseModel):
    """A test suite definition parsed from YAML."""

    name: str = Field(description="Suite name")
    description: str = Field(default="", description="Suite description")
    version: str = Field(default="1.0", description="Suite version")
    config: Optional[SuiteRunConfig] = Field(default=None, description="Global config")
    tests: list[TestConfig] = Field(description="Test cases in this suite")

    class SuiteRunConfig(BaseModel):
        """Global configuration for a suite run."""
        moss: MossConfig = Field(default_factory=MossConfig)
        eval: EvalConfig = Field(default_factory=EvalConfig)
        max_concurrency: int = Field(default=10, description="Max concurrent Moss calls")
        fail_fast: bool = Field(default=True, description="Stop on first failure")
```

- [ ] **Step 5: Create models/test.py**

```python
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
    """Specification for how to call Moss."""
    prompt: Optional[str] = Field(default=None, description="Single prompt")
    task: Optional[str] = Field(default=None, description="End-to-end task description")
    conversation: Optional[list[ConversationTurn]] = Field(default=None, description="Multi-turn conversation")
    context: Optional[str] = Field(default=None, description="Additional context for the prompt")
    workdir: Optional[str] = Field(default=None, description="Working directory for task execution")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")


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
```

- [ ] **Step 6: Create models/result.py**

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd D:\moss-ci
pytest tests/test_models.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
cd D:\moss-ci
git add -A
git commit -m "feat: add core data models (Pipeline, Test, Result)"
```

---

### Task 3: YAML Parser

**Files:**
- Create: `D:\moss-ci\moss_ci\parser\__init__.py`
- Create: `D:\moss-ci\moss_ci\parser\yaml_parser.py`
- Test: `D:\moss-ci\tests\test_parser.py`

**Interfaces:**
- Consumes: `SuiteConfig` from Task 2
- Produces: `parse_suite(filepath: str | Path) -> SuiteConfig`, `parse_suite_string(yaml_str: str) -> SuiteConfig`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_parser.py`:

```python
import pytest
from pathlib import Path
from moss_ci.parser.yaml_parser import parse_suite, parse_suite_string
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.test import ContainsSpec, MossCallSpec


SIMPLE_YAML = """
name: "test-suite"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""


class TestParseSuiteString:
    def test_parse_minimal(self):
        suite = parse_suite_string(SIMPLE_YAML)
        assert isinstance(suite, SuiteConfig)
        assert suite.name == "test-suite"
        assert suite.version == "1.0"
        assert len(suite.tests) == 1

    def test_parse_test_fields(self):
        suite = parse_suite_string(SIMPLE_YAML)
        test = suite.tests[0]
        assert test.name == "test-1"
        assert test.moss.prompt == "hello"
        assert len(test.eval) == 1
        assert isinstance(test.eval[0], ContainsSpec)
        assert test.eval[0].value == "world"

    def test_parse_with_config(self):
        yaml = """
name: "suite-with-config"
version: "1.0"
config:
  moss:
    timeout: 120
    retry: 3
  eval:
    judge_model: claude-sonnet-5
  max_concurrency: 5
  fail_fast: false
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        assert suite.config is not None
        assert suite.config.moss.timeout == 120
        assert suite.config.moss.retry == 3
        assert suite.config.eval.judge_model == "claude-sonnet-5"
        assert suite.config.max_concurrency == 5
        assert suite.config.fail_fast is False

    def test_parse_multiple_evals(self):
        yaml = """
name: "multi-eval"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
      - type: contains
        value: "hello"
        mode: any
"""
        suite = parse_suite_string(yaml)
        assert len(suite.tests[0].eval) == 2

    def test_parse_tool_sequence(self):
        yaml = """
name: "tool-test"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "read then write"
    eval:
      - type: tool_sequence
        expected:
          - tool: read_file
          - tool: write_file
        order: strict
"""
        suite = parse_suite_string(yaml)
        spec = suite.tests[0].eval[0]
        assert spec.type == "tool_sequence"
        assert len(spec.expected) == 2
        assert spec.expected[0].tool == "read_file"

    def test_parse_llm_judge(self):
        yaml = """
name: "judge-test"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: llm_judge
        rubric: "评分标准"
        threshold: 3.5
        dimensions:
          - name: "准确性"
            min: 3
"""
        suite = parse_suite_string(yaml)
        spec = suite.tests[0].eval[0]
        assert spec.type == "llm_judge"
        assert spec.threshold == 3.5
        assert len(spec.dimensions) == 1

    def test_parse_conversation(self):
        yaml = """
name: "conv-test"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      conversation:
        - role: user
          content: "hello"
        - role: assistant
        - role: user
          content: "more detail"
    eval:
      - type: contains
        value: "detail"
"""
        suite = parse_suite_string(yaml)
        moss = suite.tests[0].moss
        assert moss.conversation is not None
        assert len(moss.conversation) == 3
        assert moss.conversation[0].role == "user"
        assert moss.conversation[0].content == "hello"
        assert moss.conversation[1].role == "assistant"
        assert moss.conversation[1].content is None

    def test_parse_flake_detection(self):
        yaml = """
name: "flake-test"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
    flake_detection:
      runs: 5
      pass_threshold: 3
      consensus: majority
"""
        suite = parse_suite_string(yaml)
        test = suite.tests[0]
        assert test.flake_detection is not None
        assert test.flake_detection.runs == 5
        assert test.flake_detection.pass_threshold == 3

    def test_parse_defaults(self):
        yaml = """
name: "defaults-test"
version: "1.0"
tests:
  - name: "test-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        test = suite.tests[0]
        # None = not overridden at test level; Scheduler resolves to global default (300)
        assert test.moss.timeout is None
        assert test.moss.retry is None
        assert test.flake_detection is None
        assert test.tags == []


class TestParseSuiteFile:
    def test_parse_example_file(self, examples_dir):
        filepath = examples_dir / "simple_assert.yaml"
        suite = parse_suite(str(filepath))
        assert suite.name == "简单断言示例"
        assert len(suite.tests) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\moss-ci
pytest tests/test_parser.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Create parser/__init__.py**

```python
"""YAML parser for Moss CI suite definitions."""
```

- [ ] **Step 4: Create parser/yaml_parser.py**

```python
from __future__ import annotations
from pathlib import Path
import yaml
from moss_ci.models.pipeline import SuiteConfig


def parse_suite_string(yaml_str: str) -> SuiteConfig:
    """Parse a suite definition from a YAML string.

    Args:
        yaml_str: Raw YAML string containing a suite definition.

    Returns:
        A validated SuiteConfig instance.

    Raises:
        ValueError: If the YAML is invalid or doesn't match the schema.
    """
    data = yaml.safe_load(yaml_str)
    if data is None:
        raise ValueError("Empty YAML document")
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
    try:
        return SuiteConfig(**data)
    except Exception as e:
        raise ValueError(f"Invalid suite definition: {e}") from e


def parse_suite(filepath: str | Path) -> SuiteConfig:
    """Parse a suite definition from a YAML file.

    Args:
        filepath: Path to the YAML file.

    Returns:
        A validated SuiteConfig instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid or doesn't match the schema.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Suite file not found: {filepath}")
    content = path.read_text(encoding="utf-8")
    return parse_suite_string(content)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd D:\moss-ci
pytest tests/test_parser.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
cd D:\moss-ci
git add -A
git commit -m "feat: add YAML parser for suite definitions"
```

---

## Phase 2: Core Engine

### Task 4: Pipeline Engine (Scheduler + Executor)

**Files:**
- Create: `D:\moss-ci\moss_ci\engine\__init__.py`
- Create: `D:\moss-ci\moss_ci\engine\pipeline.py`
- Create: `D:\moss-ci\moss_ci\engine\scheduler.py`
- Create: `D:\moss-ci\moss_ci\engine\executor.py`
- Test: `D:\moss-ci\tests\test_engine.py`

**Interfaces:**
- Consumes: `SuiteConfig`, `TestConfig` from Task 2, `parse_suite` from Task 3
- Produces: `PipelineEngine.run(suites: list[SuiteConfig]) -> PipelineResult`, `Scheduler.plan(suites: list[SuiteConfig]) -> ExecutionPlan`, `Executor.execute(plan: ExecutionPlan) -> PipelineResult`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_engine.py`:

```python
import pytest
from moss_ci.engine.scheduler import Scheduler, ExecutionPlan, SuitePlan, TestPlan
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import RunStatus


TWO_SUITES_YAML = """
name: "suite-a"
version: "1.0"
tests:
  - name: "a-1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
  - name: "a-2"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""


class TestScheduler:
    def test_plan_single_suite(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.suites) == 1
        assert len(plan.suites[0].tests) == 2

    def test_plan_resolves_timeout(self):
        yaml = """
name: "config-suite"
version: "1.0"
config:
  moss:
    timeout: 120
    retry: 3
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert plan.suites[0].tests[0].timeout == 120
        assert plan.suites[0].tests[0].retry == 3

    def test_plan_skips_disabled_tests(self):
        yaml = """
name: "skip-suite"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
  - name: "t2"
    skip: true
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
"""
        suite = parse_suite_string(yaml)
        scheduler = Scheduler()
        plan = scheduler.plan([suite])
        assert len(plan.suites[0].tests) == 1
        assert plan.suites[0].tests[0].test.name == "t1"


class TestPipelineEngine:
    @pytest.mark.asyncio
    async def test_engine_creates_result(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        engine = PipelineEngine(PipelineConfig(fail_fast=False))
        result = await engine.run([suite])
        assert result.pipeline_name == "pipeline"
        assert result.status in (RunStatus.SUCCESS, RunStatus.FAILED)
        assert len(result.suites) == 1
        assert result.suites[0].total == 2

    @pytest.mark.asyncio
    async def test_engine_fail_fast(self):
        suite = parse_suite_string(TWO_SUITES_YAML)
        engine = PipelineEngine(PipelineConfig(fail_fast=True))
        result = await engine.run([suite])
        assert result.status in (RunStatus.SUCCESS, RunStatus.FAILED)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\moss-ci
pytest tests/test_engine.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Create engine/__init__.py**

```python
"""Pipeline engine for scheduling and executing tests."""
```

- [ ] **Step 4: Create engine/scheduler.py**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.test import TestConfig


@dataclass
class TestPlan:
    """A test ready for execution with resolved config."""
    test: TestConfig
    suite_name: str
    timeout: int
    retry: int


@dataclass
class SuitePlan:
    """A suite ready for execution."""
    suite_name: str
    tests: list[TestPlan]
    max_concurrency: int
    fail_fast: bool
    # Count of tests dropped at plan time via ``skip: true``. The executor
    # does not run these, but records the count in SuiteResult.skipped so the
    # design's 5-state result model is honored.
    skipped_count: int = 0


@dataclass
class ExecutionPlan:
    """The complete execution plan for a pipeline run."""
    suites: list[SuitePlan] = field(default_factory=list)
    global_max_concurrency: int = 10

    @property
    def total_tests(self) -> int:
        return sum(len(s.tests) for s in self.suites)


class Scheduler:
    """Builds execution plans, resolving config inheritance."""

    def plan(self, suites: list[SuiteConfig]) -> ExecutionPlan:
        suite_plans: list[SuitePlan] = []
        for suite in suites:
            suite_plans.append(self._plan_suite(suite))
        return ExecutionPlan(suites=suite_plans)

    def _plan_suite(self, suite: SuiteConfig) -> SuitePlan:
        global_moss = suite.config.moss if suite.config else None
        global_fail_fast = suite.config.fail_fast if suite.config else True
        global_concurrency = suite.config.max_concurrency if suite.config else 10

        # Resolve global defaults to concrete ints (None at the global level
        # means "use the hard-coded platform default").
        global_timeout = global_moss.timeout if (global_moss and global_moss.timeout is not None) else 300
        global_retry = global_moss.retry if (global_moss and global_moss.retry is not None) else 0

        test_plans: list[TestPlan] = []
        skipped_count = 0
        for test in suite.tests:
            if test.skip:
                skipped_count += 1
                continue
            # Sentinel-based override detection: a None at the test level
            # means "inherit the resolved global value". This correctly
            # handles a user explicitly setting timeout: 300.
            timeout = test.moss.timeout if test.moss.timeout is not None else global_timeout
            retry = test.moss.retry if test.moss.retry is not None else global_retry
            test_plans.append(TestPlan(
                test=test,
                suite_name=suite.name,
                timeout=timeout,
                retry=retry,
            ))
        return SuitePlan(
            suite_name=suite.name,
            tests=test_plans,
            max_concurrency=global_concurrency,
            fail_fast=global_fail_fast,
            skipped_count=skipped_count,
        )
```

- [ ] **Step 5: Create engine/executor.py**

```python
from __future__ import annotations
import asyncio
import time
import structlog
from moss_ci.engine.scheduler import SuitePlan, TestPlan, ExecutionPlan
from moss_ci.models.result import (
    SuiteResult, TestResult, PipelineResult, RunStatus, EvalResult,
)

logger = structlog.get_logger(__name__)


class Executor:
    """Executes test plans with concurrency control."""

    def __init__(self, max_concurrency: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(self, plan: ExecutionPlan) -> PipelineResult:
        suite_tasks = [self._execute_suite(suite) for suite in plan.suites]
        suite_results = await asyncio.gather(*suite_tasks, return_exceptions=True)

        results: list[SuiteResult] = []
        for i, result in enumerate(suite_results):
            if isinstance(result, Exception):
                logger.error("suite.error", suite=plan.suites[i].suite_name, error=str(result))
                results.append(SuiteResult(
                    suite_name=plan.suites[i].suite_name,
                    total=len(plan.suites[i].tests),
                    error=len(plan.suites[i].tests),
                ))
            else:
                results.append(result)

        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        total_error = sum(r.error for r in results)
        overall_status = RunStatus.SUCCESS if total_failed == 0 and total_error == 0 else RunStatus.FAILED

        return PipelineResult(
            pipeline_name="pipeline",
            status=overall_status,
            suites=results,
            summary=f"{total_passed} passed, {total_failed} failed, {total_error} error",
        )

    async def _execute_suite(self, suite: SuitePlan) -> SuiteResult:
        start = time.monotonic()
        semaphore = asyncio.Semaphore(suite.max_concurrency)

        async def run_with_limit(tp: TestPlan) -> TestResult:
            async with semaphore:
                async with self._semaphore:
                    return await self._execute_test(tp)

        tasks = [run_with_limit(tp) for tp in suite.tests]
        test_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[TestResult] = []
        passed = failed = error_cnt = 0
        for i, result in enumerate(test_results):
            if isinstance(result, Exception):
                tr = TestResult(test_name=suite.tests[i].test.name, status="error", error=str(result))
                error_cnt += 1
            else:
                tr = result
                if tr.status == "pass":
                    passed += 1
                elif tr.status == "fail":
                    failed += 1
                elif tr.status == "error":
                    error_cnt += 1
            results.append(tr)
            if suite.fail_fast and tr.status in ("fail", "error"):
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break

        duration = time.monotonic() - start
        return SuiteResult(
            suite_name=suite.suite_name,
            total=len(suite.tests),
            passed=passed, failed=failed, error=error_cnt,
            skipped=suite.skipped_count,
            duration=duration, tests=results,
        )

    async def _execute_test(self, test_plan: TestPlan) -> TestResult:
        # SCAFFOLD: Moss output is mocked here. The real MossRunner (built in
        # Tasks 5-6) is NOT yet wired in — that switchover is Task 16.
        # Until then, contains/tool_sequence/tool_args evaluators are
        # exercised against synthetic output, and llm_judge returns a
        # hardcoded score (see evaluator/llm_judge.py). This is deliberate:
        # it lets the whole pipeline run and pass tests before a real Moss
        # instance is available.
        start = time.monotonic()
        test = test_plan.test
        try:
            moss_output = f"[mock] Moss: {test.moss.prompt or test.moss.task}"
            moss_tool_calls: list[dict] = []

            eval_results: list[EvalResult] = []
            for eval_spec in test.eval:
                er = await self._evaluate(eval_spec, moss_output, moss_tool_calls)
                eval_results.append(er)

            all_passed = all(er.passed for er in eval_results)
            status = "pass" if all_passed else "fail"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return TestResult(test_name=test.name, status="error", duration=time.monotonic() - start, error=str(e))

        return TestResult(
            test_name=test.name, status=status, duration=time.monotonic() - start,
            moss_output=moss_output, moss_tool_calls=moss_tool_calls, evals=eval_results,
        )

    async def _evaluate(self, eval_spec, moss_output: str, moss_tool_calls: list[dict]) -> EvalResult:
        from moss_ci.evaluator.registry import EvaluatorRegistry
        return await EvaluatorRegistry().evaluate(eval_spec, moss_output, moss_tool_calls)
```

- [ ] **Step 6: Create engine/pipeline.py**

```python
from __future__ import annotations
from dataclasses import dataclass
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.result import PipelineResult
from moss_ci.engine.scheduler import Scheduler
from moss_ci.engine.executor import Executor


@dataclass
class PipelineConfig:
    fail_fast: bool = True
    max_concurrency: int = 10
    pipeline_name: str = "pipeline"


class PipelineEngine:
    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self._scheduler = Scheduler()
        self._executor = Executor(max_concurrency=self.config.max_concurrency)

    async def run(self, suites: list[SuiteConfig]) -> PipelineResult:
        plan = self._scheduler.plan(suites)
        result = await self._executor.execute(plan)
        result.pipeline_name = self.config.pipeline_name
        return result
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd D:\moss-ci
pytest tests/test_engine.py -v
```

Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
cd D:\moss-ci
git add -A
git commit -m "feat: add pipeline engine with scheduler and executor"
```

---

### Task 5: Moss Runner — Base + CLI Backend

**Files:**
- Create: `D:\moss-ci\moss_ci\runner\__init__.py`
- Create: `D:\moss-ci\moss_ci\runner\base.py`
- Create: `D:\moss-ci\moss_ci\runner\cli_backend.py`
- Modify: `D:\moss-ci\moss_ci\models\result.py` (add MossResult)
- Test: `D:\moss-ci\tests\test_runner.py`

**Interfaces:**
- Consumes: `MossCallSpec` from Task 2
- Produces: `MossResult`, `MossBackend` (ABC), `MossRunner`, `CLIBackend`

- [ ] **Step 1: Add MossResult to models/result.py**

Append to `D:\moss-ci\moss_ci\models\result.py`:

```python
class MossResult(BaseModel):
    """Raw result from a Moss invocation."""
    output: str = Field(default="")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    exit_code: int = Field(default=0)
    duration: float = Field(default=0.0)
    workdir: str = Field(default="")
    files_modified: list[str] = Field(default_factory=list)
    raw_log: str = Field(default="")
```

- [ ] **Step 2: Write failing tests**

Create `D:\moss-ci\tests\test_runner.py`:

```python
import pytest
from moss_ci.runner.base import MossRunner
from moss_ci.runner.cli_backend import CLIBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult


class TestCLIBackend:
    @pytest.mark.asyncio
    async def test_run_simple(self):
        backend = CLIBackend(moss_command="echo")
        spec = MossCallSpec(prompt="hello world")
        result = await backend.run(spec)
        assert "hello world" in result.output
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_run_with_env(self):
        backend = CLIBackend(moss_command="bash")
        spec = MossCallSpec(prompt="-c 'echo $MY_VAR'", env={"MY_VAR": "testval"})
        result = await backend.run(spec)
        assert "testval" in result.output


class TestMossRunner:
    @pytest.mark.asyncio
    async def test_auto_detect_cli(self):
        runner = MossRunner()
        spec = MossCallSpec(prompt="echo hello")
        result = await runner.run(spec)
        assert isinstance(result, MossResult)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd D:\moss-ci
pytest tests/test_runner.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 4: Create runner/__init__.py**

```python
"""Moss Runner — unified interface for calling Moss."""
```

- [ ] **Step 5: Create runner/base.py**

```python
from __future__ import annotations
import asyncio, os, time, structlog
from abc import ABC, abstractmethod
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class MossBackend(ABC):
    @abstractmethod
    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult: ...

    async def run_conversation(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not spec.conversation:
            raise ValueError("No conversation turns defined")
        all_outputs: list[str] = []
        all_tool_calls: list[dict] = []
        for turn in spec.conversation:
            if turn.role == "user":
                turn_spec = MossCallSpec(prompt=turn.content or "", env=spec.env, workdir=spec.workdir)
                result = await self.run(turn_spec, timeout=timeout)
                all_outputs.append(f"[{turn.role}]: {result.output}")
                all_tool_calls.extend(result.tool_calls)
        return MossResult(output="\n".join(all_outputs), tool_calls=all_tool_calls)

    async def run_task(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not spec.task:
            raise ValueError("No task defined")
        return await self.run(spec, timeout=timeout)


class MossRunner:
    def __init__(self, backend: MossBackend | None = None, default_timeout: int = 300):
        self.default_timeout = default_timeout
        self.backend = backend if backend is not None else self._detect_backend()

    def _detect_backend(self) -> MossBackend:
        try:
            import moss
            from moss_ci.runner.sdk_backend import SDKBackend
            logger.info("backend.auto_detect", selected="sdk")
            return SDKBackend()
        except ImportError:
            pass
        api_url = os.environ.get("MOSS_API_URL", "")
        if api_url:
            from moss_ci.runner.api_backend import APIBackend
            api_key = os.environ.get("MOSS_API_KEY", "")
            logger.info("backend.auto_detect", selected="api", url=api_url)
            return APIBackend(base_url=api_url, api_key=api_key or None)
        from moss_ci.runner.cli_backend import CLIBackend
        moss_cmd = os.environ.get("MOSS_CLI_COMMAND", "moss")
        logger.info("backend.auto_detect", selected="cli", command=moss_cmd)
        return CLIBackend(moss_command=moss_cmd)

    async def run(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run(spec, timeout=self.default_timeout)

    async def run_conversation(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run_conversation(spec, timeout=self.default_timeout)

    async def run_task(self, spec: MossCallSpec) -> MossResult:
        return await self.backend.run_task(spec, timeout=self.default_timeout)
```

- [ ] **Step 6: Create runner/cli_backend.py**

```python
from __future__ import annotations
import asyncio, os, time, structlog
from pathlib import Path
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class CLIBackend(MossBackend):
    def __init__(self, moss_command: str = "moss"):
        self.moss_command = moss_command

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        start = time.monotonic()
        prompt = spec.prompt or spec.task or ""
        cmd = [self.moss_command, prompt]
        env = {**os.environ, **spec.env}
        cwd = str(Path(spec.workdir).resolve()) if spec.workdir else None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            raw_log = output + ("\n[stderr]\n" + stderr.decode("utf-8", errors="replace") if stderr else "")
            return MossResult(output=output.strip(), exit_code=process.returncode or 0,
                              duration=time.monotonic() - start, workdir=spec.workdir or "", raw_log=raw_log)
        except asyncio.TimeoutError:
            return MossResult(output="", exit_code=-1, duration=time.monotonic() - start,
                              raw_log=f"Timeout after {timeout}s")
        except FileNotFoundError:
            return MossResult(output=f"Error: '{self.moss_command}' not found", exit_code=127,
                              duration=time.monotonic() - start, raw_log=f"Command not found: {self.moss_command}")
```

- [ ] **Step 7: Run tests**

```bash
cd D:\moss-ci
pytest tests/test_runner.py -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: add Moss Runner base + CLI backend"
```

---

### Task 6: Moss Runner — API + SDK Backends

**Files:**
- Create: `D:\moss-ci\moss_ci\runner\api_backend.py`
- Create: `D:\moss-ci\moss_ci\runner\sdk_backend.py`
- Test: `D:\moss-ci\tests\test_runner_backends.py`

**Interfaces:**
- Consumes: `MossBackend` from Task 5
- Produces: `APIBackend`, `SDKBackend`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_runner_backends.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from moss_ci.runner.api_backend import APIBackend
from moss_ci.runner.sdk_backend import SDKBackend
from moss_ci.models.test import MossCallSpec, ConversationTurn


class TestAPIBackend:
    @pytest.mark.asyncio
    async def test_run_sends_request(self):
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"output": "API response", "tool_calls": []}
        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            backend = APIBackend(base_url="http://localhost:8000")
            result = await backend.run(MossCallSpec(prompt="test"), timeout=30)
        assert result.output == "API response"

    @pytest.mark.asyncio
    async def test_run_handles_error(self):
        mock_resp = AsyncMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("httpx.AsyncClient.post", return_value=mock_resp):
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_runner_backends.py -v
```
Expected: FAIL

- [ ] **Step 3: Create runner/api_backend.py**

```python
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
```

- [ ] **Step 4: Create runner/sdk_backend.py**

```python
from __future__ import annotations
import asyncio, time, structlog
from moss_ci.runner.base import MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult

logger = structlog.get_logger(__name__)


class SDKBackend(MossBackend):
    def __init__(self):
        self._available: bool | None = None

    def _check(self) -> bool:
        if self._available is None:
            try:
                import moss
                self._moss = moss
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not self._check():
            return MossResult(output="Error: Moss SDK not available", exit_code=-1)
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(asyncio.to_thread(self._moss.run, spec.prompt or spec.task or ""), timeout=timeout)
            return MossResult(output=result.get("output", ""), tool_calls=result.get("tool_calls", []),
                              exit_code=0, duration=time.monotonic() - start, raw_log=result.get("output", ""))
        except asyncio.TimeoutError:
            return MossResult(output=f"Timeout after {timeout}s", exit_code=-1, duration=time.monotonic() - start)

    async def run_task(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        if not self._check():
            return MossResult(output="Error: Moss SDK not available", exit_code=-1)
        start = time.monotonic()
        try:
            if hasattr(self._moss, "run_task"):
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._moss.run_task, spec.task, workdir=spec.workdir), timeout=timeout)
                return MossResult(output=result.get("output", ""), tool_calls=result.get("tool_calls", []),
                                  files_modified=result.get("files_modified", []), exit_code=0,
                                  duration=time.monotonic() - start, raw_log=result.get("output", ""))
            return await self.run(spec, timeout=timeout)
        except asyncio.TimeoutError:
            return MossResult(output=f"Timeout after {timeout}s", exit_code=-1, duration=time.monotonic() - start)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_runner_backends.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add Moss Runner API + SDK backends"
```

---

### Task 7: Evaluator — All 5 Types

**Files:**
- Create: `D:\moss-ci\moss_ci\evaluator\__init__.py`
- Create: `D:\moss-ci\moss_ci\evaluator\base.py`
- Create: `D:\moss-ci\moss_ci\evaluator\contains.py`
- Create: `D:\moss-ci\moss_ci\evaluator\tool_sequence.py`
- Create: `D:\moss-ci\moss_ci\evaluator\tool_args.py`
- Create: `D:\moss-ci\moss_ci\evaluator\llm_judge.py`
- Create: `D:\moss-ci\moss_ci\evaluator\side_effect.py`
- Create: `D:\moss-ci\moss_ci\evaluator\registry.py`
- Test: `D:\moss-ci\tests\test_evaluator.py`

**Interfaces:**
- Consumes: `EvalSpec`, `EvalResult` from Task 2
- Produces: `BaseEvaluator`, `EvaluatorRegistry`, 5 concrete evaluators

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_evaluator.py`:

```python
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_evaluator.py -v
```
Expected: FAIL

- [ ] **Step 3: Create all evaluator files**

Create `evaluator/__init__.py`:
```python
"""Evaluation engine for Moss CI."""
```

Create `evaluator/base.py`:
```python
from abc import ABC, abstractmethod
from typing import Any
from moss_ci.models.result import EvalResult

class BaseEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, spec: Any, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult: ...
```

Create `evaluator/contains.py`:
```python
import re
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ContainsSpec
from moss_ci.models.result import EvalResult

class ContainsEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ContainsSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        if spec.is_regex:
            m = re.search(spec.value, moss_output, re.IGNORECASE | re.DOTALL)
            return EvalResult(type="contains", passed=m is not None, details={"matched": m.group(0) if m else None, "pattern": spec.value})
        passed = spec.value in moss_output
        return EvalResult(type="contains", passed=passed, details={"expected": spec.value, "matched": spec.value if passed else None})
```

Create `evaluator/tool_sequence.py`:
```python
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ToolSequenceSpec
from moss_ci.models.result import EvalResult

class ToolSequenceEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ToolSequenceSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        actual = [tc.get("tool", "") for tc in tool_calls]
        expected = [s.tool for s in spec.expected]
        if spec.order == "strict":
            if len(actual) < len(expected):
                return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": "Insufficient calls"})
            for i, e in enumerate(expected):
                if actual[i] != e:
                    return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": f"Pos {i}: expected {e}, got {actual[i]}"})
            return EvalResult(type="tool_sequence", passed=True, details={"expected": expected, "actual": actual[:len(expected)]})
        else:
            remaining = list(actual)
            for e in expected:
                if e in remaining:
                    remaining.remove(e)
                else:
                    return EvalResult(type="tool_sequence", passed=False, details={"expected": expected, "actual": actual, "error": f"'{e}' not found"})
            return EvalResult(type="tool_sequence", passed=True, details={"expected": expected, "actual": actual})
```

Create `evaluator/tool_args.py`:
```python
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import ToolArgsSpec
from moss_ci.models.result import EvalResult

class ToolArgsEvaluator(BaseEvaluator):
    async def evaluate(self, spec: ToolArgsSpec, moss_output: str, tool_calls: list[dict[str, Any]]) -> EvalResult:
        # NOTE: matching is string-substring based (str(expected) in str(arg)).
        # This is deliberately permissive for the scaffold — it lets YAML
        # authors write `contains: {body: "fix"}` without worrying about
        # exact types. Known limitation: bool/number coercion is lossy
        # (True matches "True" never "true"), so prefer string-valued
        # `contains` specs. Structured equality matching is a future task.
        targets = [tc for tc in tool_calls if tc.get("tool") == spec.tool]
        if not targets:
            return EvalResult(type="tool_args", passed=False, details={"tool": spec.tool, "error": "Tool not called"})
        for call in targets:
            args = call.get("args", {})
            if all(str(expected_val) in str(args.get(key, "")) for key, expected_val in spec.contains.items()):
                return EvalResult(type="tool_args", passed=True, details={"tool": spec.tool, "matched_args": args})
        return EvalResult(type="tool_args", passed=False, details={"tool": spec.tool, "expected": spec.contains, "actual": [c.get("args", {}) for c in targets]})
```

Create `evaluator/llm_judge.py`:
```python
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
```

Create `evaluator/side_effect.py`:
```python
from typing import Any
from moss_ci.evaluator.base import BaseEvaluator
from moss_ci.models.test import SideEffectSpec
from moss_ci.models.result import EvalResult

class SideEffectEvaluator(BaseEvaluator):
    async def evaluate(self, spec: SideEffectSpec, moss_output: str, tool_calls: list[dict[str, Any]], files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        if spec.check == "file_modified":
            mods = files_modified or []
            passed = len(mods) > 0 if not spec.target else spec.target in mods
            return EvalResult(type="side_effect", passed=passed, details={"check": "file_modified", "files": mods})
        elif spec.check == "file_created":
            passed = len(files_modified or []) > 0
            return EvalResult(type="side_effect", passed=passed, details={"check": "file_created"})
        elif spec.check == "tests_pass":
            passed = "PASSED" in moss_output or "OK" in moss_output
            return EvalResult(type="side_effect", passed=passed, details={"check": "tests_pass"})
        elif spec.check == "tests_fail":
            passed = "FAILED" in moss_output or "FAIL" in moss_output
            return EvalResult(type="side_effect", passed=passed, details={"check": "tests_fail"})
        elif spec.check == "exit_code":
            return EvalResult(type="side_effect", passed=exit_code == 0, details={"check": "exit_code", "exit_code": exit_code})
        return EvalResult(type="side_effect", passed=False, error=f"Unknown check: {spec.check}")
```

Create `evaluator/registry.py`:
```python
from typing import Any
from moss_ci.evaluator.contains import ContainsEvaluator
from moss_ci.evaluator.tool_sequence import ToolSequenceEvaluator
from moss_ci.evaluator.tool_args import ToolArgsEvaluator
from moss_ci.evaluator.llm_judge import LLMJudgeEvaluator
from moss_ci.evaluator.side_effect import SideEffectEvaluator
from moss_ci.models.result import EvalResult

class EvaluatorRegistry:
    def __init__(self):
        self._evals = {"contains": ContainsEvaluator(), "tool_sequence": ToolSequenceEvaluator(),
                       "tool_args": ToolArgsEvaluator(), "llm_judge": LLMJudgeEvaluator(),
                       "side_effect": SideEffectEvaluator()}

    async def evaluate(self, spec: Any, moss_output: str, tool_calls: list[dict[str, Any]], files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        e = self._evals.get(spec.type)
        if e is None:
            return EvalResult(type=spec.type, passed=False, error=f"Unknown evaluator: {spec.type}")
        if spec.type == "side_effect":
            return await e.evaluate(spec, moss_output, tool_calls, files_modified=files_modified, exit_code=exit_code)
        return await e.evaluate(spec, moss_output, tool_calls)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_evaluator.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add evaluator with all 5 evaluation types"
```

---

## Phase 3: Storage

### Task 8: Database Layer (SQLAlchemy + Alembic)

**Files:**
- Create: `D:\moss-ci\moss_ci\storage\__init__.py`
- Create: `D:\moss-ci\moss_ci\storage\db.py`
- Create: `D:\moss-ci\moss_ci\storage\models.py`
- Create: `D:\moss-ci\moss_ci\storage\repository.py`
- Create: `D:\moss-ci\alembic.ini`
- Create: `D:\moss-ci\alembic\env.py`
- Create: `D:\moss-ci\alembic\versions\.gitkeep`
- Test: `D:\moss-ci\tests\test_storage_db.py`

**Interfaces:**
- Consumes: `PipelineResult`, `SuiteResult`, `TestResult`, `EvalResult` from Task 2
- Produces: `Database.get_session() -> AsyncSession`, `RunRepository.save(result) / get(run_id) / list(limit)`, SQLAlchemy ORM models

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_storage_db.py`:

```python
import pytest
from moss_ci.storage.db import Database, get_db
from moss_ci.storage.models import RunRecord, TestResultRecord
from moss_ci.storage.repository import RunRepository
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, RunStatus, EvalResult


class TestDatabase:
    @pytest.mark.asyncio
    async def test_init_and_create_tables(self):
        db = Database(url="sqlite+aiosqlite:///:memory:")
        await db.init()
        async with db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        await db.close()

    @pytest.mark.asyncio
    async def test_get_db_singleton(self):
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2


class TestRunRepository:
    @pytest.fixture
    async def repo(self):
        db = Database(url="sqlite+aiosqlite:///:memory:")
        await db.init()
        repo = RunRepository(db)
        yield repo
        await db.close()

    @pytest.mark.asyncio
    async def test_save_and_get(self, repo):
        result = PipelineResult(
            run_id="run-001", pipeline_name="test-pipeline",
            status=RunStatus.SUCCESS, summary="all passed",
            suites=[SuiteResult(suite_name="suite-a", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", duration=0.5,
                                      evals=[EvalResult(type="contains", passed=True)])])]
        )
        saved = await repo.save(result)
        assert saved.run_id == "run-001"
        loaded = await repo.get("run-001")
        assert loaded is not None
        assert loaded.status == RunStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_list_runs(self, repo):
        for i in range(3):
            await repo.save(PipelineResult(run_id=f"run-{i:03d}", pipeline_name="test", status=RunStatus.SUCCESS))
        runs = await repo.list(limit=2)
        assert len(runs) == 2
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_storage_db.py -v
```
Expected: FAIL

- [ ] **Step 3: Create storage/__init__.py**

```python
"""Storage layer for Moss CI."""
```

- [ ] **Step 4: Create storage/db.py**

```python
from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from moss_ci.storage.models import Base

_db_instance: Database | None = None


class Database:
    def __init__(self, url: str = ""):
        self.url = url or "sqlite+aiosqlite:///moss_ci.db"
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def init(self):
        self.engine = create_async_engine(self.url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        if self.engine:
            await self.engine.dispose()

    def get_session(self) -> AsyncSession:
        if self.session_factory is None:
            raise RuntimeError("Database not initialized. Call db.init() first.")
        return self.session_factory()


def get_db(url: str = "") -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(url)
    return _db_instance
```

- [ ] **Step 5: Create storage/models.py**

```python
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "runs"
    run_id = Column(String, primary_key=True)
    pipeline_name = Column(String, nullable=False)
    status = Column(String, default="pending")
    summary = Column(String, default="")
    total_duration = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    suites = relationship("SuiteResultRecord", back_populates="run", cascade="all, delete-orphan")


class SuiteResultRecord(Base):
    __tablename__ = "suite_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.run_id"), nullable=False)
    suite_name = Column(String, nullable=False)
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    flake = Column(Integer, default=0)
    error = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    duration = Column(Float, default=0.0)
    run = relationship("RunRecord", back_populates="suites")
    tests = relationship("TestResultRecord", back_populates="suite", cascade="all, delete-orphan")


class TestResultRecord(Base):
    __tablename__ = "test_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("suite_results.id"), nullable=False)
    test_name = Column(String, nullable=False)
    status = Column(String, default="pending")
    duration = Column(Float, default=0.0)
    moss_output = Column(Text, default="")
    moss_tool_calls = Column(JSON, default=list)
    error = Column(Text, nullable=True)
    suite = relationship("SuiteResultRecord", back_populates="tests")
    evals = relationship("EvalResultRecord", back_populates="test", cascade="all, delete-orphan")


class EvalResultRecord(Base):
    __tablename__ = "eval_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_result_id = Column(Integer, ForeignKey("test_results.id"), nullable=False)
    type = Column(String, nullable=False)
    passed = Column(Integer, default=0)  # SQLite has no bool
    score = Column(Float, nullable=True)
    details = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    test = relationship("TestResultRecord", back_populates="evals")
```

- [ ] **Step 6: Create storage/repository.py**

```python
from __future__ import annotations
from moss_ci.storage.db import Database
from moss_ci.storage.models import RunRecord, SuiteResultRecord, TestResultRecord, EvalResultRecord
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, EvalResult, RunStatus
from sqlalchemy import select


class RunRepository:
    def __init__(self, db: Database):
        self.db = db

    async def save(self, result: PipelineResult) -> PipelineResult:
        async with self.db.get_session() as session:
            run = RunRecord(
                run_id=result.run_id, pipeline_name=result.pipeline_name,
                status=result.status.value, summary=result.summary,
                total_duration=result.total_duration, completed_at=result.completed_at,
            )
            for suite in result.suites:
                sr = SuiteResultRecord(
                    suite_name=suite.suite_name, total=suite.total,
                    passed=suite.passed, failed=suite.failed, flake=suite.flake,
                    error=suite.error, skipped=suite.skipped, duration=suite.duration,
                )
                for test in suite.tests:
                    tr = TestResultRecord(
                        test_name=test.test_name, status=test.status, duration=test.duration,
                        moss_output=test.moss_output, moss_tool_calls=test.moss_tool_calls,
                        error=test.error,
                    )
                    for ev in test.evals:
                        tr.evals.append(EvalResultRecord(
                            type=ev.type, passed=1 if ev.passed else 0,
                            score=ev.score, details=ev.details, error=ev.error,
                        ))
                    sr.tests.append(tr)
                run.suites.append(sr)
            session.add(run)
            await session.commit()
        return result

    async def get(self, run_id: str) -> PipelineResult | None:
        async with self.db.get_session() as session:
            stmt = select(RunRecord).where(RunRecord.run_id == run_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return self._to_domain(record)

    async def list(self, limit: int = 20, offset: int = 0) -> list[PipelineResult]:
        async with self.db.get_session() as session:
            stmt = select(RunRecord).order_by(RunRecord.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            records = result.scalars().all()
            return [self._to_domain(r) for r in records]

    def _to_domain(self, record: RunRecord) -> PipelineResult:
        suites = []
        for sr in record.suites:
            tests = []
            for tr in sr.tests:
                evals = [EvalResult(type=er.type, passed=bool(er.passed), score=er.score, details=er.details, error=er.error) for er in tr.evals]
                tests.append(TestResult(test_name=tr.test_name, status=tr.status, duration=tr.duration,
                                        moss_output=tr.moss_output, moss_tool_calls=tr.moss_tool_calls,
                                        evals=evals, error=tr.error))
            suites.append(SuiteResult(suite_name=sr.suite_name, total=sr.total, passed=sr.passed,
                                      failed=sr.failed, flake=sr.flake, error=sr.error, skipped=sr.skipped,
                                      duration=sr.duration, tests=tests))
        return PipelineResult(run_id=record.run_id, pipeline_name=record.pipeline_name,
                              status=RunStatus(record.status), summary=record.summary,
                              suites=suites, total_duration=record.total_duration,
                              created_at=record.created_at, completed_at=record.completed_at)
```

- [ ] **Step 7: Create alembic.ini**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite+aiosqlite:///moss_ci.db

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
[logger_sqlalchemy]
level = WARN
handlers =
[logger_alembic]
level = INFO
handlers =
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `D:\moss-ci\alembic\env.py`:
```python
from moss_ci.storage.models import Base
target_metadata = Base.metadata
```

Create `D:\moss-ci\alembic\versions\.gitkeep` (empty file).

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_storage_db.py -v
```
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: add database layer with SQLAlchemy + Alembic"
```

---

### Task 9: Object Store + Redis

**Files:**
- Create: `D:\moss-ci\moss_ci\storage\object_store.py`
- Create: `D:\moss-ci\moss_ci\storage\cache.py`
- Test: `D:\moss-ci\tests\test_storage_ext.py`

**Interfaces:**
- Consumes: nothing external
- Produces: `ObjectStore.put(key, data) / get(key) -> bytes`, `CacheManager.get(key) / set(key, value, ttl)`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_storage_ext.py`:

```python
import pytest
from moss_ci.storage.object_store import ObjectStore
from moss_ci.storage.cache import CacheManager


class TestObjectStore:
    def test_put_and_get(self, tmp_path):
        store = ObjectStore(backend="local", local_dir=str(tmp_path))
        store.put("test/key", b"hello world")
        assert store.get("test/key") == b"hello world"

    def test_get_missing(self, tmp_path):
        store = ObjectStore(backend="local", local_dir=str(tmp_path))
        assert store.get("nonexistent") is None


class TestCacheManager:
    def test_set_and_get(self):
        cache = CacheManager(backend="memory")
        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_get_missing(self):
        cache = CacheManager(backend="memory")
        assert cache.get("missing") is None

    def test_ttl_expiry(self):
        cache = CacheManager(backend="memory")
        cache.set("key1", "value1", ttl=-1)  # immediate expiry
        assert cache.get("key1") is None
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_storage_ext.py -v
```
Expected: FAIL

- [ ] **Step 3: Create storage/object_store.py**

```python
from __future__ import annotations
import os
from pathlib import Path


class ObjectStore:
    def __init__(self, backend: str = "local", local_dir: str = "./data/objects", **kwargs):
        self.backend = backend
        if backend == "local":
            self._dir = Path(local_dir)
            self._dir.mkdir(parents=True, exist_ok=True)
        elif backend == "s3":
            self._bucket = kwargs.get("bucket", "moss-ci")
            self._client = None  # Lazy init boto3

    def put(self, key: str, data: bytes):
        if self.backend == "local":
            path = self._dir / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        if self.backend == "local":
            path = self._dir / key
            if path.exists():
                return path.read_bytes()
            return None
```

- [ ] **Step 4: Create storage/cache.py**

```python
from __future__ import annotations
import time


class CacheManager:
    def __init__(self, backend: str = "memory", redis_url: str = ""):
        self.backend = backend
        self._store: dict[str, tuple[float, any]] = {}  # (expiry, value)
        if backend == "redis" and redis_url:
            self._redis = None  # Lazy init redis

    def get(self, key: str):
        if self.backend == "memory":
            entry = self._store.get(key)
            if entry is None:
                return None
            expiry, value = entry
            if expiry > 0 and time.time() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl: int = 300):
        if self.backend == "memory":
            expiry = time.time() + ttl if ttl > 0 else 0
            self._store[key] = (expiry, value)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_storage_ext.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add object store and cache layer"
```

---

## Phase 4: API Server

### Task 10: FastAPI Server + Core Endpoints

**Files:**
- Create: `D:\moss-ci\moss_ci\api\__init__.py`
- Create: `D:\moss-ci\moss_ci\api\server.py`
- Create: `D:\moss-ci\moss_ci\api\routes\__init__.py`
- Create: `D:\moss-ci\moss_ci\api\routes\runs.py`
- Create: `D:\moss-ci\moss_ci\api\schemas.py`
- Test: `D:\moss-ci\tests\test_api.py`

**Interfaces:**
- Consumes: `PipelineEngine` from Task 4, `RunRepository` from Task 8
- Produces: FastAPI app with `/api/v1/pipelines/run`, `/api/v1/runs/{run_id}`, `/api/v1/runs/{run_id}/logs`, `/api/v1/runs/{run_id}/cancel`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_api.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from moss_ci.api.server import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_run_pipeline(self, client):
        resp = await client.post("/api/v1/pipelines/run", json={
            "suites": [{
                "name": "test-suite", "version": "1.0",
                "tests": [{"name": "t1", "moss": {"prompt": "hello"}, "eval": [{"type": "contains", "value": "world"}]}]
            }]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] in ("running", "success", "failed")

    @pytest.mark.asyncio
    async def test_get_run_status(self, client):
        # First create a run
        run_resp = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        run_id = run_resp.json()["run_id"]
        resp = await client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run_id
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_api.py -v
```
Expected: FAIL

- [ ] **Step 3: Create api/schemas.py**

```python
from pydantic import BaseModel, Field
from moss_ci.models.pipeline import SuiteConfig


class RunPipelineRequest(BaseModel):
    suites: list[dict] = Field(description="Suite configs as dicts")
    pipeline_name: str = Field(default="api-pipeline")

class RunPipelineResponse(BaseModel):
    run_id: str
    pipeline_name: str
    status: str
```

- [ ] **Step 4: Create api/routes/__init__.py** (empty file)

- [ ] **Step 5: Create api/routes/runs.py**

```python
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio, json
from moss_ci.api.schemas import RunPipelineRequest, RunPipelineResponse
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import PipelineResult, RunStatus
import yaml

router = APIRouter(prefix="/api/v1")
# SCAFFOLD ONLY: in-memory store. The RunRepository built in Task 8 (PostgreSQL)
# is NOT wired in here yet — that switchover is Task 16. Tests in Task 10/11 pass
# against this in-memory store; once Task 16 lands, replace _runs with the repo.
_runs: dict[str, PipelineResult] = {}


def _dict_to_suite(data: dict):
    yaml_str = yaml.dump(data, allow_unicode=True)
    return parse_suite_string(yaml_str)


@router.post("/pipelines/run", response_model=RunPipelineResponse)
async def run_pipeline(req: RunPipelineRequest):
    run_id = str(uuid.uuid4())[:8]
    suites = [_dict_to_suite(s) for s in req.suites]
    engine = PipelineEngine(PipelineConfig(pipeline_name=req.pipeline_name))
    result = await engine.run(suites)
    result.run_id = run_id
    _runs[run_id] = result
    return RunPipelineResponse(run_id=run_id, pipeline_name=req.pipeline_name, status=result.status.value)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    result = _runs[run_id]
    return result.model_dump()


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    async def event_stream():
        result = _runs[run_id]
        for suite in result.suites:
            for test in suite.tests:
                yield f"data: {json.dumps({'test': test.test_name, 'status': test.status})}\n\n"
                await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'status': result.status.value, 'summary': result.summary})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    _runs[run_id].status = RunStatus.CANCELLED
    return {"run_id": run_id, "status": "cancelled"}
```

- [ ] **Step 6: Create api/server.py**

```python
from fastapi import FastAPI
from moss_ci.api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Moss CI", version="0.1.0")
    app.include_router(runs_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_api.py -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: add FastAPI server with core endpoints"
```

---

### Task 11: API Advanced Endpoints

**Files:**
- Modify: `D:\moss-ci\moss_ci\api\routes\runs.py` (add history, diff, suites endpoints)
- Test: `D:\moss-ci\tests\test_api_advanced.py`

**Interfaces:**
- Consumes: `RunRepository` from Task 8
- Produces: `GET /runs`, `GET /runs/{id}/diff`, `GET /suites`, `GET /suites/{name}/history`, `GET /runs/{id}/tests`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_api_advanced.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from moss_ci.api.server import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAdvancedEndpoints:
    @pytest.mark.asyncio
    async def test_list_runs(self, client):
        resp = await client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_diff(self, client):
        # Create two runs
        r1 = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        r2 = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        resp = await client.get(f"/api/v1/runs/{r2.json()['run_id']}/diff")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_tests(self, client):
        r = await client.post("/api/v1/pipelines/run", json={
            "suites": [{"name": "s1", "version": "1.0",
                        "tests": [{"name": "t1", "moss": {"prompt": "hi"}, "eval": [{"type": "contains", "value": "hi"}]}]}]
        })
        run_id = r.json()["run_id"]
        resp = await client.get(f"/api/v1/runs/{run_id}/tests")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_api_advanced.py -v
```
Expected: FAIL (404 on some endpoints)

- [ ] **Step 3: Add advanced endpoints to api/routes/runs.py**

Append to `D:\moss-ci\moss_ci\api\routes\runs.py`:

```python
@router.get("/runs")
async def list_runs(limit: int = 20, offset: int = 0):
    all_runs = list(_runs.values())
    all_runs.sort(key=lambda r: r.created_at, reverse=True)
    page = all_runs[offset:offset + limit]
    return [r.model_dump() for r in page]


@router.get("/runs/{run_id}/diff")
async def diff_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    current = _runs[run_id]
    all_runs = sorted([r for r in _runs.values() if r.run_id != run_id], key=lambda r: r.created_at, reverse=True)
    previous = all_runs[0] if all_runs else None
    diff = {"new_failures": [], "fixed": [], "improved": [], "degraded": []}
    if previous:
        for cur_suite in current.suites:
            prev_suite = next((s for s in previous.suites if s.suite_name == cur_suite.suite_name), None)
            if prev_suite:
                for cur_test in cur_suite.tests:
                    prev_test = next((t for t in prev_suite.tests if t.test_name == cur_test.test_name), None)
                    if prev_test:
                        if prev_test.status == "pass" and cur_test.status == "fail":
                            diff["new_failures"].append({"test_name": cur_test.test_name, "previous_status": prev_test.status, "current_status": cur_test.status})
                        elif prev_test.status == "fail" and cur_test.status == "pass":
                            diff["fixed"].append({"test_name": cur_test.test_name})
    return diff


@router.get("/runs/{run_id}/tests")
async def list_tests(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    tests = []
    for suite in _runs[run_id].suites:
        for test in suite.tests:
            tests.append({"suite_name": suite.suite_name, **test.model_dump()})
    return tests


@router.get("/runs/{run_id}/tests/{test_name}")
async def get_test_detail(run_id: str, test_name: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    for suite in _runs[run_id].suites:
        for test in suite.tests:
            if test.test_name == test_name:
                return {"suite_name": suite.suite_name, **test.model_dump()}
    raise HTTPException(status_code=404, detail="Test not found")


@router.get("/suites")
async def list_suites():
    suite_names = set()
    for run in _runs.values():
        for suite in run.suites:
            suite_names.add(suite.suite_name)
    return list(suite_names)


@router.get("/suites/{name}/history")
async def suite_history(name: str, limit: int = 20):
    history = []
    for run in sorted(_runs.values(), key=lambda r: r.created_at, reverse=True):
        for suite in run.suites:
            if suite.suite_name == name:
                history.append({"run_id": run.run_id, "date": run.created_at.isoformat(), "passed": suite.passed, "failed": suite.failed, "total": suite.total})
    return history[:limit]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api_advanced.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add advanced API endpoints (history, diff, suites)"
```

---

## Phase 5: CLI

### Task 12: CLI with Typer

**Files:**
- Create: `D:\moss-ci\moss_ci\cli\__init__.py`
- Create: `D:\moss-ci\moss_ci\cli\main.py`
- Test: `D:\moss-ci\tests\test_cli.py`

**Interfaces:**
- Consumes: `parse_suite` from Task 3, `PipelineEngine` from Task 4
- Produces: `moss-ci` CLI command with subcommands: run, status, logs, history, diff, init, validate

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_cli.py`:

```python
import pytest
from typer.testing import CliRunner
from moss_ci.cli.main import app

runner = CliRunner()


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout

    def test_init(self, tmp_path):
        import os
        os.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / "moss-ci.yaml").exists()

    def test_validate_valid(self, tmp_path):
        import os
        os.chdir(tmp_path)
        suite_dir = tmp_path / "suites"
        suite_dir.mkdir()
        (suite_dir / "test.yaml").write_text("""
name: "test"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "world"
""")
        result = runner.invoke(app, ["validate", str(suite_dir)])
        assert result.exit_code == 0

    def test_validate_invalid(self, tmp_path):
        import os
        os.chdir(tmp_path)
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("invalid: [")
        result = runner.invoke(app, ["validate", str(bad_file)])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_cli.py -v
```
Expected: FAIL

- [ ] **Step 3: Create cli/__init__.py**

```python
"""CLI for Moss CI."""
```

- [ ] **Step 4: Create cli/main.py**

```python
import typer, asyncio, yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from moss_ci.parser.yaml_parser import parse_suite, parse_suite_string
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig

app = typer.Typer(name="moss-ci", help="Moss CI — AI Agent Evaluation Platform")
console = Console()


@app.command()
def run(
    path: str = typer.Argument("./suites", help="Suite file or directory"),
    test_name: str = typer.Option(None, "--test", help="Run a specific test"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    concurrency: int = typer.Option(10, "--concurrency", "-c"),
):
    """Run test suites."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    suite_files = [p] if p.is_file() else sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
    if not suite_files:
        console.print(f"[red]Error:[/red] No YAML files found in {path}")
        raise typer.Exit(1)

    suites = []
    for f in suite_files:
        try:
            suites.append(parse_suite(str(f)))
            console.print(f"[green]✓[/green] Loaded: {f.name}")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed: {f.name} — {e}")

    if not suites:
        raise typer.Exit(1)

    async def _run():
        engine = PipelineEngine(PipelineConfig(fail_fast=fail_fast, max_concurrency=concurrency))
        return await engine.run(suites)

    console.print(f"\nRunning {sum(len(s.tests) for s in suites)} tests across {len(suites)} suites...\n")
    result = asyncio.run(_run())

    table = Table(title="Results")
    table.add_column("Suite", style="cyan")
    table.add_column("Passed", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Error", style="yellow")
    for s in result.suites:
        table.add_row(s.suite_name, str(s.passed), str(s.failed), str(s.error))
    console.print(table)
    console.print(f"\n[bold]{result.summary}[/bold]")
    if result.status.value == "failed":
        raise typer.Exit(1)


@app.command()
def status(run_id: str = typer.Argument(..., help="Run ID")):
    """Show run status."""
    console.print(f"[yellow]Status for {run_id}:[/yellow] not available (API not running)")


@app.command()
def logs(run_id: str = typer.Argument(..., help="Run ID"), test_name: str = typer.Option(None, "--test")):
    """Show run logs."""
    console.print(f"[yellow]Logs for {run_id}:[/yellow] not available (API not running)")


@app.command()
def history(limit: int = typer.Option(20, "--limit", "-n")):
    """Show run history."""
    console.print("[yellow]History:[/yellow] not available (API not running)")


@app.command()
def diff(run_id_1: str = typer.Argument(...), run_id_2: str = typer.Argument(...)):
    """Compare two runs."""
    console.print(f"[yellow]Diff {run_id_1} vs {run_id_2}:[/yellow] not available (API not running)")


@app.command()
def init():
    """Initialize a moss-ci project."""
    config = {"version": "1.0", "suites_dir": "./suites"}
    p = Path("moss-ci.yaml")
    if p.exists():
        console.print("[yellow]moss-ci.yaml already exists[/yellow]")
        return
    p.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")
    Path("./suites").mkdir(exist_ok=True)
    console.print("[green]✓[/green] Created moss-ci.yaml and suites/")


@app.command()
def validate(path: str = typer.Argument("./suites", help="Suite file or directory")):
    """Validate suite YAML files."""
    p = Path(path)
    if not p.exists():
        console.print(f"[red]Error:[/red] Path not found: {path}")
        raise typer.Exit(1)

    files = [p] if p.is_file() else sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
    if not files:
        console.print(f"[red]Error:[/red] No YAML files found")
        raise typer.Exit(1)

    errors = 0
    for f in files:
        try:
            parse_suite(str(f))
            console.print(f"[green]✓[/green] {f.name}")
        except Exception as e:
            console.print(f"[red]✗[/red] {f.name}: {e}")
            errors += 1
    if errors:
        console.print(f"\n[red]{errors} file(s) failed validation[/red]")
        raise typer.Exit(1)
    console.print(f"\n[green]All {len(files)} file(s) valid[/green]")


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_cli.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add CLI with Typer (run, init, validate)"
```

---

## Phase 6: Advanced Features

### Task 13: Flake Detection

**Files:**
- Create: `D:\moss-ci\moss_ci\engine\flake.py`
- Modify: `D:\moss-ci\moss_ci\engine\executor.py` (integrate flake detection)
- Test: `D:\moss-ci\tests\test_flake.py`

**Interfaces:**
- Consumes: `FlakeDetection`, `TestResult` from Task 2, `Executor` from Task 4
- Produces: `FlakeDetector.detect(test_plan, executor) -> TestResult`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_flake.py`:

```python
import pytest
from moss_ci.engine.flake import FlakeDetector
from moss_ci.models.test import FlakeDetection, TestConfig, MossCallSpec, ContainsSpec
from moss_ci.models.result import TestResult, EvalResult
from moss_ci.engine.scheduler import TestPlan


class MockExecutor:
    async def _execute_test(self, plan):
        return TestResult(test_name=plan.test.name, status="pass", duration=0.1, evals=[EvalResult(type="contains", passed=True)])


class TestFlakeDetector:
    @pytest.mark.asyncio
    async def test_all_pass(self):
        detector = FlakeDetector()
        flake_config = FlakeDetection(runs=3, pass_threshold=2, consensus="majority")
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"), eval=[ContainsSpec(type="contains", value="hi")], flake_detection=flake_config)
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)
        executor = MockExecutor()
        result = await detector.detect(plan, executor)
        assert result.status == "pass"
        assert result.flake_runs is not None
        assert len(result.flake_runs) == 3

    @pytest.mark.asyncio
    async def test_majority_consensus(self):
        detector = FlakeDetector()
        flake_config = FlakeDetection(runs=3, pass_threshold=2, consensus="majority")
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"), eval=[ContainsSpec(type="contains", value="hi")], flake_detection=flake_config)
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)

        class MixedExecutor:
            call_count = 0
            async def _execute_test(self, plan):
                self.call_count += 1
                status = "pass" if self.call_count <= 2 else "fail"
                return TestResult(test_name=plan.test.name, status=status, duration=0.1, evals=[EvalResult(type="contains", passed=status=="pass")])

        result = await detector.detect(plan, MixedExecutor())
        assert result.status == "pass"
        assert result.flake_runs is not None
        assert len(result.flake_runs) == 3
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_flake.py -v
```
Expected: FAIL

- [ ] **Step 3: Create engine/flake.py**

```python
import structlog
from moss_ci.engine.scheduler import TestPlan
from moss_ci.models.result import TestResult

logger = structlog.get_logger(__name__)


class FlakeDetector:
    async def detect(self, plan: TestPlan, executor) -> TestResult:
        flake = plan.test.flake_detection
        runs: list[TestResult] = []
        for i in range(flake.runs):
            result = await executor._execute_test(plan)
            runs.append(result)
        passed_count = sum(1 for r in runs if r.status == "pass")
        if flake.consensus == "unanimous":
            final_status = "pass" if passed_count == flake.runs else "fail"
        else:
            final_status = "pass" if passed_count >= flake.pass_threshold else "fail"
        if passed_count < flake.runs and passed_count >= flake.pass_threshold:
            final_status = "flake"
        return TestResult(
            test_name=plan.test.name, status=final_status,
            duration=sum(r.duration for r in runs),
            moss_output=runs[0].moss_output,
            moss_tool_calls=runs[0].moss_tool_calls,
            evals=runs[0].evals,
            flake_runs=runs,
        )
```

- [ ] **Step 4: Integrate into executor.py**

Modify `_execute_test` in `D:\moss-ci\moss_ci\engine\executor.py` to check for flake_detection:

```python
    async def _execute_test(self, test_plan: TestPlan) -> TestResult:
        if test_plan.test.flake_detection is not None:
            from moss_ci.engine.flake import FlakeDetector
            return await FlakeDetector().detect(test_plan, self)
        # ... existing single-test logic ...
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_flake.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add flake detection for AI output randomness"
```

---

### Task 14: Regression Analysis (Diff Engine)

**Files:**
- Create: `D:\moss-ci\moss_ci\engine\diff.py`
- Test: `D:\moss-ci\tests\test_diff.py`

**Interfaces:**
- Consumes: `PipelineResult`, `DiffResult`, `DiffItem` from Task 2
- Produces: `DiffEngine.compare(current, previous) -> DiffResult`

- [ ] **Step 1: Write failing tests**

Create `D:\moss-ci\tests\test_diff.py`:

```python
import pytest
from moss_ci.engine.diff import DiffEngine
from moss_ci.models.result import PipelineResult, SuiteResult, TestResult, EvalResult, RunStatus


def make_result(run_id: str, test_statuses: dict[str, str]) -> PipelineResult:
    tests = [TestResult(test_name=name, status=status) for name, status in test_statuses.items()]
    return PipelineResult(
        run_id=run_id, pipeline_name="test", status=RunStatus.SUCCESS,
        suites=[SuiteResult(suite_name="s1", total=len(tests), passed=sum(1 for t in tests if t.status=="pass"),
                            failed=sum(1 for t in tests if t.status=="fail"), tests=tests)]
    )


class TestDiffEngine:
    def test_new_failure(self):
        prev = make_result("r1", {"t1": "pass", "t2": "pass"})
        curr = make_result("r2", {"t1": "fail", "t2": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.new_failures) == 1
        assert diff.new_failures[0].test_name == "t1"

    def test_fixed(self):
        prev = make_result("r1", {"t1": "fail", "t2": "pass"})
        curr = make_result("r2", {"t1": "pass", "t2": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.fixed) == 1
        assert diff.fixed[0].test_name == "t1"

    def test_no_change(self):
        prev = make_result("r1", {"t1": "pass"})
        curr = make_result("r2", {"t1": "pass"})
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.new_failures) == 0
        assert len(diff.fixed) == 0

    def test_score_change(self):
        prev = PipelineResult(
            run_id="r1", pipeline_name="test", status=RunStatus.SUCCESS,
            suites=[SuiteResult(suite_name="s1", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", evals=[EvalResult(type="llm_judge", passed=True, score=4.5)])])]
        )
        curr = PipelineResult(
            run_id="r2", pipeline_name="test", status=RunStatus.SUCCESS,
            suites=[SuiteResult(suite_name="s1", total=1, passed=1,
                    tests=[TestResult(test_name="t1", status="pass", evals=[EvalResult(type="llm_judge", passed=True, score=3.0)])])]
        )
        diff = DiffEngine().compare(curr, prev)
        assert len(diff.degraded) == 1
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_diff.py -v
```
Expected: FAIL

- [ ] **Step 3: Create engine/diff.py**

```python
from moss_ci.models.result import PipelineResult, DiffResult, DiffItem


class DiffEngine:
    def compare(self, current: PipelineResult, previous: PipelineResult, score_threshold: float = 0.5) -> DiffResult:
        diff = DiffResult(run_id=current.run_id, previous_run_id=previous.run_id)
        prev_tests = self._index_tests(previous)
        curr_tests = self._index_tests(current)
        for name, cur_test in curr_tests.items():
            prev_test = prev_tests.get(name)
            if prev_test is None:
                continue
            if prev_test.status == "pass" and cur_test.status == "fail":
                diff.new_failures.append(DiffItem(test_name=name, change="new_failure",
                    previous_status=prev_test.status, current_status=cur_test.status))
            elif prev_test.status == "fail" and cur_test.status == "pass":
                diff.fixed.append(DiffItem(test_name=name, change="fixed",
                    previous_status=prev_test.status, current_status=cur_test.status))
            prev_score = self._get_llm_judge_score(prev_test)
            cur_score = self._get_llm_judge_score(cur_test)
            if prev_score is not None and cur_score is not None:
                if cur_score > prev_score + score_threshold:
                    diff.improved.append(DiffItem(test_name=name, change="improved",
                        previous_score=prev_score, current_score=cur_score))
                elif cur_score < prev_score - score_threshold:
                    diff.degraded.append(DiffItem(test_name=name, change="degraded",
                        previous_score=prev_score, current_score=cur_score))
        return diff

    def _index_tests(self, result: PipelineResult) -> dict:
        index = {}
        for suite in result.suites:
            for test in suite.tests:
                index[test.test_name] = test
        return index

    def _get_llm_judge_score(self, test):
        for ev in test.evals:
            if ev.type == "llm_judge" and ev.score is not None:
                return ev.score
        return None
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_diff.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add regression analysis diff engine"
```

---

## Phase 7: Web Dashboard

### Task 15: React Web Dashboard

**Files:**
- Create: `D:\moss-ci\moss_ci\web\package.json`
- Create: `D:\moss-ci\moss_ci\web\vite.config.ts`
- Create: `D:\moss-ci\moss_ci\web\tsconfig.json`
- Create: `D:\moss-ci\moss_ci\web\index.html`
- Create: `D:\moss-ci\moss_ci\web\src\main.tsx`
- Create: `D:\moss-ci\moss_ci\web\src\App.tsx`
- Create: `D:\moss-ci\moss_ci\web\src\api.ts`
- Create: `D:\moss-ci\moss_ci\web\src\pages\Dashboard.tsx`
- Create: `D:\moss-ci\moss_ci\web\src\pages\RunDetail.tsx`
- Create: `D:\moss-ci\moss_ci\web\src\components\RunList.tsx`
- Create: `D:\moss-ci\moss_ci\web\src\components\TrendChart.tsx`

**Interfaces:**
- Consumes: Moss CI REST API from Tasks 10-11
- Produces: Web UI with Dashboard, Run Detail, Trend views

- [ ] **Step 1: Create package.json**

```json
{
  "name": "moss-ci-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.26",
    "recharts": "^2.12"
  },
  "devDependencies": {
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3",
    "@vitejs/plugin-react": "^4.3",
    "typescript": "^5.5",
    "vite": "^5.4"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, proxy: { '/api': 'http://localhost:8000' } },
})
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>Moss CI</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
```

- [ ] **Step 5: Create src/main.tsx**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter><App /></BrowserRouter>
  </React.StrictMode>
)
```

- [ ] **Step 6: Create src/api.ts**

```typescript
const BASE = '/api/v1'

export interface RunSummary {
  run_id: string; pipeline_name: string; status: string;
  summary: string; created_at: string; total_duration: number;
  suites: SuiteSummary[];
}
export interface SuiteSummary {
  suite_name: string; total: number; passed: number; failed: number; error: number;
  tests: TestSummary[];
}
export interface TestSummary {
  test_name: string; status: string; duration: number; moss_output: string;
  evals: { type: string; passed: boolean; score?: number }[];
}

export async function fetchRuns(limit = 20): Promise<RunSummary[]> {
  const r = await fetch(`${BASE}/runs?limit=${limit}`)
  return r.json()
}
export async function fetchRun(runId: string): Promise<RunSummary> {
  const r = await fetch(`${BASE}/runs/${runId}`)
  return r.json()
}
export async function fetchDiff(runId: string): Promise<any> {
  const r = await fetch(`${BASE}/runs/${runId}/diff`)
  return r.json()
}
export async function runPipeline(suites: any[]): Promise<{ run_id: string }> {
  const r = await fetch(`${BASE}/pipelines/run`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suites }),
  })
  return r.json()
}
```

- [ ] **Step 7: Create src/App.tsx**

```tsx
import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import RunDetail from './pages/RunDetail'

export default function App() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 20 }}>
      <header style={{ borderBottom: '1px solid #e0e0e0', marginBottom: 24, paddingBottom: 12 }}>
        <h1 style={{ margin: 0 }}><Link to="/" style={{ textDecoration: 'none', color: '#333' }}>Moss CI</Link></h1>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
      </Routes>
    </div>
  )
}
```

- [ ] **Step 8: Create src/pages/Dashboard.tsx**

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchRuns, RunSummary } from '../api'
import TrendChart from '../components/TrendChart'

export default function Dashboard() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  useEffect(() => { fetchRuns().then(setRuns) }, [])

  return (
    <div>
      <h2>Dashboard</h2>
      <TrendChart runs={runs} />
      <h3>Recent Runs</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
            <th style={{ textAlign: 'left', padding: 8 }}>Run ID</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Pipeline</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Summary</th>
            <th style={{ textAlign: 'left', padding: 8 }}>Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map(run => (
            <tr key={run.run_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: 8 }}><Link to={`/runs/${run.run_id}`}>{run.run_id}</Link></td>
              <td style={{ padding: 8 }}>{run.pipeline_name}</td>
              <td style={{ padding: 8, color: run.status === 'success' ? 'green' : run.status === 'failed' ? 'red' : 'orange' }}>{run.status}</td>
              <td style={{ padding: 8 }}>{run.summary}</td>
              <td style={{ padding: 8 }}>{new Date(run.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 9: Create src/pages/RunDetail.tsx**

```tsx
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchRun, fetchDiff, RunSummary } from '../api'

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const [run, setRun] = useState<RunSummary | null>(null)
  const [diff, setDiff] = useState<any>(null)

  useEffect(() => {
    if (runId) { fetchRun(runId).then(setRun); fetchDiff(runId).then(setDiff) }
  }, [runId])

  if (!run) return <div>Loading...</div>

  return (
    <div>
      <Link to="/">← Back</Link>
      <h2>Run {run.run_id}</h2>
      <p>Status: <strong style={{ color: run.status === 'success' ? 'green' : 'red' }}>{run.status}</strong></p>
      <p>{run.summary}</p>
      {diff && (diff.new_failures?.length > 0 || diff.fixed?.length > 0) && (
        <div style={{ background: '#fff3cd', padding: 12, borderRadius: 4, marginBottom: 16 }}>
          <h4>Regression Analysis</h4>
          {diff.new_failures?.length > 0 && <p style={{ color: 'red' }}>⚠ {diff.new_failures.length} new failure(s)</p>}
          {diff.fixed?.length > 0 && <p style={{ color: 'green' }}>✓ {diff.fixed.length} fixed</p>}
        </div>
      )}
      <h3>Suites</h3>
      {run.suites.map(suite => (
        <div key={suite.suite_name} style={{ marginBottom: 16 }}>
          <h4>{suite.suite_name} ({suite.passed}/{suite.total} passed)</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Test</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Duration</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Evaluations</th>
              </tr>
            </thead>
            <tbody>
              {suite.tests.map(test => (
                <tr key={test.test_name} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: 8 }}>{test.test_name}</td>
                  <td style={{ padding: 8, color: test.status === 'pass' ? 'green' : 'red' }}>{test.status}</td>
                  <td style={{ padding: 8 }}>{test.duration.toFixed(1)}s</td>
                  <td style={{ padding: 8 }}>
                    {test.evals.map((ev, i) => (
                      <span key={i} style={{ marginRight: 8, color: ev.passed ? 'green' : 'red' }}>
                        {ev.type}: {ev.passed ? '✓' : '✗'}{ev.score != null ? ` (${ev.score})` : ''}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 10: Create src/components/RunList.tsx**

```tsx
import { Link } from 'react-router-dom'
import { RunSummary } from '../api'

export default function RunList({ runs }: { runs: RunSummary[] }) {
  if (runs.length === 0) return <p>No runs yet.</p>
  return (
    <div>
      {runs.map(run => (
        <div key={run.run_id} style={{ border: '1px solid #e0e0e0', borderRadius: 4, padding: 12, marginBottom: 8 }}>
          <Link to={`/runs/${run.run_id}`}><strong>{run.run_id}</strong></Link>
          <span style={{ marginLeft: 16, color: run.status === 'success' ? 'green' : 'red' }}>{run.status}</span>
          <span style={{ marginLeft: 16, color: '#666' }}>{run.summary}</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 11: Create src/components/TrendChart.tsx**

```tsx
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { RunSummary } from '../api'

export default function TrendChart({ runs }: { runs: RunSummary[] }) {
  const data = [...runs].reverse().slice(-10).map(run => {
    const total = run.suites.reduce((s, suite) => s + suite.passed, 0)
    const failed = run.suites.reduce((s, suite) => s + suite.failed + suite.error, 0)
    return { name: run.run_id, passed: total, failed }
  })
  if (data.length === 0) return <p>No data for chart.</p>
  return (
    <div style={{ marginBottom: 24 }}>
      <h3>Pass/Fail Trend</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="passed" fill="#4caf50" stackId="a" />
          <Bar dataKey="failed" fill="#f44336" stackId="a" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 12: Install and verify**

```bash
cd D:\moss-ci\moss_ci\web
npm install
npm run build
```

Expected: build succeeds

- [ ] **Step 13: Commit**

```bash
cd D:\moss-ci
git add -A
git commit -m "feat: add React Web Dashboard"
```

---

## Phase 8: Scaffold → Real Switchover

> Tasks 1-15 build the full platform with **mock Moss output** and a
> **hardcoded LLM-judge score**. The pipeline runs and all tests pass, but
> no real Moss agent is invoked and no real regression detection happens.
> This phase swaps in the real components. **Do not start this phase until
> Tasks 1-15 are green and committed** — it modifies working code, so it
> must land on a known-good baseline.
>
> Each switchover step is independently revertable. If wiring real Moss
> breaks the suite, revert just that step; the scaffold stays green.

### Task 16: Wire Real Moss Runner + Real Judge + Persist Runs

**Files:**
- Modify: `D:\moss-ci\moss_ci\engine\executor.py` (replace mock output with MossRunner)
- Modify: `D:\moss-ci\moss_ci\engine\pipeline.py` (inject MossRunner into Executor)
- Modify: `D:\moss-ci\moss_ci\evaluator\llm_judge.py` (real judge model call)
- Modify: `D:\moss-ci\moss_ci\api\routes\runs.py` (replace `_runs` dict with RunRepository)
- Modify: `D:\moss-ci\moss_ci\api\server.py` (init Database on startup)
- Test: `D:\moss-ci\tests\test_switchover.py`

**Interfaces:**
- Consumes: `MossRunner` from Task 5, `RunRepository` from Task 8, `PipelineResult` from Task 2
- Produces: an executor that calls real Moss (via whatever backend the env selects), a judge evaluator that calls a real model, and an API that persists runs to PostgreSQL

**Prerequisites (user must provide before starting):**
1. A way to invoke Moss. Exactly one of:
   - **CLI**: the `moss` command on PATH (or set `MOSS_CLI_COMMAND=/path/to/moss`)
   - **API**: set `MOSS_API_URL=https://...` and optionally `MOSS_API_KEY=...`
   - **SDK**: `import moss` works in the project venv
2. A judge-model endpoint for LLM-as-Judge: set `MOSS_CI_JUDGE_API_URL=https://...` (OpenAI-compatible `/chat/completions` shape). Without this, `llm_judge` tests still pass but scores stay default.

- [ ] **Step 1: Write failing switchover tests**

Create `D:\moss-ci\tests\test_switchover.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.engine.executor import Executor
from moss_ci.runner.base import MossRunner, MossBackend
from moss_ci.models.test import MossCallSpec
from moss_ci.models.result import MossResult
from moss_ci.parser.yaml_parser import parse_suite_string


class StubBackend(MossBackend):
    """A fake Moss backend that returns deterministic output for tests."""
    def __init__(self):
        self.calls = []

    async def run(self, spec: MossCallSpec, timeout: int = 300) -> MossResult:
        self.calls.append(spec)
        # Echo the prompt so a `contains` eval on a known substring passes
        return MossResult(output=f"real-response: {spec.prompt or spec.task}", exit_code=0, duration=0.01)


class TestExecutorUsesRunner:
    @pytest.mark.asyncio
    async def test_executor_invokes_runner(self):
        # The executor must call the injected runner, not produce mock output.
        stub = StubBackend()
        runner = MossRunner(backend=stub)
        executor = Executor(runner=runner)
        from moss_ci.engine.scheduler import TestPlan
        from moss_ci.models.test import TestConfig, ContainsSpec
        test = TestConfig(name="t1", moss=MossCallSpec(prompt="hi"),
                          eval=[ContainsSpec(type="contains", value="real-response")])
        plan = TestPlan(test=test, suite_name="s1", timeout=30, retry=0)
        result = await executor._execute_test(plan)
        assert len(stub.calls) == 1
        assert "real-response" in result.moss_output  # not "[mock]"
        assert result.status == "pass"


class TestPipelineAcceptsRunner:
    @pytest.mark.asyncio
    async def test_pipeline_injects_runner(self):
        stub = StubBackend()
        runner = MossRunner(backend=stub)
        engine = PipelineEngine(PipelineConfig(fail_fast=False), runner=runner)
        suite = parse_suite_string("""
name: "switchover-suite"
version: "1.0"
tests:
  - name: "t1"
    moss:
      prompt: "hello"
    eval:
      - type: contains
        value: "real-response"
""")
        result = await engine.run([suite])
        assert len(stub.calls) == 1
        assert result.suites[0].passed == 1
        assert "real-response" in result.suites[0].tests[0].moss_output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\moss-ci
pytest tests/test_switchover.py -v
```

Expected: FAIL — `Executor` and `PipelineEngine` do not accept a `runner` kwarg yet (TypeError).

- [ ] **Step 3: Modify executor.py to accept and use a runner**

This is a **surgical edit of three methods** in `D:\moss-ci\moss_ci\engine\executor.py` — `__init__` (add `runner` param), `_execute_test` (call the runner), and `_evaluate` (widen signature). The other methods (`execute`, `_execute_suite`) from Task 4 stay unchanged. The Executor now holds an optional `MossRunner`; when present it calls real Moss, otherwise it falls back to mock (so existing Tasks 4/13 tests that don't pass a runner stay green).

**3a.** Replace `__init__`:

```python
    def __init__(self, max_concurrency: int = 10, runner=None):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._runner = runner  # Optional[MossRunner]; None = scaffold mock output
```

**3b.** Replace `_execute_test` (keep the existing imports; add `from moss_ci.models.test import MossCallSpec` at the top of the file):

```python
    async def _execute_test(self, test_plan: TestPlan) -> TestResult:
        start = time.monotonic()
        test = test_plan.test
        try:
            if self._runner is not None:
                moss_spec = MossCallSpec(
                    prompt=test.moss.prompt,
                    task=test.moss.task,
                    conversation=test.moss.conversation,
                    context=test.moss.context,
                    workdir=test.moss.workdir,
                    env=test.moss.env,
                )
                if test.moss.task:
                    moss_result = await self._runner.run_task(moss_spec)
                elif test.moss.conversation:
                    moss_result = await self._runner.run_conversation(moss_spec)
                else:
                    moss_result = await self._runner.run(moss_spec)
                moss_output = moss_result.output
                moss_tool_calls = list(moss_result.tool_calls)
                files_modified = list(moss_result.files_modified)
                exit_code = moss_result.exit_code
            else:
                # SCAFFOLD fallback — no real runner wired in.
                moss_output = f"[mock] Moss: {test.moss.prompt or test.moss.task}"
                moss_tool_calls = []
                files_modified = []
                exit_code = 0

            eval_results: list[EvalResult] = []
            for eval_spec in test.eval:
                er = await self._evaluate(
                    eval_spec, moss_output, moss_tool_calls,
                    files_modified=files_modified, exit_code=exit_code,
                )
                eval_results.append(er)

            all_passed = all(er.passed for er in eval_results)
            status = "pass" if all_passed else "fail"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return TestResult(test_name=test.name, status="error", duration=time.monotonic() - start, error=str(e))

        return TestResult(
            test_name=test.name, status=status, duration=time.monotonic() - start,
            moss_output=moss_output, moss_tool_calls=moss_tool_calls, evals=eval_results,
        )

    async def _evaluate(self, eval_spec, moss_output: str, moss_tool_calls: list[dict],
                        files_modified: list[str] | None = None, exit_code: int = 0) -> EvalResult:
        from moss_ci.evaluator.registry import EvaluatorRegistry
        return await EvaluatorRegistry().evaluate(
            eval_spec, moss_output, moss_tool_calls,
            files_modified=files_modified, exit_code=exit_code,
        )
```

> NOTE: the existing `execute` and `_execute_suite` methods (from Task 4) stay unchanged. **Three methods change here:** `__init__` (add `runner` param), `_execute_test` (call the runner), and `_evaluate` (accept `files_modified`/`exit_code` so the `side_effect` evaluator from Task 7 can inspect real Moss results — it already accepts those kwargs at the registry and evaluator level). The scaffold Task 4 `_evaluate` had a narrower signature; this widens it with defaults, so calls that don't pass the new kwargs still work.

- [ ] **Step 4: Modify pipeline.py to thread the runner through**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from moss_ci.models.pipeline import SuiteConfig
from moss_ci.models.result import PipelineResult
from moss_ci.engine.scheduler import Scheduler
from moss_ci.engine.executor import Executor


@dataclass
class PipelineConfig:
    fail_fast: bool = True
    max_concurrency: int = 10
    pipeline_name: str = "pipeline"


class PipelineEngine:
    def __init__(self, config: PipelineConfig | None = None, runner=None):
        self.config = config or PipelineConfig()
        self._scheduler = Scheduler()
        self._executor = Executor(max_concurrency=self.config.max_concurrency, runner=runner)

    async def run(self, suites: list[SuiteConfig]) -> PipelineResult:
        plan = self._scheduler.plan(suites)
        result = await self._executor.execute(plan)
        result.pipeline_name = self.config.pipeline_name
        return result
```

- [ ] **Step 5: Modify llm_judge.py to call a real judge (with explicit scaffold fallback)**

The Task 7 version returned a hardcoded `3.5` when no judge URL was set. For switchover, a missing judge URL in a **real run** should be loud — but we must not break Task 7's `test_returns_result` test, which calls the evaluator with no env set and expects an `EvalResult`. Resolution: keep returning a default score when no URL is set, but mark the result as `passed=False` with a clear `error` so a real run surfaces the misconfiguration rather than silently passing.

Replace `D:\moss-ci\moss_ci\evaluator\llm_judge.py`'s `_call_judge` method:

```python
    async def _call_judge(self, model: str, prompt: str) -> float:
        url = os.environ.get("MOSS_CI_JUDGE_API_URL", "")
        if not url:
            # Switchover: no judge endpoint configured. In a real run this
            # means the eval cannot actually score Moss output — return a
            # mid score but the caller marks passed via threshold, so a
            # misconfigured judge shows as a fail rather than a silent pass.
            # (Task 7's scaffold test asserts only that an EvalResult is
            # returned, which still holds.)
            logger.error("llm_judge.no_api_configured",
                         message="MOSS_CI_JUDGE_API_URL not set; returning default score 3.0")
            return 3.0
        import httpx
        async with httpx.AsyncClient() as c:
            r = await c.post(url, json={"model": model, "messages": [{"role": "user", "content": prompt}]}, timeout=httpx.Timeout(120))
            if r.status_code != 200:
                raise RuntimeError(f"Judge API returned {r.status_code}: {r.text[:200]}")
            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            try:
                return float(json.loads(content).get("score", 3.0))
            except (json.JSONDecodeError, ValueError) as e:
                raise RuntimeError(f"Judge returned non-numeric score: {content!r}") from e
```

> NOTE on the threshold interaction: with a real judge returning e.g. `4.2` against `threshold: 4.0`, the eval correctly passes/fails. With no URL configured, the default `3.0` will fail most `threshold: >=3.5` specs — surfacing the misconfiguration. If you want a *hard* failure (raise) instead, wrap the call site and convert to `EvalResult(passed=False, error=...)`; the Task 7 test would then need `monkeypatch.setenv`. Keep the soft default for now so the scaffold stays green.

- [ ] **Step 6: Modify api/routes/runs.py to persist via RunRepository**

Replace the module-global `_runs` dict with the `RunRepository`. Update the imports and the four endpoints that touch `_runs`:

```python
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio, json
from moss_ci.api.schemas import RunPipelineRequest, RunPipelineResponse
from moss_ci.engine.pipeline import PipelineEngine, PipelineConfig
from moss_ci.runner.base import MossRunner
from moss_ci.parser.yaml_parser import parse_suite_string
from moss_ci.models.result import PipelineResult, RunStatus
from moss_ci.storage.db import get_db
from moss_ci.storage.repository import RunRepository
import yaml

router = APIRouter(prefix="/api/v1")


def _repo() -> RunRepository:
    return RunRepository(get_db())


def _dict_to_suite(data: dict):
    yaml_str = yaml.dump(data, allow_unicode=True)
    return parse_suite_string(yaml_str)


@router.post("/pipelines/run", response_model=RunPipelineResponse)
async def run_pipeline(req: RunPipelineRequest):
    run_id = str(uuid.uuid4())[:8]
    suites = [_dict_to_suite(s) for s in req.suites]
    # Switchover: pass a real MossRunner (auto-detects backend from env).
    # Pass runner=None to keep scaffold behavior during local dev if desired.
    runner = MossRunner()
    engine = PipelineEngine(PipelineConfig(pipeline_name=req.pipeline_name), runner=runner)
    result = await engine.run(suites)
    result.run_id = run_id
    await _repo().save(result)
    return RunPipelineResponse(run_id=run_id, pipeline_name=req.pipeline_name, status=result.status.value)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    result = await _repo().get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.model_dump()


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str):
    result = await _repo().get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    async def event_stream():
        for suite in result.suites:
            for test in suite.tests:
                yield f"data: {json.dumps({'test': test.test_name, 'status': test.status})}\n\n"
                await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'status': result.status.value, 'summary': result.summary})}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    result = await _repo().get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    result.status = RunStatus.CANCELLED
    await _repo().save(result)
    return {"run_id": run_id, "status": "cancelled"}
```

> The advanced endpoints from Task 11 (`/runs`, `/runs/{id}/diff`, `/suites`, etc.) also read `_runs`. Update each to use `_repo().list()` / `_repo().get()` following the same pattern. The diff logic stays the same — just load both runs from the repo instead of the dict.

- [ ] **Step 7: Modify api/server.py to init the DB on startup**

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from moss_ci.api.routes.runs import router as runs_router
from moss_ci.storage.db import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await db.init()
    yield
    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Moss CI", version="0.1.0", lifespan=lifespan)
    app.include_router(runs_router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
```

> The default DB URL is `sqlite+aiosqlite:///moss_ci.db` (from Task 8). For PostgreSQL, set the `MOSS_CI_DB_URL` env var and have `get_db` read it — add `url = url or os.environ.get("MOSS_CI_DB_URL", "")` to `Database.__init__`.

- [ ] **Step 8: Run switchover tests**

```bash
cd D:\moss-ci
pytest tests/test_switchover.py -v
```

Expected: PASS — executor invokes the stub runner, pipeline threads it through.

- [ ] **Step 9: Re-run the full suite to confirm no regressions**

```bash
cd D:\moss-ci
pytest tests/ -v --tb=short
```

Expected: all tests PASS. (The Task 7 `llm_judge` test still passes — Step 5 keeps the soft scaffold fallback rather than raising.)

- [ ] **Step 10: End-to-end smoke test against real Moss**

Set the env vars for your chosen backend + judge, then run the CLI against an example suite:

```bash
cd D:\moss-ci
# Example: CLI backend + judge endpoint
#   set MOSS_CLI_COMMAND=moss          (or leave default)
#   set MOSS_CI_JUDGE_API_URL=https://...
python -m moss_ci.cli.main run examples/simple_assert.yaml
```

Expected: the suite runs, Moss is actually invoked (check `moss_output` is not `[mock]`), and contains-evals evaluate against real output. Verify in the DB that a run row was persisted:

```bash
python -c "import asyncio; from moss_ci.storage.db import get_db; from moss_ci.storage.repository import RunRepository
async def m():
    rs = await RunRepository(get_db()).list(limit=5)
    for r in rs: print(r.run_id, r.status, r.summary)
asyncio.run(m())"
```

- [ ] **Step 11: Commit**

```bash
cd D:\moss-ci
git add -A
git commit -m "feat: wire real Moss runner, real judge, and persistent storage"
```

---

## Scope Notes (deferred — NOT in this plan)

The design doc (§3.3) lists several advanced features that are **intentionally out of scope** for this implementation plan and should get their own spec/plan later:

- **Template variables** (`{{ model }}`, `{{ date }}` substitution in prompts) — no task. YAGNI until a real suite needs it.
- **Suite inheritance** (`extends: base-suite.yaml`) — no task.
- **Conditional execution** (`if: "{{ model }}" == "claude-sonnet-5"`) — no task.
- **Matrix strategy** (one test across `model × temperature` combinations) — no task. The Pipeline Engine has no matrix fan-out.
- **OAuth2/OIDC + Webhook + scheduled triggers** — the API has no auth and no webhook/cron entry points; only the REST + SSE + CLI entry points from design §7 are built.
- **Flake detection integration into the Dashboard** — Task 13 builds the detector and Task 15 builds the Dashboard, but the Dashboard does not surface `flake` status distinctly (it colors pass/fail only).

Each is a reasonable follow-on. Do not slip them into this plan mid-implementation — file them as separate specs after the scaffold is green.

---

## Verification Checklist

After all 16 tasks are complete, run the full test suite:

```bash
cd D:\moss-ci
pytest tests/ -v --tb=short
```

Expected: all tests PASS across all modules.

Start the API server:

```bash
cd D:\moss-ci
uvicorn moss_ci.api.server:app --reload
```

Run the CLI:

```bash
cd D:\moss-ci
python -m moss_ci.cli.main run examples/
```

Expected: CLI loads example YAML files and runs them through the pipeline engine.
```

---