"""
backend.models.execution_record
══════════════════════════════════════════════════════════════════════
``ExecutionRecord`` — lifecycle wrapper around an immutable
``ExecutionResult``.

Architecture::

    ExecutionManager → ExecutionRepository → ExecutionRecord → ExecutionResult

``ExecutionRecord`` owns execution identity, status, timestamps, events,
artifacts, logs, and diagnostics.  ``ExecutionResult`` remains the
immutable framework output snapshot — never modified here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils import to_serializable


@dataclass
class ExecutionEvent:
    """One lifecycle event during an execution."""
    type: str
    status: str
    message: str
    timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        return to_serializable(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionEvent":
        return cls(
            type=d.get("type", ""),
            status=d.get("status", ""),
            message=d.get("message", ""),
            timestamp=d.get("timestamp"),
        )


@dataclass
class ExecutionRecord:
    """
    Full execution lifecycle record persisted by ``ExecutionRepository``.

    The ``result`` field holds the API-facing analysis payload
    (``UniversalAnalysisResponse`` shape).  ``execution_result`` holds
    the normalized framework snapshot for audit/regression.
    """
    execution_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[float] = None
    upload_id: Optional[str] = None
    dataset: Optional[Dict[str, Any]] = None
    events: List[ExecutionEvent] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    diagnostics: Optional[Dict[str, Any]] = None
    report_texts: Optional[Dict[str, str]] = None
    result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Flatten into the persisted JSON shape (backward compatible)."""
        payload: Dict[str, Any] = {}
        if self.result:
            payload.update(self.result)
        payload["execution_id"] = self.execution_id
        if self.upload_id:
            payload["upload_id"] = self.upload_id
        payload["context"] = self.context or {
            "execution_id": self.execution_id,
            "filename": (self.dataset or {}).get("filename"),
            "sector": (self.dataset or {}).get("sector"),
            "status": self.status,
        }
        payload["events"] = [e.to_dict() if isinstance(e, ExecutionEvent) else e for e in self.events]
        payload["diagnostics"] = self.diagnostics
        payload["report_texts"] = self.report_texts
        payload["execution_result"] = self.execution_result
        payload["artifacts"] = self.artifacts
        payload["logs"] = self.logs
        payload["pipeline_state"] = payload.get("pipeline") or payload.get("pipeline_state") or {}
        return payload

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionRecord":
        execution = d.get("execution") if isinstance(d.get("execution"), dict) else {}
        if not execution and d.get("execution_id"):
            execution = {
                "execution_id": d.get("execution_id"),
                "status": d.get("status"),
                "started_at": d.get("started_at"),
                "completed_at": d.get("completed_at"),
                "execution_time_ms": d.get("execution_time_ms"),
            }
        events_raw = d.get("events") or []
        events = [
            ExecutionEvent.from_dict(e) if isinstance(e, dict) else e
            for e in events_raw
        ]
        return cls(
            execution_id=str(execution.get("execution_id") or d.get("execution_id") or ""),
            status=str(execution.get("status") or d.get("status") or "UNKNOWN"),
            created_at=str(execution.get("started_at") or d.get("created_at") or ""),
            started_at=execution.get("started_at"),
            completed_at=execution.get("completed_at"),
            execution_time_ms=execution.get("execution_time_ms"),
            upload_id=d.get("upload_id"),
            dataset=d.get("dataset"),
            events=events,
            artifacts=d.get("artifacts") or {},
            logs=d.get("logs") or [],
            diagnostics=d.get("diagnostics"),
            report_texts=d.get("report_texts"),
            result=d,
            execution_result=d.get("execution_result"),
            context=d.get("context"),
        )
