"""Leakage-safe candidate training and holdout evaluation utilities.

Candidate artifacts are deliberately separate from the legacy inference
artifacts. Preprocessing and random oversampling live inside the estimator
pipeline so each cross-validation fit sees only its training fold.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence
import json

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import RandomOverSampler
from imblearn.pipeline import Pipeline as ImbalancedPipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, confusion_matrix, f1_score, matthews_corrcoef,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class HoldoutSplit:
    train_indices: np.ndarray
    holdout_indices: np.ndarray
    strategy: str
    group_column: str | None


def _merge_entity_and_duplicate_groups(
    features: pd.DataFrame, groups: pd.Series | None,
) -> tuple[pd.Series | None, str | None]:
    """Keep repeated entities and identical predictor rows in one group."""
    duplicate_rows = features.duplicated(keep=False)
    if groups is None and not duplicate_rows.any():
        return None, None
    values = groups.astype(str).tolist() if groups is not None else [str(i) for i in range(len(features))]
    parent = list(range(len(values)))
    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)
    def join_equal(keys: list[str]) -> None:
        first: dict[str, int] = {}
        for i, value in enumerate(keys):
            if value in first:
                union(i, first[value])
            else:
                first[value] = i
    if groups is not None:
        join_equal(values)
    if duplicate_rows.any():
        fingerprints = pd.util.hash_pandas_object(features, index=False).astype(str).tolist()
        join_equal(fingerprints)
    merged = pd.Series([str(find(i)) for i in range(len(values))])
    if not merged.duplicated().any():
        return None, None
    return merged, "entity+duplicate_predictor_groups"


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    """Stable fingerprint of ordered column names and row values."""
    digest = sha256()
    digest.update(json.dumps([str(column) for column in frame.columns], separators=(",", ":")).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy(dtype="uint64").tobytes())
    return digest.hexdigest()


def holdout_split(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    groups: pd.Series | None = None,
    group_column: str | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> HoldoutSplit:
    """Create one untouched, stratified holdout, grouping repeated entities.

    If the supplied group column is unique and there are no duplicate feature
    rows, stratified row sampling is equivalent and preserves class balance.
    Repeated entities or identical predictor rows are kept in one partition.
    """
    y = np.asarray(target, dtype=int)
    if len(features) != len(y):
        raise ValueError("Predictors and target must have the same row count.")
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Holdout evaluation requires both binary target classes 0 and 1.")

    normalized_groups = groups.reset_index(drop=True) if groups is not None else None
    resolved_groups, resolved_name = _merge_entity_and_duplicate_groups(features, normalized_groups)
    resolved_name = resolved_name or (group_column if resolved_groups is not None else None)

    indices = np.arange(len(features))
    if resolved_groups is None:
        train, holdout = train_test_split(
            indices, test_size=test_size, random_state=random_state, stratify=y,
        )
        return HoldoutSplit(train, holdout, "Stratified random holdout (80/20)", None)

    group_values = resolved_groups.astype(str).to_numpy()
    minimum_groups = min(
        len(np.unique(group_values[y == label])) for label in (0, 1)
    )
    folds = min(5, minimum_groups)
    if folds < 2:
        raise ValueError("Repeated-entity holdout needs at least two independent groups per class.")
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=random_state)
    for train, holdout in splitter.split(features, y, group_values):
        if set(y[train]) == {0, 1} and set(y[holdout]) == {0, 1}:
            return HoldoutSplit(
                train, holdout,
                f"StratifiedGroupKFold ({folds} folds; one held-out fold)",
                resolved_name,
            )
    raise ValueError("Could not form a grouped holdout containing both target classes.")


def make_training_pipeline(
    features: pd.DataFrame,
    estimator: Any,
    *,
    random_state: int = 42,
    sampler: Any | None = None,
) -> ImbalancedPipeline:
    """Create fold-local imputation, encoding, scaling and resampling.

    RandomOverSampler is used after one-hot encoding instead of SMOTE: it
    duplicates minority training rows and cannot create fractional category
    indicators. Trees do not require scale invariance, but keeping numeric
    scaling inside this pipeline preserves the existing sector preparation
    convention without leaking holdout statistics.
    """
    numeric = list(features.select_dtypes(include=["number", "bool"]).columns)
    categorical = [column for column in features.columns if column not in numeric]
    transforms = []
    if numeric:
        transforms.append((
            "numeric",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            numeric,
        ))
    if categorical:
        transforms.append((
            "categorical",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encode", OneHotEncoder(handle_unknown="ignore")),
            ]),
            categorical,
        ))
    if not transforms:
        raise ValueError("At least one predictor is required for training.")

    preprocessor = ColumnTransformer(transforms, remainder="drop")
    return ImbalancedPipeline([
        ("preprocess", preprocessor),
        ("sampler", sampler or RandomOverSampler(random_state=random_state)),
        ("model", estimator),
    ])


def classification_metrics(target: Sequence[int], probabilities: Sequence[float]) -> dict[str, Any]:
    y_true = np.asarray(target, dtype=int)
    y_score = np.asarray(probabilities, dtype=float)
    if y_score.shape != y_true.shape or not np.isfinite(y_score).all():
        raise ValueError("Evaluation probabilities must be finite and row-aligned with the target.")
    if ((y_score < 0) | (y_score > 1)).any():
        raise ValueError("Evaluation probabilities must be between zero and one.")
    y_pred = (y_score >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_score)),
        "pr_auc_average_precision": float(average_precision_score(y_true, y_score)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "matthews_correlation": float(matthews_corrcoef(y_true, y_pred)),
        "brier_score": float(brier_score_loss(y_true, y_score)),
        "confusion_matrix_labels_0_1": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
        "decision_threshold": 0.5,
    }


def fit_candidate(
    features: pd.DataFrame,
    target: pd.Series,
    estimator: Any,
    *,
    groups: pd.Series | None = None,
    group_column: str | None = None,
    parameter_grid: dict[str, list[Any]] | None = None,
    selection_metric: str = "roc_auc",
    random_state: int = 42,
    final_holdout: tuple[pd.DataFrame, pd.Series] | None = None,
    split_description: str | None = None,
    sampler: Any | None = None,
) -> dict[str, Any]:
    """Tune on development folds, refit development only, evaluate holdout once."""
    if not features.index.equals(target.index):
        target = target.reindex(features.index)
    if target.isna().any():
        raise ValueError("Target contains missing values after alignment.")
    target = target.astype(int)
    if final_holdout is None:
        split = holdout_split(
            features, target, groups=groups, group_column=group_column,
            random_state=random_state,
        )
        X_train = features.iloc[split.train_indices].reset_index(drop=True)
        X_holdout = features.iloc[split.holdout_indices].reset_index(drop=True)
        y_train = target.iloc[split.train_indices].reset_index(drop=True)
        y_holdout = target.iloc[split.holdout_indices].reset_index(drop=True)
        train_groups = groups.iloc[split.train_indices].reset_index(drop=True) if groups is not None else None
    else:
        X_train = features.reset_index(drop=True)
        y_train = target.reset_index(drop=True)
        X_holdout, y_holdout = final_holdout
        X_holdout = X_holdout.reset_index(drop=True)
        y_holdout = y_holdout.reset_index(drop=True).astype(int)
        if len(X_holdout) != len(y_holdout) or len(X_holdout) == 0:
            raise ValueError("Explicit final holdout must contain aligned, non-empty rows.")
        train_groups = groups.reset_index(drop=True) if groups is not None else None
        split = HoldoutSplit(
            np.arange(len(X_train)), np.arange(len(X_holdout)),
            split_description or "Externally defined untouched holdout", group_column,
        )
    train_groups, merged_group_name = _merge_entity_and_duplicate_groups(X_train, train_groups)
    if merged_group_name:
        split = HoldoutSplit(split.train_indices, split.holdout_indices, split.strategy, merged_group_name)

    minimum_class = int(y_train.value_counts().min())
    cv_splits = min(3, minimum_class)
    if cv_splits < 2:
        raise ValueError("Development data needs at least two examples of each class for CV.")
    if train_groups is not None and train_groups.duplicated().any():
        class_group_counts = [train_groups[y_train == label].nunique() for label in (0, 1)]
        cv_splits = min(cv_splits, *class_group_counts)
        if cv_splits < 2:
            raise ValueError("Development data lacks enough independent groups for grouped CV.")
        cv = StratifiedGroupKFold(n_splits=cv_splits, shuffle=True, random_state=random_state)
    else:
        cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=random_state)

    pipeline = make_training_pipeline(
        X_train, estimator, random_state=random_state, sampler=sampler,
    )
    search = GridSearchCV(
        pipeline,
        parameter_grid or {},
        scoring=selection_metric,
        cv=cv,
        refit=True,
        n_jobs=1,
        error_score="raise",
        return_train_score=False,
    )
    started = perf_counter()
    fit_kwargs = {"groups": train_groups} if train_groups is not None and train_groups.duplicated().any() else {}
    search.fit(X_train, y_train, **fit_kwargs)
    training_seconds = perf_counter() - started
    model = search.best_estimator_
    probabilities = model.predict_proba(X_holdout)[:, list(model.classes_).index(1)]
    return {
        "model": model,
        "split": split,
        "holdout_metrics": classification_metrics(y_holdout, probabilities),
        "cv_selection_metric": selection_metric,
        "cv_best_mean_score": float(search.best_score_),
        "cv_results": search.cv_results_,
        "best_parameters": search.best_params_,
        "training_seconds": training_seconds,
        "development_rows": len(X_train),
        "holdout_rows": len(X_holdout),
        "development_class_distribution": y_train.value_counts().sort_index().to_dict(),
        "holdout_class_distribution": y_holdout.value_counts().sort_index().to_dict(),
    }


def write_candidate_artifacts(
    result: dict[str, Any],
    *,
    output_directory: str | Path,
    model_name: str,
    metadata: dict[str, Any],
) -> tuple[Path, Path]:
    """Persist a candidate pipeline and JSON report without touching active artifacts."""
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / f"{model_name}.joblib"
    report_path = directory / f"{model_name}.json"
    if model_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite candidate artifacts in {directory}.")
    joblib.dump(result["model"], model_path)
    payload = {
        **metadata,
        "validation": {
            "holdout_strategy": result["split"].strategy,
            "group_column": result["split"].group_column,
            "development_rows": result["development_rows"],
            "holdout_rows": result["holdout_rows"],
            "development_class_distribution": result["development_class_distribution"],
            "holdout_class_distribution": result["holdout_class_distribution"],
            "cv_selection_metric": result["cv_selection_metric"],
            "cv_best_mean_score": result["cv_best_mean_score"],
            "best_parameters": result["best_parameters"],
            "holdout_metrics": result["holdout_metrics"],
            "training_seconds": result["training_seconds"],
            "probability_calibration": "Not calibrated; Brier score is diagnostic only.",
        },
    }
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return model_path, report_path
