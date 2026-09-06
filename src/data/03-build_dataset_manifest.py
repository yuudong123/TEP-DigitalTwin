from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# Project settings
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "TEP"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

OFFICIAL_CASES = [
    "case1",
    "case2",
    "case3",
    "case4",
    "case5",
    "case6",
]

EXPECTED_COLUMN_COUNT = 58
EXPECTED_IDS_PER_CASE = 100
EXPECTED_INTERVAL_HOURS = 0.05  # 3 minutes

TRAIN_COUNT = 70
VALIDATION_COUNT = 15
TEST_COUNT = 15

RANDOM_STATE = 42
FLOAT_TOLERANCE = 1e-8


def print_section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def load_cases() -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}

    for case in OFFICIAL_CASES:
        path = RAW_DIR / f"{case}.csv"

        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

        print(f"[LOAD] {path.name}")
        df = pd.read_csv(path)

        data[case] = df

    return data


def validate_columns(data: dict[str, pd.DataFrame]) -> list[str]:
    print_section("1. COLUMN SCHEMA CHECK")

    reference_case = OFFICIAL_CASES[0]
    reference_columns = list(data[reference_case].columns)

    print(f"{reference_case}: {len(reference_columns)} columns")

    if len(reference_columns) != EXPECTED_COLUMN_COUNT:
        raise ValueError(
            f"{reference_case}의 컬럼 수가 예상과 다릅니다. "
            f"expected={EXPECTED_COLUMN_COUNT}, actual={len(reference_columns)}"
        )

    if "Id" not in reference_columns:
        raise ValueError("필수 컬럼 'Id'가 없습니다.")

    if "Time" not in reference_columns:
        raise ValueError("필수 컬럼 'Time'이 없습니다.")

    for case, df in data.items():
        columns = list(df.columns)

        same = columns == reference_columns

        print(
            f"{case}: columns={len(columns)}, "
            f"same_as_reference={same}"
        )

        if not same:
            raise ValueError(
                f"{case}의 컬럼 구성이 {reference_case}와 다릅니다."
            )

    print("[PASS] 모든 공식 case의 컬럼 구성이 동일합니다.")

    return reference_columns


