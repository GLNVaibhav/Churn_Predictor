"""Contract tests for positive-class inference scores."""

import numpy as np
import pytest

from universal_churn.utils import positive_class_probabilities


class ProbabilityModel:
    def __init__(self, classes, probabilities):
        self.classes_ = np.asarray(classes)
        self.probabilities = probabilities

    def predict_proba(self, features):
        return np.asarray(self.probabilities)


def test_positive_probability_uses_class_label_not_column_position():
    model = ProbabilityModel([1, 0], [[0.8, 0.2], [0.1, 0.9]])
    np.testing.assert_array_equal(
        positive_class_probabilities(model, np.zeros((2, 1))),
        np.array([0.8, 0.1]),
    )


@pytest.mark.parametrize(
    ("classes", "probabilities", "message"),
    [
        ([0], [[1.0]], "binary classes"),
        ([0, 1], [[0.2]], "unexpected shape"),
        ([0, 1], [[float("nan"), 1.0]], "non-finite"),
        ([0, 1], [[1.2, -0.2]], "out-of-range"),
    ],
)
def test_positive_probability_rejects_invalid_model_output(classes, probabilities, message):
    model = ProbabilityModel(classes, probabilities)
    with pytest.raises(ValueError, match=message):
        positive_class_probabilities(model, np.zeros((1, 1)))
