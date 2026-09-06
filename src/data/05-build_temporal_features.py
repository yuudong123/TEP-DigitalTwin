from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TEMPORAL_DIR = PROCESSED_DIR / "temporal"

METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

FEATURE_SCHEMA_PATH = METADATA_DIR / "feature_schema.csv"
TEMPORAL_SCHEMA_PATH = METADATA_DIR / "temporal_feature_schema.csv"
SUMMARY_PATH = METADATA_DIR / "temporal_dataset_summary.csv"

BASE_FEATURE_COUNT = 52
TEMPORAL_FEATURE_COUNT = 728

LAG_15M = 5
LAG_30M = 10
LAG_60M = 20

WINDOW_15M = 6
WINDOW_30M = 11
WINDOW_60M = 21

WARMUP_ROWS = 20

META_COLUMNS = [
    "case",
    "Id",
    "Time",
    "trajectory_key",
    "rul_hours",
    "rul_fraction",
    "failure_within_4h",
    "failure_within_2h",
    "failure_within_1h",
]


def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .eq("true")
    )


def load_base_features() -> list[str]:
    schema = pd.read_csv(FEATURE_SCHEMA_PATH)

    schema["model_b_feature"] = parse_bool(
        schema["model_b_feature"]
    )

    features = schema.loc[
        schema["model_b_feature"],
        "column",
    ].tolist()

    if len(features) != BASE_FEATURE_COUNT:
        raise ValueError(
            f"Model B feature count error: {len(features)}"
        )

    return features


def rolling_slope_60m(base: pd.DataFrame) -> pd.DataFrame:
    values = base.to_numpy(dtype=np.float32)

    rows, feature_count = values.shape

    output = np.full(
        (rows, feature_count),
        np.nan,
        dtype=np.float32,
    )

    if rows < WINDOW_60M:
        return pd.DataFrame(
            output,
            columns=base.columns,
            index=base.index,
        )

    # 0 ~ 1 hour, 3 minute intervals
    x = (
        np.arange(WINDOW_60M, dtype=np.float32)
        * 0.05
    )

    x_centered = x - x.mean()

    denominator = float(
        np.sum(x_centered ** 2)
    )

    windows = np.lib.stride_tricks.sliding_window_view(
        values,
        window_shape=WINDOW_60M,
        axis=0,
    )

    slopes = np.tensordot(
        windows,
        x_centered,
        axes=([2], [0]),
    ) / denominator

    output[
        WINDOW_60M - 1:
    ] = slopes.astype(np.float32)

    return pd.DataFrame(
        output,
        columns=base.columns,
        index=base.index,
    )


def build_features(
    trajectory: pd.DataFrame,
    base_features: list[str],
) -> pd.DataFrame:

    trajectory = (
        trajectory
        .sort_values("Time")
        .reset_index(drop=True)
    )

    base = trajectory[
        base_features
    ].astype(np.float32)

    frames = []

    # ========================================================
    # Current
    # ========================================================

    frames.append(base.copy())

    # ========================================================
    # 5 minute
    #
    # Sampling is 3 minutes.
    #
    # t-5m lies between:
    # t-6m and t-3m.
    #
    # Linear interpolation:
    # 2/3 * value(t-6m)
    # +
    # 1/3 * value(t-3m)
    # ========================================================

    past_5m = (
        (2.0 / 3.0) * base.shift(2)
        +
        (1.0 / 3.0) * base.shift(1)
    )

    delta_5m = base - past_5m

    delta_5m.columns = [
        f"{c}__delta_5m"
        for c in base_features
    ]

    rate_5m = (
        delta_5m
        / (5.0 / 60.0)
    )

    rate_5m.columns = [
        f"{c}__rate_5m_per_h"
        for c in base_features
    ]

    frames.extend([
        delta_5m,
        rate_5m,
    ])

    # ========================================================
    # 15 minute
    # ========================================================

    delta_15m = (
        base
        - base.shift(LAG_15M)
    )

    delta_15m.columns = [
        f"{c}__delta_15m"
        for c in base_features
    ]

    rate_15m = delta_15m / 0.25

    rate_15m.columns = [
        f"{c}__rate_15m_per_h"
        for c in base_features
    ]

    mean_15m = (
        base
        .rolling(
            WINDOW_15M,
            min_periods=WINDOW_15M,
        )
        .mean()
    )

    mean_15m.columns = [
        f"{c}__mean_15m"
        for c in base_features
    ]

    std_15m = (
        base
        .rolling(
            WINDOW_15M,
            min_periods=WINDOW_15M,
        )
        .std(ddof=0)
    )

    std_15m.columns = [
        f"{c}__std_15m"
        for c in base_features
    ]

    frames.extend([
        mean_15m,
        std_15m,
        delta_15m,
        rate_15m,
    ])

    # ========================================================
    # 30 minute
    # ========================================================

    mean_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .mean()
    )

    mean_30m.columns = [
        f"{c}__mean_30m"
        for c in base_features
    ]

    std_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .std(ddof=0)
    )

    std_30m.columns = [
        f"{c}__std_30m"
        for c in base_features
    ]

    max_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .max()
    )

    max_30m.columns = [
        f"{c}__max_30m"
        for c in base_features
    ]

    min_30m = (
        base
        .rolling(
            WINDOW_30M,
            min_periods=WINDOW_30M,
        )
        .min()
    )

    min_30m.columns = [
        f"{c}__min_30m"
        for c in base_features
    ]

    frames.extend([
        mean_30m,
        std_30m,
        max_30m,
        min_30m,
    ])

    # ========================================================
    # 60 minute
    # ========================================================

    delta_60m = (
        base
        - base.shift(LAG_60M)
    )

    delta_60m.columns = [
        f"{c}__delta_60m"
        for c in base_features
    ]

    # 60 minutes = 1 hour
    rate_60m = delta_60m.copy()

    rate_60m.columns = [
        f"{c}__rate_60m_per_h"
        for c in base_features
    ]

    slope_60m = rolling_slope_60m(
        base
    )

    slope_60m.columns = [
        f"{c}__slope_60m_per_h"
        for c in base_features
    ]

    frames.extend([
        delta_60m,
        rate_60m,
        slope_60m,
    ])

    # ========================================================
    # Merge
    # ========================================================

    features = pd.concat(
        frames,
        axis=1,
    )

    if features.shape[1] != TEMPORAL_FEATURE_COUNT:
        raise ValueError(
            "Temporal feature count mismatch: "
            f"{features.shape[1]}"
        )

    result = pd.concat(
        [
            trajectory[META_COLUMNS],
            features,
        ],
        axis=1,
    )

    result = (
        result
        .iloc[WARMUP_ROWS:]
        .reset_index(drop=True)
    )

    feature_columns = [
        c for c in result.columns
        if c not in META_COLUMNS
    ]

    result[feature_columns] = (
        result[feature_columns]
        .astype(np.float32)
    )

    if (
        result[feature_columns]
        .isna()
        .any()
        .any()
    ):
        raise ValueError(
            "NaN remains after warm-up removal."
        )

    return result


