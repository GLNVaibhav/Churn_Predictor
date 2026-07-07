"""Framework router for FastAPI transport layer"""

from fastapi import APIRouter
from backend.api.schemas import framework as framework_schema
from backend.config import settings

router = APIRouter()

@router.get("/framework", response_model=framework_schema.FrameworkResponse)
async def get_framework_info():
    # Placeholder implementation – expand with real registry data as needed
    return framework_schema.FrameworkResponse(
        framework_version=settings.FRAMEWORK_VERSION,
        runtime_version=settings.RUNTIME_VERSION,
        available_modules=["coverage", "concept_confidence", "quality_gate", "adaptive_routing", "prediction_intelligence", "decision_intelligence"],
        supported_sectors=["telecom", "finance", "retail"],
        contract_version="1.0.0",
    )
