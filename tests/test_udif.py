from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

from universal_churn.udif import DiagnosticLevel, UDIFRun, active_run, configure
from universal_churn.udif_rendering import render_execution_terminated


def test_model_input_diagnostics_are_structured_and_read_only():
    source = pd.DataFrame({"constant": [2, 2], "varying": [1.0, 3.0]})
    run = UDIFRun(DiagnosticLevel.STANDARD)

    run.capture_model_input(source)

    assert source.equals(pd.DataFrame({"constant": [2, 2], "varying": [1.0, 3.0]}))
    assert run.feature_matrix is not None
    assert run.feature_matrix.constant_columns == ("constant",)
    assert run.model_input_health is not None
    assert run.model_input_health.result == "WARNING"
    assert asdict(run.feature_matrix)["rows"] == 2


def test_prediction_diagnostics_do_not_replace_variance_guard():
    run = UDIFRun(DiagnosticLevel.RESEARCH)

    run.capture_predictions(np.array([0.5, 0.5]))

    assert run.prediction is not None
    assert run.prediction.health == "FAIL"
    assert run.prediction.standard_deviation == 0.0
    assert sum(bucket.count for bucket in run.prediction.histogram) == 2


def test_off_level_has_no_active_collector():
    configure(DiagnosticLevel.OFF)

    assert active_run() is None


def test_termination_renderer_does_not_change_the_original_exception(capsys):
    original = RuntimeError("variance guard stopped prediction")

    with pytest.raises(RuntimeError, match="variance guard stopped prediction"):
        try:
            raise original
        except RuntimeError as exc:
            render_execution_terminated("verify_prediction_variance", exc)
            raise

    assert "EXECUTION TERMINATED" in capsys.readouterr().out
