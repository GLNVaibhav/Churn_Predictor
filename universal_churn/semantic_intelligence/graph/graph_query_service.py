from __future__ import annotations
class GraphQueryService:
    def neighbors(self, graph, node_id: str): return tuple(e.target for e in graph.edges if e.source == node_id)
