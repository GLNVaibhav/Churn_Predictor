"""
universal_churn
Schema-agnostic, multi-sector customer churn prediction framework.
"""
from __future__ import annotations

# FIX: removed trailing spaces from every item in __all__
from .sector_pipeline import SectorPipeline
from .universal_pipeline import train_universal_model, predict_universal
from .cli import main
from .config import (
    SECTOR_CONFIG, SECTOR_FEATURE_WEIGHTS, GLOBAL_CONCEPT_MAP,
    SECTOR_THRESHOLDS, PIPELINE_VERSION,
)
from .preprocessing import detect_sector, apply_sector_threshold
from .coverage import compute_coverage_score

version = "1.0.0"
author = "Churn Analysis Research Team"

__all__ = [
    "SectorPipeline",
    "predict_universal",
    "train_universal_model",
    "main",
    "SECTOR_CONFIG",
    "SECTOR_FEATURE_WEIGHTS",
    "GLOBAL_CONCEPT_MAP",
    "SECTOR_THRESHOLDS",
    "PIPELINE_VERSION",
    "detect_sector",
    "apply_sector_threshold",
    "compute_coverage_score",
    "version",
    "author",
]