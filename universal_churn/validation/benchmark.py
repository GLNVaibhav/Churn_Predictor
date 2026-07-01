"""
universal_churn/validation/benchmark.py
══════════════════════════════════════════════════════════════════════
Benchmarking module — Part 3 of the Version 6 / Chunk 4 validation
milestone. Measures, but never optimizes, pipeline latency.

Stages measured (per sector):
    schema_resolution   compute_norm_stats/derived-feature detection
    canonical_mapping    schema_resolution.resolve_schema()
    business_concepts    business_concepts.compute_concept_values()
    feature_engineering  feature_engineering.extract_universal_features()
    normalization        (folded into feature_engineering — reported
                          separately by timing transform_features_by_sector,
                          which includes normalization against persisted
                          norm_stats)
    model_inference       predict_universal() end-to-end
    total_pipeline_latency  sum of the above, measured independently
                          (not just summed) via a single full run
"""
from __future__ import annotations

import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..config import SECTOR_CONFIG
from ..schema_resolution import resolve_schema
from ..business_concepts import compute_concept_values
from ..feature_engineering import extract_universal_features, transform_features_by_sector
from ..preprocessing import sanitize_numerical_columns, derive_temporal_features


@dataclass
class StageTiming:
    stage: str
    samples_ms: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def median(self) -> float:
        return statistics.median(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def minimum(self) -> float:
        return min(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def maximum(self) -> float:
        return max(self.samples_ms) if self.samples_ms else float("nan")

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples_ms) if len(self.samples_ms) > 1 else 0.0

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "mean_ms": round(self.mean, 3),
            "median_ms": round(self.median, 3),
            "min_ms": round(self.minimum, 3),
            "max_ms": round(self.maximum, 3),
            "stdev_ms": round(self.stdev, 3),
            "iterations": len(self.samples_ms),
        }


@dataclass
class BenchmarkResult:
    sector: str
    stage_timings: list[StageTiming] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"sector": self.sector,
                "stages": [t.to_dict() for t in self.stage_timings]}


def _timed(fn, *args, **kwargs) -> tuple[float, object]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, result


def run_benchmarks(
    sectors: list[str] | None = None,
    iterations: int = 5,
    sample_rows: int = 50,
) -> dict[str, BenchmarkResult]:
    """
    Run `iterations` timed passes of every pipeline stage, for every
    sector. Measurement only — no attempt is made to optimize anything.
    """
    sectors = sectors or list(SECTOR_CONFIG.keys())
    all_results: dict[str, BenchmarkResult] = {}

    for sector in sectors:
        config = SECTOR_CONFIG[sector]
        data_path = config["data_path"]
        if not Path(data_path).exists():
            all_results[sector] = BenchmarkResult(sector=sector, stage_timings=[])
            continue

        df_base = pd.read_csv(data_path).head(sample_rows)

        timings = {
            "schema_resolution": StageTiming(stage="schema_resolution"),
            "business_concept_computation": StageTiming(stage="business_concept_computation"),
            "feature_engineering": StageTiming(stage="feature_engineering"),
            "normalization_and_model_input": StageTiming(stage="normalization_and_model_input"),
            "model_inference": StageTiming(stage="model_inference"),
            "total_pipeline_latency": StageTiming(stage="total_pipeline_latency"),
        }

        for _ in range(iterations):
            total_start = time.perf_counter()

            df_raw = sanitize_numerical_columns(df_base.copy())
            df_raw = derive_temporal_features(df_raw)

            elapsed, canonical_df = _timed(resolve_schema, df_raw)
            timings["schema_resolution"].samples_ms.append(elapsed)
            canonical_df = canonical_df[0]
            # See regression.py for why de-duplication is needed here.
            deduped_canonical = canonical_df.loc[:, ~canonical_df.columns.duplicated(keep="first")]

            elapsed, _ = _timed(compute_concept_values, deduped_canonical, sector)
            timings["business_concept_computation"].samples_ms.append(elapsed)

            elapsed, _ = _timed(
                extract_universal_features, df_raw.copy(), sector,
                config["target_col"], None)
            timings["feature_engineering"].samples_ms.append(elapsed)

            elapsed, _ = _timed(transform_features_by_sector, df_raw.copy(), sector)
            timings["normalization_and_model_input"].samples_ms.append(elapsed)

            try:
                from ..universal_pipeline import predict_universal
                with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tmp:
                    df_base.to_csv(tmp.name, index=False)
                    tmp_path = tmp.name
                elapsed, _ = _timed(
                    predict_universal, tmp_path, sector, False, None, "Benchmark")
                timings["model_inference"].samples_ms.append(elapsed)
                Path(tmp_path).unlink(missing_ok=True)
            except FileNotFoundError:
                pass  # model not trained yet — skip inference timing this iteration
            except Exception:
                pass  # benchmarking must never raise; a failed timing is just omitted

            total_elapsed = (time.perf_counter() - total_start) * 1000.0
            timings["total_pipeline_latency"].samples_ms.append(total_elapsed)

        all_results[sector] = BenchmarkResult(
            sector=sector, stage_timings=list(timings.values()))

    return all_results


def print_benchmark_report(results: dict[str, BenchmarkResult]) -> None:
    sep = "─" * 78
    print(f"\n{sep}\n  BENCHMARK REPORT (measurement only — no optimization performed)\n{sep}")
    header = f"  {'Stage':<32}{'Mean(ms)':>10}{'Median(ms)':>12}{'Min(ms)':>10}{'Max(ms)':>10}{'Std(ms)':>10}"
    for sector, result in results.items():
        print(f"\n  [{sector.upper()}]")
        if not result.stage_timings:
            print("      (data file not found — skipped)")
            continue
        print(header)
        for t in result.stage_timings:
            print(f"  {t.stage:<32}{t.mean:>10.2f}{t.median:>12.2f}"
                  f"{t.minimum:>10.2f}{t.maximum:>10.2f}{t.stdev:>10.2f}")
    print(f"\n{sep}")
