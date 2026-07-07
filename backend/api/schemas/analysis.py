# Minimal placeholder schemas for analysis endpoints
from pydantic import BaseModel
from typing import List, Dict, Any

class AnalysisResponse(BaseModel):
    execution_id: str
    status: str
    detail: str | None = None

class PipelineStep(BaseModel):
    name: str
    status: str
    metadata: Dict[str, Any] | None = None

class PipelineResponse(BaseModel):
    execution_id: str
    steps: List[PipelineStep]

class Prediction(BaseModel):
    metric: str
    value: float
    confidence: float | None = None

class PredictionsResponse(BaseModel):
    execution_id: str
    predictions: List[Prediction]

class Report(BaseModel):
    title: str
    content: str

class ReportsResponse(BaseModel):
    execution_id: str
    reports: List[Report]

class DecisionResponse(BaseModel):
    execution_id: str
    decision: str
    rationale: str | None = None

class ContextResponse(BaseModel):
    execution_id: str
    context: Dict[str, Any]

class EventsResponse(BaseModel):
    execution_id: str
    events: List[Dict[str, Any]]
