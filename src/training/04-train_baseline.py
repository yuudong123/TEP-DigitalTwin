from __future__ import annotations

import argparse
import gc
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

MODEL_ROOT = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "04-baseline"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "04-baseline"
)

FEATURE_SCHEMA_PATH = (
    METADATA_DIR
    / "feature_schema.csv"
)


# ============================================================
# Settings
# ============================================================

RANDOM_STATE = 42

MAX_BOOST_ROUNDS = 1000
EARLY_STOPPING_ROUNDS = 50

CLASSIFICATION_TARGETS = {
    "failure_within_4h": 4.0,
    "failure_within_2h": 2.0,
    "failure_within_1h": 1.0,
}

TARGET_COLUMNS = [
    "rul_hours",
    "failure_within_4h",
    "failure_within_2h",
    "failure_within_1h",
]

META_COLUMNS = [
    "trajectory_key",
    "Time",
]


# ============================================================
# Utility
# ============================================================

def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def parse_bool_column(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


# ============================================================
# CUDA check
# ============================================================

def check_cuda() -> None:
    section("CUDA CHECK")

    print(f"XGBoost version: {xgb.__version__}")

    X = np.array(
        [
            [0.0, 1.0],
            [1.0, 0.0],
            [0.5, 0.5],
            [1.0, 1.0],
        ],
        dtype=np.float32,
    )

    y = np.array(
        [0, 1, 0, 1],
        dtype=np.float32,
    )

    dtrain = xgb.DMatrix(X, label=y)

    params = {
        "objective": "binary:logistic",
        "tree_method": "hist",
        "device": "cuda",
        "verbosity": 1,
    }

    xgb.train(
        params,
        dtrain,
        num_boost_round=2,
    )

    print("[PASS] XGBoost CUDA training available")


# ============================================================
# Feature schema
# ============================================================

def load_feature_sets() -> dict[str, list[str]]:
    schema = pd.read_csv(FEATURE_SCHEMA_PATH)

    schema["model_a_feature"] = parse_bool_column(
        schema["model_a_feature"]
    )

    schema["model_b_feature"] = parse_bool_column(
        schema["model_b_feature"]
    )

    model_a = schema.loc[
        schema["model_a_feature"],
        "column",
    ].tolist()

    model_b = schema.loc[
        schema["model_b_feature"],
        "column",
    ].tolist()

    if len(model_a) != 41:
        raise ValueError(
            f"Model A feature count error: {len(model_a)}"
        )

    if len(model_b) != 52:
        raise ValueError(
            f"Model B feature count error: {len(model_b)}"
        )

    return {
        "model_a": model_a,
        "model_b": model_b,
    }


# ============================================================
# Dataset
# ============================================================

def load_split(
    split: str,
    feature_columns: list[str],
) -> pd.DataFrame:

    path = PROCESSED_DIR / f"{split}.parquet"

    required_columns = (
        feature_columns
        + META_COLUMNS
        + TARGET_COLUMNS
    )

    # 중복 컬럼 방지
    required_columns = list(
        dict.fromkeys(required_columns)
    )

    print(f"[LOAD] {path.name}")

    df = pd.read_parquet(
        path,
        columns=required_columns,
    )

    return df


def build_dmatrix(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> xgb.DMatrix:

    X = df[feature_columns].to_numpy(
        dtype=np.float32,
    )

    return xgb.DMatrix(
        X,
        feature_names=feature_columns,
    )


# ============================================================
# Threshold
# ============================================================

def choose_f1_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
) -> tuple[float, float]:

    precision, recall, thresholds = (
        precision_recall_curve(
            y_true,
            probabilities,
        )
    )

    if len(thresholds) == 0:
        return 0.5, 0.0

    precision = precision[:-1]
    recall = recall[:-1]

    denominator = precision + recall

    f1 = np.divide(
        2.0 * precision * recall,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )

    best_index = int(np.nanargmax(f1))

    return (
        float(thresholds[best_index]),
        float(f1[best_index]),
    )


# ============================================================
# Prediction
# ============================================================

def predict_best(
    model: xgb.Booster,
    matrix: xgb.DMatrix,
) -> np.ndarray:

    best_iteration = getattr(
        model,
        "best_iteration",
        None,
    )

    if best_iteration is None:
        return model.predict(matrix)

    return model.predict(
        matrix,
        iteration_range=(
            0,
            best_iteration + 1,
        ),
    )


# ============================================================
# Regression metrics
# ============================================================

def regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:

    # 실제 RUL은 음수가 될 수 없음
    y_pred = np.clip(
        y_pred,
        a_min=0.0,
        a_max=None,
    )

    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    median_ae = median_absolute_error(
        y_true,
        y_pred,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred,
        )
    )

    r2 = r2_score(
        y_true,
        y_pred,
    )

    return {
        "mae": float(mae),
        "median_absolute_error": float(median_ae),
        "rmse": float(rmse),
        "r2": float(r2),
    }


