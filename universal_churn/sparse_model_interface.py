"""
universal_churn/sparse_model_interface.py
══════════════════════════════════════════════════════════════════════
Sparse Model Interface — Version 6, Chunk 5, Part 5.

INTERFACE ONLY. routing.py's ModelType enum is NOT modified by this
file — routing.py, sector_pipeline.py, and universal_pipeline.py are
untouched by this milestone. This documents both the model contract
and the routing integration a future implementation will need.

Sparse Models target inputs worse than today's
CRITICAL_UNRELIABLE case (Red coverage + unreconstructable concepts —
see routing._red_coverage_decision()): trading per-sector accuracy for
saying *something*, at explicitly low reliability, from as few as 1-2
resolved canonical fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SparseModelInput:
    available_canonical_fields: dict[str, pd.Series]  # whatever resolved, however little
    sector: str
    coverage_score: float


@dataclass
class SparseModelOutput:
    churn_probability: pd.Series
    confidence: float
    fields_used: list[str] = field(default_factory=list)


class SparseModelInterface(ABC):
    """
    Routing integration (documentation only — not implemented here):
        1. Add `SPARSE_MODEL = "SPARSE_MODEL"` to routing.ModelType.
        2. Add a branch in routing._red_coverage_decision() (or a new
           helper) that tries SPARSE_MODEL when concepts_reconstructable
           is False but >= min_required_fields resolved, BEFORE falling
           through to CRITICAL_UNRELIABLE.
        3. Add one dispatch branch in sector_pipeline.py /
           universal_pipeline.py, mirroring the existing CORE_MODEL
           NotImplementedError branch.
        4. Add a ReliabilityLevel floor (VERY_LOW or a new LOW-adjacent
           band) so a Sparse Model prediction is never confused with a
           normal sector/universal one in reports.
    """

    @property
    @abstractmethod
    def min_required_fields(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def predict(self, model_input: SparseModelInput) -> SparseModelOutput:
        raise NotImplementedError

    @abstractmethod
    def fallback_behavior(self) -> str:
        raise NotImplementedError