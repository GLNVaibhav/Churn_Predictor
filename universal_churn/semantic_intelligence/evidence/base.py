from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..domain.models import ColumnProfile, DatasetProfile, EvidenceItem
from ..knowledge.ontology_repository import OntologyRepository

@dataclass(frozen=True)
class ExtractorContext:
    column: ColumnProfile; dataset: DatasetProfile; ontology: OntologyRepository

class EvidenceExtractor(ABC):
    @abstractmethod
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]: ...
