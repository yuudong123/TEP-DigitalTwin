from pathlib import Path
import pandas as pd
import numpy as np

DATA_DIR = Path(r"D:\TEP_DigitalTwin\data\unzip\TEP")

FILES = [
    "case1.csv",
    "case2.csv",
    "case3.csv",
    "case4.csv",
    "case5.csv",
    "case5_1.csv",
    "case6.csv",
    "case7.csv",
]

info = {}

for name in FILES:
    path = DATA_DIR / name

    if not path.exists():
        print(f"[MISSING] {name}")
        continue

    df = pd.read_csv(path)

    info[name] = df

    print(
        f"{name:12s}",
        "shape =", df.shape,
        "Ids =", df["Id"].nunique(),
        "Time range =",
        (df["Time"].min(), df["Time"].max()),
    )

print()
print("=" * 70)
print("EXTRA CASE COMPARISON")
print("=" * 70)

for extra_name in ["case5_1.csv", "case7.csv"]:

    if extra_name not in info:
        continue

    extra = info[extra_name]

    print(f"\n[{extra_name}]")

    for base_name in [
        "case1.csv",
        "case2.csv",
        "case3.csv",
        "case4.csv",
        "case5.csv",
        "case6.csv",
    ]:

        if base_name not in info:
            continue

        base = info[base_name]

        same_shape = (
            extra.shape == base.shape
        )

        same_columns = (
            list(extra.columns)
            == list(base.columns)
        )

        exact_equal = False

        if same_shape and same_columns:
            exact_equal = extra.equals(base)

        print(
            f"vs {base_name:10s} | "
            f"same_shape={same_shape} | "
            f"same_columns={same_columns} | "
            f"exact_equal={exact_equal}"
        )