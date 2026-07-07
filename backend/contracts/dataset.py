"""
backend.contracts.dataset
══════════════════════════════════════════════════════════════════════
``DatasetInfo`` — a description of the input dataset an analysis run
was performed against.

Every field here is either supplied by the caller (filename) or read
straight off values the framework already produced (sector,
prediction_mode, rows/columns, schema_version) — nothing is
recomputed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utils import to_serializable


@dataclass
class DatasetInfo:
    """
    Attributes
    ----------
    filename : str | None
        Name of the uploaded/processed input file, if known.
    sector : str | None
        Sector detected or explicitly requested for this run
        (``preprocessing.detect_sector`` / ``--sector``).
    prediction_mode : str | None
        The requested prediction mode: ``'sector'`` | ``'universal'``
        | ``'auto'`` (mirrors ``routing.PredictionMode``).
    rows : int | None
        Row count of the input dataset.
    columns : int | None
        Column count of the input dataset.
    schema_version : str | None
        Version tag for whatever canonical schema the input resolved
        against (e.g. ``feature_engineering.SCHEMA_PIPELINE_VERSION``).
    """
    filename: Optional[str] = None
    sector: Optional[str] = None
    prediction_mode: Optional[str] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    schema_version: Optional[str] = None

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetInfo":
        return cls(
            filename=d.get("filename"),
            sector=d.get("sector"),
            prediction_mode=d.get("prediction_mode"),
            rows=d.get("rows"),
            columns=d.get("columns"),
            schema_version=d.get("schema_version"),
        )