def build_schema(
    base_features: list[str],
) -> pd.DataFrame:

    rows = []

    def add(
        source: str,
        feature: str,
        transform: str,
        window: str,
    ):
        rows.append(
            {
                "feature": feature,
                "source_feature": source,
                "transform": transform,
                "window": window,
                "model_feature": True,
            }
        )

    for c in base_features:
        add(c, c, "current", "current")

        add(c, f"{c}__delta_5m", "delta", "5m")
        add(
            c,
            f"{c}__rate_5m_per_h",
            "rate",
            "5m",
        )

        add(c, f"{c}__mean_15m", "mean", "15m")
        add(c, f"{c}__std_15m", "std", "15m")
        add(c, f"{c}__delta_15m", "delta", "15m")
        add(
            c,
            f"{c}__rate_15m_per_h",
            "rate",
            "15m",
        )

        add(c, f"{c}__mean_30m", "mean", "30m")
        add(c, f"{c}__std_30m", "std", "30m")
        add(c, f"{c}__max_30m", "max", "30m")
        add(c, f"{c}__min_30m", "min", "30m")

        add(c, f"{c}__delta_60m", "delta", "60m")
        add(
            c,
            f"{c}__rate_60m_per_h",
            "rate",
            "60m",
        )
        add(
            c,
            f"{c}__slope_60m_per_h",
            "slope",
            "60m",
        )

    schema = pd.DataFrame(rows)

    if len(schema) != TEMPORAL_FEATURE_COUNT:
        raise ValueError(
            f"Schema count error: {len(schema)}"
        )

    return schema


