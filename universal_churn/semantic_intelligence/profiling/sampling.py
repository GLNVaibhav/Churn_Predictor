from __future__ import annotations
import pandas as pd
from ..domain.models import SamplingPolicy


def deterministic_sample(df: pd.DataFrame, policy: SamplingPolicy) -> pd.DataFrame:
    """Return a reproducible bounded sample without changing column order."""
    if len(df) <= policy.max_rows: return df.copy()
    return df.sample(n=policy.max_rows, random_state=policy.seed).sort_index()
