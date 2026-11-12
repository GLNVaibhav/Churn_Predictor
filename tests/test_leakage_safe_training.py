"""Regression tests for candidate training data boundaries."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.linear_model import LogisticRegression

from universal_churn.leakage_safe_training import (
    _merge_entity_and_duplicate_groups, fit_candidate, holdout_split,
)


class RecordingSampler(BaseEstimator):
    seen_rows = []

    def fit_resample(self, X, y):
        type(self).seen_rows.append(X.shape[0])
        return X, y


def test_preprocessor_learns_only_from_development_rows_and_ignores_unknown_category():
    X_train = pd.DataFrame({"number": [0.0, 2.0, 4.0, 6.0], "kind": ["a", "a", "b", "b"]})
    y_train = pd.Series([0, 0, 1, 1])
    X_holdout = pd.DataFrame({"number": [1000.0, 8.0], "kind": ["holdout-only", "a"]})
    y_holdout = pd.Series([1, 0])
    result = fit_candidate(
        X_train, y_train, LogisticRegression(random_state=1),
        final_holdout=(X_holdout, y_holdout),
    )
    prep = result["model"].named_steps["preprocess"]
    numeric = prep.named_transformers_["numeric"]
    assert numeric.named_steps["scale"].mean_[0] == 3.0
    categorical = prep.named_transformers_["categorical"].named_steps["encode"]
    assert list(categorical.categories_[0]) == ["a", "b"]
    assert result["holdout_rows"] == 2
    assert len(result["holdout_metrics"]["confusion_matrix_labels_0_1"]) == 2
    direct = result["model"].predict_proba(X_holdout)[:, 1]
    reverse = result["model"].predict_proba(X_holdout.iloc[::-1])[:, 1]
    np.testing.assert_allclose(direct[::-1], reverse)


def test_sampler_runs_inside_each_training_fold_and_never_on_final_holdout():
    RecordingSampler.seen_rows = []
    X = pd.DataFrame({"x": np.arange(30, dtype=float)})
    y = pd.Series([0, 1] * 15)
    X_holdout = pd.DataFrame({"x": [100.0, 101.0, 102.0, 103.0]})
    y_holdout = pd.Series([0, 1, 0, 1])
    result = fit_candidate(
        X, y, LogisticRegression(),
        final_holdout=(X_holdout, y_holdout),
        sampler=RecordingSampler(),
    )
    assert len(RecordingSampler.seen_rows) >= 4  # three CV fits + development refit
    assert max(RecordingSampler.seen_rows) == len(X)
    assert all(size < len(X) for size in RecordingSampler.seen_rows[:-1])
    assert result["holdout_rows"] == len(X_holdout)


def test_duplicate_predictor_observations_do_not_cross_holdout_boundary():
    X = pd.DataFrame({"value": np.arange(20, dtype=float), "kind": ["a", "b"] * 10})
    X.loc[18] = X.loc[0]
    X.loc[19] = X.loc[1]
    y = pd.Series([0, 1] * 10)
    split = holdout_split(X, y, random_state=7)
    train_hashes = set(pd.util.hash_pandas_object(X.iloc[split.train_indices], index=False))
    holdout_hashes = set(pd.util.hash_pandas_object(X.iloc[split.holdout_indices], index=False))
    assert train_hashes.isdisjoint(holdout_hashes)
    assert split.group_column == "entity+duplicate_predictor_groups"


def test_duplicate_rows_are_kept_together_in_validation_folds():
    from sklearn.model_selection import StratifiedGroupKFold

    X = pd.DataFrame({"value": np.arange(20, dtype=float)})
    X.loc[18] = X.loc[0]
    X.loc[19] = X.loc[1]
    y = pd.Series([0, 1] * 10)
    groups, _ = _merge_entity_and_duplicate_groups(X, pd.Series([f"id-{i}" for i in range(len(X))]))
    assert groups is not None
    for train, validation in StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42).split(X, y, groups):
        assert set(groups.iloc[train]).isdisjoint(set(groups.iloc[validation]))
