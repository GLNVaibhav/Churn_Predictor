"""
backend.presentation
══════════════════════════════════════════════════════════════════════
Type-B presentation aggregation — KPI roll-ups, chart series, and
dashboard widgets.  Business metrics (Type A) remain in universal_churn;
nothing here re-derives coverage scores, routing confidence, or quality.
"""
from __future__ import annotations

from .prediction_rollup import build_prediction_summary

__all__ = ["build_prediction_summary"]
