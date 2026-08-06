"""Console rendering for UDIF structured diagnostics."""
from __future__ import annotations

from .udif import UDIFRun


def _heading(title: str) -> None:
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)


def render(run: UDIFRun, *, include_root_cause: bool = True) -> None:
    if run.semantic:
        _heading("SEMANTIC INTELLIGENCE REPORT")
        print(f"Dataset: {run.semantic.rows} rows / {run.semantic.columns} columns")
        print(f"Sector: {run.semantic.sector}")
        print(f"Business Confidence: {run.semantic.business_confidence:.1%}")
        for item in run.semantic.concepts:
            print(f"\n{item.original_column}\n→ {item.business_concept}\n→ {item.canonical_concept}\nConfidence: {item.confidence:.2f}")
            if item.mapping_reason:
                print(f"Reason: {item.mapping_reason}")
    if run.canonical:
        _heading("CANONICAL FEATURE REPORT")
        print("Mapped")
        for item in run.canonical.mapped_features:
            print(f"✔ {item.canonical_feature} ({item.original_column}, {item.confidence:.2f})")
        print("\nMissing")
        for item in run.canonical.missing_features:
            print(f"✘ {item}")
        print(f"\nCoverage: {run.canonical.coverage_score:.1%}")
        print(f"Coverage Confidence: {run.canonical.coverage_confidence:.1%}")
        print(f"Readiness: {run.canonical.readiness}")
    if run.feature_matrix:
        _heading("FEATURE ENGINEERING DIAGNOSTICS")
        report = run.feature_matrix
        print(f"Rows / Columns: {report.rows} / {report.columns}")
        print("Columns: " + ", ".join(report.column_names))
        print(f"Missing Values: {report.missing_values}")
        print("Constant Columns: " + (", ".join(report.constant_columns) or "None"))
        print("Near-constant Columns: " + (", ".join(report.near_constant_columns) or "None"))
        print("Numeric Standard Deviations: " + ", ".join(f"{name}={value:.6g}" for name, value in report.numeric_standard_deviations))
        print("First Five Rows:")
        for row in report.first_five_rows: print(row)
    if run.feature_provenance:
        _heading("FEATURE PROVENANCE REPORT")
        for item in run.feature_provenance:
            sources = ", ".join(source or "None" for source in item.resolved_from) or "None"
            confidence = ", ".join(f"{value:.0%}" for value in item.confidence) or "—"
            print(f"{item.feature}: {item.status} | Concepts={', '.join(item.canonical_concepts) or '—'} | Source={sources} | Confidence={confidence} | Transformation={item.transformation}")
            if item.reason: print(f"Reason: {item.reason}")
    if run.prediction_coverage:
        report = run.prediction_coverage
        print(f"Prediction Coverage: {report.score:.1%} (resolved={report.resolved}, derived={report.derived}, compatibility={report.compatibility}, default={report.default}, intentional-neutral={report.intentional_neutral})")
    if run.model_input_health:
        _heading("MODEL INPUT HEALTH")
        report = run.model_input_health
        print(f"Health Result: {report.result}")
        for reason in report.reasons: print(f"Reason: {reason}")
    if run.prediction:
        _heading("PREDICTION DIAGNOSTICS")
        report = run.prediction
        print(f"Min / Max / Mean / Std: {report.minimum_probability:.6f} / {report.maximum_probability:.6f} / {report.mean_probability:.6f} / {report.standard_deviation:.6f}")
        print(f"Unique Probability Count: {report.unique_probability_count}")
        print("Histogram: " + "; ".join(f"[{bucket.lower:.1f}, {bucket.upper:.1f}): {bucket.count}" for bucket in report.histogram))
        print(f"Prediction Health: {report.health}")
    if include_root_cause:
        render_root_cause(run)


def render_root_cause(run: UDIFRun) -> None:
    """Render the evidence-only root cause report after downstream stages."""
    _heading("ROOT CAUSE ANALYSIS")
    for stage in run.root_cause_analysis().stages:
        print(f"{stage.stage}: {stage.status}")
        for evidence in stage.evidence: print(f"Evidence: {evidence}")
        if stage.recommendation: print(f"Recommendation: {stage.recommendation}")


def render_execution_terminated(guard: str, error: BaseException) -> None:
    """Explain a diagnostic guard termination without changing its exception."""
    _heading("EXECUTION TERMINATED")
    print(f"Guard: {guard}")
    print(f"Reason: {error}")
