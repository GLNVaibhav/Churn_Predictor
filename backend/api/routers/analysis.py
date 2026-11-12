"""Analysis router for starting managed UCIF executions."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.dependencies import get_execution_manager, get_execution_repository
from backend.api.auth import CurrentUser, owns_resource, require_user
from backend.api.dependencies import get_upload_storage
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
    recommended_action: str | None = Field(default=None, max_length=1000)
    department: str | None = Field(default=None, max_length=120)
    priority: int | None = Field(default=None, ge=1, le=5)
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
    status: str = "PENDING"


@router.post("/analyze", response_model=AnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    request: AnalyzeRequest,
    repo=Depends(get_execution_repository),
    manager=Depends(get_execution_manager),
    user: CurrentUser = Depends(require_user),
    storage=Depends(get_upload_storage),
):
    upload = repo.load(request.upload_id)
    if upload is None or "filename" not in upload or not owns_resource(upload, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    selected_sector = request.sector or upload.get("sector")
    if request.business_context and request.business_context.sector and selected_sector:
        aliases = {"e-commerce": "ecommerce", "retail": "ecommerce"}
        context_sector = aliases.get(request.business_context.sector.lower(), request.business_context.sector.lower())
        actual_sector = aliases.get(str(selected_sector).lower(), str(selected_sector).lower())
        if context_sector != actual_sector:
            raise HTTPException(status_code=422, detail="Business context sector must match the selected analysis sector.")

    business_context = request.business_context.model_dump(exclude_none=True) if request.business_context else None
    if business_context:
        for event in business_context["events"]:
            # ABIL source documents use `recommended_action`; the evaluator's
            # canonical event contract calls the same field `recommendation`.
            if not event.get("recommendation") and event.get("recommended_action"):
                event["recommendation"] = event["recommended_action"]
    try:
        input_path, temporary_input = storage.materialize(request.upload_id, upload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Uploaded dataset storage is unavailable.") from exc
    if not input_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded file not found")

    async def task_factory(execution_id: str, cancel_event):
        try:
            return await run_analysis_task(
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
        finally:
            if temporary_input:
                input_path.unlink(missing_ok=True)

    try:
        execution_id = manager.start_execution(
            task_factory,
            initial_data={
            "owner_id": user.user_id,
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
    except Exception:
        if temporary_input:
            input_path.unlink(missing_ok=True)
        raise

    initial_state = manager.get_status(execution_id) if hasattr(manager, "get_status") else None
    initial_status = initial_state.get("status") if isinstance(initial_state, dict) else None
    return AnalyzeStartResponse(
        execution_id=execution_id,
        upload_id=request.upload_id,
        status=str(initial_status or "PENDING").upper(),
    )
