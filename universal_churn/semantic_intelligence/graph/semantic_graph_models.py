from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class SemanticGraphNode: node_id: str; kind: str; label: str
@dataclass(frozen=True)
class SemanticGraphEdge: source: str; target: str; relation: str
@dataclass(frozen=True)
class DatasetSemanticGraph: nodes: tuple[SemanticGraphNode, ...]; edges: tuple[SemanticGraphEdge, ...]
