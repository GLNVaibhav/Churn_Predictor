from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from ..application.semantic_understanding_engine import SemanticUnderstandingEngine
from ..domain.enums import ExecutionMode

@dataclass(frozen=True)
class BenchmarkResult: name: str; accepted_coverage: float; semantic_accepts: int
class BenchmarkSuite:
    def run(self, datasets: dict[str, pd.DataFrame]) -> tuple[BenchmarkResult, ...]:
        engine = SemanticUnderstandingEngine(); results = []
        for name, dataset in datasets.items():
            schema = engine.understand(dataset, ExecutionMode.DIAGNOSTIC)
            accepts = sum(r.status.value == "SEMANTIC_ACCEPTED" for r in schema.resolutions)
            results.append(BenchmarkResult(name, accepts / (len(schema.resolutions) or 1), accepts))
        return tuple(results)
