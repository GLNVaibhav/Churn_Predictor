from __future__ import annotations
import pandas as pd
from .run_manifest import SemanticRunManifest
from ..application.online_resolution_service import OnlineResolutionService

class ReplayService:
    def replay(self, dataset: pd.DataFrame, manifest: SemanticRunManifest, deterministic_resolutions: dict | None = None):
        result = OnlineResolutionService().resolve_schema(dataset, deterministic_resolutions)
        if result.fingerprint != manifest.fingerprint: raise ValueError("Dataset fingerprint does not match replay manifest.")
        return result
