"""
universal_churn/core_model_interface.py
══════════════════════════════════════════════════════════════════════
Core Model Interface — Version 6, Chunk 5, Part 4.

INTERFACE ONLY. No Core Model is implemented in Version 6. This gives
routing.py's existing ModelType.CORE_MODEL hook (already present,
already reachable in principle — see routing.py's auto-mode Yellow
branch comment and sector_pipeline.py's CORE_MODEL dispatch, which
today raises NotImplementedError) a concrete contract to implement
against in Version 7, with zero routing.py API changes required then.

Nothing in this file is imported by cli.py, sector_pipeline.py,
universal_pipeline.py, or routing.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class CoreModelInput:
    """
    Deliberately concept-level, not raw-column-level — a Core Model
    consumes the Business Concept Layer (business_concepts.py /
    concept_confidence.py) rather than sector-specific engineered
    features, which is the whole point of a sector-agnostic model.
    """
    concept_values: pd.DataFrame          # one column per BUSINESS_CONCEPTS name
    concept_confidence: dict[str, float]  # concept_name -> confidence, 0..1
    sector: str
    row_ids: pd.Series | None = None


@dataclass
class CoreModelOutput:
    churn_probability: pd.Series          # aligned to input index
    confidence: float                     # scalar model-level confidence
    concepts_used: list[str] = field(default_factory=list)
    fallback_triggered: bool = False
    fallback_reason: str | None = None


class CoreModelInterface(ABC):
    """
    Contract a future CoreModelPipeline must satisfy. Implementing this
    and wiring one dispatch branch into sector_pipeline.py /
    universal_pipeline.py is the ONLY work Version 7 needs to enable it.
    """

    @property
    @abstractmethod
    def required_concepts(self) -> list[str]:
        """
        Business concept names (business_concepts.CONCEPT_NAMES) needed
        at nonzero confidence. Checked by the caller BEFORE predict()
        to decide whether to attempt this model at all.
        """
        raise NotImplementedError

    @abstractmethod
    def predict(self, model_input: CoreModelInput) -> CoreModelOutput:
        """
        Concept-level input only — no sector-specific engineered
        features, no raw columns. Implementations MUST set
        fallback_triggered=True (with a reason) rather than raising
        whenever required-concept confidence is too low to trust — the
        caller is expected to route to UNIVERSAL_MODEL in that case,
        mirroring the CRITICAL_UNRELIABLE / Red-coverage fallback
        pattern already used in routing.py.
        """
        raise NotImplementedError

    @abstractmethod
    def fallback_behavior(self) -> str:
        """Human-readable description of what happens when this model can't
        produce a confident prediction, surfaced in diagnostics the same
        way routing.RoutingDecision already explains fallback/rejection."""
        raise NotImplementedError