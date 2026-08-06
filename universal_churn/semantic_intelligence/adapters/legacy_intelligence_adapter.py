from __future__ import annotations
from ..application.semantic_understanding_engine import SemanticUnderstandingEngine
from ..domain.enums import ExecutionMode
class LegacyIntelligenceAdapter:
    def infer(self, dataframe): return SemanticUnderstandingEngine().understand(dataframe, ExecutionMode.DIAGNOSTIC)