def build_trajectory_summary(
    data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    print_section("2. TRAJECTORY / DATA QUALITY CHECK")

    rows = []

    total_missing = 0
    total_duplicate_timestamps = 0
    total_interval_errors = 0
    total_inf = 0

    for case, df in data.items():
        id_count = df["Id"].nunique()

        print()
        print(f"[{case}]")
        print(f"rows             : {len(df):,}")
        print(f"trajectory count : {id_count}")

        if id_count != EXPECTED_IDS_PER_CASE:
            print(
                f"[WARN] expected {EXPECTED_IDS_PER_CASE} trajectories, "
                f"found {id_count}"
            )

        case_missing = int(df.isna().sum().sum())
        total_missing += case_missing

        numeric_df = df.select_dtypes(include=[np.number])
        case_inf = int(np.isinf(numeric_df.to_numpy()).sum())
        total_inf += case_inf

        print(f"missing values    : {case_missing:,}")
        print(f"infinite values   : {case_inf:,}")

        for trajectory_id, trajectory in df.groupby("Id", sort=True):
            trajectory = trajectory.sort_values("Time").reset_index(drop=True)

            trajectory_key = f"{case}::{trajectory_id}"

            missing_count = int(trajectory.isna().sum().sum())

            duplicate_timestamp_count = int(
                trajectory["Time"].duplicated().sum()
            )

            times = trajectory["Time"].to_numpy(dtype=float)

            if len(times) > 1:
                intervals = np.diff(times)

                invalid_interval_mask = ~np.isclose(
                    intervals,
                    EXPECTED_INTERVAL_HOURS,
                    atol=FLOAT_TOLERANCE,
                    rtol=0.0,
                )

                invalid_interval_count = int(
                    invalid_interval_mask.sum()
                )

                min_interval = float(intervals.min())
                max_interval = float(intervals.max())
            else:
                invalid_interval_count = 0
                min_interval = np.nan
                max_interval = np.nan

            start_time = float(times[0])
            end_time = float(times[-1])
            duration_hours = end_time - start_time

            total_duplicate_timestamps += duplicate_timestamp_count
            total_interval_errors += invalid_interval_count

            numeric_trajectory = trajectory.select_dtypes(
                include=[np.number]
            )

            inf_count = int(
                np.isinf(numeric_trajectory.to_numpy()).sum()
            )

            rows.append(
                {
                    "trajectory_key": trajectory_key,
                    "case": case,
                    "Id": trajectory_id,
                    "row_count": len(trajectory),
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration_hours": duration_hours,
                    "missing_count": missing_count,
                    "infinite_count": inf_count,
                    "duplicate_timestamp_count": duplicate_timestamp_count,
                    "invalid_interval_count": invalid_interval_count,
                    "min_interval_hours": min_interval,
                    "max_interval_hours": max_interval,
                }
            )

    summary = pd.DataFrame(rows)

    print_section("3. GLOBAL DATA QUALITY RESULT")

    print(f"trajectories                : {len(summary):,}")
    print(f"missing values              : {total_missing:,}")
    print(f"infinite values             : {total_inf:,}")
    print(
        f"duplicate trajectory/time   : "
        f"{total_duplicate_timestamps:,}"
    )
    print(
        f"non-0.05h sampling interval : "
        f"{total_interval_errors:,}"
    )

    if len(summary) != 600:
        print(
            f"[WARN] 공식 trajectory 수가 600이 아닙니다: "
            f"{len(summary)}"
        )
    else:
        print("[PASS] 총 600개의 공식 trajectory를 확인했습니다.")

    if total_missing == 0:
        print("[PASS] 결측치 없음")
    else:
        print("[WARN] 결측치 존재")

    if total_inf == 0:
        print("[PASS] inf / -inf 없음")
    else:
        print("[WARN] inf / -inf 존재")

    if total_duplicate_timestamps == 0:
        print("[PASS] 중복 timestamp 없음")
    else:
        print("[WARN] 중복 timestamp 존재")

    if total_interval_errors == 0:
        print("[PASS] 모든 trajectory의 sampling interval = 0.05h")
    else:
        print("[WARN] sampling interval 이상 존재")

    return summary


def build_split_manifest(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    print_section("4. TRAIN / VALIDATION / TEST SPLIT")

    rng = np.random.default_rng(RANDOM_STATE)

    split_rows = []

    for case in OFFICIAL_CASES:
        case_summary = summary[
            summary["case"] == case
        ].copy()

        ids = np.array(sorted(case_summary["Id"].unique()))
        rng.shuffle(ids)

        if len(ids) != 100:
            raise ValueError(
                f"{case}: trajectory 수가 100이 아니므로 "
                "70/15/15 split을 생성할 수 없습니다."
            )

        train_ids = set(ids[:TRAIN_COUNT])
        validation_ids = set(
            ids[
                TRAIN_COUNT:
                TRAIN_COUNT + VALIDATION_COUNT
            ]
        )
        test_ids = set(
            ids[
                TRAIN_COUNT + VALIDATION_COUNT:
            ]
        )

        for trajectory_id in sorted(ids):
            if trajectory_id in train_ids:
                split = "train"
            elif trajectory_id in validation_ids:
                split = "validation"
            elif trajectory_id in test_ids:
                split = "test"
            else:
                raise RuntimeError("split assignment error")

            split_rows.append(
                {
                    "trajectory_key": f"{case}::{trajectory_id}",
                    "case": case,
                    "Id": trajectory_id,
                    "split": split,
                }
            )

        print(
            f"{case}: "
            f"train={len(train_ids)}, "
            f"validation={len(validation_ids)}, "
            f"test={len(test_ids)}"
        )

    manifest = pd.DataFrame(split_rows)

    print()
    print(manifest["split"].value_counts())

    expected = {
        "train": 420,
        "validation": 90,
        "test": 90,
    }

    actual = manifest["split"].value_counts().to_dict()

    for split, count in expected.items():
        if actual.get(split, 0) != count:
            raise ValueError(
                f"{split}: expected={count}, "
                f"actual={actual.get(split, 0)}"
            )

    if manifest["trajectory_key"].duplicated().any():
        raise ValueError(
            "동일 trajectory가 여러 split에 배정되었습니다."
        )

    print("[PASS] 420 / 90 / 90 trajectory split 생성 완료")

    return manifest


def classify_column_role(column: str) -> tuple[str, bool, str]:
    """
    이 단계에서는 최종 센서/제어 변수 선별을 확정하지 않는다.
    Section 4 Baseline에서 실제 feature 조합을 비교할 예정이므로
    모든 공정 변수는 candidate_feature로 기록한다.
    """

    if column == "Id":
        return (
            "identifier",
            False,
            "trajectory 식별용. 모델 입력 제외",
        )

    if column == "Time":
        return (
            "time",
            False,
            "경과시간 누수 가능성 때문에 모델 입력 제외",
        )

    if column.lower().startswith("msv"):
        return (
            "manipulated_or_control_variable",
            True,
            "제어/조작 변수 후보. Baseline Model B에서 별도 검증",
        )

    return (
        "process_candidate_feature",
        True,
        "공정 측정 또는 상태 변수 후보. Section 4에서 최종 선별",
    )


def build_feature_schema(
    data: dict[str, pd.DataFrame],
    columns: list[str],
) -> pd.DataFrame:
    print_section("5. FEATURE SCHEMA")

    reference_df = data[OFFICIAL_CASES[0]]

    rows = []

    for column in columns:
        role, candidate, note = classify_column_role(column)

        series = reference_df[column]

        rows.append(
            {
                "column": column,
                "dtype": str(series.dtype),
                "role": role,
                "candidate_feature": candidate,
                "note": note,
            }
        )

    schema = pd.DataFrame(rows)

    print(schema["role"].value_counts())

    return schema


def check_constant_columns(
    data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    print_section("6. BASIC OUTLIER / CONSTANT CHECK")

    # 전체 공식 데이터를 메모리에 다시 합치지 않고
    # case별 min/max/nunique 정보를 누적한다.
    numeric_columns = [
        col
        for col in data[OFFICIAL_CASES[0]].columns
        if pd.api.types.is_numeric_dtype(
            data[OFFICIAL_CASES[0]][col]
        )
    ]

    results = []

    for column in numeric_columns:
        mins = []
        maxs = []
        unique_values = set()

        for df in data.values():
            series = df[column].dropna()

            if len(series) == 0:
                continue

            mins.append(float(series.min()))
            maxs.append(float(series.max()))

            # constant 여부 판단만 필요하므로
            # unique를 무한정 저장하지 않음.
            if len(unique_values) <= 2:
                unique_values.update(
                    series.drop_duplicates().head(3).tolist()
                )

        global_min = min(mins) if mins else np.nan
        global_max = max(maxs) if maxs else np.nan

        constant = (
            len(unique_values) == 1
            if unique_values
            else False
        )

        results.append(
            {
                "column": column,
                "global_min": global_min,
                "global_max": global_max,
                "constant_candidate": constant,
            }
        )

    result_df = pd.DataFrame(results)

    constants = result_df[
        result_df["constant_candidate"]
    ]

    if constants.empty:
        print("[PASS] 전체 데이터에서 고정된 numeric column 없음")
    else:
        print("[WARN] 고정값 후보 컬럼:")
        print(constants.to_string(index=False))

    print()
    print(
        "주의: 여기서 '이상값 없음'을 물리적으로 증명하는 것은 아님."
    )
    print(
        "NaN, inf, 시간축 오류, 고정 컬럼 등 명백한 데이터 이상을 "
        "우선 검사함."
    )

    return result_df


def save_outputs(
    trajectory_summary: pd.DataFrame,
    split_manifest: pd.DataFrame,
    feature_schema: pd.DataFrame,
    column_summary: pd.DataFrame,
) -> None:
    print_section("7. SAVE METADATA")

    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    trajectory_path = (
        METADATA_DIR / "trajectory_summary.csv"
    )
    split_path = (
        METADATA_DIR / "split_manifest.csv"
    )
    feature_path = (
        METADATA_DIR / "feature_schema.csv"
    )
    column_path = (
        METADATA_DIR / "column_summary.csv"
    )

    trajectory_summary.to_csv(
        trajectory_path,
        index=False,
        encoding="utf-8-sig",
    )

    split_manifest.to_csv(
        split_path,
        index=False,
        encoding="utf-8-sig",
    )

    feature_schema.to_csv(
        feature_path,
        index=False,
        encoding="utf-8-sig",
    )

    column_summary.to_csv(
        column_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"[SAVE] {trajectory_path}")
    print(f"[SAVE] {split_path}")
    print(f"[SAVE] {feature_path}")
    print(f"[SAVE] {column_path}")


def main() -> int:
    print_section("TEP DATASET MANIFEST BUILDER")

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Raw data     : {RAW_DIR}")
    print(f"Metadata     : {METADATA_DIR}")

    try:
        data = load_cases()

        columns = validate_columns(data)

        trajectory_summary = build_trajectory_summary(
            data
        )

        split_manifest = build_split_manifest(
            trajectory_summary
        )

        feature_schema = build_feature_schema(
            data,
            columns,
        )

        column_summary = check_constant_columns(
            data
        )

        save_outputs(
            trajectory_summary=trajectory_summary,
            split_manifest=split_manifest,
            feature_schema=feature_schema,
            column_summary=column_summary,
        )

    except Exception as exc:
        print()
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1

    print_section("COMPLETE")
    print("Dataset validation and split metadata generated successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())