"""Dataset-level artifact generation for the Enterprise Intelligence Console."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any

import pandas as pd


def build_quality_metrics(intelligence: Any, decision: Any) -> dict[str, float]:
    """Transparent framework-health metrics derived from existing typed outputs."""
    meanings = intelligence.business_meanings
    business = sum(item.confidence for item in meanings) / len(meanings) if meanings else 0.0
    coverage = intelligence.coverage.summary
    metrics = {
        "business_understanding_score": business,
        "semantic_maturity_score": intelligence.semantic_graph.consistency_score,
        "canonical_consistency": intelligence.canonical_mapping.overall_confidence,
        "knowledge_coverage": coverage.concept_coverage,
        "routing_reliability": intelligence.routing.decision.confidence,
        "decision_reliability": decision.overall_confidence if decision else 0.0,
    }
    metrics["overall_ucif_intelligence_score"] = sum(metrics.values()) / len(metrics)
    return metrics


def build_executive_narrative(intelligence: Any, decision: Any, evidence: Any) -> str:
    coverage = intelligence.coverage.summary
    routing = intelligence.routing.decision
    context = (
        "No external business context was supplied."
        if not evidence.evidences else f"Adaptive Business Intelligence found {evidence.overall_business_impact} impact: {evidence.assessment.dominant_driver}."
    )
    action = decision.recommended_action if decision else "Review the available evidence."
    return (
        f"Business semantics indicate {coverage.confidence_coverage:.0%} confidence and coverage is {coverage.readiness}. "
        f"Routing selected {routing.selected_pipeline} at {routing.confidence:.0%} confidence. "
        f"{context} Final recommendation: {action}"
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    return value


def build_feature_lineage(
    intelligence: Any, results: pd.DataFrame, source_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Create an evidence-only trace for each source column.

    This is deliberately descriptive: UCIF's typed intelligence outputs are
    reported as-is and model contribution is marked unavailable unless a
    row-level explainer supplied one.
    """
    graph = intelligence.semantic_graph
    entity_by_node = {
        node_id: entity.entity_type
        for entity in graph.entities for node_id in entity.node_ids
    }
    entity_by_label = {
        node.label: entity_by_node.get(node.node_id, "Unclassified")
        for node in graph.nodes
    }
    coverage = intelligence.coverage.summary
    routing = intelligence.routing.decision
    lineage = []
    for index, meaning in enumerate(intelligence.business_meanings):
        mapping = intelligence.canonical_mapping.mappings[index] if index < len(intelligence.canonical_mapping.mappings) else None
        canonical = mapping.chosen_concept.name if mapping else "Unmapped"
        lineage.append({
            "input_feature": (
                source_columns[index] if source_columns and index < len(source_columns)
                else mapping.column_name if mapping else f"feature_{index + 1}"
            ),
            "business_meaning": meaning.primary_business_concept,
            "business_confidence": meaning.confidence,
            "semantic_confidence": (
                _jsonable(meaning.semantic_confidence)
                if getattr(meaning, "semantic_confidence", None) is not None else None
            ),
            "semantic_entity": entity_by_label.get(meaning.primary_business_concept, "Unclassified"),
            "canonical_concept": canonical,
            "canonical_mapping_confidence": mapping.confidence if mapping else 0.0,
            "coverage": {
                "concept_coverage": coverage.concept_coverage,
                "semantic_coverage": coverage.semantic_coverage,
                "confidence_coverage": coverage.confidence_coverage,
                "readiness": coverage.readiness,
            },
            "routing": {
                "selected_pipeline": routing.selected_pipeline,
                "routing_confidence": routing.confidence,
                "influence": "Semantic evidence contributes through coverage and routing factors.",
            },
            "prediction_feature": canonical,
            "prediction_contribution": "not_available_without_row_level_explainer",
            "decision_contribution": "Coverage and routing evidence informs Decision Intelligence.",
        })
    return lineage


def write_enterprise_artifacts(
    results: pd.DataFrame,
    intelligence: Any,
    execution: dict[str, Any],
    output_path: str,
    decision_assessment: Any = None,
    reasoning_report: Any = None,
    business_evidence: Any = None,
    diagnostics: bool = False,
    source_columns: list[str] | None = None,
) -> list[Path]:
    """Persist row-level predictions separately from typed dataset diagnostics."""
    output_root = Path("outputs").resolve()
    prediction_path = output_root / "predictions" / Path(output_path).name
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    row_columns = [
        column for column in (
            "CustomerID", "Predicted_Churn", "Churn_Probability", "Risk_Level",
            "Prediction_Confidence",
        ) if column in results.columns
    ]
    results.loc[:, row_columns].to_csv(prediction_path, index=False)

    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    standard_payloads = {
        "execution_summary.json": {**execution, "coverage": intelligence.coverage,
                                   "routing": intelligence.routing.decision,
                                   "decision": decision_assessment,
                                   "adaptive_business_evidence": business_evidence,
                                   "quality_metrics": build_quality_metrics(intelligence, decision_assessment),
                                   "executive_narrative": build_executive_narrative(intelligence, decision_assessment, business_evidence)},
        "decision_report.json": {"decision": decision_assessment or {"status": "not_generated"},
                                 "adaptive_business_evidence": business_evidence},
    }
    paths = [prediction_path]
    for filename, payload in standard_payloads.items():
        path = reports_dir / filename
        path.write_text(json.dumps(_jsonable(payload), indent=2, default=str), encoding="utf-8")
        paths.append(path.resolve())
    if diagnostics:
        diagnostics_dir = output_root / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        diagnostic_payloads = {
            "coverage_report.json": intelligence.coverage,
            "routing_report.json": intelligence.routing,
            "canonical_mapping.json": intelligence.canonical_mapping,
            "reasoning_report.json": reasoning_report or {"status": "not_generated"},
            "semantic_graph.json": intelligence.semantic_graph,
            "feature_lineage.json": build_feature_lineage(intelligence, results, source_columns),
            "business_evidence.json": business_evidence,
        }
        for filename, payload in diagnostic_payloads.items():
            path = diagnostics_dir / filename
            path.write_text(json.dumps(_jsonable(payload), indent=2, default=str), encoding="utf-8")
            paths.append(path.resolve())
    return paths
