"""One-command EDA, chronological evaluation and capacity scenarios."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline

from quality_lab.data import download, dump_json, load, manifest
from quality_lab.decision import metrics, temporal_split, top_k

ROOT = Path(__file__).resolve().parents[2]
CAPACITIES = (0.1, 0.2, 0.3)


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("variance", VarianceThreshold()),
            (
                "forest",
                RandomForestClassifier(
                    n_estimators=200, min_samples_leaf=3, class_weight="balanced", random_state=42, n_jobs=1
                ),
            ),
        ]
    )


def write_figures(
    out: Path,
    feature_eda: pd.DataFrame,
    split_stats: pd.DataFrame,
    monthly: pd.DataFrame,
    decisions: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {"figure.dpi": 140, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    axes[0].bar(split_stats["split"], split_stats["fail_rate"] * 100, color="#207f91")
    axes[0].set(ylabel="FAIL rate (%)", title="Chronological partitions")
    axes[1].bar(monthly["month"], monthly["fail_rate"] * 100, color="#6657a8")
    axes[1].set(ylabel="FAIL rate (%)", title="Monthly descriptive rates")
    fig.savefig(out / "01_label_distribution.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    ax.hist(feature_eda["missing_fraction"] * 100, bins=20, color="#207f91")
    ax.set(
        xlabel="Missing measurements per feature (%)",
        ylabel="Feature count",
        title="Source data missingness: all 590 anonymous features",
    )
    fig.savefig(out / "02_missingness.png")
    plt.close(fig)
    d = decisions[(decisions["split"] == "test") & decisions.policy.str.startswith("top_")]
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    x = np.arange(len(d))
    ax.bar(x - 0.2, d.tp, width=0.4, label="Model: observed FAIL captured", color="#207f91")
    ax.bar(
        x + 0.2,
        d.random_expected_tp_at_same_k,
        width=0.4,
        label="Random review: expected FAIL captured",
        color="#c0b8dc",
    )
    ax.set(
        xticks=x,
        xticklabels=d.policy,
        ylabel="FAIL count",
        title="Test batch: illustrative review capacities",
    )
    ax.legend()
    fig.savefig(out / "03_capacity_capture.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4), layout="constrained")
    ax.bar(x, d.tp, label="FAIL reviewed (TP)", color="#207f91")
    ax.bar(x, d.fp, bottom=d.tp, label="PASS reviewed (FP)", color="#c0b8dc")
    ax.set(
        xticks=x,
        xticklabels=d.policy,
        ylabel="Additional review candidates",
        title="Review workload is not confirmed defects",
    )
    ax.legend()
    fig.savefig(out / "04_review_workload.png")
    plt.close(fig)


def report(out: Path, summary: dict, decisions: pd.DataFrame, ranking: pd.DataFrame) -> None:
    lines = [
        "# 품질 의사결정 분석 결과",
        "",
        "상태: 실행 완료 / 해석 Draft / 사용자 검토 대기",
        "",
        "이 문서는 실제 실행 산출물로 자동 생성된다. 운영 승인이나 사업효과 검증이 아니다.",
        "",
        "## 데이터·분할",
        "",
        f"원본 {summary['rows']:,}행 × {summary['features']}변수, FAIL {summary['fails']}건. "
        f"결측 {summary['missing_cells']:,}셀, 관측값 기준 상수 {summary['constant_observed_features']}변수.",
        "",
        "시간순 약 60/20/20 분할이며 경계의 동일 timestamp는 앞 분할에 모두 배정한다.",
        "",
        "| 구간 | 표본 | FAIL | 시작 | 끝 |",
        "|---|---:|---:|---|---|",
    ]
    for s in summary["splits"]:
        lines.append(f"| {s['split']} | {s['n']} | {s['fails']} | {s['start']} | {s['end']} |")
    lines += ["", "## 순위 성능", "", "| 구간 | RF AP | 상수점수 AP | ROC-AUC |", "|---|---:|---:|---:|"]
    for r in ranking.itertuples():
        lines.append(f"| {r.split} | {r.ap:.4f} | {r.dummy_ap:.4f} | {r.roc_auc:.4f} |")
    lines += [
        "",
        "## 평가 구간의 검토 정책",
        "",
        "TP=검토 후보에 포함된 FAIL, FP=검토 후보에 포함된 PASS, FN=검토에서 빠진 FAIL.",
        "검토 자체가 실제 불량 발견·해결을 보장하지는 않는다.",
        "",
        "| 정책 | 검토 | TP | FP | FN | Recall | Precision | 무작위 TP 기대값 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in decisions[decisions["split"] == "test"].itertuples():
        precision = "N/A" if pd.isna(r.precision) else f"{r.precision:.3f}"
        lines.append(
            f"| {r.policy} | {r.reviewed} | {r.tp} | {r.fp} | {r.fn} | "
            f"{r.recall:.3f} | {precision} | {r.random_expected_tp_at_same_k:.2f} |"
        )
    top20 = decisions[(decisions["split"] == "test") & (decisions.policy == "top_20pct")].iloc[0]
    lines += [
        "",
        f"20% 용량 예시에서는 {int(top20.reviewed)}건을 검토 후보로 잡아 FAIL "
        f"{int(top20.tp)}건을 포함하고 {int(top20.fn)}건을 놓친다. PASS 추가 검토는 {int(top20.fp)}건이다.",
        f"이 Recall의 Wilson 95% 구간은 {top20.recall_wilson_lower:.3f}–"
        f"{top20.recall_wilson_upper:.3f}다. 표본 독립을 가정하며 학습·기간 변동은 반영하지 않는다.",
        "",
        f"validation 점수의 80% quantile에서 고정한 임계값은 {summary['validation_threshold']:.9f}다. "
        "이 값은 불량 확률이 아니며 test 검토 용량을 보장하지 않는다.",
        "",
        "## 해석과 한계",
        "",
        "- 검토하지 않은 표본을 PASS나 출하 가능으로 승인하지 않는다. 기본 검사 절차는 평가 대상 밖이다.",
        "- top-k는 평가 구간 전체 점수를 한꺼번에 알고 정렬하는 회고적 batch 시나리오다. 실시간·일별 정책이 아니다.",
        "- 10/20/30%는 운영팀이 제공한 용량이 아니다. 결과를 보고 최적 용량을 선택하지 않았다.",
        "- 무작위 기준은 동일 k에서의 기대값이다. 관측 차이만으로 통계적 우위나 개선율을 주장하지 않는다.",
        "- 공개 2008년 데이터이며 현장·외부 검증이 없다. 익명 변수명으로 공정 원인을 추정하지 않는다.",
        "- UCI 설명의 591 features와 달리 원본에는 590개 측정 열이 있다.",
        "- lot/batch/장비/고객/불량 비용/검사 정확도/웨이퍼맵은 제공되지 않는다.",
        "- 동일 timestamp의 분할 교차는 막았으나 알려지지 않은 군집 의존성은 통제할 수 없다.",
        "- 기존 SECOM 실험 결과를 알고 시작했으므로 완전히 새로운 blind holdout 연구가 아니다.",
        "- 성능 최적화, 비용 최적화, 수율·매출 개선, 고객 납기 영향은 검증하지 않았다.",
        "",
        "## 재계산 근거",
        "",
        "`predictions.csv`의 label/score/정책별 결정을 이용해 `decision_metrics.csv`를 재계산할 수 있다.",
        "`split_assignments.csv`, `source_manifest.json`, `run_metadata.json`에 분할·원본·코드 해시와 환경을 기록한다.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines))


def run(raw: Path, out: Path, fetch: bool) -> None:
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}; choose a new --output path")
    if fetch:
        download(raw)
    x, meta = load(raw)
    splits = temporal_split(meta)
    for ids in splits.values():
        if meta.loc[ids, "fail"].nunique() != 2:
            raise ValueError("Each split needs both classes for this evaluation")
    out.mkdir(parents=True, exist_ok=False)
    train, validation, test = (splits[s] for s in ("train", "validation", "test"))
    model = make_model()
    model.fit(x.loc[train], meta.loc[train, "fail"])
    scores = {
        name: model.predict_proba(x.loc[ids])[:, 1]
        for name, ids in (("validation", validation), ("test", test))
    }
    threshold = float(np.quantile(scores["validation"], 0.8, method="linear"))
    decisions, predictions, ranking, split_stats = [], [], [], []
    assignments = meta.copy()
    for name, ids in splits.items():
        y = meta.loc[ids, "fail"].to_numpy()
        assignments.loc[ids, "split"] = name
        split_stats.append(
            {
                "split": name,
                "n": len(ids),
                "fails": int(y.sum()),
                "fail_rate": float(y.mean()),
                "start": str(meta.loc[ids, "timestamp"].min()),
                "end": str(meta.loc[ids, "timestamp"].max()),
            }
        )
        if name == "train":
            continue
        score = scores[name]
        pred = meta.loc[ids].copy()
        pred["split"], pred["score"] = name, score
        policies = {f"top_{int(c * 100)}pct": top_k(score, pred.row_id.to_numpy(), c) for c in CAPACITIES}
        policies.update(
            {
                "fixed_val_q80": score >= threshold,
                "review_none": np.zeros(len(ids), dtype=bool),
                "review_all": np.ones(len(ids), dtype=bool),
            }
        )
        for policy, selected in policies.items():
            pred[policy] = selected.astype(int)
            decisions.append({"split": name, "policy": policy, **metrics(y, selected)})
        predictions.append(pred)
        dummy = np.full(len(ids), meta.loc[train, "fail"].mean())
        ranking.append(
            {
                "split": name,
                "ap": float(average_precision_score(y, score)),
                "dummy_ap": float(average_precision_score(y, dummy)),
                "roc_auc": float(roc_auc_score(y, score)),
            }
        )
    eda = pd.DataFrame(
        {
            "feature": x.columns,
            "missing_count": x.isna().sum().to_numpy(),
            "missing_fraction": x.isna().mean().to_numpy(),
            "observed_unique": x.nunique().to_numpy(),
        }
    )
    monthly = (
        meta.assign(month=meta.timestamp.dt.strftime("%Y-%m"))
        .groupby("month")
        .agg(n=("fail", "size"), fails=("fail", "sum"), fail_rate=("fail", "mean"))
        .reset_index()
    )
    summary = {
        "rows": len(x),
        "features": x.shape[1],
        "fails": int(meta.fail.sum()),
        "missing_cells": int(x.isna().sum().sum()),
        "constant_observed_features": int((x.nunique() == 1).sum()),
        "all_missing_features": int((x.nunique() == 0).sum()),
        "duplicate_feature_rows": int(x.duplicated().sum()),
        "duplicate_timestamp_rows": int(meta.timestamp.duplicated(keep=False).sum()),
        "splits": split_stats,
        "validation_threshold": threshold,
        "retained_train_features": int(model.named_steps["variance"].get_support().sum()),
    }
    d, r = pd.DataFrame(decisions), pd.DataFrame(ranking)
    tables = {
        "feature_eda": eda,
        "monthly_eda": monthly,
        "split_assignments": assignments,
        "predictions": pd.concat(predictions),
        "decision_metrics": d,
        "ranking_metrics": r,
    }
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", index=False, float_format="%.17g")
    source_paths = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py"))
    source_paths += [ROOT / "docs/ANALYSIS_PROTOCOL.md", ROOT / "requirements-lock.txt"]
    metadata = {
        "python": platform.python_version(),
        "platform": platform.system(),
        "versions": {
            p: importlib.metadata.version(p)
            for p in ("numpy", "pandas", "scikit-learn", "scipy", "matplotlib", "joblib")
        },
        "seed": 42,
        "model": "RandomForestClassifier",
        "trees": 200,
        "min_samples_leaf": 3,
        "class_weight": "balanced",
        "n_jobs": 1,
        "threshold_rule": "validation score quantile .8, linear; score >= threshold",
        "capacities": list(CAPACITIES),
        "tie_rule": "row_id ascending",
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths
        },
    }
    dump_json(out / "summary.json", summary)
    dump_json(out / "source_manifest.json", manifest())
    dump_json(out / "run_metadata.json", metadata)
    write_figures(out, eda, pd.DataFrame(split_stats), monthly, d)
    report(out, summary, d, r)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())}
    dump_json(out / "artifact_hashes.json", hashes)
    print(json.dumps({"output": str(out), "summary": summary}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output", type=Path, default=ROOT / "results/reproduced")
    parser.add_argument("--download", action="store_true", help="Fetch and hash-check official UCI files")
    args = parser.parse_args()
    run(args.raw, args.output, args.download)
