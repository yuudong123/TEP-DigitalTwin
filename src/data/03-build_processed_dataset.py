from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "TEP"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

OFFICIAL_CASES = [
    "case1",
    "case2",
    "case3",
    "case4",
    "case5",
    "case6",
]

CONSTANT_COLUMNS = [
    "Agitator",
]


def load_split_manifest() -> pd.DataFrame:
    path = METADATA_DIR / "split_manifest.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"split manifest가 없습니다: {path}"
        )

    return pd.read_csv(path)


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 같은 case 내부에서도 Id별로 각각 독립적인 trajectory이다.
    eol_time = df.groupby("Id")["Time"].transform("max")
    start_time = df.groupby("Id")["Time"].transform("min")

    duration = eol_time - start_time

    df["rul_hours"] = eol_time - df["Time"]

    df["rul_fraction"] = (
        df["rul_hours"] / duration
    )

    df["failure_within_4h"] = (
        df["rul_hours"] <= 4.0
    ).astype("int8")

    df["failure_within_2h"] = (
        df["rul_hours"] <= 2.0
    ).astype("int8")

    df["failure_within_1h"] = (
        df["rul_hours"] <= 1.0
    ).astype("int8")

    return df


def process_case(
    case: str,
    manifest: pd.DataFrame,
) -> list[pd.DataFrame]:

    path = RAW_DIR / f"{case}.csv"

    print(f"[LOAD] {path.name}")

    df = pd.read_csv(path)

    # case 정보를 데이터 관리용으로 추가.
    # 모델 feature로 사용해서는 안 된다.
    df.insert(0, "case", case)

    df["trajectory_key"] = (
        df["case"]
        + "::"
        + df["Id"].astype(str)
    )

    df = add_targets(df)

    for column in CONSTANT_COLUMNS:
        if column in df.columns:
            df = df.drop(columns=column)

    case_manifest = manifest[
        manifest["case"] == case
    ][
        ["trajectory_key", "split"]
    ]

    df = df.merge(
        case_manifest,
        on="trajectory_key",
        how="left",
        validate="many_to_one",
    )

    if df["split"].isna().any():
        missing = df.loc[
            df["split"].isna(),
            "trajectory_key",
        ].unique()

        raise ValueError(
            f"{case}: split을 찾을 수 없는 trajectory가 있습니다: "
            f"{missing[:10]}"
        )

    outputs = []

    for split in ["train", "validation", "test"]:
        split_df = df[df["split"] == split].copy()

        outputs.append(
            (
                split,
                split_df,
            )
        )

    return outputs


def validate_processed(
    datasets: dict[str, pd.DataFrame],
) -> None:

    print()
    print("=" * 80)
    print("PROCESSED DATA VALIDATION")
    print("=" * 80)

    trajectory_sets = {}

    for split, df in datasets.items():

        keys = set(df["trajectory_key"].unique())
        trajectory_sets[split] = keys

        print()
        print(f"[{split}]")
        print(f"rows         : {len(df):,}")
        print(f"trajectories : {len(keys):,}")
        print(
            f"RUL range    : "
            f"{df['rul_hours'].min():.2f} ~ "
            f"{df['rul_hours'].max():.2f} h"
        )

        for target in [
            "failure_within_4h",
            "failure_within_2h",
            "failure_within_1h",
        ]:
            positives = int(df[target].sum())
            ratio = float(df[target].mean())

            print(
                f"{target:18s}: "
                f"{positives:,} positive "
                f"({ratio:.4%})"
            )

        if df.isna().any().any():
            raise ValueError(
                f"{split}: processed 데이터에 결측치가 있습니다."
            )

        if "Agitator" in df.columns:
            raise ValueError(
                f"{split}: Agitator가 제거되지 않았습니다."
            )

    if trajectory_sets["train"] & trajectory_sets["validation"]:
        raise ValueError(
            "Train과 Validation trajectory가 중복됩니다."
        )

    if trajectory_sets["train"] & trajectory_sets["test"]:
        raise ValueError(
            "Train과 Test trajectory가 중복됩니다."
        )

    if trajectory_sets["validation"] & trajectory_sets["test"]:
        raise ValueError(
            "Validation과 Test trajectory가 중복됩니다."
        )

    expected_counts = {
        "train": 420,
        "validation": 90,
        "test": 90,
    }

    for split, expected in expected_counts.items():
        actual = len(trajectory_sets[split])

        if actual != expected:
            raise ValueError(
                f"{split}: expected={expected}, actual={actual}"
            )

    print()
    print("[PASS] split 간 trajectory 중복 없음")
    print("[PASS] 420 / 90 / 90 trajectory 확인")
    print("[PASS] target 생성 확인")
    print("[PASS] 상수 컬럼 Agitator 제거 확인")


def save_datasets(
    datasets: dict[str, pd.DataFrame],
) -> None:

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 80)
    print("SAVE PARQUET")
    print("=" * 80)

    for split, df in datasets.items():

        path = PROCESSED_DIR / f"{split}.parquet"

        # split은 파일 자체로 이미 구분되므로 저장할 필요 없음.
        output = df.drop(columns=["split"])

        output.to_parquet(
            path,
            index=False,
        )

        size_mb = path.stat().st_size / 1024 / 1024

        print(
            f"[SAVE] {path.name}"
            f" | rows={len(output):,}"
            f" | {size_mb:.1f} MB"
        )


def update_feature_schema() -> None:

    path = METADATA_DIR / "feature_schema.csv"

    if not path.exists():
        return

    schema = pd.read_csv(path)

    mask = schema["column"] == "Agitator"

    if mask.any():
        schema.loc[mask, "role"] = "constant"
        schema.loc[mask, "candidate_feature"] = False
        schema.loc[
            mask,
            "note",
        ] = (
            "전체 공식 데이터에서 값이 100으로 고정되어 "
            "예측 정보가 없으므로 제외"
        )

        schema.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            "[UPDATE] feature_schema.csv: "
            "Agitator -> constant / excluded"
        )


def main() -> None:

    print("=" * 80)
    print("TEP PROCESSED DATASET BUILDER")
    print("=" * 80)

    manifest = load_split_manifest()

    parts = {
        "train": [],
        "validation": [],
        "test": [],
    }

    for case in OFFICIAL_CASES:

        case_outputs = process_case(
            case,
            manifest,
        )

        for split, df in case_outputs:
            parts[split].append(df)

    datasets = {}

    for split, frames in parts.items():

        datasets[split] = pd.concat(
            frames,
            ignore_index=True,
        )

        # 파일 순서와 관계없이 항상 명시적으로 정렬
        datasets[split] = datasets[split].sort_values(
            ["case", "Id", "Time"]
        ).reset_index(drop=True)

    validate_processed(datasets)

    save_datasets(datasets)

    update_feature_schema()

    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print("Processed dataset generation completed successfully.")


if __name__ == "__main__":
    main()