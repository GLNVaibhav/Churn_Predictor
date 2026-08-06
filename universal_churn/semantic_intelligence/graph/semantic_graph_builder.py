from __future__ import annotations
from .semantic_graph_models import DatasetSemanticGraph, SemanticGraphEdge, SemanticGraphNode
class SemanticGraphBuilder:
    def build(self, resolved_schema, graph_options: dict | None = None) -> DatasetSemanticGraph:
        nodes, edges = [], []
        for r in resolved_schema.resolutions:
            column_id = f"column:{r.column_position}"; nodes.append(SemanticGraphNode(column_id, "column", r.raw_column))
            if r.assignment.canonical_id:
                canonical = r.assignment.canonical_id.value; nodes.append(SemanticGraphNode(canonical, "canonical", canonical)); edges.append(SemanticGraphEdge(column_id, canonical, "resolves_to"))
        return DatasetSemanticGraph(tuple(nodes), tuple(edges))
