from __future__ import annotations
from ..domain.identifiers import OntologyId
from ..domain.models import CapabilityAssessment, ResolvedSchema

class CapabilityAssessmentService:
    """Assesses dataset-level business capabilities from accepted meanings."""
    def assess(self, resolved_schema: ResolvedSchema, capability_id: OntologyId, required_meanings: tuple[OntologyId, ...]) -> CapabilityAssessment:
        available = {r.business_meaning.selected.interpretation.meaning_id for r in resolved_schema.resolutions if r.business_meaning.selected is not None and r.status.value.endswith("ACCEPTED")}
        found = tuple(sorted(available & set(required_meanings), key=lambda x: x.value))
        return CapabilityAssessment(capability_id, set(required_meanings).issubset(available), len(found) / len(required_meanings) if required_meanings else 1.0, required_meanings, found)
