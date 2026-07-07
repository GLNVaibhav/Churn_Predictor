'''Execution router exposing live execution state.'''

from fastapi import APIRouter, HTTPException, status, Depends
from backend.api.dependencies import get_execution_repository
from backend.api.schemas.execution import (
    ExecutionSummaryResponse,
    ExecutionDetailResponse,
    PipelineStateResponse,
    PredictionsResponse,
    ReportsResponse,
    DecisionResponse,
    ContextResponse,
    EventsResponse,
)

router = APIRouter()

@router.get("/executions", response_model=list[ExecutionSummaryResponse])
def list_executions(
    repo=Depends(get_execution_repository),
):
    """Return a summary list of all executions stored in the repository."""
    return repo.list_executions()

def _load_execution(execution_id: str, repo) -> dict:
    data = repo.load(execution_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return data

@router.get("/analysis/{execution_id}", response_model=ExecutionDetailResponse)
def get_execution_detail(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    return ExecutionDetailResponse(execution=data)

@router.get("/analysis/{execution_id}/pipeline", response_model=PipelineStateResponse)
def get_pipeline_state(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    pipeline = data.get("pipeline_state", {})
    return PipelineStateResponse(pipeline_state=pipeline)

@router.get("/analysis/{execution_id}/predictions", response_model=PredictionsResponse)
def get_predictions(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    predictions = data.get("predictions", [])
    return PredictionsResponse(predictions=predictions)

@router.get("/analysis/{execution_id}/reports", response_model=ReportsResponse)
def get_reports(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    reports = data.get("reports", [])
    return ReportsResponse(reports=reports)

@router.get("/analysis/{execution_id}/decision", response_model=DecisionResponse)
def get_decision(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    decision = data.get("decision", {})
    return DecisionResponse(decision=decision)

@router.get("/analysis/{execution_id}/context", response_model=ContextResponse)
def get_context(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    context = data.get("context", {})
    return ContextResponse(context=context)

@router.get("/analysis/{execution_id}/events", response_model=EventsResponse)
def get_events(
    execution_id: str,
    repo=Depends(get_execution_repository),
):
    data = _load_execution(execution_id, repo)
    events = data.get("events", [])
    return EventsResponse(events=events)
