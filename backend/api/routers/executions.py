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
    DiagnosticsResponse,
    FeatureEngineeringResponse,
    SemanticIntelligenceResponse,
    FrameworkMapperResponse,
    CliOutputResponse,
    ReportTextsResponse,
)

router = APIRouter()


@router.get("/executions", response_model=list[ExecutionSummaryResponse])
def list_executions(repo=Depends(get_execution_repository)):
    return repo.list_executions()


def _load_execution(execution_id: str, repo) -> dict:
    data = repo.load(execution_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return data


@router.get("/analysis/{execution_id}", response_model=ExecutionDetailResponse)
def get_execution_detail(execution_id: str, repo=Depends(get_execution_repository)):
    return ExecutionDetailResponse(execution=_load_execution(execution_id, repo))


@router.get("/analysis/{execution_id}/pipeline", response_model=PipelineStateResponse)
def get_pipeline_state(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    pipeline = data.get("pipeline") or data.get("pipeline_state") or {}
    return PipelineStateResponse(pipeline_state=pipeline)


@router.get("/analysis/{execution_id}/predictions", response_model=PredictionsResponse)
def get_predictions(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    predictions = data.get("predictions")
    if predictions is None:
        prediction = data.get("prediction")
        predictions = [prediction] if isinstance(prediction, dict) and prediction else []
    if not isinstance(predictions, list):
        predictions = []
    return PredictionsResponse(predictions=predictions)


@router.get("/analysis/{execution_id}/reports", response_model=ReportsResponse)
def get_reports(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    reports = data.get("reports") or []
    return ReportsResponse(reports=reports)


@router.get("/analysis/{execution_id}/reports/text", response_model=ReportTextsResponse)
def get_report_texts(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return ReportTextsResponse(report_texts=data.get("report_texts") or {})


@router.get("/analysis/{execution_id}/decision", response_model=DecisionResponse)
def get_decision(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return DecisionResponse(decision=data.get("decision") or {})


@router.get("/analysis/{execution_id}/context", response_model=ContextResponse)
def get_context(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return ContextResponse(context=data.get("context") or {})


@router.get("/analysis/{execution_id}/events", response_model=EventsResponse)
def get_events(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return EventsResponse(events=data.get("events") or [])


@router.get("/analysis/{execution_id}/diagnostics", response_model=DiagnosticsResponse)
def get_diagnostics(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return DiagnosticsResponse(
        diagnostics=data.get("diagnostics") or {},
        execution_state=data.get("execution_state") or {},
    )


@router.get("/analysis/{execution_id}/feature-engineering", response_model=FeatureEngineeringResponse)
def get_feature_engineering(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return FeatureEngineeringResponse(
        feature_engineering=data.get("feature_engineering") or {},
    )


@router.get(
    "/analysis/{execution_id}/semantic-intelligence",
    response_model=SemanticIntelligenceResponse,
)
def get_semantic_intelligence(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    diagnostics = data.get("diagnostics") or {}
    return SemanticIntelligenceResponse(
        semantic_intelligence=(
            data.get("semantic_intelligence")
            or diagnostics.get("intelligence")
            or {}
        ),
    )


@router.get(
    "/analysis/{execution_id}/framework-mapper",
    response_model=FrameworkMapperResponse,
)
def get_framework_mapper(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return FrameworkMapperResponse(framework_mapper=data.get("framework_mapper") or {})


@router.get(
    "/analysis/{execution_id}/cli-output",
    response_model=CliOutputResponse,
)
def get_cli_output(execution_id: str, repo=Depends(get_execution_repository)):
    data = _load_execution(execution_id, repo)
    return CliOutputResponse(cli_output=data.get("cli_output") or {})
