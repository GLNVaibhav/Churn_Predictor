"""
backend.adapters.framework_adapter
══════════════════════════════════════════════════════════════════════
``FrameworkAdapter`` — Sprint 3 Anti-Corruption Layer between
``backend`` and ``universal_churn``.

Responsibilities (and ONLY these):
    1. Select the correct framework entry point for the requested mode.
    2. Execute the framework exactly once.
    3. Capture raw framework output, unmodified.
    4. Convert raw output into ``ExecutionResult``.

This class performs NO business logic, NO routing decisions, NO scoring,
NO aggregation.  Every routing choice is made inside ``routing.route()``
or the sector/universal pipelines — this adapter only reads what they
return and dispatches on it, exactly as ``cli.py`` does.

Why this exists (rather than importing ``cli.main`` directly)
------------------------------------------------------------------
``cli.py``'s ``main()`` is built around ``argparse.Namespace`` and
talks to stdout/CSV files — it is not an importable function a service
layer can call and get a structured result back from.  This adapter
mirrors its control flow using the exact same framework calls, in the
exact same order, but returns ``ExecutionResult`` instead of writing
files or printing.

Refusal handling
------------------
A prediction can be legitimately REFUSED by the framework itself
(``routing.ModelType.CRITICAL_UNRELIABLE``).  That is not a backend
error — it is modeled explicitly via ``ExecutionResult.metadata.refused``
rather than letting the ``ValueError`` propagate as an exception.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from universal_churn.config import SECTOR_CONFIG
from universal_churn.preprocessing import detect_sector
from universal_churn.feature_engineering import build_canonical_dataframe
from universal_churn.coverage import compute_coverage_score
from universal_churn.quality_gate import run_quality_gate
from universal_churn.routing import route, ModelType
from universal_churn.sector_pipeline import SectorPipeline
from universal_churn.universal_pipeline import predict_universal
from universal_churn.prediction_explanation_report import build_and_attach_explanations
from universal_churn.decision_report import build_and_attach_decision_intelligence

from ..models.execution_result import ExecutionResult


class FrameworkAdapter:
    """
    Stateless Anti-Corruption Layer — safe to share across requests.
    Executes ``universal_churn`` once per call and returns ``ExecutionResult``.
    """

    @staticmethod
    def _enrich(results: pd.DataFrame, df_raw: pd.DataFrame, sector: str) -> pd.DataFrame:
        """Shared enrichment — identical to cli.py's post-predict step."""
        results = build_and_attach_explanations(results, df_raw, sector)
        prediction_explanation = results.attrs.get("prediction_explanation")
        reasoning_report = (
            prediction_explanation.reasoning_report
            if prediction_explanation is not None else None
        )
        results = build_and_attach_decision_intelligence(
            results=results, sector=sector, reasoning_report=reasoning_report,
        )
        return results

    def _run_sector(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> ExecutionResult:
        probe_df = pd.read_csv(input_path)
        resolved_sector = sector or detect_sector(probe_df)

        pipeline = SectorPipeline(resolved_sector).load()
        try:
            results = pipeline.predict(
                input_path, explain=explain, _prediction_mode='Sector',
            )
        except ValueError as exc:
            return ExecutionResult.from_framework_output(
                sector=resolved_sector, mode='sector',
                refused=True, refusal_reason=str(exc),
                input_path=input_path,
            )

        results = self._enrich(results, pd.read_csv(input_path), resolved_sector)

        return ExecutionResult.from_framework_output(
            sector=resolved_sector, mode='sector', input_path=input_path,
            results=results,
            coverage=results.attrs.get('coverage'),
            quality=results.attrs.get('quality'),
            routing_decision=results.attrs.get('routing_decision'),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
        )

    def _run_universal(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> ExecutionResult:
        probe_df = pd.read_csv(input_path)
        sector_for_report = sector or detect_sector(probe_df)

        try:
            results = predict_universal(
                input_path, force_sector=sector, explain=explain,
                _prediction_mode='Universal',
            )
        except ValueError as exc:
            return ExecutionResult.from_framework_output(
                sector=sector_for_report, mode='universal',
                refused=True, refusal_reason=str(exc),
                input_path=input_path,
            )

        results = self._enrich(results, pd.read_csv(input_path), sector_for_report)

        return ExecutionResult.from_framework_output(
            sector=sector_for_report, mode='universal', input_path=input_path,
            results=results,
            coverage=results.attrs.get('coverage'),
            quality=results.attrs.get('quality'),
            routing_decision=results.attrs.get('routing_decision'),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
        )

    def _run_auto(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> ExecutionResult:
        """Mirrors cli.py's 'auto' branch: coverage → quality → route → dispatch."""
        probe_df = pd.read_csv(input_path)
        resolved_sector = sector or detect_sector(probe_df)

        canonical_df, _resolutions, _manifest = build_canonical_dataframe(probe_df)
        coverage = compute_coverage_score(
            df_input=canonical_df, sector=resolved_sector, mode='auto', raw_df=probe_df,
        )
        quality = run_quality_gate(
            probe_df, target_col=SECTOR_CONFIG[resolved_sector]['target_col'],
        )
        decision = route(mode='auto', coverage=coverage, quality=quality, sector=resolved_sector)

        diagnostics = {
            "resolutions": _resolutions,
            "manifest": _manifest,
        }

        if decision.selected_model == ModelType.CRITICAL_UNRELIABLE:
            return ExecutionResult.from_framework_output(
                sector=resolved_sector, mode='auto',
                refused=True, refusal_reason=decision.routing_reason,
                input_path=input_path,
                coverage=coverage, quality=quality,
                routing_decision=decision,
                diagnostics=diagnostics,
            )

        if decision.selected_model == ModelType.FULL_SECTOR_MODEL:
            pipeline = SectorPipeline(resolved_sector).load()
            results = pipeline.predict(input_path, explain=explain, _prediction_mode='Auto')

        elif decision.selected_model == ModelType.UNIVERSAL_MODEL:
            results = predict_universal(
                input_path, force_sector=resolved_sector, explain=explain,
                _prediction_mode='Auto', _precomputed_coverage=coverage,
            )
            for k, v in decision.report_fields().items():
                results[k] = v
            results.attrs['coverage'] = coverage
            results.attrs['quality'] = quality
            results.attrs['routing_decision'] = decision

        elif decision.selected_model == ModelType.CORE_MODEL:
            raise NotImplementedError(
                "Routing selected CORE_MODEL, but no core model pipeline "
                "is implemented yet. This is a future-readiness hook."
            )
        else:
            raise RuntimeError(
                f"Unhandled RoutingDecision.selected_model: {decision.selected_model}"
            )

        results = self._enrich(results, pd.read_csv(input_path), resolved_sector)

        return ExecutionResult.from_framework_output(
            sector=resolved_sector, mode='auto', input_path=input_path,
            results=results,
            coverage=results.attrs.get('coverage', coverage),
            quality=results.attrs.get('quality', quality),
            routing_decision=results.attrs.get('routing_decision', decision),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
            diagnostics=diagnostics,
        )

    def execute(
        self,
        input_path: str,
        sector: Optional[str] = None,
        mode: str = 'auto',
        explain: bool = False,
    ) -> ExecutionResult:
        """
        Run one prediction through the framework and return ``ExecutionResult``.

        ``mode`` mirrors ``cli.py --mode``'s three prediction-time values.
        """
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if mode == 'sector':
            return self._run_sector(input_path, sector, explain)
        if mode == 'universal':
            return self._run_universal(input_path, sector, explain)
        if mode == 'auto':
            return self._run_auto(input_path, sector, explain)

        raise ValueError(
            f"Unsupported mode '{mode}' — expected one of: 'sector', 'universal', 'auto'."
        )
