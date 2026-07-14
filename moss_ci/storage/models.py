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
    # Serialized list[TestResult] from flake detection runs. Stored as JSON
    # (each run's status/output/evals) rather than as nested rows, because flake
    # runs are read-only detail — `status`/`logs` show them but nothing queries
    # them relationally. Without this column the per-run verdicts were lost on
    # save, so `status` showed "flake" with no breakdown of which runs passed.
    flake_runs = Column(JSON, nullable=True)
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