# ============================================================
# Classification metrics
# ============================================================

def classification_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict:

    predicted = (
        probabilities >= threshold
    ).astype(np.int8)

    ap = average_precision_score(
        y_true,
        probabilities,
    )

    roc_auc = roc_auc_score(
        y_true,
        probabilities,
    )

    precision = precision_score(
        y_true,
        predicted,
        zero_division=0,
    )

    recall = recall_score(
        y_true,
        predicted,
        zero_division=0,
    )

    f1 = f1_score(
        y_true,
        predicted,
        zero_division=0,
    )

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predicted,
        labels=[0, 1],
    ).ravel()

    fpr = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0.0
    )

    return {
        "average_precision": float(ap),
        "roc_auc": float(roc_auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "point_fpr": float(fpr),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


# ============================================================
# Event-level metrics
# ============================================================

def event_metrics(
    trajectory_keys: pd.Series,
    rul_hours: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
    horizon_hours: float,
) -> dict:

    evaluation = pd.DataFrame(
        {
            "trajectory_key": trajectory_keys.to_numpy(),
            "rul_hours": rul_hours.to_numpy(),
            "probability": probabilities,
        }
    )

    detected_count = 0
    early_alert_count = 0

    warning_leads = []

    total_trajectories = (
        evaluation["trajectory_key"].nunique()
    )

    for _, group in evaluation.groupby(
        "trajectory_key",
        sort=False,
    ):
        group = group.reset_index(drop=True)

        alerts = (
            group["probability"].to_numpy()
            >= threshold
        )

        # 2개 연속 양성일 때 두 번째 시점에 실제 경고 발생
        sustained = np.zeros(
            len(alerts),
            dtype=bool,
        )

        if len(alerts) >= 2:
            sustained[1:] = (
                alerts[:-1]
                & alerts[1:]
            )

        rul = group[
            "rul_hours"
        ].to_numpy()

        inside_horizon = (
            rul <= horizon_hours
        )

        valid_alerts = np.where(
            sustained & inside_horizon
        )[0]

        if len(valid_alerts) > 0:
            detected_count += 1

            first_alert_index = (
                valid_alerts[0]
            )

            warning_leads.append(
                float(
                    rul[first_alert_index]
                )
            )

        # horizon보다 더 일찍 지속 경고가 있었는지 별도 기록
        if np.any(
            sustained
            & (rul > horizon_hours)
        ):
            early_alert_count += 1

    detection_rate = (
        detected_count
        / total_trajectories
    )

    early_alert_rate = (
        early_alert_count
        / total_trajectories
    )

    median_lead = (
        float(np.median(warning_leads))
        if warning_leads
        else np.nan
    )

    return {
        "event_detection_rate": float(
            detection_rate
        ),
        "median_warning_lead_hours": (
            median_lead
        ),
        "early_alert_trajectory_rate": float(
            early_alert_rate
        ),
        "detected_trajectories": int(
            detected_count
        ),
        "total_trajectories": int(
            total_trajectories
        ),
    }


# ============================================================
# Params
# ============================================================

def regression_params() -> dict:
    return {
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "tree_method": "hist",
        "device": "cuda",
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "seed": RANDOM_STATE,
    }


def classification_params(
    scale_pos_weight: float,
) -> dict:

    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "device": "cuda",
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "scale_pos_weight": scale_pos_weight,
        "seed": RANDOM_STATE,
    }


# ============================================================
# Feature-set training
# ============================================================

def train_feature_set(
    feature_set_name: str,
    feature_columns: list[str],
) -> list[dict]:

    section(
        f"TRAINING {feature_set_name.upper()}"
    )

    print(
        f"Feature count: "
        f"{len(feature_columns)}"
    )

    train_df = load_split(
        "train",
        feature_columns,
    )

    validation_df = load_split(
        "validation",
        feature_columns,
    )

    test_df = load_split(
        "test",
        feature_columns,
    )

    section("BUILD DMATRIX")

    dtrain = build_dmatrix(
        train_df,
        feature_columns,
    )

    dvalidation = build_dmatrix(
        validation_df,
        feature_columns,
    )

    dtest = build_dmatrix(
        test_df,
        feature_columns,
    )

    model_dir = (
        MODEL_ROOT
        / feature_set_name
    )

    model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict] = []

    # ========================================================
    # RUL Regression
    # ========================================================

    section(
        f"{feature_set_name}: RUL REGRESSION"
    )

    y_train = train_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_validation = validation_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_test = test_df[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    dtrain.set_label(y_train)
    dvalidation.set_label(
        y_validation
    )

    model = xgb.train(
        regression_params(),
        dtrain,
        num_boost_round=MAX_BOOST_ROUNDS,
        evals=[
            (dtrain, "train"),
            (
                dvalidation,
                "validation",
            ),
        ],
        early_stopping_rounds=(
            EARLY_STOPPING_ROUNDS
        ),
        verbose_eval=50,
    )

    validation_pred = predict_best(
        model,
        dvalidation,
    )

    test_pred = predict_best(
        model,
        dtest,
    )

    validation_result = (
        regression_metrics(
            y_validation,
            validation_pred,
        )
    )

    test_result = regression_metrics(
        y_test,
        test_pred,
    )

    model_path = (
        model_dir
        / "rul_hours.json"
    )

    model.save_model(model_path)

    print()
    print(
        f"Validation MAE: "
        f"{validation_result['mae']:.4f} h"
    )

    print(
        f"Test MAE      : "
        f"{test_result['mae']:.4f} h"
    )

    print(
        f"Test R²       : "
        f"{test_result['r2']:.4f}"
    )

    results.append(
        {
            "feature_set": feature_set_name,
            "feature_count": len(
                feature_columns
            ),
            "task": "regression",
            "target": "rul_hours",
            "best_iteration": getattr(
                model,
                "best_iteration",
                np.nan,
            ),
            "threshold": np.nan,
            "scale_pos_weight": np.nan,

            "validation_mae":
                validation_result["mae"],
            "validation_rmse":
                validation_result["rmse"],
            "validation_r2":
                validation_result["r2"],

            "test_mae":
                test_result["mae"],
            "test_median_absolute_error":
                test_result[
                    "median_absolute_error"
                ],
            "test_rmse":
                test_result["rmse"],
            "test_r2":
                test_result["r2"],
        }
    )

    del model
    gc.collect()

    # ========================================================
    # Classifiers
    # ========================================================

    for (
        target,
        horizon_hours,
    ) in CLASSIFICATION_TARGETS.items():

        section(
            f"{feature_set_name}: {target}"
        )

        y_train = train_df[
            target
        ].to_numpy(
            dtype=np.float32
        )

        y_validation = (
            validation_df[target]
            .to_numpy(
                dtype=np.float32
            )
        )

        y_test = test_df[
            target
        ].to_numpy(
            dtype=np.int8
        )

        positive = float(
            y_train.sum()
        )

        negative = float(
            len(y_train)
            - positive
        )

        scale_pos_weight = (
            negative / positive
        )

        print(
            f"scale_pos_weight = "
            f"{scale_pos_weight:.4f}"
        )

        dtrain.set_label(
            y_train
        )

        dvalidation.set_label(
            y_validation
        )

        model = xgb.train(
            classification_params(
                scale_pos_weight
            ),
            dtrain,
            num_boost_round=(
                MAX_BOOST_ROUNDS
            ),
            evals=[
                (
                    dtrain,
                    "train",
                ),
                (
                    dvalidation,
                    "validation",
                ),
            ],
            early_stopping_rounds=(
                EARLY_STOPPING_ROUNDS
            ),
            verbose_eval=50,
        )

        validation_prob = (
            predict_best(
                model,
                dvalidation,
            )
        )

        test_prob = predict_best(
            model,
            dtest,
        )

        threshold, best_val_f1 = (
            choose_f1_threshold(
                y_validation,
                validation_prob,
            )
        )

        validation_metrics = (
            classification_metrics(
                y_validation.astype(
                    np.int8
                ),
                validation_prob,
                threshold,
            )
        )

        test_metrics = (
            classification_metrics(
                y_test,
                test_prob,
                threshold,
            )
        )

        event_result = event_metrics(
            trajectory_keys=(
                test_df[
                    "trajectory_key"
                ]
            ),
            rul_hours=(
                test_df[
                    "rul_hours"
                ]
            ),
            probabilities=test_prob,
            threshold=threshold,
            horizon_hours=(
                horizon_hours
            ),
        )

        model_path = (
            model_dir
            / f"{target}.json"
        )

        model.save_model(
            model_path
        )

        print()
        print(
            f"Threshold       : "
            f"{threshold:.6f}"
        )

        print(
            f"Validation F1   : "
            f"{best_val_f1:.4f}"
        )

        print(
            f"Test AP         : "
            f"{test_metrics['average_precision']:.4f}"
        )

        print(
            f"Test ROC-AUC    : "
            f"{test_metrics['roc_auc']:.4f}"
        )

        print(
            f"Test Recall     : "
            f"{test_metrics['recall']:.4f}"
        )

        print(
            f"Event Detection : "
            f"{event_result['event_detection_rate']:.4f}"
        )

        print(
            f"Median Lead     : "
            f"{event_result['median_warning_lead_hours']:.4f} h"
        )

        results.append(
            {
                "feature_set": feature_set_name,
                "feature_count": len(
                    feature_columns
                ),
                "task": "classification",
                "target": target,
                "best_iteration": getattr(
                    model,
                    "best_iteration",
                    np.nan,
                ),
                "threshold": threshold,
                "scale_pos_weight":
                    scale_pos_weight,

                "validation_average_precision":
                    validation_metrics[
                        "average_precision"
                    ],
                "validation_roc_auc":
                    validation_metrics[
                        "roc_auc"
                    ],
                "validation_f1":
                    validation_metrics[
                        "f1"
                    ],

                "test_average_precision":
                    test_metrics[
                        "average_precision"
                    ],
                "test_roc_auc":
                    test_metrics[
                        "roc_auc"
                    ],
                "test_precision":
                    test_metrics[
                        "precision"
                    ],
                "test_recall":
                    test_metrics[
                        "recall"
                    ],
                "test_f1":
                    test_metrics[
                        "f1"
                    ],
                "test_point_fpr":
                    test_metrics[
                        "point_fpr"
                    ],

                "event_detection_rate":
                    event_result[
                        "event_detection_rate"
                    ],
                "median_warning_lead_hours":
                    event_result[
                        "median_warning_lead_hours"
                    ],
                "early_alert_trajectory_rate":
                    event_result[
                        "early_alert_trajectory_rate"
                    ],
            }
        )

        del model
        gc.collect()

    del dtrain
    del dvalidation
    del dtest

    del train_df
    del validation_df
    del test_df

    gc.collect()

    return results


# ============================================================
# Main
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--feature-set",
        choices=[
            "A",
            "B",
            "all",
        ],
        default="all",
        help=(
            "A = XMEAS only, "
            "B = XMEAS + XMV, "
            "all = both"
        ),
    )

    args = parser.parse_args()

    section("TEP BASELINE TRAINER")

    check_cuda()

    feature_sets = (
        load_feature_sets()
    )

    selected = []

    if args.feature_set in (
        "A",
        "all",
    ):
        selected.append(
            "model_a"
        )

    if args.feature_set in (
        "B",
        "all",
    ):
        selected.append(
            "model_b"
        )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = []

    for feature_set_name in selected:

        result = train_feature_set(
            feature_set_name,
            feature_sets[
                feature_set_name
            ],
        )

        all_results.extend(
            result
        )

        # 중간 결과도 매번 저장
        pd.DataFrame(
            all_results
        ).to_csv(
            REPORT_DIR
            / "baseline_metrics.csv",
            index=False,
            encoding="utf-8-sig",
        )

    section("FINAL RESULT")

    result_df = pd.DataFrame(
        all_results
    )

    print(
        result_df.to_string(
            index=False
        )
    )

    output_path = (
        REPORT_DIR
        / "baseline_metrics.csv"
    )

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        f"[SAVE] {output_path}"
    )

    print()
    print(
        "[PASS] Baseline training completed"
    )


if __name__ == "__main__":
    main()