def validate_no_future_leakage(
    source: pd.DataFrame,
    base_features: list[str],
) -> None:

    section("NO FUTURE LEAKAGE CHECK")

    trajectory_keys = (
        source["trajectory_key"]
        .drop_duplicates()
        .head(3)
        .tolist()
    )

    checks = 0

    for key in trajectory_keys:

        trajectory = (
            source[
                source["trajectory_key"] == key
            ]
            .sort_values("Time")
            .reset_index(drop=True)
        )

        full = build_features(
            trajectory,
            base_features,
        )

        candidate_indices = sorted(
            set(
                [
                    20,
                    min(100, len(trajectory) - 2),
                    len(trajectory) // 2,
                ]
            )
        )

        for cut in candidate_indices:

            if cut < 20 or cut >= len(trajectory) - 1:
                continue

            current_time = float(
                trajectory.loc[cut, "Time"]
            )

            expected = full[
                np.isclose(
                    full["Time"],
                    current_time,
                )
            ]

            if len(expected) != 1:
                raise ValueError(
                    "Leakage validation row lookup failed."
                )

            expected_features = (
                expected
                .drop(columns=META_COLUMNS)
                .iloc[0]
                .to_numpy(dtype=np.float32)
            )

            # ------------------------------------------------
            # Test 1:
            # truncate future completely
            # ------------------------------------------------

            truncated = (
                trajectory
                .iloc[:cut + 1]
                .copy()
            )

            truncated_features = build_features(
                truncated,
                base_features,
            )

            actual_features = (
                truncated_features
                .drop(columns=META_COLUMNS)
                .iloc[-1]
                .to_numpy(dtype=np.float32)
            )

            if not np.allclose(
                expected_features,
                actual_features,
                rtol=1e-5,
                atol=1e-5,
            ):
                raise ValueError(
                    f"Future leakage detected: "
                    f"{key}, Time={current_time}"
                )

            # ------------------------------------------------
            # Test 2:
            # destroy future sensor values.
            # Current features must remain unchanged.
            # ------------------------------------------------

            mutated = trajectory.copy()

            mutated.loc[
                cut + 1:,
                base_features,
            ] = (
                mutated.loc[
                    cut + 1:,
                    base_features,
                ]
                + 1_000_000.0
            )

            mutated_features = build_features(
                mutated,
                base_features,
            )

            mutated_row = mutated_features[
                np.isclose(
                    mutated_features["Time"],
                    current_time,
                )
            ]

            changed_features = (
                mutated_row
                .drop(columns=META_COLUMNS)
                .iloc[0]
                .to_numpy(dtype=np.float32)
            )

            if not np.allclose(
                expected_features,
                changed_features,
                rtol=1e-5,
                atol=1e-5,
            ):
                raise ValueError(
                    "Future mutation changed current feature: "
                    f"{key}, Time={current_time}"
                )

            checks += 1

    print(
        f"[PASS] {checks} temporal checkpoints verified"
    )

    print(
        "[PASS] Truncating future data does not change current features"
    )

    print(
        "[PASS] Mutating future values does not change current features"
    )


def process_split(
    split: str,
    base_features: list[str],
) -> dict:

    section(f"PROCESS {split.upper()}")

    input_path = (
        PROCESSED_DIR
        / f"{split}.parquet"
    )

    output_path = (
        TEMPORAL_DIR
        / f"{split}.parquet"
    )

    columns = (
        META_COLUMNS
        + base_features
    )

    df = pd.read_parquet(
        input_path,
        columns=columns,
    )

    df = (
        df
        .sort_values(
            ["case", "Id", "Time"]
        )
        .reset_index(drop=True)
    )

    if split == "test":
        validate_no_future_leakage(
            df,
            base_features,
        )

    input_rows = len(df)

    trajectory_count = (
        df["trajectory_key"]
        .nunique()
    )

    writer = None
    output_rows = 0
    completed = 0

    try:
        for _, trajectory in df.groupby(
            "trajectory_key",
            sort=False,
        ):
            result = build_features(
                trajectory,
                base_features,
            )

            table = pa.Table.from_pandas(
                result,
                preserve_index=False,
            )

            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    table.schema,
                    compression="zstd",
                )

            writer.write_table(table)

            output_rows += len(result)
            completed += 1

            if completed % 25 == 0:
                print(
                    f"[PROGRESS] "
                    f"{completed}/{trajectory_count}"
                )

    finally:
        if writer is not None:
            writer.close()

    expected_removed = (
        trajectory_count
        * WARMUP_ROWS
    )

    expected_output = (
        input_rows
        - expected_removed
    )

    if output_rows != expected_output:
        raise ValueError(
            f"{split} output row mismatch: "
            f"expected={expected_output}, "
            f"actual={output_rows}"
        )

    size_mb = (
        output_path.stat().st_size
        / 1024
        / 1024
    )

    print(
        f"[PASS] {split}: "
        f"{output_rows:,} rows, "
        f"{trajectory_count} trajectories, "
        f"{size_mb:.1f} MB"
    )

    return {
        "split": split,
        "trajectory_count": trajectory_count,
        "input_rows": input_rows,
        "removed_warmup_rows": expected_removed,
        "output_rows": output_rows,
        "feature_count": TEMPORAL_FEATURE_COUNT,
        "file_size_mb": size_mb,
    }


def main() -> None:

    section("TEP TEMPORAL FEATURE BUILDER")

    TEMPORAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_features = load_base_features()

    print(
        f"Base features     : {len(base_features)}"
    )

    print(
        f"Temporal features : {TEMPORAL_FEATURE_COUNT}"
    )

    schema = build_schema(
        base_features
    )

    schema.to_csv(
        TEMPORAL_SCHEMA_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"[SAVE] {TEMPORAL_SCHEMA_PATH}"
    )

    results = []

    for split in [
        "train",
        "validation",
        "test",
    ]:
        results.append(
            process_split(
                split,
                base_features,
            )
        )

    summary = pd.DataFrame(
        results
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    section("COMPLETE")

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print(
        "[PASS] Temporal feature dataset completed"
    )


if __name__ == "__main__":
    main()