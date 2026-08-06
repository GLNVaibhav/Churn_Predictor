"""Explainable semantic-confidence value object used by Business Meaning reporting."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticConfidence:
    score: float
    reason: str
    evidence: tuple[str, ...]


def from_pack_match(match_type: str, domain_match: bool, canonical_available: bool, relationship_consistent: bool, alias: str) -> SemanticConfidence:
    """Average independently observable evidence signals; no hidden weighting."""
    match_strength = {"exact": 1.0, "synonym": 0.8, "alias": 0.7}[match_type]
    signals = (match_strength, float(domain_match), float(canonical_available), float(relationship_consistent))
    score = sum(signals) / len(signals)
    evidence = tuple(label for label, present in (
        (f"{match_type} knowledge-pack match: {alias}", True),
        ("sector domain match", domain_match),
        ("canonical concept declared by knowledge pack", canonical_available),
        ("knowledge-pack relationships available", relationship_consistent),
    ) if present)
    return SemanticConfidence(score, "Confidence is the mean of observed semantic evidence signals.", evidence)
