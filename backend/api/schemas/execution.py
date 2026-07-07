from typing import Any

from pydantic import BaseModel


class ExecutionSummaryResponse(BaseModel):
    execution_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    progress: float | int | None = None


class ExecutionDetailResponse(BaseModel):
    execution: dict[str, Any]


class PipelineStateResponse(BaseModel):
    pipeline_state: dict[str, Any]


class PredictionsResponse(BaseModel):
    predictions: list[dict[str, Any]]


class ReportsResponse(BaseModel):
    reports: list[dict[str, Any]]


class DecisionResponse(BaseModel):
    decision: dict[str, Any]


class ContextResponse(BaseModel):
    context: dict[str, Any]


class EventsResponse(BaseModel):
    events: list[dict[str, Any]]
