from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "TEP"
    / "case1.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "feature_schema.csv"
)


XMV_COLUMNS = [
    "D feed",
    "E Feed",
    "A Feed",
    "A and C Feed",
    "Recycle",
    "Purge",
    "Separator",
    "Stripper",
    "Steam",
    "Reactor Coolant",
    "Condenser Coolant",
    "Agitator",
]


XMEAS_COLUMNS = [
    "msv A Feed",
    "msv D Feed",
    "msv E Feed",
    "msv A and C Feed",
    "Recycle Flow",
    "Reactor Feed Rate",
    "Reactor Pressure",
    "Reactor Level",
    "Reactor Temperature",
    "Purge Rate",
    "Product Sep Temp",
    "Product Sep Level",
    "Product Sep Pressure",
    "Product Sep Underflow",
    "Stripper Level",
    "Stripper Pressure",
    "Stripper Underflow",
    "Stripper Temp",
    "Stripper Steam Flow",
    "Compressor Work",
    "Reactor Coolant Temp",
    "Separator Coolant Temp",
    "Component A to Reactor",
    "Component B to Reactor",
    "Component C to Reactor",
    "Component D to Reactor",
    "Component E to Reactor",
    "Component F to Reactor",
    "Component A to Purge",
    "Component B to Purge",
    "Component C to Purge",
    "Component D to Purge",
    "Component E to Purge",
    "Component F to Purge",
    "Component G to Purge",
    "Component H to Purge",
    "Component D to Product",
    "Component E to Product",
    "Component F to Product",
    "Component G to Product",
    "Component H to Product",
]


EXTRA_COLUMNS = [
    "Liquid Input Stripper",
    "Liquid Input Separator",
    "Liquid Input Reactor",
]


def main():
    df = pd.read_csv(RAW_PATH, nrows=5)

    rows = []

    for column in df.columns:

        # ----------------------------------------------------
        # Identifier
        # ----------------------------------------------------
        if column == "Id":
            role = "identifier"
            tep_variable = None
            model_a = False
            model_b = False
            note = "trajectory 식별자. 모델 입력 제외"

        # ----------------------------------------------------
        # Time
        # ----------------------------------------------------
        elif column == "Time":
            role = "time"
            tep_variable = None
            model_a = False
            model_b = False
            note = "경과시간 정보. 모델 입력 제외"

        # ----------------------------------------------------
        # Manipulated Variables (XMV)
        # ----------------------------------------------------
        elif column in XMV_COLUMNS:
            index = XMV_COLUMNS.index(column) + 1

            role = "manipulated_variable"
            tep_variable = f"XMV({index})"

            # Agitator는 전체 데이터에서 100으로 고정됨
            if column == "Agitator":
                model_a = False
                model_b = False
                note = (
                    "XMV 변수이나 전체 공식 데이터에서 "
                    "100으로 고정된 상수이므로 제외"
                )
            else:
                model_a = False
                model_b = True
                note = (
                    "공정 조작/제어 변수. "
                    "Model B에서만 사용"
                )

        # ----------------------------------------------------
        # Measured Variables (XMEAS)
        # ----------------------------------------------------
        elif column in XMEAS_COLUMNS:
            index = XMEAS_COLUMNS.index(column) + 1

            role = "measured_variable"
            tep_variable = f"XMEAS({index})"

            model_a = True
            model_b = True

            note = (
                "공정 측정 변수. "
                "Model A와 Model B 모두 사용"
            )

        # ----------------------------------------------------
        # Additional RTF variables
        # ----------------------------------------------------
        elif column in EXTRA_COLUMNS:
            role = "degradation_state_candidate"
            tep_variable = None

            model_a = False
            model_b = False

            note = (
                "RTF 데이터셋의 추가 변수. "
                "열화 정보 누수 가능성이 있으므로 "
                "Baseline feature에서 제외"
            )

        else:
            raise ValueError(
                f"분류되지 않은 컬럼 발견: {column}"
            )

        rows.append(
            {
                "column": column,
                "dtype": str(df[column].dtype),
                "role": role,
                "tep_variable": tep_variable,
                "model_a_feature": model_a,
                "model_b_feature": model_b,
                "note": note,
            }
        )

    schema = pd.DataFrame(rows)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    xmv_count = (schema["role"] == "manipulated_variable").sum()
    xmeas_count = (schema["role"] == "measured_variable").sum()
    extra_count = (
        schema["role"] == "degradation_state_candidate"
    ).sum()

    model_a_count = schema["model_a_feature"].sum()
    model_b_count = schema["model_b_feature"].sum()

    print("=" * 80)
    print("TEP FEATURE SCHEMA")
    print("=" * 80)

    print(f"XMV variables       : {xmv_count}")
    print(f"XMEAS variables     : {xmeas_count}")
    print(f"Extra RTF variables : {extra_count}")
    print()
    print(f"Model A features    : {model_a_count}")
    print(f"Model B features    : {model_b_count}")

    if xmv_count != 12:
        raise ValueError(
            f"XMV 개수 오류: expected=12, actual={xmv_count}"
        )

    if xmeas_count != 41:
        raise ValueError(
            f"XMEAS 개수 오류: expected=41, actual={xmeas_count}"
        )

    if extra_count != 3:
        raise ValueError(
            f"Extra 변수 개수 오류: expected=3, actual={extra_count}"
        )

    if model_a_count != 41:
        raise ValueError(
            f"Model A feature 오류: {model_a_count}"
        )

    if model_b_count != 52:
        raise ValueError(
            f"Model B feature 오류: {model_b_count}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    schema.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(f"[SAVE] {OUTPUT_PATH}")
    print()
    print("[PASS] Feature schema 생성 완료")


if __name__ == "__main__":
    main()