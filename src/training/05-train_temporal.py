from __future__ import annotations

import gc
import json
import time
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "temporal"
)

SCHEMA_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "temporal_feature_schema.csv"
)

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "candidates"
    / "05-temporal"
)

REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
)

MAX_ROUNDS = 1000
EARLY_STOPPING = 50
RANDOM_STATE = 42
MAX_BIN = 256

TARGETS = {
    "failure_within_4h": 4.0,
    "failure_within_2h": 2.0,
    "failure_within_1h": 1.0,
}


def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def feature_columns():
    schema = pd.read_csv(SCHEMA_PATH)

    return schema[
        schema["model_feature"] == True
    ]["feature"].tolist()


def load(split, features):
    columns = (
        [
            "trajectory_key",
            "Time",
            "rul_hours",
            "failure_within_4h",
            "failure_within_2h",
            "failure_within_1h",
        ]
        + features
    )

    print(f"[LOAD] {split}.parquet")

    return pd.read_parquet(
        DATA_DIR / f"{split}.parquet",
        columns=columns,
    )


def choose_threshold(y, probability):
    precision, recall, thresholds = (
        precision_recall_curve(
            y,
            probability,
        )
    )

    precision = precision[:-1]
    recall = recall[:-1]

    denominator = precision + recall

    f1 = np.divide(
        2 * precision * recall,
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 0,
    )

    index = int(np.nanargmax(f1))

    return (
        float(thresholds[index]),
        float(f1[index]),
    )


def classification_metrics(
    y,
    probability,
    threshold,
):
    pred = (
        probability >= threshold
    ).astype(np.int8)

    tn, fp, fn, tp = confusion_matrix(
        y,
        pred,
        labels=[0, 1],
    ).ravel()

    return {
        "average_precision":
            average_precision_score(
                y,
                probability,
            ),

        "roc_auc":
            roc_auc_score(
                y,
                probability,
            ),

        "precision":
            precision_score(
                y,
                pred,
                zero_division=0,
            ),

        "recall":
            recall_score(
                y,
                pred,
                zero_division=0,
            ),

        "f1":
            f1_score(
                y,
                pred,
                zero_division=0,
            ),

        "point_fpr":
            fp / (fp + tn),
    }


def event_metrics(
    df,
    probability,
    threshold,
    horizon,
):
    temp = pd.DataFrame(
        {
            "trajectory_key":
                df["trajectory_key"].to_numpy(),

            "rul_hours":
                df["rul_hours"].to_numpy(),

            "probability":
                probability,
        }
    )

    detected = 0
    leads = []

    for _, group in temp.groupby(
        "trajectory_key",
        sort=False,
    ):
        alert = (
            group["probability"]
            .to_numpy()
            >= threshold
        )

        sustained = np.zeros(
            len(alert),
            dtype=bool,
        )

        sustained[1:] = (
            alert[:-1]
            & alert[1:]
        )

        rul = (
            group["rul_hours"]
            .to_numpy()
        )

        indexes = np.where(
            sustained
            & (rul <= horizon)
        )[0]

        if len(indexes):
            detected += 1

            leads.append(
                float(
                    rul[indexes[0]]
                )
            )

    total = (
        temp["trajectory_key"]
        .nunique()
    )

    return {
        "event_detection_rate":
            detected / total,

        "median_warning_lead_hours":
            float(np.median(leads))
            if leads
            else np.nan,
    }


def regression_params():
    return {
        "objective": "reg:squarederror",
        "eval_metric": "mae",
        "tree_method": "hist",
        "device": "cuda",
        "max_bin": MAX_BIN,
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "seed": RANDOM_STATE,
    }


def classifier_params(weight):
    return {
        "objective": "binary:logistic",
        "eval_metric": "aucpr",
        "tree_method": "hist",
        "device": "cuda",
        "max_bin": MAX_BIN,
        "eta": 0.05,
        "max_depth": 8,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": weight,
        "seed": RANDOM_STATE,
    }


