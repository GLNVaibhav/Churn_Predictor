from __future__ import annotations
from ..domain.models import ColumnProfile, RelationshipProfile


class RelationshipDiscoverer:
    def discover(self, columns: tuple[ColumnProfile, ...]) -> tuple[RelationshipProfile, ...]:
        identifiers = [c for c in columns if c.identifier_likelihood >= .8]
        return tuple(RelationshipProfile(c.raw_column, "__dataset__", "candidate_key", c.identifier_likelihood, "High uniqueness and identifier naming evidence.") for c in identifiers)
