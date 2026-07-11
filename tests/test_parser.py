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
