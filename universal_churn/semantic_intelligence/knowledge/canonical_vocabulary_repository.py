from __future__ import annotations
from ..domain.identifiers import OntologyId
from .ontology_repository import OntologyRepository


class CanonicalVocabularyRepository:
    def __init__(self, ontology: OntologyRepository | None = None) -> None: self._ontology = ontology or OntologyRepository()
    def candidates(self, meaning_id: OntologyId) -> tuple[OntologyId, ...]:
        concept = self._ontology.get(meaning_id)
        return concept.canonical_ids if concept else ()
