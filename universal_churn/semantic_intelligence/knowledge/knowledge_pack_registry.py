from __future__ import annotations
from dataclasses import dataclass
from ..domain.identifiers import OntologyId, SemanticVersion


@dataclass(frozen=True)
class KnowledgePack:
    pack_id: str; version: SemanticVersion; sector_id: OntologyId
    abbreviations: tuple[tuple[str, str], ...] = ()
    aliases: tuple[tuple[str, OntologyId], ...] = ()


class KnowledgePackRegistry:
    def __init__(self, packs: tuple[KnowledgePack, ...] = ()) -> None: self._packs = packs
    def resolve(self, sectors: tuple[OntologyId, ...]) -> tuple[KnowledgePack, ...]: return tuple(p for p in self._packs if p.sector_id in sectors)
    def abbreviations(self, sectors: tuple[OntologyId, ...]) -> dict[str, str]: return dict(pair for p in self.resolve(sectors) for pair in p.abbreviations)
