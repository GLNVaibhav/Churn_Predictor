from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.preprocessing import detect_sector


class UploadService:
    """Service that processes an uploaded CSV file.

    Profiles the dataset and runs a minimal framework pass to detect
    sector and coverage.  Reads framework-provided values verbatim —
    no backend business computation.
    """

    def __init__(self) -> None:
        pass

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
    def _extract_coverage_score(coverage) -> Optional[float]:
        summary = getattr(coverage, "summary", None)
        if summary is None:
            return None
        return float(getattr(summary, "overall_coverage", 0.0) or 0.0)

    @staticmethod
    def _extract_concept_confidence(coverage) -> Optional[float]:
        summary = getattr(coverage, "summary", None)
        if summary is None:
            return None
        return float(getattr(summary, "confidence_coverage", 0.0) or 0.0)

    def process_upload(self, file_path: Path, original_name: str) -> dict:
        df = pd.read_csv(file_path)
        profiling = self._profile(df)

        try:
            sector = detect_sector(df)
            intelligence = infer_intelligence(df)
            coverage_score = self._extract_coverage_score(intelligence.coverage)
            concept_confidence = self._extract_concept_confidence(intelligence.coverage)
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
