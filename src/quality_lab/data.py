"""Download only the attributed UCI source; validate before every analysis."""

import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
HASHES = {
    "secom.zip": "eea568baf3c2229096d7d294cf0b096b5502bd96d92c0b80a65b84714059be8e",
    "secom.data": "20f0e7ee434f7dcbae0eea9ffff009a2b57f42d6b0dc9a5bd4f00782c0a3374c",
    "secom_labels.data": "126884cf453705c9e61a903fe906f0665a3b45ce3639e621edc5c93c89627e03",
    "secom.names": "6d91b0b46cdee03064ee3e3112f937c1b3f7fcd9933575794ec07974e6f1ea59",
}


def verify(name: str, payload: bytes) -> None:
    if hashlib.sha256(payload).hexdigest() != HASHES[name]:
        raise ValueError(f"Source hash mismatch: {name}; no files replaced")


def download(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    existing = [name for name in HASHES if (raw / name).exists()]
    for name in existing:
        verify(name, (raw / name).read_bytes())
    if len(existing) == len(HASHES):
        return
    with urllib.request.urlopen(URL, timeout=60) as response:
        payload = response.read()
    verify("secom.zip", payload)
    files = {"secom.zip": payload}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in HASHES:
            if name != "secom.zip":
                files[name] = archive.read(name)
    for name, contents in files.items():
        verify(name, contents)
    for name, contents in files.items():
        if not (raw / name).exists():
            with (raw / name).open("xb") as target:
                target.write(contents)


def load(raw: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    for name in ("secom.data", "secom_labels.data", "secom.names"):
        verify(name, (raw / name).read_bytes())
    features = pd.read_csv(raw / "secom.data", sep=r"\s+", header=None)
    labels = pd.read_csv(raw / "secom_labels.data", sep=r"\s+", header=None)
    if features.shape != (1567, 590) or labels.shape != (1567, 2):
        raise ValueError("Unexpected source dimensions")
    if not labels[0].isin([-1, 1]).all() or np.isinf(features.to_numpy()).any():
        raise ValueError("Invalid labels or infinite measurements")
    features.columns = [f"feature_{i:03d}" for i in range(590)]
    meta = pd.DataFrame(
        {
            "row_id": np.arange(len(features)),
            "timestamp": pd.to_datetime(labels[1], format="%d/%m/%Y %H:%M:%S"),
            "fail": (labels[0] == 1).astype(int),
        }
    )
    return features, meta


def manifest() -> dict:
    return {
        "dataset": "UCI SECOM",
        "url": URL,
        "page": "https://archive.ics.uci.edu/dataset/179/secom",
        "citation": "McCann, M. & Johnston, A. (2008). SECOM. DOI:10.24432/C54305",
        "license": "CC BY 4.0",
        "sha256": HASHES,
        "dimensions_note": "UCI page says 591 features; source file contains 590 measurements.",
    }


def dump_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
