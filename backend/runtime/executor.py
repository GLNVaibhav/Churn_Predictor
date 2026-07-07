import asyncio
from typing import Dict, Any
from ..services.analysis_service import AnalysisService

async def run_analysis_task(
    execution_id: str,
    cancel_event: asyncio.Event,
    input_path: str,
    sector: str | None = None,
    mode: str = "auto",
    explain: bool = False,
    include_reports: bool = False,
) -> Dict[str, Any]:
    """Background coroutine invoked by :class:`ExecutionManager`.

    It performs a full analysis using :class:`AnalysisService` and returns a
    serialisable dictionary representing the final execution payload. The
    ``cancel_event`` can be checked periodically for graceful termination –
    the current implementation does not support mid‑pipeline cancellation
    because the underlying ``AnalysisService`` runs synchronously, but the
    flag is kept for future fine‑grained support.
    """
    # Early cancellation check before starting heavy work
    if cancel_event.is_set():
        raise asyncio.CancelledError()

    service = AnalysisService()
    service.initialize()
    try:
        response = service.execute(
            input_path=input_path,
            sector=sector,
            mode=mode,
            explain=explain,
            include_reports=include_reports,
        )
    finally:
        service.shutdown()

    # ``UniversalAnalysisResponse`` provides ``to_dict`` for JSON export
    payload = response.to_dict()
    # Ensure the execution_id in the payload matches the manager's id
    if "execution" in payload and isinstance(payload["execution"], dict):
        payload["execution"]["execution_id"] = execution_id
    else:
        payload["execution_id"] = execution_id
    dataset = payload.get("dataset") or {}
    execution = payload.get("execution") or {}
    payload["context"] = {
        "execution_id": execution_id,
        "filename": dataset.get("filename"),
        "sector": dataset.get("sector"),
        "status": execution.get("status", "SUCCEEDED"),
    }
    payload["pipeline_state"] = payload.get("pipeline") or {}
    payload["events"] = [
        {"type": "analysis_started", "status": "RUNNING", "message": "Execution started"},
        {"type": "analysis_completed", "status": execution.get("status", "SUCCEEDED"), "message": "Execution completed"},
    ]
    return payload
