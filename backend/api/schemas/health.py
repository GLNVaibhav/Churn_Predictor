from pydantic import BaseModel
from datetime import datetime

class HealthResponse(BaseModel):
    status: str
    framework_version: str
    runtime_version: str
    api_version: str
    timestamp: str  # ISO8601 UTC timestamp
