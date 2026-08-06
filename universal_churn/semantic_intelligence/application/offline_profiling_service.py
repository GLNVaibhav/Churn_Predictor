from __future__ import annotations
import pandas as pd
from ..domain.models import ProfilingResult, SamplingPolicy
from ..profiling.dataset_profiler import DatasetProfiler
from ..profiling.profile_cache import ProfileCache


class OfflineProfilingService:
    def __init__(self, profiler: DatasetProfiler | None = None, cache: ProfileCache | None = None) -> None:
        self._profiler, self._cache = profiler or DatasetProfiler(), cache or ProfileCache()
    def profile_dataset(self, dataset: pd.DataFrame, source_metadata: dict | None = None, sampling_policy: SamplingPolicy = SamplingPolicy(), profile_options: dict | None = None) -> ProfilingResult:
        provisional = self._profiler.profile(dataset, sampling_policy, source_metadata)
        key = str((profile_options or {}).get("version", "8.0.0"))
        cached = self._cache.get(provisional.dataset.fingerprint.value, key)
        if cached is not None: return cached
        self._cache.put(provisional, key)
        return provisional
