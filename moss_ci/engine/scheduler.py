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
