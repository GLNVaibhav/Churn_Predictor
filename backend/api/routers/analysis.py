"""Analysis router for starting managed UCIF executions."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.dependencies import get_execution_manager, get_execution_repository
from backend.config import settings
from backend.runtime.executor import run_analysis_task

router = APIRouter()


class BusinessContextEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float = Field(ge=0, le=1)
    affected_segments: list[str] = Field(default_factory=list, max_length=50)
    source: str | None = Field(default=None, max_length=160)
    recommendation: str | None = Field(default=None, max_length=1000)
    timestamp: str | None = Field(default=None, max_length=80)


class BusinessContextDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector: str | None = Field(default=None, min_length=1, max_length=40)
    events: list[BusinessContextEvent] = Field(min_length=1, max_length=100)


class AnalyzeRequest(BaseModel):
    upload_id: str
    sector: str | None = None
    mode: str = "auto"
    explain: bool = True
    include_reports: bool = True
    business_context: BusinessContextDocument | None = None

    @model_validator(mode="after")
    def context_sector_matches_analysis(self):
        if self.business_context and self.business_context.sector and self.sector:
            aliases = {"e-commerce": "ecommerce", "retail": "ecommerce"}
            context_sector = aliases.get(self.business_context.sector.lower(), self.business_context.sector.lower())
            selected_sector = aliases.get(self.sector.lower(), self.sector.lower())
            if context_sector != selected_sector:
                raise ValueError("Business context sector must match the selected analysis sector.")
        return self


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

    selected_sector = request.sector or upload.get("sector")
    if request.business_context and request.business_context.sector and selected_sector:
        aliases = {"e-commerce": "ecommerce", "retail": "ecommerce"}
        context_sector = aliases.get(request.business_context.sector.lower(), request.business_context.sector.lower())
        actual_sector = aliases.get(str(selected_sector).lower(), str(selected_sector).lower())
        if context_sector != actual_sector:
            raise HTTPException(status_code=422, detail="Business context sector must match the selected analysis sector.")

    business_context = request.business_context.model_dump(exclude_none=True) if request.business_context else None

    def task_factory(execution_id: str, cancel_event):
        return run_analysis_task(
            execution_id=execution_id,
            cancel_event=cancel_event,
            input_path=str(input_path),
            sector=selected_sector,
            mode=request.mode,
            explain=request.explain,
            include_reports=request.include_reports,
            upload_id=request.upload_id,
            business_context=business_context,
        )

    execution_id = manager.start_execution(
        task_factory,
        initial_data={
            "upload_id": request.upload_id,
            "filename": upload.get("filename"),
            "sector": selected_sector,
            "context": {
                "upload_id": request.upload_id,
                "filename": upload.get("filename"),
                "sector": selected_sector,
                "business_context": business_context,
                "status": "PENDING",
            },
            "events": [{
                "type": "analysis_started",
                "status": "PENDING",
                "message": "Analysis execution queued",
            }],
        },
    )

    return AnalyzeStartResponse(execution_id=execution_id, upload_id=request.upload_id)
