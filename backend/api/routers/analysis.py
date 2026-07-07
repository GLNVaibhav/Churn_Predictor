"""Analysis router for starting managed UCIF executions."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.dependencies import get_execution_manager, get_execution_repository
from backend.config import settings
from backend.runtime.executor import run_analysis_task

router = APIRouter()


class AnalyzeRequest(BaseModel):
    upload_id: str
    sector: str | None = None
    mode: str = "auto"
    explain: bool = True
    include_reports: bool = True


class AnalyzeStartResponse(BaseModel):
    execution_id: str
    upload_id: str
    status: str = "RUNNING"


@router.post("/analyze", response_model=AnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalyzeRequest,
    repo=Depends(get_execution_repository),
    manager=Depends(get_execution_manager),
):
    upload = repo.load(request.upload_id)
    if upload is None or "filename" not in upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    input_path = Path(settings.UPLOAD_ROOT) / request.upload_id / upload["filename"]
    if not input_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded file not found")

    def task_factory(execution_id: str, cancel_event):
        return run_analysis_task(
            execution_id=execution_id,
            cancel_event=cancel_event,
            input_path=str(input_path),
            sector=request.sector or upload.get("sector"),
            mode=request.mode,
            explain=request.explain,
            include_reports=request.include_reports,
        )

    execution_id = manager.start_execution(task_factory)
    current = repo.load(execution_id) or {}
    current.update({
        "upload_id": request.upload_id,
        "filename": upload.get("filename"),
        "sector": request.sector or upload.get("sector"),
        "context": {
            "upload_id": request.upload_id,
            "execution_id": execution_id,
            "filename": upload.get("filename"),
            "sector": request.sector or upload.get("sector"),
            "status": "RUNNING",
        },
        "events": [
            {
                "type": "analysis_started",
                "status": "RUNNING",
                "message": "Analysis execution started",
            }
        ],
    })
    repo.save(execution_id, current)

    return AnalyzeStartResponse(execution_id=execution_id, upload_id=request.upload_id)
