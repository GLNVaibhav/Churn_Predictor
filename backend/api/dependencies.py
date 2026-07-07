# dependencies for FastAPI layer
import uuid
from backend.runtime.repository import ExecutionRepository
from backend.runtime.manager import ExecutionManager
from backend.services.analysis_service import AnalysisService
from backend.services.upload_service import UploadService
from backend.config import settings

# Singleton instances (created once at import time)
execution_repository = ExecutionRepository(base_dir=str(settings.RUN_ROOT))
execution_manager = ExecutionManager(repository=execution_repository)
analysis_service = AnalysisService()

# Dependency factories

def get_execution_repository() -> ExecutionRepository:
    """Return the singleton ExecutionRepository."""
    return execution_repository


def get_execution_manager() -> ExecutionManager:
    """Return the singleton ExecutionManager."""
    return execution_manager


def get_analysis_service() -> AnalysisService:
    """Return the singleton AnalysisService."""
    return analysis_service


def get_upload_service() -> UploadService:
    """Return a new UploadService instance."""
    return UploadService()
