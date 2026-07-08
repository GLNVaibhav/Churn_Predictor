"""Framework router — live framework metadata from universal_churn constants."""

from fastapi import APIRouter
from backend.api.schemas import framework as framework_schema
from backend.config import settings

router = APIRouter()


@router.get("/framework", response_model=framework_schema.FrameworkResponse)
async def get_framework_info():
    coverage_version = None
    pi_version = None
    try:
        from universal_churn.config import PIPELINE_VERSION, COVERAGE_ALGORITHM_VERSION, SECTOR_CONFIG
        from universal_churn.prediction_intelligence import PREDICTION_INTELLIGENCE_VERSION
        framework_version = PIPELINE_VERSION
        coverage_version = COVERAGE_ALGORITHM_VERSION
        pi_version = PREDICTION_INTELLIGENCE_VERSION
        supported_sectors = list(SECTOR_CONFIG.keys())
    except Exception:
        framework_version = settings.FRAMEWORK_VERSION
        supported_sectors = ["telecom", "banking", "ecommerce", "healthcare"]

    return framework_schema.FrameworkResponse(
        framework_version=framework_version,
        runtime_version=settings.RUNTIME_VERSION,
        available_modules=[
            "coverage", "concept_confidence", "quality_gate",
            "adaptive_routing", "feature_engineering", "sector_pipeline",
            "universal_pipeline", "prediction_explanation",
            "business_reasoning", "decision_intelligence",
            "prediction_intelligence", "reporting",
        ],
        supported_sectors=supported_sectors,
        contract_version="1.0.0",
        coverage_version=coverage_version,
        prediction_intelligence_version=pi_version,
    )
