"""
universal_churn/model_registry.py
══════════════════════════════════════════════════════════════════════
Model Registry Interface — Version 6, Chunk 5, Part 2.

This is METADATA ONLY. It does not load, save, replace, or modify any
model artifact, and `sector_pipeline.py` / `universal_pipeline.py`
still load models exactly as before (`joblib.load(config['model_path'])`
etc.) — this module is not on that path and nothing currently calls it
in production.

Purpose: give every model artifact (sector, universal, and the not-yet-
implemented sparse/core models) one consistent descriptor shape, so
Version 7 can introspect "what models exist, what version are they,
are they compatible with the current pipeline" without bespoke
per-caller logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .config import (
    SECTOR_CONFIG, PIPELINE_VERSION, SECTOR_MODEL_VERSION,
    UNIVERSAL_MODEL_VERSION, NORMALIZATION_VERSION,
    UNIVERSAL_MODEL_PATH,
)


class ModelKind(str, Enum):
    SECTOR = "sector"
    UNIVERSAL = "universal"
    SPARSE = "sparse"      # future — see sparse_model_interface.py
    CORE = "core"           # future — see core_model_interface.py


@dataclass(frozen=True)
class ModelRegistryEntry:
    """One artifact's descriptor. Every field is metadata; none of it
    is consumed by the loading code in sector_pipeline.py /
    universal_pipeline.py today."""
    model_name: str
    model_version: str
    sector: str | None            # None for cross-sector models
    kind: ModelKind
    training_date: str | None     # ISO8601, derived from artifact mtime
    artifact_path: str
    feature_schema_version: str
    normalization_version: str
    compatible_pipeline_version: str
    exists: bool

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "sector": self.sector,
            "kind": self.kind.value,
            "training_date": self.training_date,
            "artifact_path": self.artifact_path,
            "feature_schema_version": self.feature_schema_version,
            "normalization_version": self.normalization_version,
            "compatible_pipeline_version": self.compatible_pipeline_version,
            "exists": self.exists,
        }


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


class ModelRegistry:
    """
    Read-only, on-demand registry. Does not cache to disk (that would
    be a second source of truth for artifacts that already have one:
    the filesystem + config.py). `list_entries()` re-stats the
    filesystem every call, which is intentional and cheap.
    """

    def entries(self) -> list[ModelRegistryEntry]:
        out: list[ModelRegistryEntry] = []

        for sector, cfg in SECTOR_CONFIG.items():
            path = Path(cfg["model_path"])
            out.append(ModelRegistryEntry(
                model_name=f"{sector}_sector_model",
                model_version=SECTOR_MODEL_VERSION,
                sector=sector,
                kind=ModelKind.SECTOR,
                training_date=_mtime_iso(path),
                artifact_path=str(path),
                feature_schema_version=NORMALIZATION_VERSION,
                normalization_version=NORMALIZATION_VERSION,
                compatible_pipeline_version=PIPELINE_VERSION,
                exists=path.exists(),
            ))

        universal_path = Path(UNIVERSAL_MODEL_PATH)
        out.append(ModelRegistryEntry(
            model_name="universal_cross_sector_model",
            model_version=UNIVERSAL_MODEL_VERSION,
            sector=None,
            kind=ModelKind.UNIVERSAL,
            training_date=_mtime_iso(universal_path),
            artifact_path=str(universal_path),
            feature_schema_version=NORMALIZATION_VERSION,
            normalization_version=NORMALIZATION_VERSION,
            compatible_pipeline_version=PIPELINE_VERSION,
            exists=universal_path.exists(),
        ))

        # Sparse / Core entries are intentionally omitted here (not
        # "exists=False" placeholders) — no artifact_path convention
        # for them exists yet. See sparse_model_interface.py and
        # core_model_interface.py for the interfaces that will produce
        # real entries once those models exist.

        return out

    def get(self, model_name: str) -> ModelRegistryEntry | None:
        return next((e for e in self.entries() if e.model_name == model_name), None)

    def for_sector(self, sector: str) -> list[ModelRegistryEntry]:
        return [e for e in self.entries() if e.sector == sector]


def print_registry_report() -> None:
    sep = "─" * 78
    print(f"\n{sep}\n  MODEL REGISTRY  (metadata only — does not affect model loading)\n{sep}")
    for entry in ModelRegistry().entries():
        status = "✔ present" if entry.exists else "✖ missing"
        print(f"  [{status}] {entry.model_name:<28} kind={entry.kind.value:<10} "
              f"version={entry.model_version:<8} trained={entry.training_date}")
        print(f"             path={entry.artifact_path}")
    print(sep)
