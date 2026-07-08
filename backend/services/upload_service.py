from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from backend.adapters.framework_adapter import FrameworkAdapter
from backend.models.execution_result import ExecutionResult


class UploadService:
    """Service that processes an uploaded CSV file.

    Profiles the dataset and runs a minimal framework pass to detect
    sector and coverage.  Reads framework-provided values verbatim —
    no backend business computation.
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

    @staticmethod
    def _extract_coverage_score(result: ExecutionResult) -> Optional[float]:
        if not result.coverage:
            return None
        return result.coverage.get("coverage_score")

    @staticmethod
    def _extract_concept_confidence(result: ExecutionResult) -> Optional[float]:
        if not result.coverage:
            return None
        concept = result.coverage.get("concept_confidence") or {}
        if concept.get("error"):
            return None
        return concept.get("overall_confidence")

    def process_upload(self, file_path: Path, original_name: str) -> dict:
        df = pd.read_csv(file_path)
        profiling = self._profile(df)

        try:
            exec_result = self.adapter.execute(str(file_path), mode="auto", explain=False)
            sector = exec_result.sector
            coverage_score = self._extract_coverage_score(exec_result)
            concept_confidence = self._extract_concept_confidence(exec_result)
        except Exception:
            sector = None
            coverage_score = None
            concept_confidence = None

        created_at = datetime.utcnow().isoformat() + "Z"
        warnings: List[str] = []

        return {
            "filename": original_name,
            **profiling,
            "sector": sector,
            "coverage_score": coverage_score,
            "concept_confidence": concept_confidence,
            "warnings": warnings,
            "created_at": created_at,
        }
