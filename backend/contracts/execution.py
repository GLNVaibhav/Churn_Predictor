"""
backend.contracts.execution
══════════════════════════════════════════════════════════════════════
``ExecutionInfo`` — who/when/how-long for one analysis run.

This section describes the RUN itself (an execution envelope), not
anything the framework computed. It exists so every future consumer
(CLI, API, agent) can correlate logs, retries, and timing without
reaching into framework internals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..utils import to_serializable, utc_timestamp, new_execution_id


@dataclass
class ExecutionInfo:
    """
    Attributes
    ----------
    execution_id : str
        Unique identifier for this analysis run.
    status : str
        One of ``'PENDING'``, ``'RUNNING'``, ``'SUCCEEDED'``,
        ``'FAILED'``. The backend sets this; the framework has no
        notion of run status.
    started_at : str
        UTC timestamp the run began.
    completed_at : str | None
        UTC timestamp the run finished, or ``None`` while still running.
    execution_time_ms : float | None
        Wall-clock duration, once known.
    framework_version : str | None
        The ``universal_churn`` pipeline version this run executed
        against (e.g. ``config.PIPELINE_VERSION``) — recorded here,
        not recomputed, by whichever mapper call attaches it.
    """
    execution_id: str
    status: str = "PENDING"
    started_at: str = ""
    completed_at: Optional[str] = None
    execution_time_ms: Optional[float] = None
    framework_version: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = utc_timestamp()

    # ── constructors ─────────────────────────────────────────────

    @classmethod
    def start(cls, framework_version: Optional[str] = None) -> "ExecutionInfo":
        """Begin tracking a new execution."""
        return cls(
            execution_id=new_execution_id(),
            status="RUNNING",
            started_at=utc_timestamp(),
            framework_version=framework_version,
        )

    def mark_succeeded(self, execution_time_ms: Optional[float] = None) -> "ExecutionInfo":
        """Return a completed copy of this execution record (this
        object is otherwise treated as immutable by callers)."""
        return _replace_status(self, "SUCCEEDED", execution_time_ms)

    def mark_failed(self, execution_time_ms: Optional[float] = None) -> "ExecutionInfo":
        return _replace_status(self, "FAILED", execution_time_ms)

    # ── serialization ────────────────────────────────────────────

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionInfo":
        return cls(
            execution_id=d.get("execution_id", new_execution_id()),
            status=d.get("status", "PENDING"),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at"),
            execution_time_ms=d.get("execution_time_ms"),
            framework_version=d.get("framework_version"),
        )


def _replace_status(
    info: ExecutionInfo, status: str, execution_time_ms: Optional[float],
) -> ExecutionInfo:
    return ExecutionInfo(
        execution_id=info.execution_id,
        status=status,
        started_at=info.started_at,
        completed_at=utc_timestamp(),
        execution_time_ms=execution_time_ms,
        framework_version=info.framework_version,
    )
