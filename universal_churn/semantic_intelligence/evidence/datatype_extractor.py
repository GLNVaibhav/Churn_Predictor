from __future__ import annotations
from ..domain.enums import EvidenceFamily
from ..domain.identifiers import OntologyId
from ..domain.models import EvidenceItem
from .base import EvidenceExtractor, ExtractorContext

class DatatypeExtractor(EvidenceExtractor):
    def extract(self, context: ExtractorContext) -> tuple[EvidenceItem, ...]:
        col = context.column; items = []
        if col.datatype.logical_type == "numeric":
            for concept in context.ontology.meanings():
                if any(word in concept.label.lower() for word in ("charge", "spend", "count", "score", "tenure", "recency")):
                    items.append(EvidenceItem(f"datatype:{col.raw_column}:{concept.ontology_id.value}", EvidenceFamily.DATATYPE, concept.ontology_id, .35, 1, "Numeric datatype supports numeric semantic measure.", "dtype"))
        return tuple(items)