def main():

    section("TEMPORAL MODEL TRAINING")

    features = feature_columns()

    if len(features) != 728:
        raise ValueError(
            f"Expected 728 features, got {len(features)}"
        )

    train = load("train", features)
    val = load("validation", features)
    test = load("test", features)

    X_train = train[
        features
    ].to_numpy(dtype=np.float32)

    X_val = val[
        features
    ].to_numpy(dtype=np.float32)

    X_test = test[
        features
    ].to_numpy(dtype=np.float32)

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []
    thresholds = {}

    # ========================================================
    # RUL
    # ========================================================

    section("RUL")

    y_train = train[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_val = val[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    y_test = test[
        "rul_hours"
    ].to_numpy(dtype=np.float32)

    dtrain = xgb.QuantileDMatrix(
        X_train,
        y_train,
        max_bin=MAX_BIN,
    )

    dval = xgb.QuantileDMatrix(
        X_val,
        y_val,
        ref=dtrain,
        max_bin=MAX_BIN,
    )

    dtest = xgb.QuantileDMatrix(
        X_test,
        ref=dtrain,
        max_bin=MAX_BIN,
    )

    started = time.perf_counter()

    model = xgb.train(
        regression_params(),
        dtrain,
        num_boost_round=MAX_ROUNDS,
        evals=[
            (dtrain, "train"),
            (dval, "validation"),
        ],
        early_stopping_rounds=
            EARLY_STOPPING,
        verbose_eval=50,
    )

    training_seconds = (
        time.perf_counter()
        - started
    )

    prediction = model.predict(
        dtest,
        iteration_range=(
            0,
            model.best_iteration + 1,
        ),
    )

    prediction = np.clip(
        prediction,
        0,
        None,
    )

    mae = mean_absolute_error(
        y_test,
        prediction,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            prediction,
        )
    )

    r2 = r2_score(
        y_test,
        prediction,
    )

    median_ae = (
        median_absolute_error(
            y_test,
            prediction,
        )
    )

    model.save_model(
        MODEL_DIR / "rul_hours.json"
    )

    results.append(
        {
            "task": "regression",
            "target": "rul_hours",
            "feature_count": 728,
            "best_iteration":
                model.best_iteration,
            "training_seconds":
                training_seconds,
            "test_mae": mae,
            "test_median_absolute_error":
                median_ae,
            "test_rmse": rmse,
            "test_r2": r2,
        }
    )

    print(
        f"MAE={mae:.4f} h | "
        f"R²={r2:.6f}"
    )

    del model
    gc.collect()

    # ========================================================
    # Classification
    # ========================================================

    for target, horizon in TARGETS.items():

        section(target)

        y_train = train[
            target
        ].to_numpy(dtype=np.float32)

        y_val = val[
            target
        ].to_numpy(dtype=np.float32)

        y_test = test[
            target
        ].to_numpy(dtype=np.int8)

        positive = y_train.sum()
        negative = len(y_train) - positive

        weight = (
            negative / positive
        )

        dtrain.set_label(y_train)
        dval.set_label(y_val)

        started = time.perf_counter()

        model = xgb.train(
            classifier_params(
                weight
            ),
            dtrain,
            num_boost_round=MAX_ROUNDS,
            evals=[
                (dtrain, "train"),
                (dval, "validation"),
            ],
            early_stopping_rounds=
                EARLY_STOPPING,
            verbose_eval=50,
        )

        training_seconds = (
            time.perf_counter()
            - started
        )

        val_prob = model.predict(
            dval,
            iteration_range=(
                0,
                model.best_iteration + 1,
            ),
        )

        test_prob = model.predict(
            dtest,
            iteration_range=(
                0,
                model.best_iteration + 1,
            ),
        )

        threshold, val_f1 = (
            choose_threshold(
                y_val,
                val_prob,
            )
        )

        thresholds[target] = threshold

        metrics = classification_metrics(
            y_test,
            test_prob,
            threshold,
        )

        events = event_metrics(
            test,
            test_prob,
            threshold,
            horizon,
        )

        model.save_model(
            MODEL_DIR
            / f"{target}.json"
        )

        results.append(
            {
                "task":
                    "classification",

                "target":
                    target,

                "feature_count":
                    728,

                "best_iteration":
                    model.best_iteration,

                "training_seconds":
                    training_seconds,

                "threshold":
                    threshold,

                "validation_f1":
                    val_f1,

                "test_average_precision":
                    metrics[
                        "average_precision"
                    ],

                "test_roc_auc":
                    metrics[
                        "roc_auc"
                    ],

                "test_precision":
                    metrics[
                        "precision"
                    ],

                "test_recall":
                    metrics[
                        "recall"
                    ],

                "test_f1":
                    metrics["f1"],

                "test_point_fpr":
                    metrics[
                        "point_fpr"
                    ],

                "event_detection_rate":
                    events[
                        "event_detection_rate"
                    ],

                "median_warning_lead_hours":
                    events[
                        "median_warning_lead_hours"
                    ],
            }
        )

        print(
            f"AP={metrics['average_precision']:.6f} | "
            f"F1={metrics['f1']:.6f} | "
            f"Event={events['event_detection_rate']:.4f}"
        )

        del model
        gc.collect()

    # ========================================================
    # Save
    # ========================================================

    result = pd.DataFrame(
        results
    )

    metrics_path = (
        REPORT_DIR
        / "temporal_metrics.csv"
    )

    result.to_csv(
        metrics_path,
        index=False,
        encoding="utf-8-sig",
    )

    with open(
        REPORT_DIR / "thresholds.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            thresholds,
            file,
            indent=2,
        )

    section("FINAL RESULT")

    print(
        result.to_string(
            index=False
        )
    )

    print()
    print(
        "[PASS] Temporal model training complete"
    )


if __name__ == "__main__":
    main()