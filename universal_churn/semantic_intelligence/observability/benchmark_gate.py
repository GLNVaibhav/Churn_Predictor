from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class BenchmarkGateResult: passed: bool; regressions: tuple[str, ...] = (); rationale: str = ""
class BenchmarkGate:
    def evaluate(self, deterministic_regressions: int, semantic_precision: float, baseline_precision: float) -> BenchmarkGateResult:
        issues = []
        if deterministic_regressions: issues.append("deterministic regression")
        if semantic_precision < baseline_precision: issues.append("semantic precision regression")
        return BenchmarkGateResult(not issues, tuple(issues), "Passed non-regression gate." if not issues else "Benchmark gate blocked promotion.")
