from __future__ import annotations
from dataclasses import dataclass
from ..domain.identifiers import OntologyId
@dataclass(frozen=True)
class HumanOverride: raw_column: str; canonical_id: OntologyId; reviewer: str; reason: str; expires_at: str | None = None
class OverrideRegistry:
    def __init__(self) -> None: self._items: dict[str, HumanOverride] = {}
    def put(self, override: HumanOverride) -> None: self._items[override.raw_column] = override
    def get(self, raw_column: str) -> HumanOverride | None: return self._items.get(raw_column)
