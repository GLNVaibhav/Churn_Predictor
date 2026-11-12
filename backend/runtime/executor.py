import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from ..mappers.platform_enricher import enrich_platform_payload
from ..models.execution_record import ExecutionEvent, ExecutionRecord
from ..services.analysis_service import AnalysisService
from ..services.business_context_service import evaluate_business_context
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
    business_context: Optional[Dict[str, Any]] = None,
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

    adaptive_business = None
    if business_context is not None:
        context_sector = sector or (payload.get("dataset") or {}).get("sector") or "unknown"
        adaptive_business = evaluate_business_context(
            business_context, sector=str(context_sector), execution_id=execution_id,
        )
        payload["adaptive_business"] = adaptive_business
        signal_count = adaptive_business["signal_count"]
        adaptive_summary = adaptive_business["summary"]
        decision = payload.get("decision")
        if isinstance(decision, dict):
            decision["adaptive_context"] = adaptive_summary
            decision["context_recommendations"] = [
                {
                    "signal": item["name"],
                    "affected_segments": item["affected_segments"],
                    "action": item["recommendation_influence"],
                    "severity": item["impact"],
                    "department": item.get("department"),
                    "priority": item.get("priority"),
                    "evidence_id": item["evidence_id"],
                }
                for item in adaptive_business["signals"]
            ]
        report_texts = payload.get("report_texts")
        if isinstance(report_texts, dict) and signal_count:
            appendix = ["", "ADAPTIVE BUSINESS CONTEXT", adaptive_summary]
            for item in adaptive_business["signals"]:
                organization = f"; department {item['department']}" if item.get("department") else ""
                priority = f"; priority {item['priority']}" if item.get("priority") is not None else ""
                appendix.append(
                    f"[{item['impact']}] {item['name']}: {item['value']} "
                    f"(confidence {item['confidence']:.0%}{organization}{priority}); "
                    f"recommendation: {item['recommendation_influence']}"
                )
            existing = report_texts.get("decision_report_text") or ""
            report_texts["decision_report_text"] = (existing + "\n" + "\n".join(appendix)).strip()

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
        artifacts={"input_path": Path(input_path).name, "mode": mode},
        diagnostics=payload.get("diagnostics"),
        report_texts=payload.get("report_texts"),
        result=payload,
        execution_result=payload.get("execution_result"),
        context={
            "execution_id": execution_id,
            "filename": (payload.get("dataset") or {}).get("filename"),
            "sector": (payload.get("dataset") or {}).get("sector"),
            "status": status,
            "business_context": business_context,
        },
    )

    return record.to_dict()
