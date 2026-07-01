"""
universal_churn/pipeline_stages.py
══════════════════════════════════════════════════════════════════════
Pipeline Plugin Architecture — Version 6, Chunk 5, Part 1.

This module introduces a lightweight `PipelineStage` abstraction so
future stages (semantic matching, a Core Model, etc.) can be added
WITHOUT modifying `feature_engineering.py`, `routing.py`,
`coverage.py`, `quality_gate.py`, or `schema_resolution.py`.

It does not change current behaviour: every concrete stage below is a
thin wrapper around an existing, unmodified function. Nothing in
`cli.py`, `sector_pipeline.py`, or `universal_pipeline.py` calls this
module — it exists as an *optional* composition layer (used today by
`universal_churn/validation/*`) and as the seam Version 7 will extend.

Stage chain (current, all implemented, all wrapping existing code):

    SchemaStage         -> preprocessing.sanitize_numerical_columns +
                            preprocessing.derive_temporal_features
    CanonicalStage       -> schema_resolution.resolve_schema
    ConceptStage         -> business_concepts.compute_concept_values
    FeatureStage         -> feature_engineering.extract_universal_features
    NormalizationStage   -> feature_engineering.transform_features_by_sector
                            (normalization is folded into this call today —
                            see module docstring in feature_engineering.py)
    ModelInputStage       -> identity pass-through of NormalizationStage's
                            output (kept as its own stage so a future
                            model-input-specific transform has a seam
                            without touching NormalizationStage)

Future stage chain (interfaces only, NOT implemented — Part 3/4/5):

    FutureSemanticStage    -> see schema_resolution.py's
                              resolve_semantic_alias() hook
    FutureCoreModelStage    -> see core_model_interface.py

Adding a Version-7 stage means subclassing `PipelineStage` and adding
it to a `PipelineRunner`'s stage list — it never requires editing an
existing stage or an existing production module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .preprocessing import sanitize_numerical_columns, derive_temporal_features
from .schema_resolution import resolve_schema
from .business_concepts import compute_concept_values
from .feature_engineering import extract_universal_features, transform_features_by_sector
from .config import SECTOR_CONFIG


@dataclass
class StageContext:
    """
    Threaded through a `PipelineRunner`. Each stage reads what it
    needs and writes its own output under `outputs[stage.name]`;
    stages never mutate each other's outputs.
    """
    sector: str
    df_raw: pd.DataFrame
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineStage(ABC):
    """
    Minimal extension point. A stage:
      - has a stable `name` used as its key in StageContext.outputs
      - declares which prior stage outputs it depends on (`requires`)
      - implements `run(context) -> Any`

    Stages are pure with respect to StageContext: they read
    `context.outputs[...]` for their dependencies and return their own
    result — `PipelineRunner` is responsible for storing it.
    """
    name: str = "unnamed_stage"
    requires: tuple[str, ...] = ()

    @abstractmethod
    def run(self, context: StageContext) -> Any:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<PipelineStage:{self.name}>"


class PipelineRunner:
    """
    Runs an ordered list of stages against a StageContext, checking
    `requires` before each stage and stopping (rather than silently
    continuing) on the first stage failure — mirrors the "never
    silently continue after a regression" rule used by the Chunk 4
    regression harness.
    """

    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    def run(self, sector: str, df_raw: pd.DataFrame) -> StageContext:
        context = StageContext(sector=sector, df_raw=df_raw)
        for stage in self.stages:
            missing = [r for r in stage.requires if r not in context.outputs]
            if missing:
                raise RuntimeError(
                    f"Stage '{stage.name}' is missing required upstream "
                    f"output(s): {missing}. Check PipelineRunner stage order."
                )
            context.outputs[stage.name] = stage.run(context)
        return context


# ══════════════════════════════════════════════════════════════════
# CONCRETE STAGES (all implemented — thin wrappers, zero new logic)
# ══════════════════════════════════════════════════════════════════

class SchemaStage(PipelineStage):
    """Sanitize + derive temporal features. Wraps preprocessing.py verbatim."""
    name = "schema"

    def run(self, context: StageContext) -> pd.DataFrame:
        df = sanitize_numerical_columns(context.df_raw.copy())
        return derive_temporal_features(df)


class CanonicalStage(PipelineStage):
    """Wraps schema_resolution.resolve_schema() verbatim."""
    name = "canonical"
    requires = ("schema",)

    def run(self, context: StageContext) -> pd.DataFrame:
        df = context.outputs["schema"]
        canonical_df, resolutions = resolve_schema(df)
        context.metadata["schema_resolutions"] = resolutions
        return canonical_df


class ConceptStage(PipelineStage):
    """Wraps business_concepts.compute_concept_values() verbatim."""
    name = "concepts"
    requires = ("canonical",)

    def run(self, context: StageContext) -> pd.DataFrame:
        canonical_df = context.outputs["canonical"]
        # Duplicate-labelled columns are de-duplicated (keep-first) — see
        # universal_churn/validation/regression.py for the full rationale;
        # this mirrors that same defensive handling, not a behaviour change.
        deduped = canonical_df.loc[:, ~canonical_df.columns.duplicated(keep="first")]
        concept_df, confidence = compute_concept_values(deduped, context.sector)
        context.metadata["concept_confidence"] = confidence
        return concept_df


class FeatureStage(PipelineStage):
    """Wraps feature_engineering.extract_universal_features() verbatim."""
    name = "features"
    requires = ("schema",)

    def run(self, context: StageContext) -> pd.DataFrame:
        df = context.outputs["schema"]
        target_col = SECTOR_CONFIG[context.sector]["target_col"]
        return extract_universal_features(df.copy(), context.sector, target_col, norm_stats=None)


class NormalizationStage(PipelineStage):
    """
    Wraps feature_engineering.transform_features_by_sector(), which
    already folds normalization into model-input preparation today.
    Kept as its own named stage (rather than merged into FeatureStage)
    specifically so Version 7 can insert a standalone normalization
    strategy later without touching FeatureStage or ModelInputStage.
    """
    name = "normalization"
    requires = ("schema",)

    def run(self, context: StageContext) -> pd.DataFrame:
        df = context.outputs["schema"]
        return transform_features_by_sector(df.copy(), context.sector)


class ModelInputStage(PipelineStage):
    """
    Identity pass-through of NormalizationStage's output today. Exists
    as a distinct stage so a future model-input-specific transform
    (e.g. per-model feature selection) has a seam without editing
    NormalizationStage.
    """
    name = "model_input"
    requires = ("normalization",)

    def run(self, context: StageContext) -> pd.DataFrame:
        return context.outputs["normalization"]


# ══════════════════════════════════════════════════════════════════
# FUTURE STAGES — interfaces only, NOT implemented (Version 7)
# ══════════════════════════════════════════════════════════════════

class FutureSemanticStage(PipelineStage):
    """
    Placeholder for Version 7 semantic schema matching. See
    schema_resolution.py's `resolve_semantic_alias()` /
    `future_embedding_match()` / `future_llm_resolution()` hooks for
    where the actual matching logic will eventually live. This stage
    intentionally raises NotImplementedError — it must never be added
    to a live PipelineRunner today.
    """
    name = "future_semantic"
    requires = ("canonical",)

    def run(self, context: StageContext) -> Any:
        raise NotImplementedError(
            "FutureSemanticStage is an architecture placeholder for "
            "Version 7 (semantic/embedding-based schema matching). "
            "Not implemented in Version 6."
        )


class FutureCoreModelStage(PipelineStage):
    """
    Placeholder for a future Core Model prediction stage. See
    `core_model_interface.py` for the interface this stage will
    eventually call, and `routing.py`'s existing `ModelType.CORE_MODEL`
    hook (already present, already routed-to-but-unreachable) for how
    a real implementation plugs into routing without an API change.
    """
    name = "future_core_model"
    requires = ("model_input",)

    def run(self, context: StageContext) -> Any:
        raise NotImplementedError(
            "FutureCoreModelStage is an architecture placeholder. "
            "Not implemented in Version 6 — see core_model_interface.py."
        )
