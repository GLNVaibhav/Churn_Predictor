from __future__ import annotations
from dataclasses import dataclass
from ..domain.identifiers import OntologyId

@dataclass(frozen=True)
class FeatureContract: sector_id: OntologyId; required_meanings: tuple[OntologyId, ...]
class FeatureContractRepository:
    def get(self, sector: OntologyId, version: str = "8.0.0") -> FeatureContract: return FeatureContract(sector, ())
