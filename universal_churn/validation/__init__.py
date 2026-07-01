"""
universal_churn.validation
===========================
Validation, regression-detection, benchmarking, and diagnostics
utilities for the schema-adaptive churn pipeline.

Nothing in this subpackage is imported by, or influences, the
prediction path (cli.py, sector_pipeline.py, universal_pipeline.py,
routing.py). It is purely observational tooling used by
validate_framework.py and the test suite.
"""
from __future__ import annotations

from .regression import (
    PipelineStageResult,
    RegressionResult,
    run_regression_for_sector,
    run_full_regression,
)
from .benchmark import BenchmarkResult, run_benchmarks
from .diagnostics import StageDiagnostics, DiagnosticsCollector

__all__ = [
    "PipelineStageResult",
    "RegressionResult",
    "run_regression_for_sector",
    "run_full_regression",
    "BenchmarkResult",
    "run_benchmarks",
    "StageDiagnostics",
    "DiagnosticsCollector",
]
