from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from backend.adapters.framework_adapter import FrameworkAdapter
from universal_churn.config import SECTOR_CONFIG
from universal_churn.intelligence_pipeline import infer_intelligence
from universal_churn.preprocessing import detect_sector, sector_signature_scores


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
        # CSV readers leave whitespace-only cells as strings. Treat those as
        # missing for the profile without mutating the frame used by sector or
        # semantic inference below.
        profile_df = df.replace(to_replace=r"^\s*$", value=pd.NA, regex=True)
        null_counts = profile_df.isnull().sum().to_dict()
        dtypes = {c: str(dt) for c, dt in df.dtypes.items()}
        preview_rows = df.head().to_dict(orient="records")
        column_profiles = []
        for column in df.columns:
            series = profile_df[column]
            if is_bool_dtype(series.dtype):
                inferred_type = "boolean"
            elif is_numeric_dtype(series.dtype):
                inferred_type = "numeric"
            elif is_datetime64_any_dtype(series.dtype):
                inferred_type = "datetime"
            else:
                non_missing = series.dropna()
                numeric_values = pd.to_numeric(non_missing, errors="coerce")
                inferred_type = (
                    "numeric"
                    if not non_missing.empty and numeric_values.notna().all()
                    else "categorical"
                )
            samples = [str(value) for value in series.dropna().drop_duplicates().head(5).tolist()]
            column_profiles.append({
                "name": str(column),
                "inferredType": inferred_type,
                "nullPercentage": round(float(series.isna().mean() * 100), 2),
                "sampleValues": samples,
            })
        return {
            "rows": rows,
            "columns": columns,
            "null_counts": null_counts,
            "dtypes": dtypes,
            "preview_rows": preview_rows,
            "column_profiles": column_profiles,
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
        warnings: List[str] = []
        signature_scores = sector_signature_scores(df)

        try:
            sector = detect_sector(df)
            sector_detection = {
                "status": "DETECTED",
                "sector": sector,
                "signature_hits": signature_scores[sector],
                "candidate_scores": signature_scores,
            }
        except ValueError as exc:
            sector = None
            sector_detection = {
                "status": "UNCERTAIN",
                "sector": None,
                "signature_hits": 0,
                "candidate_scores": signature_scores,
            }
            warnings.append(str(exc))

        try:
            intelligence = infer_intelligence(df)
            coverage_score = self._extract_coverage_score(intelligence.coverage)
            concept_confidence = self._extract_concept_confidence(intelligence.coverage)
            coverage_contract = FrameworkAdapter._coverage_contract(intelligence.coverage) or {}
            missing_critical = coverage_contract.get("missing_critical", [])
        except Exception:
            coverage_score = None
            concept_confidence = None
            missing_critical = []
            warnings.append("Feature coverage could not be assessed from the uploaded schema.")

        target_column = None
        target_name = SECTOR_CONFIG.get(sector, {}).get("target_col") if sector else None
        if target_name:
            target_column = next(
                (str(column) for column in df.columns if str(column).casefold() == target_name.casefold()),
                None,
            )

        created_at = datetime.utcnow().isoformat() + "Z"
        return {
            "filename": original_name,
            **profiling,
            "sector": sector,
            "sector_detection": sector_detection,
            "coverage_score": coverage_score,
            "concept_confidence": concept_confidence,
            "target_column": target_column,
            "missing_critical": missing_critical,
            "warnings": warnings,
            "created_at": created_at,
        }
