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
