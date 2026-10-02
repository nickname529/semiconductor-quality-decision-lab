"""Label-independent ranking rules and auditable confusion counts."""

import math

import numpy as np
import pandas as pd


def temporal_split(meta: pd.DataFrame) -> dict[str, np.ndarray]:
    ordered = meta.sort_values(["timestamp", "row_id"])
    first = ordered.iloc[math.floor(len(meta) * 0.6) - 1].timestamp
    second = ordered.iloc[math.floor(len(meta) * 0.8) - 1].timestamp
    groups = {
        "train": ordered.index[ordered.timestamp <= first].to_numpy(),
        "validation": ordered.index[(ordered.timestamp > first) & (ordered.timestamp <= second)].to_numpy(),
        "test": ordered.index[ordered.timestamp > second].to_numpy(),
    }
    if any(len(rows) == 0 for rows in groups.values()):
        raise ValueError("Timestamp groups cannot support three nonempty partitions")
    return groups


def top_k(scores: np.ndarray, row_ids: np.ndarray, fraction: float) -> np.ndarray:
    scores, row_ids = np.asarray(scores), np.asarray(row_ids)
    if not 0 <= fraction <= 1:
        raise ValueError("Capacity fraction must be within [0, 1]")
    if len(scores) != len(row_ids) or not np.isfinite(scores).all():
        raise ValueError("Scores and row IDs must align and be finite")
    if len(np.unique(row_ids)) != len(row_ids):
        raise ValueError("Row IDs must be unique")
    selected = np.zeros(len(scores), dtype=bool)
    count = math.floor(len(scores) * fraction)
    selected[np.lexsort((row_ids, -scores))[:count]] = True
    return selected


def wilson(successes: int, total: int) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def metrics(y: np.ndarray, selected: np.ndarray) -> dict:
    y, selected = np.asarray(y), np.asarray(selected, dtype=bool)
    if len(y) != len(selected) or not np.isin(y, [0, 1]).all():
        raise ValueError("Binary labels and decisions must align")
    tp = int(((y == 1) & selected).sum())
    fp = int(((y == 0) & selected).sum())
    fn = int(((y == 1) & ~selected).sum())
    tn = int(((y == 0) & ~selected).sum())
    lower, upper = wilson(tp, tp + fn)
    return {
        "n": len(y),
        "reviewed": tp + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "recall_wilson_lower": lower,
        "recall_wilson_upper": upper,
        "review_fraction": (tp + fp) / len(y) if len(y) else None,
        "random_expected_tp_at_same_k": (tp + fp) * float(y.mean()) if len(y) else None,
    }
