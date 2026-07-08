"""
backend.models.execution_result
══════════════════════════════════════════════════════════════════════
``ExecutionResult`` — the backend's canonical immutable execution model.

This is NOT a framework object.  It belongs exclusively to the backend
and normalizes raw ``universal_churn`` output into structured sections
without computing, aggregating, or modifying any business values.

Dependency rule
---------------
    Backend → FrameworkAdapter → universal_churn

``universal_churn`` must never import anything from ``backend``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from ..utils import safe_get, to_serializable


# ══════════════════════════════════════════════════════════════════
# SECTION DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionMetadata:
    """Run context produced by the adapter — not framework business logic."""
    sector: str
    mode: str
    refused: bool = False
    refusal_reason: Optional[str] = None
    input_path: Optional[str] = None


@dataclass(frozen=True)
class PredictionsSection:
    """
    Raw prediction output preserved from the framework.

    The DataFrame is kept intact internally; it is never flattened
    away during normalization.
    """
    results_df: Optional[pd.DataFrame] = None
    attrs: Dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════
# CANONICAL EXECUTION MODEL
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExecutionResult:
    """
    Backend canonical execution model — one normalized view of everything
    a single framework run produced.

    Sections mirror the framework pipeline stages.  Every value is
    captured verbatim from framework output; nothing is computed here.
    """
    metadata: ExecutionMetadata
    predictions: PredictionsSection = field(default_factory=PredictionsSection)
    coverage: Optional[Dict[str, Any]] = None
    quality: Optional[Dict[str, Any]] = None
    routing: Optional[Any] = None
    reasoning: Optional[Any] = None
    decision: Optional[Any] = None
    reports: Optional[Dict[str, str]] = None
    diagnostics: Optional[Dict[str, Any]] = None

    # ── convenience accessors (read-only views into structured sections) ──

    @property
    def sector(self) -> str:
        return self.metadata.sector

    @property
    def mode(self) -> str:
        return self.metadata.mode

    @property
    def refused(self) -> bool:
        return self.metadata.refused

    @property
    def refusal_reason(self) -> Optional[str]:
        return self.metadata.refusal_reason

    @property
    def results_df(self) -> Optional[pd.DataFrame]:
        return self.predictions.results_df

    @property
    def explanation_report(self) -> Optional[Any]:
        return self.reasoning

    @property
    def decision_assessment(self) -> Optional[Any]:
        return self.decision

    @property
    def routing_decision(self) -> Optional[Any]:
        return self.routing

    # ── factory: raw framework bundle → ExecutionResult ──────────

    @classmethod
    def from_framework_output(
        cls,
        *,
        sector: str,
        mode: str,
        refused: bool = False,
        refusal_reason: Optional[str] = None,
        input_path: Optional[str] = None,
        results: Optional[pd.DataFrame] = None,
        coverage: Optional[Dict[str, Any]] = None,
        quality: Optional[Dict[str, Any]] = None,
        routing_decision: Optional[Any] = None,
        explanation_report: Optional[Any] = None,
        decision_assessment: Optional[Any] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionResult":
        """
        Normalize raw framework output into ``ExecutionResult``.

        Performs structural packaging only — no business computation,
        no field derivation, no value modification.
        """
        attrs: Dict[str, Any] = {}
        if results is not None and hasattr(results, "attrs"):
            attrs = dict(results.attrs)

        predictions = PredictionsSection(
            results_df=results,
            attrs=attrs,
        )

        return cls(
            metadata=ExecutionMetadata(
                sector=sector,
                mode=mode,
                refused=refused,
                refusal_reason=refusal_reason,
                input_path=input_path,
            ),
            predictions=predictions,
            coverage=coverage,
            quality=quality,
            routing=routing_decision,
            reasoning=explanation_report,
            decision=decision_assessment,
            diagnostics=diagnostics,
        )

    def with_reports(self, report_texts: Optional[Dict[str, str]]) -> "ExecutionResult":
        """Return a copy with report texts attached (immutable update)."""
        return ExecutionResult(
            metadata=self.metadata,
            predictions=self.predictions,
            coverage=self.coverage,
            quality=self.quality,
            routing=self.routing,
            reasoning=self.reasoning,
            decision=self.decision,
            reports=report_texts,
            diagnostics=self.diagnostics,
        )

    # ── serialization (for golden contract / regression artifacts) ──

    def to_dict(self, *, include_dataframe: bool = True) -> dict:
        """
        Serialize to a JSON-safe dict for persistence and golden contracts.

        Framework objects (RoutingDecision, DecisionAssessment, etc.) are
        recursively converted via ``to_serializable``.  The DataFrame is
        included as records when ``include_dataframe`` is True.
        """
        predictions_dict: Dict[str, Any] = {"attrs": to_serializable(self.predictions.attrs)}
        if include_dataframe and self.predictions.results_df is not None:
            df = self.predictions.results_df
            predictions_dict["columns"] = list(df.columns)
            predictions_dict["records"] = df.to_dict(orient="records")

        routing_dict = _serialize_routing(self.routing)
        reasoning_dict = _serialize_reasoning(self.reasoning)
        decision_dict = _serialize_decision(self.decision)

        return {
            "metadata": to_serializable(self.metadata),
            "predictions": predictions_dict,
            "coverage": to_serializable(self.coverage),
            "quality": to_serializable(self.quality),
            "routing": routing_dict,
            "reasoning": reasoning_dict,
            "decision": decision_dict,
            "reports": to_serializable(self.reports),
            "diagnostics": to_serializable(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionResult":
        """Reconstruct from ``to_dict()`` output (golden contract round-trip)."""
        meta_raw = d.get("metadata") or {}
        metadata = ExecutionMetadata(
            sector=meta_raw.get("sector", ""),
            mode=meta_raw.get("mode", "auto"),
            refused=bool(meta_raw.get("refused", False)),
            refusal_reason=meta_raw.get("refusal_reason"),
            input_path=meta_raw.get("input_path"),
        )

        pred_raw = d.get("predictions") or {}
        results_df = None
        if "records" in pred_raw and "columns" in pred_raw:
            results_df = pd.DataFrame(pred_raw["records"], columns=pred_raw["columns"])
            attrs = pred_raw.get("attrs") or {}
            if attrs:
                results_df.attrs.update(attrs)

        predictions = PredictionsSection(
            results_df=results_df,
            attrs=dict(pred_raw.get("attrs") or {}),
        )

        return cls(
            metadata=metadata,
            predictions=predictions,
            coverage=d.get("coverage"),
            quality=d.get("quality"),
            routing=d.get("routing"),
            reasoning=d.get("reasoning"),
            decision=d.get("decision"),
            reports=d.get("reports"),
            diagnostics=d.get("diagnostics"),
        )


# ══════════════════════════════════════════════════════════════════
# SERIALIZATION HELPERS (structural only — no value changes)
# ══════════════════════════════════════════════════════════════════

def _coerce_value(val: Any) -> Any:
    """Convert Enum-like objects to their scalar value for JSON safety."""
    if val is None:
        return None
    if isinstance(val, dict):
        return {k: _coerce_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_coerce_value(v) for v in val]
    if hasattr(val, "value") and not isinstance(val, (str, int, float, bool)):
        inner = getattr(val, "value")
        if not isinstance(inner, type):
            return inner
    return val


def _serialize_routing(routing: Any) -> Optional[dict]:
    if routing is None:
        return None
    if isinstance(routing, dict):
        return to_serializable(_coerce_value(routing))
    fields_dict: Dict[str, Any] = {}
    for name in (
        "selected_model", "selected_pipeline", "prediction_mode",
        "routing_reason", "coverage_score", "coverage_band",
        "quality_score", "quality_status", "concept_confidence",
        "reliability", "model_artifact", "warnings",
    ):
        val = safe_get(routing, name)
        if val is not None:
            fields_dict[name] = _coerce_value(val)
    if hasattr(routing, "report_fields"):
        try:
            fields_dict.update(_coerce_value(routing.report_fields()))
        except Exception:
            pass
    return fields_dict or to_serializable(_coerce_value(routing))


def _serialize_reasoning(reasoning: Any) -> Optional[dict]:
    if reasoning is None:
        return None
    narrative = safe_get(reasoning, "dataset_narrative")
    dataset = safe_get(reasoning, "dataset_explanation")
    return {
        "headline": safe_get(narrative, "headline"),
        "reason_text": safe_get(narrative, "reason_text"),
        "recommendation_text": safe_get(narrative, "recommendation_text"),
        "overall_business_health": safe_get(dataset, "overall_business_health"),
        "overall_customer_risk": safe_get(dataset, "overall_customer_risk"),
        "dominant_findings": list(safe_get(dataset, "dominant_findings", []) or []),
    }


def _serialize_decision(decision: Any) -> Optional[dict]:
    if decision is None:
        return None
    readiness = safe_get(decision, "decision_readiness")
    risk = safe_get(decision, "risk_level")
    return {
        "decision_readiness": getattr(readiness, "value", readiness),
        "overall_confidence": safe_get(decision, "overall_confidence"),
        "business_confidence": safe_get(decision, "business_confidence"),
        "technical_confidence": safe_get(decision, "technical_confidence"),
        "evidence_strength": safe_get(decision, "evidence_strength"),
        "risk_level": getattr(risk, "value", risk),
        "recommended_action": safe_get(decision, "recommended_action"),
        "warnings": list(safe_get(decision, "warnings", []) or []),
    }


def extract_raw_framework_output(result: ExecutionResult) -> dict:
    """
    Extract the raw framework output bundle for golden contract artifacts.

    Returns the pre-normalization shape that ``FrameworkAdapter`` captured
    from ``universal_churn`` — used by ``scripts/generate_golden_contract.py``.
    """
    raw: Dict[str, Any] = {
        "sector": result.sector,
        "mode": result.mode,
        "refused": result.refused,
        "refusal_reason": result.refusal_reason,
        "coverage": to_serializable(result.coverage),
        "quality": to_serializable(result.quality),
        "routing_decision": _serialize_routing(result.routing),
        "explanation_report": _serialize_reasoning(result.reasoning),
        "decision_assessment": _serialize_decision(result.decision),
    }
    if result.results_df is not None:
        raw["results"] = {
            "columns": list(result.results_df.columns),
            "records": result.results_df.to_dict(orient="records"),
            "attrs": to_serializable(result.predictions.attrs),
        }
    else:
        raw["results"] = None
    return raw
