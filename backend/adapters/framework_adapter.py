"""
backend.adapters.framework_adapter
══════════════════════════════════════════════════════════════════════
``FrameworkAdapter`` — Sprint 2's orchestration seam between the
``backend`` package and ``universal_churn``.

NON-NEGOTIABLE RULE (same posture as ``backend.mappers.FrameworkMapper``,
one layer earlier in the pipeline): this class performs NO business
logic, NO routing decisions, NO scoring. It calls the framework's own
public functions in the SAME sequence ``universal_churn.cli`` already
uses for each mode, and returns whatever they produced, unmodified, as
a plain ``FrameworkExecutionResult`` bundle. Every routing choice
(which model runs, whether a prediction is refused) is still made
entirely inside ``routing.route()`` — this adapter only reads the
``RoutingDecision`` it returns and dispatches on it, exactly as
``cli.py``'s ``auto`` branch does.

Why this exists (rather than importing ``cli.main`` directly)
------------------------------------------------------------------
``cli.py``'s ``main()`` is built around ``argparse.Namespace`` and
talks to stdout/CSV files — it is not an importable function a service
layer can call and get a structured result back from. This adapter
mirrors its control flow (see ``_run_auto`` vs. ``cli.py``'s
``elif args.mode == 'auto':`` block) using the exact same framework
calls, in the exact same order, but returns objects instead of writing
files or printing.

Refusal handling
------------------
A prediction can be legitimately REFUSED by the framework itself
(``routing.ModelType.CRITICAL_UNRELIABLE`` — quality-gate leakage, or
coverage too low with unreconstructable concepts). That is not a
backend error: it is the framework's own documented decision, and the
adapter models it explicitly via ``FrameworkExecutionResult.refused``
rather than letting the ``ValueError`` that ``sector_pipeline.py`` /
``universal_pipeline.py`` raise for it propagate as an exception.

- ``mode='auto'``: coverage/quality/routing are computed by this
  adapter BEFORE dispatch (mirroring ``cli.py``), so a refusal is
  detected up front — ``coverage`` / ``quality`` / ``routing_decision``
  are all populated on a refused ``auto`` result.
- ``mode='sector'`` / ``mode='universal'``: routing happens INSIDE
  ``SectorPipeline.predict()`` / ``predict_universal()`` themselves,
  which raise a plain ``ValueError`` on refusal — by the time that
  exception is caught here, the coverage/quality/routing objects that
  triggered it were never returned to this scope. A refused result
  from these two modes therefore has ``coverage=None`` /
  ``quality=None`` / ``routing_decision=None`` — there is nothing to
  report beyond the fact and reason. Recomputing them just to attach
  them here would be genuinely new work this adapter does not do, on
  principle: it never invents evidence the framework itself didn't
  hand back.

Anything else — a missing input file, a sector model that hasn't been
trained yet, an unexpected internal error — is a genuine failure, not
a modeled refusal. Those propagate as a raw exception out of this
adapter; ``backend.services.AnalysisService`` is the layer that wraps
them in ``backend.exceptions.FrameworkExecutionError``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from universal_churn.config import SECTOR_CONFIG
from universal_churn.preprocessing import detect_sector
from universal_churn.feature_engineering import build_canonical_dataframe
from universal_churn.coverage import compute_coverage_score
from universal_churn.quality_gate import run_quality_gate
from universal_churn.routing import route, ModelType, RoutingDecision
from universal_churn.sector_pipeline import SectorPipeline
from universal_churn.universal_pipeline import predict_universal
from universal_churn.prediction_explanation_report import build_and_attach_explanations
from universal_churn.decision_report import build_and_attach_decision_intelligence


# ══════════════════════════════════════════════════════════════════
# RESULT BUNDLE
# ══════════════════════════════════════════════════════════════════

@dataclass
class FrameworkExecutionResult:
    """
    Everything one ``FrameworkAdapter.execute()`` call produced, as raw
    framework objects — untouched, unmapped. ``backend.mappers.
    FrameworkMapper.build_response()`` is the next stage that turns
    this into the public contract; this dataclass exists purely so the
    adapter and the service layer have one stable, typed handoff shape
    between them.

    Attributes
    ----------
    sector : str
        The sector this run executed against (detected or explicit).
    mode : str
        The requested prediction mode: ``'sector'`` | ``'universal'``
        | ``'auto'``.
    refused : bool
        True iff the framework's own routing decided
        ``ModelType.CRITICAL_UNRELIABLE`` for this input — a modeled
        outcome, not a backend error (see module docstring).
    refusal_reason : str | None
        ``RoutingDecision.routing_reason`` when refused, or the
        framework's own ``ValueError`` message when routing happened
        inside ``sector_pipeline.py`` / ``universal_pipeline.py`` and
        no ``RoutingDecision`` was ever returned to this scope.
    results : pd.DataFrame | None
        The prediction results DataFrame, or ``None`` if refused.
    coverage : dict | None
        ``coverage.compute_coverage_score()``'s return dict.
    quality : dict | None
        ``quality_gate.run_quality_gate()``'s return dict.
    routing_decision : RoutingDecision | None
        The typed decision object ``routing.route()`` returned.
    explanation_report : PredictionExplanationReport | None
        Attached via ``results.attrs['prediction_explanation']`` by
        ``prediction_explanation_report.build_and_attach_explanations()``
        — ``None`` if the enrichment step failed (it is best-effort
        and exception-safe by its own design) or was never reached
        (refused predictions have no results to explain).
    decision_assessment : DecisionAssessment | None
        Attached via ``results.attrs['decision_assessment']`` by
        ``decision_report.build_and_attach_decision_intelligence()``.
    """
    sector: str
    mode: str
    refused: bool = False
    refusal_reason: Optional[str] = None
    results: Optional[pd.DataFrame] = None
    coverage: Optional[dict] = None
    quality: Optional[dict] = None
    routing_decision: Optional[RoutingDecision] = None
    explanation_report: Optional[Any] = None
    decision_assessment: Optional[Any] = None


# ══════════════════════════════════════════════════════════════════
# THE ADAPTER
# ══════════════════════════════════════════════════════════════════

class FrameworkAdapter:
    """
    Stateless — every method is a pure orchestration of existing
    ``universal_churn`` calls. Safe to share a single instance across
    many requests (mirrors ``FrameworkMapper``'s own statelessness).
    """

    # ── shared enrichment step (explanation + decision intelligence) ──
    # Identical for every mode once a non-refused `results` DataFrame
    # exists — cli.py performs this same pair of calls at the end of
    # each of its 'sector' / 'universal' / 'auto' branches.

    @staticmethod
    def _enrich(results: pd.DataFrame, df_raw: pd.DataFrame, sector: str) -> pd.DataFrame:
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

    # ── mode: sector ─────────────────────────────────────────────

    def _run_sector(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> FrameworkExecutionResult:
        probe_df = pd.read_csv(input_path)
        resolved_sector = sector or detect_sector(probe_df)

        pipeline = SectorPipeline(resolved_sector).load()
        try:
            results = pipeline.predict(
                input_path, explain=explain, _prediction_mode='Sector',
            )
        except ValueError as exc:
            # sector_pipeline.py raises plain ValueError on routing
            # refusal (CRITICAL_UNRELIABLE) — see its predict() docstring.
            return FrameworkExecutionResult(
                sector=resolved_sector, mode='sector',
                refused=True, refusal_reason=str(exc),
            )

        results = self._enrich(results, pd.read_csv(input_path), resolved_sector)

        return FrameworkExecutionResult(
            sector=resolved_sector, mode='sector', results=results,
            coverage=results.attrs.get('coverage'),
            quality=results.attrs.get('quality'),
            routing_decision=results.attrs.get('routing_decision'),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
        )

    # ── mode: universal ──────────────────────────────────────────

    def _run_universal(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> FrameworkExecutionResult:
        probe_df = pd.read_csv(input_path)
        sector_for_report = sector or detect_sector(probe_df)

        try:
            results = predict_universal(
                input_path, force_sector=sector, explain=explain,
                _prediction_mode='Universal',
            )
        except ValueError as exc:
            return FrameworkExecutionResult(
                sector=sector_for_report, mode='universal',
                refused=True, refusal_reason=str(exc),
            )

        results = self._enrich(results, pd.read_csv(input_path), sector_for_report)

        return FrameworkExecutionResult(
            sector=sector_for_report, mode='universal', results=results,
            coverage=results.attrs.get('coverage'),
            quality=results.attrs.get('quality'),
            routing_decision=results.attrs.get('routing_decision'),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
        )

    # ── mode: auto ───────────────────────────────────────────────

    def _run_auto(
        self, input_path: str, sector: Optional[str], explain: bool,
    ) -> FrameworkExecutionResult:
        """Mirrors cli.py's 'auto' branch: compute coverage + quality,
        call routing.route() exactly once, dispatch on the decision."""
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

        if decision.selected_model == ModelType.CRITICAL_UNRELIABLE:
            return FrameworkExecutionResult(
                sector=resolved_sector, mode='auto',
                refused=True, refusal_reason=decision.routing_reason,
                coverage=coverage, quality=quality, routing_decision=decision,
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
            # Future-readiness hook — route() does not currently return
            # CORE_MODEL (see routing.py); mirrors cli.py's own guard.
            raise NotImplementedError(
                "Routing selected CORE_MODEL, but no core model pipeline "
                "is implemented yet. This is a future-readiness hook."
            )
        else:
            raise RuntimeError(
                f"Unhandled RoutingDecision.selected_model: {decision.selected_model}"
            )

        results = self._enrich(results, pd.read_csv(input_path), resolved_sector)

        return FrameworkExecutionResult(
            sector=resolved_sector, mode='auto', results=results,
            coverage=results.attrs.get('coverage', coverage),
            quality=results.attrs.get('quality', quality),
            routing_decision=results.attrs.get('routing_decision', decision),
            explanation_report=results.attrs.get('prediction_explanation'),
            decision_assessment=results.attrs.get('decision_assessment'),
        )

    # ── public entry point ───────────────────────────────────────

    def execute(
        self,
        input_path: str,
        sector: Optional[str] = None,
        mode: str = 'auto',
        explain: bool = False,
    ) -> FrameworkExecutionResult:
        """
        Run one prediction through the framework and return the raw
        result bundle. ``mode`` mirrors ``cli.py --mode``'s three
        prediction-time values; training modes (``train_sector`` /
        ``train_universal`` / ``train_all``) and ``list_heads`` are out
        of scope for this adapter — see ``PipelineService`` for
        read-only model/registry status instead.
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