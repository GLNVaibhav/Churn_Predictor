from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from backend.adapters.framework_adapter import FrameworkAdapter

class UploadService:
    """Service that processes an uploaded CSV file.

    It profiles the dataset and runs minimal UCIF logic to detect sector,
    compute coverage, and extract a concept‑confidence placeholder.
    """

    def __init__(self, adapter: Optional[FrameworkAdapter] = None) -> None:
        self.adapter = adapter or FrameworkAdapter()

    def _profile(self, df: pd.DataFrame) -> dict:
        rows, columns = df.shape
        null_counts = df.isnull().sum().to_dict()
        dtypes = {c: str(dt) for c, dt in df.dtypes.items()}
        preview_rows = df.head().to_dict(orient="records")
        return {
            "rows": rows,
            "columns": columns,
            "null_counts": null_counts,
            "dtypes": dtypes,
            "preview_rows": preview_rows,
        }

    def process_upload(self, file_path: Path, original_name: str) -> dict:
        # Load CSV once
        df = pd.read_csv(file_path)
        profiling = self._profile(df)

        # Run minimal auto execution to obtain sector, coverage and quality
        try:
            exec_result = self.adapter.execute(str(file_path), mode="auto", explain=False)
            sector = exec_result.sector
            coverage_score = exec_result.coverage.get("score") if exec_result.coverage else None
            concept_confidence = (
                exec_result.quality.get("confidence") if exec_result.quality else None
            )
        except Exception:
            # If the framework fails, fall back to None values – upload still succeeds
            sector = None
            coverage_score = None
            concept_confidence = None

        created_at = datetime.utcnow().isoformat() + "Z"
        warnings: List[str] = []  # placeholder for future validation warnings

        return {
            "filename": original_name,
            **profiling,
            "sector": sector,
            "coverage_score": coverage_score,
            "concept_confidence": concept_confidence,
            "warnings": warnings,
            "created_at": created_at,
        }
