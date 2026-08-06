from __future__ import annotations
import pandas as pd
from ..domain.enums import ExecutionMode
from .offline_profiling_service import OfflineProfilingService
from .online_resolution_service import OnlineResolutionService

class SemanticUnderstandingEngine:
    def __init__(self, offline: OfflineProfilingService | None = None, online: OnlineResolutionService | None = None) -> None: self._offline, self._online = offline or OfflineProfilingService(), online or OnlineResolutionService()
    def understand(self, dataset: pd.DataFrame, execution_mode: ExecutionMode = ExecutionMode.STRICT_PRODUCTION, source_metadata: dict | None = None, semantic_options: dict | None = None, deterministic_resolutions: dict | None = None):
        profile = self._offline.profile_dataset(dataset, source_metadata, profile_options=semantic_options)
        if execution_mode == ExecutionMode.OFFLINE_PROFILE_ONLY: return profile
        return self._online.resolve_schema(dataset, deterministic_resolutions, profile)
