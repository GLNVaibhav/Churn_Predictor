"""
universal_churn/prediction_explanation.py
══════════════════════════════════════════════════════════════════════
Prediction Explanation Layer — Version 7, Chunk 5.

Unifies coverage, quality, concept confidence, routing, business
reasoning, and the Knowledge Base into ONE coherent explanation per
prediction — without recomputing or modifying any of them.

Non-interference guarantee
-----------------------------
This module is a pure, read-only CONSUMER of:
    - coverage.py's compute_coverage_score() dict          (via results.attrs['coverage'])
    - quality_gate.py's run_quality_gate() dict             (via results.attrs['quality'])
    - routing.py's RoutingDecision                          (via results.attrs['routing_decision'])
    - business_reasoning.py's run_business_reasoning()      (called fresh, read-only, on raw input)
    - knowledge_base.py's KnowledgeBase                     (via knowledge_loader singleton)

It does not import, patch, or re-implement any of coverage.py,
quality_gate.py, routing.py, feature_engineering.py,
business_concept_graph.py, business_reasoning.py, or knowledge_base.py's
internals. It calls exactly one function on business_reasoning.py
(`run_business_reasoning`, already public and already read-only /
diagnostics-only per that module's own docstring) and otherwise only
reads dicts/objects prediction pipelines already produce.

Nothing in cli.py, sector_pipeline.py, or universal_pipeline.py is
required to change its RETURN VALUE for this module to work — the
enrichment happens as an optional, best-effort, exception-safe step
layered on top (see prediction_explanation_report.py's
`build_and_attach_explanations()`, the one function cli.py calls).

All dataclasses here are frozen — an explanation, once built, does not
mutate. No prediction logic, no scoring, no ML computation lives here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from .knowledge_base import KnowledgeBase
from .knowledge_loader import get_default_knowledge_base
from .business_reasoning import (
    ReasoningReport, BusinessFinding, BusinessInference,
    run_business_reasoning,
)
from .routing import RoutingDecision


# ══════════════════════════════════════════════════════════════════
# PART 1 — DATACLASSES (derived information only)
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PredictionSummary:
    """What was predicted — for one row, or None-indexed for the dataset."""
    row_index: int | None
    customer_id: str | None
    predicted_label: str          # 'Yes' | 'No'
    probability: float
    risk_level: str
    sector: str
    prediction_model: str
    prediction_mode: str

    def to_dict(self) -> dict:
        return {
            'row_index': self.row_index,
            'customer_id': self.customer_id,
            'predicted_label': self.predicted_label,
            'probability': self.probability,
            'risk_level': self.risk_level,
            'sector': self.sector,
            'prediction_model': self.prediction_model,
            'prediction_mode': self.prediction_mode,
        }


@dataclass(frozen=True)
class PredictionEvidenceItem:
    """One piece of evidence, tagged with the existing object that produced it."""
    name: str
    value: str
    source: str   # e.g. 'CoverageResult', 'QualityResult', 'RoutingDecision',
                   # 'ConceptConfidenceReport', 'ReasoningReport'

    def to_dict(self) -> dict:
        return {'name': self.name, 'value': self.value, 'source': self.source}


@dataclass(frozen=True)
class PredictionEvidence:
    """
    Aggregated evidence for one explanation. Every field is copied
    from an existing framework output — nothing here is computed.
    """
    coverage_score: float
    coverage_band: str
    concept_confidence: float | None
    quality_status: str
    routing_selected_model: str
    routing_reason: str
    business_finding_ids: tuple[str, ...]
    items: tuple[PredictionEvidenceItem, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            'coverage_score': self.coverage_score,
            'coverage_band': self.coverage_band,
            'concept_confidence': self.concept_confidence,
            'quality_status': self.quality_status,
            'routing_selected_model': self.routing_selected_model,
            'routing_reason': self.routing_reason,
            'business_finding_ids': list(self.business_finding_ids),
            'items': [i.to_dict() for i in self.items],
        }


@dataclass(frozen=True)
class PredictionRecommendation:
    """The single top recommendation — sourced from the Knowledge Base
    via the highest-severity fired BusinessFinding, if any."""
    finding_id: str | None
    recommendation_text: str

    def to_dict(self) -> dict:
        return {'finding_id': self.finding_id, 'recommendation_text': self.recommendation_text}


@dataclass(frozen=True)
class PredictionReliability:
    """Structured reliability reasoning — replaces a bare 'Low' label."""
    level: str
    reasons: tuple[str, ...]
    missing_features: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            'level': self.level,
            'reasons': list(self.reasons),
            'missing_features': list(self.missing_features),
        }


@dataclass(frozen=True)
class PredictionNarrative:
    """Deterministic, template-assembled narrative text. No LLM, no
    generative AI — pure string formatting over existing state."""
    headline: str
    reason_text: str
    findings_text: str
    recommendation_text: str
    acceptance_text: str
    full_text: str

    def to_dict(self) -> dict:
        return {
            'headline': self.headline,
            'reason_text': self.reason_text,
            'findings_text': self.findings_text,
            'recommendation_text': self.recommendation_text,
            'acceptance_text': self.acceptance_text,
            'full_text': self.full_text,
        }


@dataclass(frozen=True)
class PredictionExplanation:
    """One row's (or the dataset's) full explanation."""
    summary: PredictionSummary
    evidence: PredictionEvidence
    recommendation: PredictionRecommendation
    reliability: PredictionReliability
    narrative: PredictionNarrative

    def to_dict(self) -> dict:
        return {
            'summary': self.summary.to_dict(),
            'evidence': self.evidence.to_dict(),
            'recommendation': self.recommendation.to_dict(),
            'reliability': self.reliability.to_dict(),
            'narrative': self.narrative.to_dict(),
        }


@dataclass(frozen=True)
class DatasetExplanation:
    """Part 6 — dataset-level roll-up."""
    rows_analyzed: int
    predicted_churners: int
    average_probability: float
    risk_distribution: dict[str, int]
    dominant_findings: tuple[str, ...]
    business_strengths: tuple[str, ...]
    business_weaknesses: tuple[str, ...]
    overall_business_health: str
    overall_customer_risk: str
    top_recommendation: str

    def to_dict(self) -> dict:
        return {
            'rows_analyzed': self.rows_analyzed,
            'predicted_churners': self.predicted_churners,
            'average_probability': self.average_probability,
            'risk_distribution': self.risk_distribution,
            'dominant_findings': list(self.dominant_findings),
            'business_strengths': list(self.business_strengths),
            'business_weaknesses': list(self.business_weaknesses),
            'overall_business_health': self.overall_business_health,
            'overall_customer_risk': self.overall_customer_risk,
            'top_recommendation': self.top_recommendation,
        }


@dataclass(frozen=True)
class PredictionExplanationReport:
    """
    The full Chunk 5 deliverable for one prediction run: a dataset-level
    explanation plus one PredictionExplanation per row. Holds a
    reference to the ReasoningReport it was built from (Part 4's "each
    evidence item must reference the existing object that produced it").
    """
    sector: str
    generated_at: str
    dataset_explanation: DatasetExplanation
    dataset_narrative: PredictionNarrative
    row_explanations: tuple[PredictionExplanation, ...]
    reasoning_report: ReasoningReport

    def to_dict(self) -> dict:
        return {
            'sector': self.sector,
            'generated_at': self.generated_at,
            'dataset_explanation': self.dataset_explanation.to_dict(),
            'dataset_narrative': self.dataset_narrative.to_dict(),
            'row_explanations': [r.to_dict() for r in self.row_explanations],
        }


# ══════════════════════════════════════════════════════════════════
# PART 3 — NARRATIVE TEMPLATES (deterministic, no LLM)
# ══════════════════════════════════════════════════════════════════

def _findings_text(findings: list[BusinessFinding]) -> str:
    if not findings:
        return "No business findings fired for this input."
    parts = []
    for f in findings:
        parts.append(
            f"{f.title} ({f.severity.value}, confidence {f.confidence*100:.0f}%): "
            f"{f.explanation}"
        )
    return " ".join(parts)


def _reason_text(findings: list[BusinessFinding], reasoning: ReasoningReport) -> str:
    if findings:
        top = max(findings, key=lambda f: {
            'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3,
        }[f.severity.value])
        return top.explanation
    if reasoning.summary and reasoning.summary.dominant_failure_reason:
        return reasoning.summary.dominant_failure_reason
    return "No specific business driver was strong enough to explain this prediction."


def _recommendation_for(
    findings: list[BusinessFinding],
    knowledge_base: KnowledgeBase,
) -> PredictionRecommendation:
    if not findings:
        return PredictionRecommendation(finding_id=None, recommendation_text="")
    top = max(findings, key=lambda f: {
        'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3,
    }[f.severity.value])
    text = top.recommendation or knowledge_base.get_recommendation(top.finding_id)
    return PredictionRecommendation(finding_id=top.finding_id, recommendation_text=text)


def _acceptance_text(
    coverage_band: str,
    concepts_reconstructable: bool | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
) -> str:
    coverage_phrase = f"Coverage was {coverage_band.lower()}"
    if concepts_reconstructable is True:
        concept_phrase = "concepts remained reconstructable"
    elif concepts_reconstructable is False:
        concept_phrase = "concepts could not be fully reconstructed"
    else:
        concept_phrase = "concept reconstructability was not evaluated"
    quality_phrase = (
        "quality gate passed" if quality_status != 'FAIL' else "quality gate failed"
    )
    model_phrase = (
        f"{routing_decision.selected_model.value} selected"
        if routing_decision is not None else "model selection unavailable"
    )
    return f"{coverage_phrase}, {concept_phrase}, {quality_phrase}, {model_phrase}."


def _headline_for(predicted_label: str) -> str:
    return "HIGH CHURN" if predicted_label == 'Yes' else "LOW CHURN"


def _build_narrative(
    predicted_label: str,
    findings: list[BusinessFinding],
    reasoning: ReasoningReport,
    recommendation: PredictionRecommendation,
    coverage_band: str,
    concepts_reconstructable: bool | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
) -> PredictionNarrative:
    headline = _headline_for(predicted_label)
    reason = _reason_text(findings, reasoning)
    findings_text = _findings_text(findings)
    acceptance = _acceptance_text(
        coverage_band, concepts_reconstructable, quality_status, routing_decision,
    )
    rec_text = recommendation.recommendation_text or "No specific recommendation available."

    full_text = (
        f"Prediction: {headline}\n"
        f"Reason: {reason}\n"
        f"Business Findings: {findings_text}\n"
        f"Recommendation: {rec_text}\n"
        f"Prediction accepted because: {acceptance}"
    )
    return PredictionNarrative(
        headline=headline, reason_text=reason, findings_text=findings_text,
        recommendation_text=rec_text, acceptance_text=acceptance, full_text=full_text,
    )


# ══════════════════════════════════════════════════════════════════
# PART 5 — RELIABILITY EXPLANATION
# ══════════════════════════════════════════════════════════════════

def _missing_features(coverage: dict | None) -> tuple[str, ...]:
    if not coverage:
        return ()
    missing = list(coverage.get('missing_critical', [])) + list(
        coverage.get('missing_high_impact', [])
    )
    seen: list[str] = []
    for f in missing:
        if f not in seen:
            seen.append(f)
    return tuple(seen)


def _build_reliability(
    routing_decision: RoutingDecision | None,
    coverage: dict | None,
    quality_status: str,
) -> PredictionReliability:
    if routing_decision is None:
        return PredictionReliability(level="Unknown", reasons=(), missing_features=())

    reasons: list[str] = [
        f"Coverage {routing_decision.coverage_score*100:.1f}%",
    ]
    if routing_decision.concept_confidence is not None:
        reasons.append(f"Concept Confidence {routing_decision.concept_confidence*100:.1f}%")
    reasons.append(f"Quality {'PASS' if quality_status != 'FAIL' else 'FAIL'}")
    reasons.append(f"{routing_decision.selected_model.value} selected")
    if routing_decision.warnings:
        reasons.extend(routing_decision.warnings)

    return PredictionReliability(
        level=routing_decision.reliability.value,
        reasons=tuple(reasons),
        missing_features=_missing_features(coverage),
    )


# ══════════════════════════════════════════════════════════════════
# EVIDENCE ASSEMBLY (Part 4)
# ══════════════════════════════════════════════════════════════════

def _build_evidence(
    coverage: dict | None,
    quality_status: str,
    routing_decision: RoutingDecision | None,
    findings: list[BusinessFinding],
) -> PredictionEvidence:
    coverage_score = coverage.get('coverage_score', 0.0) if coverage else 0.0
    coverage_band = coverage.get('status', 'Unknown') if coverage else 'Unknown'
    concept_confidence = None
    if coverage and coverage.get('concept_confidence'):
        concept_confidence = coverage['concept_confidence'].get('overall_confidence')

    items = [
        PredictionEvidenceItem(
            name="Coverage Score", value=f"{coverage_score*100:.1f}%",
            source="CoverageResult",
        ),
        PredictionEvidenceItem(
            name="Coverage Band", value=coverage_band, source="CoverageResult",
        ),
        PredictionEvidenceItem(
            name="Concept Confidence",
            value=f"{concept_confidence*100:.1f}%" if concept_confidence is not None else "N/A",
            source="ConceptConfidenceReport",
        ),
        PredictionEvidenceItem(
            name="Quality Status", value=quality_status, source="QualityResult",
        ),
    ]
    if routing_decision is not None:
        items.append(PredictionEvidenceItem(
            name="Selected Model", value=routing_decision.selected_model.value,
            source="RoutingDecision",
        ))
        items.append(PredictionEvidenceItem(
            name="Routing Reason", value=routing_decision.routing_reason,
            source="RoutingDecision",
        ))
    for f in findings:
        items.append(PredictionEvidenceItem(
            name=f"Business Finding: {f.title}",
            value=f"{f.severity.value} ({f.confidence*100:.0f}%)",
            source="ReasoningReport",
        ))

    return PredictionEvidence(
        coverage_score=coverage_score,
        coverage_band=coverage_band,
        concept_confidence=concept_confidence,
        quality_status=quality_status,
        routing_selected_model=(
            routing_decision.selected_model.value if routing_decision else "Unknown"
        ),
        routing_reason=routing_decision.routing_reason if routing_decision else "",
        business_finding_ids=tuple(f.finding_id for f in findings),
        items=tuple(items),
    )


# ══════════════════════════════════════════════════════════════════
# PART 2 — BUILDER
# ══════════════════════════════════════════════════════════════════

class PredictionExplanationBuilder:
    """
    Assembles a PredictionExplanationReport from existing framework
    outputs. Does not compute coverage, quality, routing, or
    prediction — it reads them (as dicts/objects already produced by
    the prediction path) and calls the existing, unmodified
    business_reasoning.run_business_reasoning() exactly once.
    """

    def __init__(self, knowledge_base: KnowledgeBase | None = None) -> None:
        self.knowledge_base = knowledge_base or get_default_knowledge_base()

    def build(
        self,
        df_raw: pd.DataFrame,
        sector: str,
        results: pd.DataFrame,
        coverage: dict | None,
        quality: dict | None,
        routing_decision: RoutingDecision | None,
        reasoning_report: ReasoningReport | None = None,
    ) -> PredictionExplanationReport:
        """
        Parameters
        ----------
        df_raw : the raw input DataFrame used for this prediction run
            (read fresh from the same input file cli.py already read —
            never mutated, only passed to run_business_reasoning()).
        results : the ALREADY-COMPUTED prediction results DataFrame
            (Predicted_Churn, Churn_Probability, Risk_Level, CustomerID,
            Prediction_Model, Prediction_Mode columns). Not mutated here.
        coverage / quality : the dicts already attached to
            results.attrs['coverage'] / results.attrs['quality'].
        routing_decision : the RoutingDecision already attached to
            results.attrs['routing_decision'] (may be None).
        reasoning_report : optional precomputed ReasoningReport; if
            omitted, run_business_reasoning(df_raw, sector) is called.
        """
        if reasoning_report is None:
            try:
                reasoning_report = run_business_reasoning(df_raw, sector)
            except Exception as exc:
                reasoning_report = ReasoningReport(
                    sector=sector,
                    generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    inferences={}, findings=[], summary=None,
                )
                reasoning_report.to_dict()  # no-op; keeps shape consistent
                print(f"  WARNING: business reasoning failed ({exc}); "
                      f"explanation will omit findings.")

        quality_status = (
            'FAIL' if (quality and quality.get('leakage_detected')) else
            ('WARN' if quality and (
                [c for c in quality.get('failed_columns', [])
                 if c not in quality.get('leakage_flagged', [])]
                or quality.get('leakage_warned')
            ) else 'GOOD')
        ) if quality is not None else (
            routing_decision.quality_status if routing_decision else 'Unknown'
        )

        findings = list(reasoning_report.findings)
        recommendation = _recommendation_for(findings, self.knowledge_base)
        evidence = _build_evidence(coverage, quality_status, routing_decision, findings)
        reliability = _build_reliability(routing_decision, coverage, quality_status)
        concepts_reconstructable = (
            coverage.get('concept_confidence', {}).get('concepts_reconstructable')
            if coverage else None
        )

        dataset_narrative = _build_narrative(
            predicted_label=self._dominant_label(results),
            findings=findings, reasoning=reasoning_report, recommendation=recommendation,
            coverage_band=evidence.coverage_band,
            concepts_reconstructable=concepts_reconstructable,
            quality_status=quality_status, routing_decision=routing_decision,
        )

        dataset_explanation = self._build_dataset_explanation(
            results, reasoning_report, recommendation,
        )

        row_explanations = tuple(
            self._build_row_explanation(
                idx, row, sector, evidence, recommendation, reliability,
                findings, reasoning_report, coverage, quality_status, routing_decision,
                concepts_reconstructable,
            )
            for idx, row in results.iterrows()
        )

        return PredictionExplanationReport(
            sector=sector,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            dataset_explanation=dataset_explanation,
            dataset_narrative=dataset_narrative,
            row_explanations=row_explanations,
            reasoning_report=reasoning_report,
        )

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _dominant_label(results: pd.DataFrame) -> str:
        if 'Predicted_Churn' not in results.columns or results.empty:
            return 'No'
        counts = results['Predicted_Churn'].value_counts()
        return counts.idxmax() if not counts.empty else 'No'

    def _build_dataset_explanation(
        self,
        results: pd.DataFrame,
        reasoning_report: ReasoningReport,
        recommendation: PredictionRecommendation,
    ) -> DatasetExplanation:
        rows = len(results)
        churners = int((results['Predicted_Churn'] == 'Yes').sum()) if rows else 0
        avg_prob = float(results['Churn_Probability'].mean()) if rows else 0.0
        risk_dist = (
            results['Risk_Level'].value_counts().to_dict()
            if 'Risk_Level' in results.columns else {}
        )
        dominant_findings = tuple(f.title for f in reasoning_report.findings)
        summary = reasoning_report.summary
        return DatasetExplanation(
            rows_analyzed=rows,
            predicted_churners=churners,
            average_probability=round(avg_prob, 4),
            risk_distribution=risk_dist,
            dominant_findings=dominant_findings,
            business_strengths=tuple(summary.business_strengths) if summary else (),
            business_weaknesses=tuple(summary.business_weaknesses) if summary else (),
            overall_business_health=summary.overall_business_health if summary else "Unknown",
            overall_customer_risk=summary.overall_customer_risk if summary else "Unknown",
            top_recommendation=recommendation.recommendation_text,
        )

    def _build_row_explanation(
        self,
        idx: int,
        row: pd.Series,
        sector: str,
        evidence: PredictionEvidence,
        recommendation: PredictionRecommendation,
        reliability: PredictionReliability,
        findings: list[BusinessFinding],
        reasoning_report: ReasoningReport,
        coverage: dict | None,
        quality_status: str,
        routing_decision: RoutingDecision | None,
        concepts_reconstructable: bool | None,
    ) -> PredictionExplanation:
        predicted_label = row.get('Predicted_Churn', 'No')
        summary = PredictionSummary(
            row_index=int(idx) if isinstance(idx, (int,)) else None,
            customer_id=str(row.get('CustomerID')) if 'CustomerID' in row else None,
            predicted_label=predicted_label,
            probability=float(row.get('Churn_Probability', 0.0)),
            risk_level=str(row.get('Risk_Level', 'Unknown')),
            sector=sector,
            prediction_model=str(row.get('Prediction_Model', 'Unknown')),
            prediction_mode=str(row.get('Prediction_Mode', 'Unknown')),
        )
        narrative = _build_narrative(
            predicted_label=predicted_label, findings=findings, reasoning=reasoning_report,
            recommendation=recommendation, coverage_band=evidence.coverage_band,
            concepts_reconstructable=concepts_reconstructable,
            quality_status=quality_status, routing_decision=routing_decision,
        )
        return PredictionExplanation(
            summary=summary, evidence=evidence, recommendation=recommendation,
            reliability=reliability, narrative=narrative,
        )