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


def main():
    df = pd.read_csv(
        RAW_PATH,
        nrows=5,
    )

    print("=" * 80)
    print("TEP FEATURE COLUMNS")
    print("=" * 80)

    for index, column in enumerate(df.columns, start=1):
        print(f"{index:02d}. {column}")


if __name__ == "__main__":
    main()