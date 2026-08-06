"""Semantic Intelligence V8 public contracts and services.

V8 is additive: deterministic schema resolution remains the compatibility
boundary while this package owns meaning-first semantic understanding.
"""
from .application.semantic_understanding_engine import SemanticUnderstandingEngine
from .application.offline_profiling_service import OfflineProfilingService
from .application.online_resolution_service import OnlineResolutionService
from .application.legacy_schema_adapter import LegacySchemaAdapter
from .domain.models import SemanticResolution, ResolvedSchema

__all__ = [
    "SemanticUnderstandingEngine", "OfflineProfilingService",
    "OnlineResolutionService", "LegacySchemaAdapter", "SemanticResolution",
    "ResolvedSchema",
]
