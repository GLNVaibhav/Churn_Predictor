"""
universal_churn/concept_graph_report.py
══════════════════════════════════════════════════════════════════════
Business Concept Graph Diagnostics — Version 7, Chunk 2, Part 4.

Human-readable report over a resolved BusinessConceptGraph (i.e. the
output of business_concept_graph.resolve_graph_confidence()), in the
same visual style as coverage.py / quality_gate.py /
concept_confidence.py's existing reports.

This module does NOT compute anything new — it only formats
BusinessConceptGraph / BusinessConceptNode data that already exists.
"""
from __future__ import annotations

from .business_concept_graph import BusinessConceptGraph, resolve_graph_confidence

import pandas as pd


def generate_concept_graph_report(graph: BusinessConceptGraph, sector: str = "") -> str:
    """
    Build the "Business Concept Graph Report" text, e.g.:

        Recurring Commitment
          Confidence        82%
          Resolved          Recurring_Cost, Tenure_Raw
          Missing           Subscription_Type, Contract_Length
          Dependency Health GOOD
    """
    sep = '─' * 60
    lines = [sep, "  BUSINESS CONCEPT GRAPH REPORT" +
             (f"  [{sector.upper()}]" if sector else ""), sep]

    for concept_id, node in graph.nodes.items():
        health_icon = {'GOOD': '✔', 'FAIR': '△', 'POOR': '✖'}[node.dependency_health()]
        lines.append("")
        lines.append(f"  {node.display_name}")
        lines.append(f"    Confidence         {node.confidence*100:5.1f}%")
        lines.append(
            f"    Resolved           "
            f"{', '.join(node.resolved_fields) if node.resolved_fields else 'None'}"
        )
        lines.append(
            f"    Missing            "
            f"{', '.join(node.missing_fields) if node.missing_fields else 'None'}"
        )
        lines.append(f"    Dependency Health  {health_icon} {node.dependency_health()}")
        path = node.metadata.get('reconstruction_path')
        if path:
            lines.append(f"    Reconstruction     {path}")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def print_concept_graph_report(graph: BusinessConceptGraph, sector: str = "") -> None:
    print(generate_concept_graph_report(graph, sector))


def concept_graph_report_for(df_input: pd.DataFrame, sector: str) -> str:
    """Convenience one-shot: resolve the graph for this input file and
    return its formatted report, without the caller needing to import
    business_concept_graph directly."""
    graph = resolve_graph_confidence(df_input, sector)
    return generate_concept_graph_report(graph, sector)
