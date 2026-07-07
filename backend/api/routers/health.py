'''Health router for FastAPI transport layer'''

import logging
from fastapi import APIRouter
from datetime import datetime
from backend.config import settings
from backend.api.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    now = datetime.utcnow().isoformat() + "Z"
    return HealthResponse(
        status="OK",
        framework_version=settings.FRAMEWORK_VERSION,
        runtime_version=settings.RUNTIME_VERSION,
        api_version=settings.API_VERSION,
        timestamp=now,
    )
