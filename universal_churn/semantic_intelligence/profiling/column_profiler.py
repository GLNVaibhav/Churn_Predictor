from __future__ import annotations
import re
import pandas as pd
from ..domain.models import CardinalityProfile, ColumnProfile, DatatypeProfile, DistributionProfile

_UNIT_WORDS = {"usd", "inr", "eur", "gbp", "rs", "percent", "pct", "gb", "mb", "kb", "km", "mile", "miles", "day", "days", "month", "months", "year", "years", "minute", "minutes"}
_TEMPORAL_WORDS = {"date", "time", "timestamp", "day", "days", "month", "months", "year", "years", "tenure", "since", "recency", "age"}


class ColumnProfiler:
    def profile(self, raw_column: str, position: int, series: pd.Series) -> ColumnProfile:
        logical = self._logical_type(series)
        count = len(series)
        distinct = int(series.nunique(dropna=True))
        cardinality = CardinalityProfile(distinct, distinct / count if count else 0.0)
        numeric = pd.to_numeric(series, errors="coerce") if logical in {"numeric", "boolean"} else pd.Series(dtype=float)
        if not numeric.empty and numeric.notna().any():
            values = numeric.dropna()
            distribution = DistributionProfile(float(values.min()), float(values.max()), float(values.mean()), float(values.median()), float(values.std(ddof=0)), float((values % 1 == 0).mean()), float((values == 0).mean()))
        else:
            distribution = DistributionProfile()
        tokens = tuple(token.lower() for token in re.findall(r"[A-Za-z]+|%", re.sub(r"([a-z])([A-Z])", r"\1 \2", raw_column)))
        values = tuple(str(v)[:120] for v in series.dropna().astype(str).head(5))
        uniqueness = cardinality.uniqueness_ratio
        id_likelihood = min(1.0, 0.65 * uniqueness + (0.35 if raw_column.lower().endswith(("id", "_id")) else 0.0))
        return ColumnProfile(raw_column, position, DatatypeProfile(str(series.dtype), logical, 1.0), cardinality, float(series.isna().mean()) if count else 0.0, distribution, tuple(t for t in tokens if t in _UNIT_WORDS), tuple(t for t in tokens if t in _TEMPORAL_WORDS), id_likelihood, values)

    @staticmethod
    def _logical_type(series: pd.Series) -> str:
        if pd.api.types.is_bool_dtype(series): return "boolean"
        if pd.api.types.is_datetime64_any_dtype(series): return "datetime"
        if pd.api.types.is_numeric_dtype(series): return "numeric"
        non_null = series.dropna()
        if non_null.empty: return "unknown"
        return "text" if non_null.nunique() > len(non_null) * .5 else "categorical"
