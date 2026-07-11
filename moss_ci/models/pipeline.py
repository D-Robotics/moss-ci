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
