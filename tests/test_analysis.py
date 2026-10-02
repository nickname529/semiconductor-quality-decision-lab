import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quality_lab.data import verify
from quality_lab.decision import metrics, temporal_split, top_k, wilson
from quality_lab.pipeline import make_model, run

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/baseline"


def test_split_keeps_boundary_timestamp_groups_together():
    meta = pd.DataFrame(
        {
            "row_id": range(10),
            "timestamp": pd.to_datetime(["2008-01-01"] * 6 + ["2008-01-02"] * 2 + ["2008-01-03"] * 2),
        }
    )
    splits = temporal_split(meta.sample(frac=1, random_state=9))
    assert {k: len(v) for k, v in splits.items()} == {"train": 6, "validation": 2, "test": 2}
    assert set(np.concatenate(list(splits.values()))) == set(range(10))
    assert meta.loc[splits["train"], "timestamp"].max() < meta.loc[splits["validation"], "timestamp"].min()
    assert meta.loc[splits["validation"], "timestamp"].max() < meta.loc[splits["test"], "timestamp"].min()


def test_unsplittable_time_groups_rejected():
    with pytest.raises(ValueError, match="nonempty"):
        temporal_split(pd.DataFrame({"row_id": range(10), "timestamp": [pd.Timestamp("2008-01-01")] * 10}))


@pytest.mark.parametrize("fraction,expected", [(0, 0), (0.1, 0), (0.2, 1), (0.3, 1), (1, 5)])
def test_capacity_floor_and_tie_break(fraction, expected):
    ids = np.array([4, 3, 2, 1, 0])
    selected = top_k(np.ones(5), ids, fraction)
    assert selected.sum() == expected
    assert set(ids[selected]) == set(range(expected))


@pytest.mark.parametrize("fraction", [-0.1, 1.1, float("nan")])
def test_invalid_capacity(fraction):
    with pytest.raises(ValueError):
        top_k(np.ones(2), np.arange(2), fraction)


def test_ranking_uses_score_and_id_only():
    scores, ids = np.array([0.2, 0.9, 0.9, 0.1]), np.array([0, 2, 1, 3])
    assert top_k(scores, ids, 0.25).tolist() == [False, False, True, False]
    with pytest.raises(ValueError):
        top_k(np.array([np.nan]), np.array([0]), 0.5)
    with pytest.raises(ValueError):
        top_k(np.ones(2), np.array([0, 0]), 0.5)


def test_confusion_counts_and_undefined_precision():
    y = np.array([1, 1, 0, 0, 0])
    m = metrics(y, np.array([1, 0, 1, 0, 0]))
    assert [m[k] for k in ("tp", "fp", "fn", "tn")] == [1, 1, 1, 2]
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert m["random_expected_tp_at_same_k"] == 0.8
    assert metrics(y, np.zeros(5))["precision"] is None
    assert metrics(np.zeros(5), np.zeros(5))["recall"] is None
    assert wilson(0, 0) == (None, None)


def test_preprocessing_never_fits_validation_values():
    train = pd.DataFrame({"a": [0.0, 2.0, np.nan, 4.0], "empty": [np.nan] * 4, "constant": [7.0] * 4})
    model = make_model().fit(train, [0, 1, 0, 1])
    before = model.named_steps["impute"].statistics_.copy()
    model.predict_proba(pd.DataFrame({"a": [100000.0], "empty": [1000.0], "constant": [-10.0]}))
    np.testing.assert_equal(before, model.named_steps["impute"].statistics_)
    assert before[0] == 2
    assert model.named_steps["variance"].get_support().tolist() == [True, False, False]


def test_modified_source_rejected():
    with pytest.raises(ValueError, match="hash mismatch"):
        verify("secom.data", b"changed input")


def test_existing_output_is_preserved(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    (out / "user.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        run(tmp_path / "missing_raw", out, False)
    assert (out / "user.txt").read_text() == "keep"


def test_recorded_artifact_integrity_and_code_provenance():
    for name, expected in json.loads((BASE / "artifact_hashes.json").read_text()).items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == expected
    for name, expected in json.loads((BASE / "run_metadata.json").read_text())["source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected


def test_saved_decisions_independently_recompute():
    pred = pd.read_csv(BASE / "predictions.csv")
    table = pd.read_csv(BASE / "decision_metrics.csv")
    for row in table.itertuples():
        batch = pred[pred["split"] == row.split]
        chosen = batch[row.policy] == 1
        tp = int(batch.loc[chosen, "fail"].sum())
        fp = int(chosen.sum()) - tp
        fn = int(batch.fail.sum()) - tp
        tn = len(batch) - tp - fp - fn
        assert (tp, fp, fn, tn) == (row.tp, row.fp, row.fn, row.tn)
        assert row.reviewed == int(chosen.sum())
        assert row.recall == pytest.approx(tp / (tp + fn))
        if row.policy.startswith("top_"):
            fraction = int(row.policy.removeprefix("top_").removesuffix("pct")) / 100
            assert chosen.sum() == math.floor(len(batch) * fraction)
            expected = batch.sort_values(["score", "row_id"], ascending=[False, True]).head(int(chosen.sum()))
            assert set(batch.loc[chosen, "row_id"]) == set(expected.row_id)
        if row.reviewed:
            assert row.precision == pytest.approx(tp / row.reviewed)


def test_saved_partition_and_threshold_are_label_independent():
    splits = pd.read_csv(BASE / "split_assignments.csv", parse_dates=["timestamp"])
    assert len(splits) == 1567 and splits.row_id.nunique() == 1567
    assert splits.groupby("timestamp")["split"].nunique().max() == 1
    dates = [splits[splits["split"] == k].timestamp for k in ("train", "validation", "test")]
    assert dates[0].max() < dates[1].min() < dates[2].min()
    pred = pd.read_csv(BASE / "predictions.csv")
    threshold = json.loads((BASE / "summary.json").read_text())["validation_threshold"]
    assert threshold == pytest.approx(np.quantile(pred[pred["split"] == "validation"].score, 0.8))
    assert ((pred.score >= threshold).astype(int) == pred.fixed_val_q80).all()
