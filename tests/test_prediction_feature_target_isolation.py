"""Regression checks for supervised target isolation at inference."""

import numpy as np
import pandas as pd

from universal_churn.config import SECTOR_CONFIG
from universal_churn.feature_engineering import prepare_prediction_features


def test_telecom_prediction_features_ignore_target_and_preserve_rows():
    source = pd.read_csv(SECTOR_CONFIG["telecom"]["data_path"]).head(20)
    features = prepare_prediction_features(source.copy(), "telecom")

    target_flipped = source.copy()
    target_flipped["Churn"] = target_flipped["Churn"].map({"Yes": "No", "No": "Yes"})
    flipped_features = prepare_prediction_features(target_flipped, "telecom")

    assert len(features) == len(source)
    assert features.index.equals(source.index)
    assert not {"Churn", "Exited", "Churned"}.intersection(features.columns)
    pd.testing.assert_frame_equal(features, flipped_features)

    numeric = features.select_dtypes(include=["number", "bool"]).to_numpy()
    assert np.isfinite(numeric).all()
