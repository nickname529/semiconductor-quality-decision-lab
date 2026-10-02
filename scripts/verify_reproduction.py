"""Compare recomputed evidence, allowing only tiny numeric roundoff across platforms."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def compare(expected: Path, actual: Path) -> None:
    names = [
        "decision_metrics",
        "ranking_metrics",
        "predictions",
        "feature_eda",
        "monthly_eda",
        "split_assignments",
    ]
    for name in names:
        pd.testing.assert_frame_equal(
            pd.read_csv(expected / f"{name}.csv"),
            pd.read_csv(actual / f"{name}.csv"),
            check_exact=False,
            rtol=1e-10,
            atol=1e-12,
        )
    a = json.loads((expected / "summary.json").read_text())
    b = json.loads((actual / "summary.json").read_text())
    np.testing.assert_allclose(a.pop("validation_threshold"), b.pop("validation_threshold"), rtol=1e-10)
    assert a == b, "Summary changed"
    for name in ("source_manifest.json",):
        assert json.loads((expected / name).read_text()) == json.loads((actual / name).read_text())
    a = json.loads((expected / "run_metadata.json").read_text())
    b = json.loads((actual / "run_metadata.json").read_text())
    for key in (
        "source_sha256",
        "versions",
        "seed",
        "model",
        "trees",
        "min_samples_leaf",
        "class_weight",
        "n_jobs",
        "threshold_rule",
        "capacities",
        "tie_rule",
    ):
        assert a[key] == b[key], f"Protocol/environment differs: {key}"
    print(
        "Reproduction passed: 6 CSV tables, summary, source manifest, code/protocol hashes and package versions"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=ROOT / "results/baseline")
    parser.add_argument("--actual", type=Path, required=True)
    args = parser.parse_args()
    compare(args.expected, args.actual)
