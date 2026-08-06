from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml
from ..domain.identifiers import OntologyId


@dataclass(frozen=True)
class OntologyConcept:
    ontology_id: OntologyId
    label: str
    kind: str
    aliases: tuple[str, ...] = ()
    canonical_ids: tuple[OntologyId, ...] = ()


class OntologyRepository:
    """Read-only repository with built-in core concepts plus optional YAML extensions."""
    _CORE = {
        "ucif.meaning.customer.identifier": ("Customer Identifier", "meaning", ("customer id", "customerid", "patient id", "account id"), ("ucif.canonical.customer.identifier",)),
        "ucif.meaning.customer.relationship.tenure": ("Customer Relationship Tenure", "meaning", ("tenure", "duration", "relationship age"), ("ucif.canonical.customer.relationship.tenure",)),
        "ucif.meaning.financial.recurring_charge": ("Recurring Charge", "meaning", ("monthly charges", "monthly premium", "subscription fee", "recurring cost"), ("ucif.canonical.financial.recurring_charge",)),
        "ucif.meaning.financial.total_spend": ("Total Spend", "meaning", ("total charges", "total spend", "balance"), ("ucif.canonical.financial.total_spend",)),
        "ucif.meaning.support.interaction_count": ("Support Interaction Count", "meaning", ("support tickets", "support calls", "complaints", "billing issues"), ("ucif.canonical.support.interaction_count",)),
        "ucif.meaning.customer.activity_recency": ("Customer Activity Recency", "meaning", ("days since last order", "last visit", "recency"), ("ucif.canonical.customer.activity_recency",)),
        "ucif.meaning.customer.satisfaction_score": ("Customer Satisfaction Score", "meaning", ("satisfaction", "rating", "provider rating"), ("ucif.canonical.customer.satisfaction_score",)),
        "ucif.meaning.risk.churn": ("Churn Risk", "meaning", ("churn", "attrition", "exited", "churned"), ("ucif.canonical.risk.churn",)),
    }
    def __init__(self, root: Path | None = None) -> None:
        self._concepts = {OntologyId(k): OntologyConcept(OntologyId(k), *v[:3], tuple(OntologyId(x) for x in v[3])) for k, v in self._CORE.items()}
        if root and root.exists(): self._load(root)
    def _load(self, root: Path) -> None:
        for path in root.rglob("*.yaml"):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for item in payload.get("concepts", []) if isinstance(payload, dict) else []:
                oid = OntologyId(str(item["id"])); self._concepts[oid] = OntologyConcept(oid, str(item.get("label", oid.value)), str(item.get("kind", "meaning")), tuple(map(str, item.get("aliases", []))), tuple(OntologyId(x) for x in item.get("canonical_ids", [])))
    def get(self, ontology_id: OntologyId) -> OntologyConcept | None: return self._concepts.get(ontology_id)
    def meanings(self) -> tuple[OntologyConcept, ...]: return tuple(c for c in self._concepts.values() if c.kind == "meaning")
