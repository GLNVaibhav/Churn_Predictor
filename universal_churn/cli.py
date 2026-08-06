"""
universal_churn/cli.py
Command-line interface for the universal churn prediction framework.

Routing note
------------
The auto-mode branch previously branched directly on
compute_coverage_score()'s 'Refused'/'Full'/'Fallback' values. It now
computes coverage + quality, calls routing.route() exactly once, and
dispatches purely on RoutingDecision.selected_model — the CLI makes no
routing decisions of its own, matching sector_pipeline.py and
universal_pipeline.py.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4
import pandas as pd
from .config import PIPELINE_VERSION, SECTOR_CONFIG
from .preprocessing import detect_sector
from .reporting import _maybe_emit_report
from .prediction_explanation_report import (
    build_and_attach_explanations, print_prediction_explanation_report,
    print_execution_summary,
)
from .decision_report import (
    build_and_attach_decision_intelligence, print_decision_report,
)
from .quality_gate import run_quality_gate
from .sector_pipeline import SectorPipeline
from .universal_pipeline import train_universal_model, predict_universal
from .intelligence_pipeline import infer_intelligence
from .console_ui import (
    print_artifact, print_banner, print_bar, print_count_bar, print_metric,
    print_stage_header, print_success, print_summary, print_timing, print_warning,
)
from .enterprise_reporting import build_executive_narrative, build_feature_lineage, build_quality_metrics, write_enterprise_artifacts
from .adaptive_business import AdaptiveBusinessEngine, ExecutionContext, load_business_context
from .udif import DiagnosticLevel, active_run, configure
from .udif_rendering import render as render_udif, render_root_cause


def _render_enterprise_console(
    execution_id: str, args: argparse.Namespace, input_df: pd.DataFrame,
    sector: str, intelligence, results: pd.DataFrame, elapsed: float,
    prediction_time: float, artifacts: list[Path], lineage: list[dict], business_evidence, abil_time: float,
) -> None:
    """Render a read-only, stage-oriented view of the typed execution."""
    assessment = results.attrs.get("decision_assessment")
    print_banner(execution_id, args.mode, str(Path(args.input).resolve()), PIPELINE_VERSION)

    print_stage_header(1, "Data Profiling", "Validate the supplied dataset and establish execution context.")
    print_success("Dataset loaded successfully")
    print_metric("Dataset Name", Path(args.input).name)
    print_metric("Rows / Columns", f"{len(input_df)} / {len(input_df.columns)}")
    print_metric("Missing Values", int(input_df.isna().sum().sum()))
    print_metric("Duplicate Rows", int(input_df.duplicated().sum()))
    print_metric("Memory Usage", f"{input_df.memory_usage(deep=True).sum() / 1024:.1f} KB")
    print_metric("Detected Sector", sector.upper())
    print_metric("Target Column", SECTOR_CONFIG[sector]["target_col"])

    meanings = intelligence.business_meanings
    print_stage_header(2, "Business Meaning Intelligence", "Infer business semantics from column names and values.")
    print_success(f"{len(meanings)} business concepts inferred")
    print_metric("Business Confidence", f"{sum(m.confidence for m in meanings) / len(meanings):.1%}")
    print_metric("Top Concepts", ", ".join(m.primary_business_concept for m in meanings[:5]))
    print_metric("Top Domains", ", ".join(sorted({m.domain for m in meanings})))
    print_metric("Feature Lineage", "Input Feature -> Business Meaning")
    for item in lineage:
        print_metric(item["input_feature"], item["business_meaning"])
    low = [m.primary_business_concept for m in meanings if m.confidence < 0.6]
    if low:
        print_warning("Low-confidence semantics: " + ", ".join(low[:5]) + ". These reduce coverage confidence.")
    print_timing(intelligence.stage_timings["business_meaning"])

    context = intelligence.context
    print_stage_header(3, "Context Validation", "Check whether column-level meanings agree on a dataset domain.")
    print_metric("Dominant Domain", context.dataset_domain)
    print_metric("Agreement", f"{context.consensus_score:.1%}")
    for domain, votes in sorted(context.domain_votes.items(), key=lambda item: item[1], reverse=True):
        print_bar(domain, votes / max(1, sum(context.domain_votes.values())))
    print_metric("Validation Result", context.dataset_health)
    if context.validation_messages:
        print_warning(context.validation_messages[0])
    print_timing(intelligence.stage_timings["context_validation"])

    graph = intelligence.semantic_graph
    print_stage_header(4, "Semantic Knowledge Graph", "Evaluate relationships and consistency across inferred concepts.")
    print_metric("Nodes / Edges", f"{graph.node_count} / {graph.edge_count}")
    print_metric("Connected Components", graph.connected_components)
    print_metric("Entities", len(graph.entities))
    print_bar("Semantic Consistency", graph.consistency_score)
    if graph.connected_components > 1:
        print_warning("Disconnected components reduce confidence in cross-concept reasoning.")
    print_timing(intelligence.stage_timings["semantic_graph"])

    mapping = intelligence.canonical_mapping
    mapped_names = [item.chosen_concept.name for item in mapping.mappings]
    duplicates = [name for name, count in Counter(mapped_names).items() if count > 1]
    print_stage_header(5, "Canonical Mapping", "Resolve dataset concepts to UCIF's canonical vocabulary.")
    print_metric("Resolved Columns", len(mapping.mappings))
    print_metric("Canonical Concepts", len(set(mapped_names)))
    print_bar("Mapping Quality", mapping.overall_confidence)
    print_metric("Duplicate Mappings", ", ".join(duplicates) if duplicates else "None")
    if duplicates:
        print_warning("Repeated canonical concepts can create conflicting entity interpretations.")
    print_timing(intelligence.stage_timings["canonical_mapping"])

    print_stage_header(5.5, "Semantic Feature Trace", "Show each feature's semantic entity and canonical destination.")
    for item in lineage:
        print_metric(
            item["input_feature"],
            f"{item['business_meaning']} -> {item['semantic_entity']} -> {item['canonical_concept']}",
        )
    print_metric("Coverage Contribution", "Reported through shared concept, semantic, and confidence coverage components.")

    coverage = intelligence.coverage
    print_stage_header(6, "Coverage Intelligence", "Assess whether semantic evidence is sufficient for reliable operation.")
    print_bar("Overall Coverage", coverage.summary.overall_coverage)
    print_bar("Concept Coverage", coverage.summary.concept_coverage)
    print_bar("Semantic Coverage", coverage.summary.semantic_coverage)
    print_bar("Confidence Coverage", coverage.summary.confidence_coverage)
    print_metric("Readiness", coverage.summary.readiness)
    if coverage.summary.readiness != "READY":
        print_warning("Readiness is limited by: " + "; ".join(issue.issue_type for issue in coverage.assessment.issues[:3]))
    print_timing(intelligence.stage_timings["coverage"])

    routing = intelligence.routing
    print_stage_header(7, "Routing Intelligence", "Select the most appropriate prediction pipeline from typed evidence.")
    print_metric("Candidate Pipelines", len(routing.assessment.candidates))
    for candidate in routing.assessment.candidates:
        print_bar(candidate.pipeline_name, candidate.final_score)
    print_metric("Selected Pipeline", routing.decision.selected_pipeline)
    print_metric("Routing Confidence", f"{routing.decision.confidence:.1%}")
    print_metric("Fallback Used", routing.decision.fallback_used)
    print_metric("Routing Reason", routing.decision.reasoning)
    print_timing(intelligence.stage_timings["routing"])

    print_stage_header(7.5, "Feature Mapping To Model", "Document the interpreted model-facing feature source for explainability.")
    for item in lineage:
        print_metric(item["prediction_feature"], f"<- {item['input_feature']}")
    print_metric("Features Used", ", ".join(sorted({item['prediction_feature'] for item in lineage})))
    print_metric("Features Ignored", "None reported by the prediction schema.")
    print_metric("Prediction Contribution", "Row-level contribution is available only when an explainer is supplied.")

    print_stage_header(8, "Prediction Engine", "Generate customer-level churn predictions without altering intelligence evidence.")
    print_metric("Prediction Model", results["Prediction_Model"].iloc[0])
    print_metric("Rows Analysed", len(results))
    print_metric("Predicted Churn / Retention", f"{(results['Predicted_Churn'] == 'Yes').sum()} / {(results['Predicted_Churn'] == 'No').sum()}")
    print_metric("Average Churn Probability", f"{results['Churn_Probability'].mean():.1%}")
    risk_counts = results["Risk_Level"].value_counts().to_dict()
    for label in ("High", "Medium", "Low"):
        print_count_bar(f"{label} Risk", int(risk_counts.get(label, 0)), len(results))
    explain_summary = results.attrs.get("explain_summary")
    if explain_summary:
        print_metric("Factors Increasing Churn", ", ".join(map(str, explain_summary.get("top_increasing", [])[:5])) or "No dominant factors")
        print_metric("Factors Reducing Churn", ", ".join(map(str, explain_summary.get("top_decreasing", [])[:5])) or "No dominant factors")
    else:
        print_metric("Prediction Explanation", "Use --explain to generate model-factor direction summaries; row-level contribution is not inferred without an explainer.")
    print_timing(prediction_time)

    print_stage_header(8.5, "Adaptive Business Intelligence", "Evaluate optional external business signals for operational context.")
    if not business_evidence.evidences:
        print_metric("Business Signals", "No external business context supplied.")
        print_metric("Operational Interpretation", "Prediction generated using internal customer evidence only.")
    else:
        print_metric("Overall Business Impact", business_evidence.overall_business_impact)
        print_metric("Evidence Confidence", f"{business_evidence.confidence:.1%}")
        print_metric("Summary", business_evidence.summary)
        for evidence in business_evidence.evidences:
            print_metric(evidence.category, f"[{evidence.severity}] {evidence.description}")
            print_metric("Recommendation Influence", evidence.recommendation)
        impact = business_evidence.assessment
        print_metric("Dominant Driver", impact.dominant_driver)
        print_metric("Affected Segments", ", ".join(impact.affected_segments) or "All evaluated customers")
        print_metric("Priority", impact.priority)
    print_timing(abil_time)

    print_stage_header(9, "Decision Intelligence", "Translate technical evidence into an executive recommendation.")
    if assessment is None:
        print_warning("Decision assessment was not generated.")
    else:
        print_metric("Decision Readiness", assessment.decision_readiness.value)
        print_metric("Overall Confidence", f"{assessment.overall_confidence:.1%}")
        print_metric("Business / Technical Confidence", f"{assessment.business_confidence:.1%} / {assessment.technical_confidence:.1%}")
        print_metric("Evidence Strength", f"{assessment.evidence_strength:.1%}")
        print_metric("Risk Level", assessment.risk_level.value)
        print_metric("Recommended Action", assessment.recommended_action)
        if business_evidence.evidences:
            print_metric("Adaptive Context", f"{business_evidence.overall_business_impact} business impact supplements the recommendation; prediction and decision scores are unchanged.")
        for warning in assessment.warnings:
            print_warning(warning)
        metrics = build_quality_metrics(intelligence, assessment)
        print_metric("UCIF Intelligence Score", f"{metrics['overall_ucif_intelligence_score']:.1%}")
        print_metric("Executive Narrative", build_executive_narrative(intelligence, assessment, business_evidence))

    print_stage_header(10, "Generated Reports", "Persist business outputs by default and diagnostics only in Explain/Debug mode.")
    purposes = {
        "predictions": "Customer-level prediction output.",
        "execution_summary": "Framework execution overview.",
        "decision_report": "Executive recommendation.",
        "coverage_report": "Semantic quality assessment.",
        "routing_report": "Pipeline selection reasoning.",
        "canonical_mapping": "Business concept resolution.",
        "semantic_graph": "Semantic relationship diagnostics.",
        "feature_lineage": "Complete feature traceability.",
        "reasoning_report": "Business reasoning diagnostics.",
        "business_evidence": "Adaptive business-context diagnostics.",
    }
    for artifact in artifacts:
        print_artifact(str(artifact), next((description for key, description in purposes.items() if key in artifact.stem), "Generated report."))

    print_summary()
    print_metric("Execution Time", f"{elapsed:.3f} sec")
    print_metric("Framework / Pipeline Version", f"UCIF 2.0 / {PIPELINE_VERSION}")
    print_metric("Dataset / Sector", f"{Path(args.input).name} / {sector.upper()}")
    print_metric("Selected Pipeline", routing.decision.selected_pipeline)
    print_metric("Coverage Score", f"{coverage.summary.overall_coverage:.1%}")
    print_metric("Decision Readiness", assessment.decision_readiness.value if assessment else "UNKNOWN")
    print_success("Execution completed successfully")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and return the parsed CLI namespace."""
    parser = argparse.ArgumentParser(
        description="Universal schema-agnostic churn predictor.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--mode',
        choices=[
            'train_sector', 'train_universal', 'sector', 'universal',
            'auto', 'train_all', 'list_heads',
        ],
        default='train_all',
    )
    parser.add_argument('--sector', type=str, default=None)
    parser.add_argument('--input', type=str, default=None)
    parser.add_argument('--output', type=str,
                        default='outputs/results/universal_predictions.csv')
    parser.add_argument('--tune', type=str, default=None, choices=['f1', 'recall'])
    parser.add_argument('--explain', action='store_true')
    parser.add_argument('--debug', action='store_true', help='Write developer diagnostics and complete feature lineage artifacts.')
    parser.add_argument(
        '--debug-level', choices=['standard', 'research'], default=None,
        help='Optional UDIF verbosity. Research includes the complete diagnostic sequence.',
    )
    parser.add_argument('--context', type=str, default=None, help='Optional validated business-context JSON for ABIL.')
    parser.add_argument('--explain-output', type=str, default=None)
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--report-output', type=str, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    execution_started = perf_counter()
    args = parse_args(argv)
    diagnostic_level = (
        DiagnosticLevel.RESEARCH if args.debug_level == 'research' else
        DiagnosticLevel.STANDARD if args.debug or args.debug_level == 'standard' else
        DiagnosticLevel.OFF
    )
    configure(diagnostic_level)

    if args.mode == 'train_all':
        print("\nTraining all sector pipelines...")
        for sector_name in SECTOR_CONFIG:
            try:
                SectorPipeline(sector_name, tune_metric=args.tune).fit()
            except FileNotFoundError as exc:
                print(f"  Skipping {sector_name}: {exc}")
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'train_sector':
        if not args.sector:
            raise ValueError("--sector is required for train_sector mode.")
        SectorPipeline(args.sector, tune_metric=args.tune).fit()

    elif args.mode == 'train_universal':
        train_universal_model(tune_metric=args.tune)

    elif args.mode == 'sector':
        # Routing decision (Green/Yellow → sector model w/ optional
        # warning, Red → refused, leakage → refused) is made entirely
        # inside SectorPipeline.predict() via routing.route(). The CLI
        # only loads the pipeline and surfaces whatever it returns.
        if not args.input:
            raise ValueError("--input is required for sector mode.")
        sector = args.sector
        if not sector:
            probe_df = pd.read_csv(args.input)
            sector = detect_sector(probe_df)
            print(f"  Auto-detected sector: {sector}")
        pipeline = SectorPipeline(sector).load()
        results = pipeline.predict(
            args.input, explain=args.explain,
            explain_output=args.explain_output, _prediction_mode='Sector')
        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(results, probe_for_explanation, sector)
        prediction_explanation = results.attrs.get("prediction_explanation")
        reasoning_report = None
        if prediction_explanation is not None:
            reasoning_report = prediction_explanation.reasoning_report
        results = build_and_attach_decision_intelligence(
            results=results,
            sector=sector,
            reasoning_report=reasoning_report,
        )
        diagnostic_run = active_run()
        if diagnostic_run is not None:
            render_udif(diagnostic_run)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        routing_decision_obj = results.attrs.get('routing_decision')
        routing_decision_text = (
            routing_decision_obj.reasoning if routing_decision_obj is not None
            else "User explicitly requested the sector-specific model."
        )
        _maybe_emit_report(
            results, sector,
            routing_decision=routing_decision_text,
            args=args)
        if getattr(args, 'report', False):
            explanation_report = results.attrs.get('prediction_explanation')
            if explanation_report is not None:
                print_prediction_explanation_report(explanation_report)
                print_execution_summary(explanation_report, results.attrs.get('coverage'))
            assessment = results.attrs.get('decision_assessment')
            if assessment is not None:
                print_decision_report(assessment)

    elif args.mode == 'universal':
        # Routing decision (quality gate / leakage check) is made
        # entirely inside predict_universal() via routing.route() when
        # called as the CLI entry point (no _precomputed_coverage).
        if not args.input:
            raise ValueError("--input is required for universal mode.")
        probe_df = pd.read_csv(args.input)
        sector_for_report = args.sector or detect_sector(probe_df)
        results = predict_universal(
            args.input, force_sector=args.sector,
            explain=args.explain, explain_output=args.explain_output,
            _prediction_mode='Universal')
        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(
            results, probe_for_explanation, sector_for_report)
        prediction_explanation = results.attrs.get("prediction_explanation")
        reasoning_report = None
        if prediction_explanation is not None:
            reasoning_report = prediction_explanation.reasoning_report
        results = build_and_attach_decision_intelligence(
            results=results,
            sector=sector_for_report,
            reasoning_report=reasoning_report,
        )
        diagnostic_run = active_run()
        if diagnostic_run is not None:
            render_udif(diagnostic_run)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"\nResults saved to: {args.output}")
        routing_decision_obj = results.attrs.get('routing_decision')
        routing_decision_text = (
            routing_decision_obj.reasoning if routing_decision_obj is not None
            else "User explicitly requested the universal model."
        )
        _maybe_emit_report(
            results, sector_for_report,
            routing_decision=routing_decision_text,
            args=args)
        if getattr(args, 'report', False):
            explanation_report = results.attrs.get('prediction_explanation')
            if explanation_report is not None:
                print_prediction_explanation_report(explanation_report)
                print_execution_summary(explanation_report, results.attrs.get('coverage'))
            assessment = results.attrs.get('decision_assessment')
            if assessment is not None:
                print_decision_report(assessment)

    elif args.mode == 'auto':
        # Centralized routing: compute coverage + quality, call
        # routing.route() exactly once, then dispatch purely on
        # RoutingDecision.selected_model. The CLI makes no routing
        # decisions of its own — it only executes what route() returns.
        if not args.input:
            raise ValueError("--input is required for auto mode.")
        execution_id = f"UCIF-{uuid4().hex[:10].upper()}"
        probe_df = pd.read_csv(args.input)
        sector = args.sector or detect_sector(probe_df)
        intelligence = infer_intelligence(probe_df)
        diagnostic_run = active_run()
        if diagnostic_run is not None:
            diagnostic_run.capture_intelligence(probe_df, sector, intelligence)
        decision = intelligence.routing.decision

        # UCIF currently ships a universal artifact for the typed Generic
        # fallback. A sector-specific artifact is used only when the typed
        # router selected that exact sector pipeline.
        prediction_started = perf_counter()
        if decision.selected_pipeline == f"{sector.capitalize()}Pipeline":
            pipeline = SectorPipeline(sector).load()
            results = pipeline._run_sector_model(
                probe_df, intelligence.coverage,
                run_quality_gate(probe_df, target_col=SECTOR_CONFIG[sector]['target_col']),
                decision, args.explain, args.explain_output, 'Auto')
            results.attrs['intelligence'] = intelligence
        else:
            results = predict_universal(
                args.input, force_sector=sector, explain=args.explain,
                explain_output=args.explain_output, _prediction_mode='Auto',
                _intelligence=intelligence)
        prediction_time = perf_counter() - prediction_started

        abil_started = perf_counter()
        business_context = ExecutionContext(
            sector=sector, execution_id=execution_id,
            events=load_business_context(args.context),
        )
        business_evidence = AdaptiveBusinessEngine().evaluate(business_context)
        abil_time = perf_counter() - abil_started

        # Prediction Explanation Layer (Version 7, Chunk 5) — additive,
        # best-effort, never blocks prediction. See prediction_explanation.py
        # for the non-interference guarantee.
        probe_for_explanation = pd.read_csv(args.input)
        results = build_and_attach_explanations(results, probe_for_explanation, sector)
        prediction_explanation = results.attrs.get("prediction_explanation")
        reasoning_report = None
        if prediction_explanation is not None:
            reasoning_report = prediction_explanation.reasoning_report
        results = build_and_attach_decision_intelligence(
            results=results,
            sector=sector,
            reasoning_report=reasoning_report,
        )

        if diagnostic_run is not None:
            render_udif(
                diagnostic_run,
                include_root_cause=diagnostic_level is not DiagnosticLevel.RESEARCH,
            )

        assessment = results.attrs.get('decision_assessment')
        reasoning_report = results.attrs.get("prediction_explanation")
        lineage = build_feature_lineage(intelligence, results, list(probe_df.columns))
        artifacts = write_enterprise_artifacts(
            results=results,
            intelligence=intelligence,
            execution={
                "execution_id": execution_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": args.mode,
                "dataset": str(Path(args.input).resolve()),
                "sector": sector,
                "pipeline_version": PIPELINE_VERSION,
                "stage_timings_seconds": intelligence.stage_timings,
                "prediction_seconds": prediction_time,
                "elapsed_seconds": perf_counter() - execution_started,
            },
            output_path=args.output,
            decision_assessment=assessment,
            reasoning_report=(reasoning_report.reasoning_report if reasoning_report else None),
            business_evidence=business_evidence,
            diagnostics=args.explain or diagnostic_level is not DiagnosticLevel.OFF,
            source_columns=list(probe_df.columns),
        )
        _render_enterprise_console(
            execution_id, args, probe_df, sector, intelligence, results,
            perf_counter() - execution_started, prediction_time, artifacts, lineage,
            business_evidence, abil_time,
        )
        if diagnostic_run is not None and diagnostic_level is DiagnosticLevel.RESEARCH:
            render_root_cause(diagnostic_run)

    elif args.mode == 'list_heads':
        print("\nMulti-head model architecture:")
        print(f"{'Sector': <12} {'Model file': <55} {'Trained?'}")
        print("-" * 85)
        for sector_name, cfg in SECTOR_CONFIG.items():
            model_file = cfg['model_path']
            trained = "Yes" if Path(model_file).exists() else "No"
            print(f"{sector_name: <12} {model_file: <55} {trained}")
