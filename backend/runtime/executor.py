import asyncio
from typing import Dict, Any, Optional

from ..mappers.platform_enricher import enrich_platform_payload
from ..models.execution_record import ExecutionEvent, ExecutionRecord
from ..services.analysis_service import AnalysisService
from ..utils import utc_timestamp


async def run_analysis_task(
    execution_id: str,
    cancel_event: asyncio.Event,
    input_path: str,
    sector: str | None = None,
    mode: str = "auto",
    explain: bool = False,
    include_reports: bool = False,
    upload_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Background coroutine invoked by :class:`ExecutionManager`.

    Runs analysis, builds ``ExecutionRecord``, and returns the full
    platform payload for persistence.
    """
    if cancel_event.is_set():
        raise asyncio.CancelledError()

    service = AnalysisService()
    service.initialize()
    try:
        bundle = service.execute(
            input_path=input_path,
            sector=sector,
            mode=mode,
            explain=explain,
            include_reports=include_reports,
        )
    finally:
        service.shutdown()

    payload = enrich_platform_payload(
        bundle.response,
        bundle.execution_result,
        upload_id=upload_id,
    )

    execution = payload.get("execution") or {}
    if isinstance(execution, dict):
        execution["execution_id"] = execution_id
        payload["execution"] = execution

    started_at = execution.get("started_at") if isinstance(execution, dict) else None
    completed_at = execution.get("completed_at") if isinstance(execution, dict) else None
    status = execution.get("status", "SUCCEEDED") if isinstance(execution, dict) else "SUCCEEDED"

    events = [
        ExecutionEvent(
            type="analysis_started", status="RUNNING",
            message="Execution started", timestamp=started_at,
        ),
        ExecutionEvent(
            type="analysis_completed", status=status,
            message="Execution completed", timestamp=completed_at or utc_timestamp(),
        ),
    ]

    record = ExecutionRecord(
        execution_id=execution_id,
        status=status,
        created_at=started_at or utc_timestamp(),
        started_at=started_at,
        completed_at=completed_at,
        execution_time_ms=execution.get("execution_time_ms") if isinstance(execution, dict) else None,
        upload_id=upload_id,
        dataset=payload.get("dataset"),
        events=events,
        artifacts={"input_path": input_path, "mode": mode},
        diagnostics=payload.get("diagnostics"),
        report_texts=payload.get("report_texts"),
        result=payload,
        execution_result=payload.get("execution_result"),
        context={
            "execution_id": execution_id,
            "filename": (payload.get("dataset") or {}).get("filename"),
            "sector": (payload.get("dataset") or {}).get("sector"),
            "status": status,
        },
    )

    return record.to_dict()
