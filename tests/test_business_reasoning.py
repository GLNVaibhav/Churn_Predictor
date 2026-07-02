"""
tests/test_business_reasoning.py
Focused validation for Version 7 / Chunk 3 — Business Reasoning Engine.
Exercises the module in isolation (no trained models / no sector CSVs
required), consistent with "Reasoning exists independently" (Part 7).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from universal_churn.business_reasoning import (
    BusinessReasoningEngine, BusinessInference, BusinessFinding,
    ReasoningReport, ReasoningSummary, ConceptBand, Severity,
    run_business_reasoning,
)
from universal_churn.business_reasoning_report import (
    generate_business_reasoning_report, business_reasoning_report_for,
)


def _skewed_ecommerce_df(n=300, seed=1):
    rng = np.random.default_rng(seed)
    cashback = np.concatenate([
        rng.uniform(90, 100, int(n * 0.95)),
        rng.uniform(0, 5, int(n * 0.05)),
    ])
    complain = np.concatenate([np.ones(int(n * 0.9)), np.zeros(int(n * 0.1))])
    rng.shuffle(cashback)
    rng.shuffle(complain)
    return pd.DataFrame({
        'Tenure': rng.integers(1, 6, n),
        'CashbackAmount': cashback,
        'Complain': complain,
        'SatisfactionScore': rng.uniform(1, 2, n),
        'OrderCount': rng.uniform(1, 3, n),
        'DaySinceLastOrder': rng.uniform(1, 5, n),
        'WarehouseToHome': rng.uniform(5, 20, n),
        'PreferredPaymentMode': ['COD'] * n,
        'CouponUsed': rng.uniform(0, 2, n),
    })


def _loyal_engaged_ecommerce_df(n=200, seed=2):
    # Min-max normalization (concepts.py/_safe_normalize) only cares
    # about spread WITHIN the batch, not absolute magnitude — a narrow
    # uniform range always normalizes to a ~0.5 mean regardless of its
    # absolute level. To get a genuine HIGH-banded aggregate we need a
    # skewed distribution (most rows near the max, a minority of
    # outliers near the min), mirroring the skew used for the
    # Retention Risk fixture above.
    rng = np.random.default_rng(seed)
    tenure = np.concatenate([rng.uniform(55, 60, int(n * 0.95)), rng.uniform(0, 2, int(n * 0.05))])
    orders = np.concatenate([rng.uniform(95, 100, int(n * 0.95)), rng.uniform(0, 2, int(n * 0.05))])
    rng.shuffle(tenure)
    rng.shuffle(orders)
    return pd.DataFrame({
        'Tenure': tenure,
        'CashbackAmount': rng.uniform(40, 60, n),
        'Complain': np.zeros(n),
        'SatisfactionScore': rng.uniform(4, 5, n),
        'OrderCount': orders,
        'DaySinceLastOrder': rng.uniform(0, 2, n),
        'WarehouseToHome': rng.uniform(5, 20, n),
        'PreferredPaymentMode': ['Credit Card'] * n,
        'CouponUsed': rng.uniform(0, 2, n),
    })


class TestBusinessInferenceBanding:
    def test_report_shape(self):
        report = run_business_reasoning(_skewed_ecommerce_df(), 'ecommerce')
        assert isinstance(report, ReasoningReport)
        assert report.sector == 'ecommerce'
        assert set(report.inferences.keys()) == {
            'RECURRING_COMMITMENT', 'CUSTOMER_LOYALTY', 'SUPPORT_FRICTION',
            'ENGAGEMENT_LEVEL', 'SATISFACTION_SIGNAL',
        }
        for inf in report.inferences.values():
            assert isinstance(inf, BusinessInference)
            assert inf.band in ConceptBand
            assert 0.0 <= inf.aggregate_value <= 1.0
            assert 0.0 <= inf.confidence <= 1.0


class TestDeterministicRules:
    def test_retention_risk_fires_on_low_commitment_high_friction(self):
        report = run_business_reasoning(_skewed_ecommerce_df(), 'ecommerce')
        ids = {f.finding_id for f in report.findings}
        assert 'RETENTION_RISK' in ids
        finding = next(f for f in report.findings if f.finding_id == 'RETENTION_RISK')
        assert finding.severity == Severity.HIGH
        assert set(finding.supporting_concepts) == {'RECURRING_COMMITMENT', 'SUPPORT_FRICTION'}
        assert 0.0 < finding.confidence <= 1.0

    def test_retention_strength_fires_on_loyal_engaged_population(self):
        report = run_business_reasoning(_loyal_engaged_ecommerce_df(), 'ecommerce')
        ids = {f.finding_id for f in report.findings}
        assert 'RETENTION_STRENGTH' in ids

    def test_rules_never_fire_on_insufficient_evidence(self):
        # Telecom has no documented SUPPORT_FRICTION / SATISFACTION_SIGNAL
        # source at all -> those concepts must never support a finding.
        df = pd.DataFrame({
            'tenure': [1] * 50, 'MonthlyCharges': [10.0] * 50,
            'Contract': ['Month-to-month'] * 50, 'TechSupport': ['No'] * 50,
        })
        report = run_business_reasoning(df, 'telecom')
        for finding in report.findings:
            assert 'SATISFACTION_SIGNAL' not in finding.supporting_concepts

    def test_empty_dataframe_does_not_raise(self):
        df = pd.DataFrame({'tenure': [], 'MonthlyCharges': []})
        report = run_business_reasoning(df, 'telecom')
        assert isinstance(report, ReasoningReport)
        assert report.findings == []


class TestReasoningSummary:
    def test_summary_present_and_consistent_with_findings(self):
        report = run_business_reasoning(_skewed_ecommerce_df(), 'ecommerce')
        assert isinstance(report.summary, ReasoningSummary)
        if report.findings:
            severities = {f.severity.value for f in report.findings}
            assert report.summary.overall_customer_risk in severities or \
                   report.summary.overall_customer_risk == 'LOW'


class TestReportFormatting:
    def test_generate_report_is_a_nonempty_string(self):
        report = run_business_reasoning(_skewed_ecommerce_df(), 'ecommerce')
        text = generate_business_reasoning_report(report)
        assert isinstance(text, str)
        assert 'BUSINESS REASONING REPORT' in text
        assert 'ECOMMERCE' in text

    def test_convenience_wrapper_matches_engine_output_shape(self):
        text = business_reasoning_report_for(_skewed_ecommerce_df(), 'ecommerce')
        assert 'Business Findings' in text
        assert 'CONCEPT INFERENCES' in text


class TestSerialization:
    def test_to_dict_is_json_ready(self):
        import json
        report = run_business_reasoning(_skewed_ecommerce_df(), 'ecommerce')
        payload = json.dumps(report.to_dict())
        assert isinstance(payload, str)


class TestNonInterference:
    def test_module_has_no_dependency_on_prediction_modules(self):
        """
        Chunk 3, Part 7: 'No model should consume reasoning yet.'
        This is enforced structurally — business_reasoning.py must not
        import anything from the prediction/routing surface.
        """
        import inspect
        import universal_churn.business_reasoning as br
        src = inspect.getsource(br)
        forbidden = ['routing', 'sector_pipeline', 'universal_pipeline', 'cli']
        for name in forbidden:
            assert f"import {name}" not in src and f"from .{name}" not in src
