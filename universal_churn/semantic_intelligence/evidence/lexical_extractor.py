from __future__ import annotations
import re
from ..domain.enums import EvidenceFamily
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext

class LexicalExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", context.column.raw_column).replace("_", " ").lower()
        tokens = set(re.findall(r"[a-z]+", text))
        items = []
        for concept in context.ontology.meanings():
            alias_tokens = [set(re.findall(r"[a-z]+", a.lower())) for a in concept.aliases]
            score = max((len(tokens & a) / len(a) for a in alias_tokens if a), default=0.0)
            if score: items.append(EvidenceItem(f"lexical:{context.column.raw_column}:{concept.ontology_id.value}", EvidenceFamily.LEXICAL, concept.ontology_id, score, 1, "Column-name tokens overlap ontology aliases.", "column_name", {"tokens": sorted(tokens)}))
        return tuple(items)
