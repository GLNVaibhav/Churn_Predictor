"""Standalone V2 trainer for canonical, cross-enterprise sector models.

No V1 inference, routing, or model artifact imports this module.  Models
created here are new future-use artifacts trained solely on V2 canonical
training datasets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss,
    confusion_matrix, f1_score, matthews_corrcoef, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import ParameterGrid, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .canonical_feature_builder import load_canonical_feature_specifications
from .preprocessing import normalize_target


@dataclass(frozen=True)
class UniversalTrainingConfig:
    random_state: int = 42
    stratified_folds: int = 5
    max_parameter_candidates: int = 3
    algorithms: tuple[str, ...] = (
        "xgboost", "lightgbm", "catboost", "random_forest", "hist_gradient_boosting", "logistic_regression",
    )
    model_directory: str = "outputs/universal/sector_models_v2"


@dataclass(frozen=True)
class EvaluationFold:
    held_out_origin: str
    metrics: dict[str, float]
    confusion_matrix: tuple[tuple[int, int], tuple[int, int]]


@dataclass(frozen=True)
class AlgorithmBenchmark:
    algorithm: str
    available: bool
    best_parameters: dict[str, Any]
    folds: tuple[EvaluationFold, ...]
    mean_metrics: dict[str, float]
    metric_stddev: dict[str, float]
    selection_score: float | None
    training_seconds: float
    note: str | None = None


@dataclass(frozen=True)
class LegacyComparison:
    available: bool
    universal_metrics: dict[str, float]
    legacy_metrics: dict[str, float] | None
    delta: dict[str, float]
    note: str


@dataclass(frozen=True)
class UniversalModelTrainingResult:
    sector: str
    canonical_feature_order: tuple[str, ...]
    training_origins: tuple[str, ...]
    validation_strategy: str
    benchmarks: tuple[AlgorithmBenchmark, ...]
    selected_algorithm: str
    selected_parameters: dict[str, Any]
    selected_metrics: dict[str, float]
    model_path: Path
    report_path: Path
    legacy_comparison: LegacyComparison


def _safe_metric(function: Callable[..., float], *args: Any) -> float:
    try:
        return float(function(*args))
    except (ValueError, TypeError):
        return float("nan")


def _metrics(y_true: np.ndarray, probability: np.ndarray) -> tuple[dict[str, float], tuple[tuple[int, int], tuple[int, int]]]:
    prediction = (probability >= 0.5).astype(int)
    matrix = confusion_matrix(y_true, prediction, labels=[0, 1])
    metric_values = {
        "accuracy": float(accuracy_score(y_true, prediction)),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
        "roc_auc": _safe_metric(roc_auc_score, y_true, probability),
        "pr_auc": _safe_metric(average_precision_score, y_true, probability),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "matthews_correlation": _safe_metric(matthews_corrcoef, y_true, prediction),
        # Higher is better and bounded at one for straightforward selection.
        "calibration_score": 1.0 - float(brier_score_loss(y_true, probability)),
    }
    return metric_values, tuple(tuple(int(cell) for cell in row) for row in matrix)  # type: ignore[return-value]


def _mean_metrics(folds: Iterable[EvaluationFold]) -> tuple[dict[str, float], dict[str, float]]:
    rows = [fold.metrics for fold in folds]
    if not rows: return {}, {}
    names = rows[0].keys()
    return (
        {name: float(np.nanmean([row[name] for row in rows])) for name in names},
        {name: float(np.nanstd([row[name] for row in rows])) for name in names},
    )


def _selection_score(metrics: dict[str, float], deviation: dict[str, float]) -> float:
    """Prioritise discrimination, recall and calibration, with LODOCV stability."""
    def value(name: str) -> float: return 0.0 if np.isnan(metrics.get(name, np.nan)) else metrics[name]
    instability = 0.0 if np.isnan(deviation.get("roc_auc", np.nan)) else deviation["roc_auc"]
    return 0.40 * value("roc_auc") + 0.25 * value("f1") + 0.20 * value("recall") + 0.15 * value("calibration_score") - 0.10 * instability


def _preprocessor(features: pd.DataFrame) -> ColumnTransformer:
    numeric = list(features.select_dtypes(include=[np.number, "bool"]).columns)
    categorical = [column for column in features.columns if column not in numeric]
    return ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical),
    ], remainder="drop")


def _algorithm_catalog(config: UniversalTrainingConfig) -> dict[str, tuple[Callable[[], Any] | None, list[dict[str, Any]], str | None]]:
    catalog: dict[str, tuple[Callable[[], Any] | None, list[dict[str, Any]], str | None]] = {
        "random_forest": (
            lambda: RandomForestClassifier(random_state=config.random_state, n_jobs=1, class_weight="balanced"),
            [{"n_estimators": 250, "max_depth": depth, "min_samples_leaf": leaf} for depth, leaf in ((None, 1), (8, 2), (14, 3))], None),
        "hist_gradient_boosting": (
            lambda: HistGradientBoostingClassifier(random_state=config.random_state),
            [{"learning_rate": rate, "max_leaf_nodes": leaves, "l2_regularization": penalty} for rate, leaves, penalty in ((0.08, 15, 0.0), (0.05, 31, 0.1), (0.12, 15, 0.2))], None),
        "logistic_regression": (
            lambda: LogisticRegression(random_state=config.random_state, max_iter=2000, class_weight="balanced"),
            [{"C": value} for value in (0.25, 1.0, 4.0)], None),
    }
    try:
        from xgboost import XGBClassifier
        catalog["xgboost"] = (
            lambda: XGBClassifier(random_state=config.random_state, eval_metric="logloss", n_jobs=1),
            [{"n_estimators": count, "max_depth": depth, "learning_rate": rate, "subsample": 0.9, "colsample_bytree": 0.9}
             for count, depth, rate in ((200, 3, 0.05), (300, 4, 0.05), (200, 5, 0.10))], None)
    except ImportError:
        catalog["xgboost"] = (None, [], "xgboost is not installed.")
    try:
        from lightgbm import LGBMClassifier
        catalog["lightgbm"] = (
            lambda: LGBMClassifier(random_state=config.random_state, n_jobs=1, verbosity=-1),
            [{"n_estimators": count, "num_leaves": leaves, "learning_rate": rate} for count, leaves, rate in ((200, 15, .05), (300, 31, .05), (200, 31, .10))], None)
    except ImportError:
        catalog["lightgbm"] = (None, [], "lightgbm is not installed.")
    try:
        from catboost import CatBoostClassifier
        catalog["catboost"] = (
            lambda: CatBoostClassifier(random_state=config.random_state, verbose=False, allow_writing_files=False),
            [{"iterations": iterations, "depth": depth, "learning_rate": rate} for iterations, depth, rate in ((200, 4, .05), (300, 5, .05), (200, 6, .10))], None)
    except ImportError:
        catalog["catboost"] = (None, [], "catboost is not installed.")
    return catalog


def _folds(origins: pd.Series, target: pd.Series, config: UniversalTrainingConfig) -> tuple[list[tuple[np.ndarray, np.ndarray, str]], str]:
    distinct = tuple(sorted(origins.astype(str).unique()))
    if len(distinct) > 1:
        output = []
        for origin in distinct:
            test = np.flatnonzero(origins.astype(str).to_numpy() == origin)
            train = np.flatnonzero(origins.astype(str).to_numpy() != origin)
            if len(set(target.iloc[train])) >= 2:
                output.append((train, test, origin))
        if output: return output, "Leave-One-Dataset-Out Cross Validation"
    minimum_class = int(target.value_counts().min())
    folds = min(config.stratified_folds, minimum_class)
    if folds < 2: raise ValueError("Training target requires two classes with at least two observations each.")
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=config.random_state)
    return [(train, test, f"StratifiedFold{index + 1}") for index, (train, test) in enumerate(splitter.split(np.zeros(len(target)), target))], "Stratified K-Fold (single enterprise fallback)"


def _evaluate_candidate(
    algorithm: str, estimator_factory: Callable[[], Any], parameters: dict[str, Any],
    features: pd.DataFrame, target: pd.Series, folds: list[tuple[np.ndarray, np.ndarray, str]],
) -> tuple[tuple[EvaluationFold, ...], float]:
    started = perf_counter(); evaluated = []
    for train, test, origin in folds:
        model = Pipeline([("preprocess", _preprocessor(features)), ("model", estimator_factory())])
        model.set_params(**{f"model__{key}": value for key, value in parameters.items()})
        model.fit(features.iloc[train], target.iloc[train])
        probabilities = model.predict_proba(features.iloc[test])[:, 1]
        metrics, matrix = _metrics(target.iloc[test].to_numpy(), probabilities)
        evaluated.append(EvaluationFold(origin, metrics, matrix))
    return tuple(evaluated), perf_counter() - started


def _validate_canonical_dataset(frame: pd.DataFrame, sector: str) -> tuple[pd.DataFrame, pd.Series, pd.Series, tuple[str, ...]]:
    canonical = tuple(spec.name for spec in load_canonical_feature_specifications(sector))
    required = set(canonical) | {"Target", "DatasetOrigin"}
    missing = sorted(required - set(frame.columns))
    if missing: raise ValueError(f"Canonical training dataset is missing required columns: {missing}")
    target = normalize_target(frame["Target"])
    if len(set(target)) != 2: raise ValueError("Universal training requires a binary Target with both classes.")
    return frame.loc[:, canonical].copy(), target, frame["DatasetOrigin"].astype(str), canonical


def compare_legacy_and_universal(
    universal_metrics: dict[str, float], legacy_metrics: dict[str, float] | None = None,
) -> LegacyComparison:
    """Compare externally measured legacy metrics without invoking V1 models."""
    if legacy_metrics is None:
        return LegacyComparison(False, universal_metrics, None, {}, "Legacy comparison requires externally supplied, like-for-like benchmark metrics.")
    common = set(universal_metrics) & set(legacy_metrics)
    delta = {name: universal_metrics[name] - legacy_metrics[name] for name in common}
    return LegacyComparison(True, universal_metrics, legacy_metrics, delta, "Metrics were compared without changing or invoking V1 inference.")


def _render_report(result: UniversalModelTrainingResult, frame: pd.DataFrame) -> str:
    lines = [f"# Universal {result.sector.title()} Model Report", "", "## Dataset composition", "",
             f"- Rows: {len(frame)}", f"- Enterprise datasets: {', '.join(result.training_origins)}",
             f"- Validation: {result.validation_strategy}", f"- Canonical features: {', '.join(result.canonical_feature_order)}", "", "## Algorithm comparison", "",
             "| Algorithm | Available | ROC-AUC | F1 | Recall | PR-AUC | Calibration | Selection score |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for benchmark in result.benchmarks:
        metrics = benchmark.mean_metrics
        metric = lambda name: "—" if name not in metrics or np.isnan(metrics[name]) else f"{metrics[name]:.4f}"
        selection = "—" if benchmark.selection_score is None else f"{benchmark.selection_score:.4f}"
        lines.append(f"| {benchmark.algorithm} | {benchmark.available} | {metric('roc_auc')} | {metric('f1')} | {metric('recall')} | {metric('pr_auc')} | {metric('calibration_score')} | {selection} |")
        if benchmark.note: lines.append(f"\n{benchmark.algorithm}: {benchmark.note}")
    lines += ["", "## Selected model", "", f"- Algorithm: {result.selected_algorithm}", f"- Parameters: `{json.dumps(result.selected_parameters, sort_keys=True)}`", f"- Metrics: `{json.dumps(result.selected_metrics, sort_keys=True)}`", "", "## Cross-enterprise validation", ""]
    selected = next(item for item in result.benchmarks if item.algorithm == result.selected_algorithm)
    for fold in selected.folds:
        lines.append(f"- {fold.held_out_origin}: `{json.dumps(fold.metrics, sort_keys=True)}`, confusion matrix `{fold.confusion_matrix}`")
    lines += ["", "## Legacy vs Universal", "", result.legacy_comparison.note, "", "## Limitations", "", "- This V2 artifact is not connected to V1 inference or routing.", "- Results reflect only the accepted canonical datasets and held-out enterprise composition.", "- Optional LightGBM/CatBoost benchmarks are skipped when those libraries are not installed."]
    return "\n".join(lines) + "\n"


def train_universal_sector_model(
    canonical_dataset: pd.DataFrame, *, sector: str,
    config: UniversalTrainingConfig | None = None,
    legacy_metrics: dict[str, float] | None = None,
) -> UniversalModelTrainingResult:
    """Benchmark, select, refit, and persist a new canonical-sector model."""
    configuration = config or UniversalTrainingConfig()
    features, target, origins, canonical_order = _validate_canonical_dataset(canonical_dataset, sector)
    folds, strategy = _folds(origins, target, configuration)
    catalog = _algorithm_catalog(configuration)
    benchmarks: list[AlgorithmBenchmark] = []
    for algorithm in configuration.algorithms:
        if algorithm not in catalog: raise ValueError(f"Unknown algorithm '{algorithm}'.")
        factory, candidates, unavailable = catalog[algorithm]
        if factory is None:
            benchmarks.append(AlgorithmBenchmark(algorithm, False, {}, (), {}, {}, None, 0.0, unavailable)); continue
        best: AlgorithmBenchmark | None = None
        for parameters in list(ParameterGrid(candidates))[:configuration.max_parameter_candidates]:
            try:
                evaluated, seconds = _evaluate_candidate(algorithm, factory, parameters, features, target, folds)
                means, deviations = _mean_metrics(evaluated)
                candidate = AlgorithmBenchmark(algorithm, True, parameters, evaluated, means, deviations, _selection_score(means, deviations), seconds)
                if best is None or (candidate.selection_score or -np.inf) > (best.selection_score or -np.inf): best = candidate
            except ValueError as exc:
                best = best or AlgorithmBenchmark(algorithm, True, parameters, (), {}, {}, None, 0.0, str(exc))
        if best is not None: benchmarks.append(best)
    eligible = [item for item in benchmarks if item.available and item.selection_score is not None]
    if not eligible: raise ValueError("No candidate algorithm completed cross-enterprise evaluation.")
    selected = max(eligible, key=lambda item: item.selection_score or -np.inf)
    factory = catalog[selected.algorithm][0]
    assert factory is not None
    final_model = Pipeline([("preprocess", _preprocessor(features)), ("model", factory())])
    final_model.set_params(**{f"model__{key}": value for key, value in selected.best_parameters.items()})
    final_model.fit(features, target)
    comparison = compare_legacy_and_universal(selected.mean_metrics, legacy_metrics)
    output_dir = Path(configuration.model_directory); output_dir.mkdir(parents=True, exist_ok=True)
    title = sector.title()
    model_path = output_dir / f"Universal_{title}_Model.pkl"
    report_path = output_dir / f"Universal_{title}_Model_Report.md"
    bundle = {
        "model": final_model, "sector": sector.lower(), "feature_specification_version": "v2",
        "canonical_feature_order": canonical_order, "training_configuration": asdict(configuration),
        "selected_algorithm": selected.algorithm, "selected_parameters": selected.best_parameters,
        "selected_metrics": selected.mean_metrics, "training_datasets": tuple(sorted(origins.unique())),
        "validation_strategy": strategy,
    }
    joblib.dump(bundle, model_path)
    provisional = UniversalModelTrainingResult(sector.lower(), canonical_order, tuple(sorted(origins.unique())), strategy, tuple(benchmarks), selected.algorithm, selected.best_parameters, selected.mean_metrics, model_path, report_path, comparison)
    report_path.write_text(_render_report(provisional, canonical_dataset), encoding="utf-8")
    return provisional


def train_universal_sector_model_from_csv(
    path: str | Path, *, sector: str, config: UniversalTrainingConfig | None = None,
    legacy_metrics: dict[str, float] | None = None,
) -> UniversalModelTrainingResult:
    return train_universal_sector_model(pd.read_csv(path), sector=sector, config=config, legacy_metrics=legacy_metrics)
