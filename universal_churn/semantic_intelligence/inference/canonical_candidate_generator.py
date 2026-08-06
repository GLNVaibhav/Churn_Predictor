from __future__ import annotations
from ..domain.models import BusinessMeaningResolution, CanonicalCandidate
from ..knowledge.canonical_vocabulary_repository import CanonicalVocabularyRepository

class CanonicalCandidateGenerator:
    def __init__(self, vocabulary: CanonicalVocabularyRepository | None = None) -> None: self._vocabulary = vocabulary or CanonicalVocabularyRepository()
    def generate(self, meaning: BusinessMeaningResolution) -> tuple[CanonicalCandidate, ...]:
        source = meaning.selected or (meaning.candidates[0] if meaning.candidates else None)
        if source is None: return ()
        return tuple(CanonicalCandidate(cid, source.raw_score, True, "Canonical candidate declared by ontology meaning.") for cid in self._vocabulary.candidates(source.interpretation.meaning_id))
