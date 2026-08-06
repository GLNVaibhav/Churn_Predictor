from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd
from ..domain.identifiers import DatasetFingerprint, OntologyId
from ..domain.models import DatasetProfile, ProfilingResult, ProfileProvenance, SamplingPolicy
from .sampling import deterministic_sample
from .column_profiler import ColumnProfiler


class DatasetProfiler:
    def __init__(self, column_profiler: ColumnProfiler | None = None) -> None:
        self._columns = column_profiler or ColumnProfiler()

    def profile(self, df: pd.DataFrame, policy: SamplingPolicy = SamplingPolicy(), metadata: dict | None = None) -> ProfilingResult:
        sample = deterministic_sample(df, policy)
        columns = tuple(self._columns.profile(str(name), pos, sample[name]) for pos, name in enumerate(sample.columns))
        fingerprint = DatasetFingerprint.build([str(c) for c in df.columns], len(df), metadata)
        sectors = self._sector_hypotheses(columns)
        grain = "entity_snapshot" if any(p.identifier_likelihood >= .8 for p in columns) else "event_or_unknown"
        provenance = ProfileProvenance("full" if len(sample) == len(df) else "sampled", len(sample), len(df), datetime.now(timezone.utc).isoformat())
        return ProfilingResult(DatasetProfile(fingerprint, len(df), len(df.columns), grain, sectors, provenance), columns)

    @staticmethod
    def _sector_hypotheses(columns):
        tokens = " ".join(p.raw_column.lower() for p in columns)
        definitions = {"telecom": ("call", "internet", "data", "contract"), "banking": ("balance", "credit", "account", "salary"), "healthcare": ("patient", "visit", "provider", "insurance"), "ecommerce": ("order", "coupon", "cashback", "warehouse")}
        scored = []
        for sector, markers in definitions.items():
            score = sum(marker in tokens for marker in markers) / len(markers)
            if score: scored.append((OntologyId(f"ucif.sector.{sector}"), score))
        return tuple(sorted(scored, key=lambda x: (-x[1], str(x[0]))))
