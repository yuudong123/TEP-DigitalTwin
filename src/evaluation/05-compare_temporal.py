from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASELINE_PATH = (
    PROJECT_ROOT
    / "reports"
    / "04-baseline"
    / "baseline_metrics.csv"
)

TEMPORAL_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "temporal_metrics.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "05-temporal"
    / "comparison_vs_baseline.csv"
)


def main():

    baseline = pd.read_csv(
        BASELINE_PATH
    )

    temporal = pd.read_csv(
        TEMPORAL_PATH
    )

    # 대표 Baseline은 Model B
    baseline = baseline[
        baseline["feature_set"]
        == "model_b"
    ]

    rows = []

    # RUL
    b = baseline[
        baseline["target"]
        == "rul_hours"
    ].iloc[0]

    t = temporal[
        temporal["target"]
        == "rul_hours"
    ].iloc[0]

    rows.append(
        {
            "target": "rul_hours",
            "metric": "MAE",
            "baseline": b["test_mae"],
            "temporal": t["test_mae"],
            "improvement_percent":
                (
                    (
                        b["test_mae"]
                        - t["test_mae"]
                    )
                    / b["test_mae"]
                    * 100
                ),
        }
    )

    for target in [
        "failure_within_4h",
        "failure_within_2h",
        "failure_within_1h",
    ]:

        b = baseline[
            baseline["target"]
            == target
        ].iloc[0]

        t = temporal[
            temporal["target"]
            == target
        ].iloc[0]

        rows.append(
            {
                "target": target,
                "metric":
                    "Average Precision",
                "baseline":
                    b[
                        "test_average_precision"
                    ],
                "temporal":
                    t[
                        "test_average_precision"
                    ],
                "improvement_percent":
                    (
                        (
                            t[
                                "test_average_precision"
                            ]
                            -
                            b[
                                "test_average_precision"
                            ]
                        )
                        /
                        b[
                            "test_average_precision"
                        ]
                        * 100
                    ),
            }
        )

    comparison = pd.DataFrame(
        rows
    )

    comparison.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print(
        comparison.to_string(
            index=False
        )
    )

    print()
    print(
        f"[SAVE] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()