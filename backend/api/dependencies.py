# dependencies for FastAPI layer
import uuid
from backend.runtime.repository import ExecutionRepository
from backend.runtime.manager import ExecutionManager
from backend.services.analysis_service import AnalysisService
from backend.config import settings

# Singleton instances (created once at import time)
execution_repository = ExecutionRepository(base_dir=str(settings.RUN_ROOT))
execution_manager = ExecutionManager(repository=execution_repository)
analysis_service = AnalysisService()
# Ensure the AnalysisService is initialized at startup; FastAPI app can call .initialize() in lifespan if needed
