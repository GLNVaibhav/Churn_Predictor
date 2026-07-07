"""
backend.services.pipeline_service
══════════════════════════════════════════════════════════════════════
``PipelineService`` — read-only pipeline/model status, sourced entirely
from ``universal_churn.model_registry.ModelRegistry`` (itself already
metadata-only — see that module's docstring: "does not load, save,
replace, or modify any model artifact").

This service performs no coverage/routing/prediction computation of
any kind. It exists so a future consumer can ask "what models exist
and are they trained" (e.g. to decide whether ``AnalysisService.
execute(mode='sector')`` will even be able to load a model) without
reaching into ``universal_churn`` directly.
"""
from __future__ import annotations

from typing import List, Optional

from universal_churn.model_registry import ModelRegistry, ModelRegistryEntry

from ..contracts.pipeline import PipelineStageInfo, PipelineSummary
from ..exceptions import ServiceInitializationError


class PipelineService:
    """Stateless aside from an internal ``ModelRegistry`` instance,
    itself already stateless/on-demand (re-stats the filesystem on
    every call — see ``model_registry.ModelRegistry``'s docstring)."""

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self._registry = registry or ModelRegistry()
        self._initialized = False

    def initialize(self) -> "PipelineService":
        self._initialized = True
        return self

    def shutdown(self) -> None:
        self._initialized = False

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise ServiceInitializationError(
                "PipelineService method called before initialize()."
            )

    # ── model registry status ───────────────────────────────────

    def list_models(self) -> List[ModelRegistryEntry]:
        """Every known model artifact's descriptor — sector models plus
        the universal cross-sector model — exactly as
        ``ModelRegistry.entries()`` already produces them."""
        self._require_initialized()
        return self._registry.entries()

    def models_for_sector(self, sector: str) -> List[ModelRegistryEntry]:
        self._require_initialized()
        return self._registry.for_sector(sector)

    def sector_ready(self, sector: str) -> bool:
        """True iff every model artifact this sector depends on
        (its own sector model) exists on disk. Purely a filesystem
        check delegated to the registry entry's own ``exists`` flag —
        no attempt is made to load or validate the artifact itself."""
        self._require_initialized()
        entries = self._registry.for_sector(sector)
        return bool(entries) and all(e.exists for e in entries)

    # ── pipeline stage summary (diagnostics-shaped, for the contract) ──

    def summary(self) -> PipelineSummary:
        """
        A coarse ``PipelineSummary`` built purely by translating each
        registry entry's ``exists`` flag into an OK/WARNING stage —
        this is model-artifact readiness, not a live prediction run's
        per-stage diagnostics (see ``universal_churn.validation.
        diagnostics.StageDiagnostics`` for that finer-grained shape,
        which is per-run and not something this always-on service
        computes proactively).
        """
        self._require_initialized()
        stages = [
            PipelineStageInfo(
                name=entry.model_name,
                status="OK" if entry.exists else "WARNING",
                description=(
                    f"trained={entry.training_date}" if entry.exists
                    else "model artifact not found on disk"
                ),
            )
            for entry in self._registry.entries()
        ]
        return PipelineSummary.from_stages(stages)