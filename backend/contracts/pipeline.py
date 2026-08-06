"""
backend.contracts.pipeline
══════════════════════════════════════════════════════════════════════
``PipelineSummary`` / ``PipelineStageInfo`` — a stage-by-stage account
of what the framework actually did during one analysis run.

This is diagnostics, not computation: the backend does not decide
which stages ran or what their status is — it reads that from
whatever the framework already recorded (e.g.
``universal_churn.validation.diagnostics.StageDiagnostics``,
``feature_engineering.FeaturePreparationContext.pipeline_manifest``,
or a ``RegressionResult``'s per-stage list) and reshapes it into this
stable, consumer-facing form.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..utils import to_serializable


@dataclass
class PipelineStageInfo:
    """
    One pipeline stage's outcome.

    Attributes
    ----------
    name : str
        Stage name (e.g. ``'schema_resolution'``, ``'business_concepts'``,
        ``'feature_engineering'``, ``'coverage'``, ``'quality_gate'``,
        ``'routing'``, ``'prediction'``).
    status : str
        One of ``'OK'``, ``'WARNING'``, ``'FAILED'``, ``'SKIPPED'``.
    description : str
        Short human-readable note about what happened at this stage
        (e.g. a drift/recovery message already produced upstream).
    execution_time : float | None
        Milliseconds spent in this stage, if timing was captured.
    """
    name: str
    status: str
    id: str = ""
    description: str = ""
    execution_time: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.name

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineStageInfo":
        return cls(
            id=d.get("id", d.get("name", "unnamed_stage")),
            name=d.get("name", "unnamed_stage"),
            status=d.get("status", "OK"),
            description=d.get("description", ""),
            execution_time=d.get("execution_time"),
        )


@dataclass
class PipelineSummary:
    """
    Attributes
    ----------
    total_stages : int
    completed : int
    failed : int
    warnings : int
    overall_status : str
        One of ``'OK'``, ``'DEGRADED'``, ``'FAILED'`` — a roll-up of
        ``stages``, computed here purely as a count/aggregate (no
        framework logic is re-run to produce it).
    stages : list[PipelineStageInfo]
    """
    total_stages: int = 0
    completed: int = 0
    failed: int = 0
    warnings: int = 0
    overall_status: str = "OK"
    stages: List[PipelineStageInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineSummary":
        return cls(
            total_stages=d.get("total_stages", 0),
            completed=d.get("completed", 0),
            failed=d.get("failed", 0),
            warnings=d.get("warnings", 0),
            overall_status=d.get("overall_status", "OK"),
            stages=[PipelineStageInfo.from_dict(s) for s in d.get("stages", [])],
        )

    @classmethod
    def from_stages(cls, stages: List[PipelineStageInfo]) -> "PipelineSummary":
        """
        Build a summary purely by counting an already-assembled stage
        list — a pure aggregation helper, not framework logic.
        """
        failed = sum(1 for s in stages if s.status == "FAILED")
        warnings = sum(1 for s in stages if s.status == "WARNING")
        completed = sum(1 for s in stages if s.status in ("OK", "WARNING"))
        overall = "FAILED" if failed else ("DEGRADED" if warnings else "OK")
        return cls(
            total_stages=len(stages), completed=completed, failed=failed,
            warnings=warnings, overall_status=overall, stages=list(stages),
        )
