"""Small, reproducible activity-recognition experiments for Falsify.

All scores come from local model fitting. Case A uses only the official training
pool, leaving the official held-out participants untouched until confirmation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
from urllib.request import Request, urlopen
import warnings
import zipfile

import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC


SOURCE_URL = "https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones"
DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/240/human%2Bactivity%2Brecognition%2Busing%2Bsmartphones.zip"
DATASET_NAME = "UCI Human Activity Recognition Using Smartphones"
CLAIM = "The activity classifier generalizes to people absent from its training data, within this study's recording conditions."
ACTIVITIES = ["WALKING", "WALKING_UPSTAIRS", "WALKING_DOWNSTAIRS", "SITTING", "STANDING", "LAYING"]
CASE_IDS = ("row_split", "participant_holdout")
CACHE_VERSION = 1
_CACHE_LOCK = threading.RLock()
_MEMORY_CACHE: dict[str, tuple[dict[str, np.ndarray], dict[str, Any]]] = {}


def list_cases() -> list[dict[str, str]]:
    """Return task descriptions without an evaluator's verdict."""
    return [
        {"id": "row_split", "case_id": "row_split", "title": "Case A: shuffled recordings", "claim": CLAIM,
         "description": "A stratified random split of recordings from the official training pool."},
        {"id": "participant_holdout", "case_id": "participant_holdout", "title": "Case B: official evaluation", "claim": CLAIM,
         "description": "The dataset authors' official training and test partitions."},
    ]


def _data_dir() -> Path:
    return Path(os.environ.get("FALSIFY_DATA_DIR", Path(__file__).resolve().parent.parent / "data")).resolve()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".json", delete=False) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        temporary = Path(stream.name)
    temporary.replace(path)


def _download_archive(destination: Path) -> None:
    temporary: Path | None = None
    try:
        request = Request(DOWNLOAD_URL, headers={"User-Agent": "Falsify-hackathon-research/0.1"})
        with urlopen(request, timeout=90) as response, tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".download", delete=False) as stream:
            temporary = Path(stream.name)
            size = 0
            for block in iter(lambda: response.read(1024 * 1024), b""):
                size += len(block)
                if size > 100 * 1024 * 1024:
                    raise ValueError("UCI download exceeded the expected archive size limit.")
                stream.write(block)
        if not zipfile.is_zipfile(temporary):
            raise ValueError("UCI download was not a ZIP archive.")
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_arrays(archive: Path) -> dict[str, np.ndarray]:
    """Read exactly six named numeric members, without extracting any files."""
    def read_members(source: zipfile.ZipFile) -> dict[str, np.ndarray]:
        arrays = {}
        for partition in ("train", "test"):
            for kind in ("X", "y", "subject"):
                member = f"UCI HAR Dataset/{partition}/{kind}_{partition}.txt"
                info = source.getinfo(member)
                if info.file_size > 100 * 1024 * 1024:
                    raise ValueError(f"Unexpectedly large dataset member: {member}")
                with source.open(info) as stream:
                    arrays[f"{kind}_{partition}"] = np.loadtxt(stream, dtype=np.float32 if kind == "X" else np.int64)
        return arrays

    with zipfile.ZipFile(archive) as outer:
        if "UCI HAR Dataset/train/X_train.txt" in outer.namelist():
            arrays = read_members(outer)
        else:
            member = outer.getinfo("UCI HAR Dataset.zip")
            if member.file_size > 100 * 1024 * 1024:
                raise ValueError("Unexpectedly large nested dataset archive.")
            with zipfile.ZipFile(io.BytesIO(outer.read(member))) as inner:
                arrays = read_members(inner)
    _validate_arrays(arrays)
    return arrays


def _validate_arrays(arrays: dict[str, np.ndarray]) -> None:
    for partition in ("train", "test"):
        features = arrays[f"X_{partition}"]
        labels = arrays[f"y_{partition}"]
        participants = arrays[f"subject_{partition}"]
        if features.ndim != 2 or features.shape[1] != 561:
            raise ValueError("Expected 561 UCI HAR features.")
        if labels.ndim != 1 or participants.ndim != 1 or len(features) != len(labels) or len(labels) != len(participants):
            raise ValueError("UCI HAR row counts do not match.")
        if not np.isfinite(features).all() or not set(labels.tolist()) <= set(range(1, 7)):
            raise ValueError("Invalid UCI HAR feature or label values.")
        if not set(participants.tolist()) <= set(range(1, 31)):
            raise ValueError("Invalid UCI HAR participant identifiers.")
    if set(arrays["subject_train"].tolist()) & set(arrays["subject_test"].tolist()):
        raise ValueError("The official UCI HAR partitions unexpectedly share participants.")


def _load_data() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    directory = _data_dir()
    key = str(directory)
    with _CACHE_LOCK:
        if key in _MEMORY_CACHE:
            return _MEMORY_CACHE[key]
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / "uci-har.zip"
        cache = directory / "uci-har-arrays.npz"
        manifest_path = directory / "uci-har-manifest.json"
        if cache.exists() and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("cache_version") != CACHE_VERSION:
                raise ValueError("Unsupported UCI HAR cache version; remove the derived arrays and manifest to rebuild.")
            if _sha256_file(cache) != manifest.get("arrays_sha256"):
                raise ValueError("Cached UCI HAR arrays failed integrity verification; remove the arrays and manifest to rebuild.")
            with np.load(cache, allow_pickle=False) as saved:
                arrays = {name: saved[name] for name in saved.files}
            _validate_arrays(arrays)
        else:
            if not archive.exists():
                _download_archive(archive)
            arrays = _read_arrays(archive)
            with tempfile.NamedTemporaryFile(dir=directory, suffix=".npz", delete=False) as stream:
                temporary = Path(stream.name)
                np.savez_compressed(stream, **arrays)
            temporary.replace(cache)
            manifest = {
                "name": DATASET_NAME,
                "source_url": SOURCE_URL,
                "download_url": DOWNLOAD_URL,
                "doi": "10.24432/C54S4K",
                "license": "CC BY 4.0",
                "citation": "Reyes-Ortiz, Anguita, Ghio, Oneto, and Parra (2013). Human Activity Recognition Using Smartphones. UCI Machine Learning Repository.",
                "sha256": _sha256_file(archive),
                "arrays_sha256": _sha256_file(cache),
                "sha256_scope": "Downloaded archive, not independently publisher-signed",
                "cache_version": CACHE_VERSION,
                "n_features": int(arrays["X_train"].shape[1]),
                "n_rows": int(len(arrays["y_train"]) + len(arrays["y_test"])),
                "n_participants": len(set(arrays["subject_train"].tolist()) | set(arrays["subject_test"].tolist())),
            }
            _atomic_json(manifest_path, manifest)
        for array in arrays.values():
            array.flags.writeable = False
        _MEMORY_CACHE[key] = (arrays, manifest)
        return arrays, manifest


def prepare_data() -> dict[str, Any]:
    """Download/cache the public data if necessary and return its provenance."""
    _, manifest = _load_data()
    return dict(manifest)


def _select_split(arrays: dict[str, np.ndarray], case_id: str, evaluation: str, seed: int) -> dict[str, Any]:
    if case_id not in CASE_IDS:
        raise ValueError(f"Unknown case_id: {case_id}. Expected one of {CASE_IDS}.")
    if evaluation not in ("original", "participant_holdout"):
        raise ValueError("evaluation must be 'original' or 'participant_holdout'.")
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer from 0 through 2**32 - 1.")
    if case_id == "row_split" and evaluation == "original":
        train_indices, test_indices = train_test_split(
            np.arange(len(arrays["y_train"])), test_size=0.30,
            random_state=seed, stratify=arrays["y_train"],
        )
        result = {
            "X_train": arrays["X_train"][train_indices], "X_test": arrays["X_train"][test_indices],
            "y_train": arrays["y_train"][train_indices], "y_test": arrays["y_train"][test_indices],
            "subject_train": arrays["subject_train"][train_indices], "subject_test": arrays["subject_train"][test_indices],
            "train_row_ids": train_indices, "test_row_ids": test_indices,
            "strategy": "stratified_random_rows_from_official_training_pool",
            "test_population": "Other recordings from the same development participant pool",
        }
    else:
        result = {name: arrays[name] for name in ("X_train", "X_test", "y_train", "y_test", "subject_train", "subject_test")}
        result.update({
            "train_row_ids": np.arange(len(arrays["y_train"])),
            "test_row_ids": np.arange(len(arrays["y_test"])) + len(arrays["y_train"]),
            "strategy": "official_participant_holdout",
            "test_population": "Nine participants absent from the official training partition",
        })
    return result


def _split_metadata(split: dict[str, Any]) -> dict[str, Any]:
    train_participants = sorted(set(split["subject_train"].tolist()))
    test_participants = sorted(set(split["subject_test"].tolist()))
    overlap = sorted(set(train_participants) & set(test_participants))
    rows_overlap = np.intersect1d(split["train_row_ids"], split["test_row_ids"])
    return {
        "strategy": split["strategy"], "test_population": split["test_population"],
        "n_train": len(split["y_train"]), "n_test": len(split["y_test"]),
        "train_participants": train_participants, "test_participants": test_participants,
        "overlap_participants": overlap, "overlap_count": len(overlap),
        "n_train_participants": len(train_participants), "n_test_participants": len(test_participants),
        "row_overlap_count": int(len(rows_overlap)),
        "train_row_ids_sha256": hashlib.sha256(np.asarray(split["train_row_ids"], dtype="<i8").tobytes()).hexdigest(),
        "test_row_ids_sha256": hashlib.sha256(np.asarray(split["test_row_ids"], dtype="<i8").tobytes()).hexdigest(),
    }


def audit_split(case_id: str, seed: int = 42) -> dict[str, Any]:
    """Inspect the original split without fitting a classifier or seeing scores."""
    started = time.perf_counter()
    arrays, dataset = _load_data()
    split = _split_metadata(_select_split(arrays, case_id, "original", seed))
    disjoint = split["overlap_count"] == 0
    result = {
        "case_id": case_id, "seed": seed, "claim": CLAIM, "split": split,
        "supports_unseen_participant_claim": disjoint,
        "split_supports_unseen_participant_evaluation": disjoint,
        "reason": (
            "No participant appears in both partitions. This permits measuring performance on held-out study participants; the audit alone does not establish adequate performance or broader deployment validity."
            if disjoint else
            f"{split['overlap_count']} participants appear in both partitions. A score on these recordings does not establish performance on people absent from training."
        ),
        "required_followup": "review_heldout_metrics_and_limit_scope" if disjoint else "run_participant_holdout",
        "dataset_sha256": dataset["sha256"],
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    return result


def run_experiment(case_id: str, evaluation: str = "original", seed: int = 42) -> dict[str, Any]:
    """Fit the same fixed pipeline and report actual local predictions and metrics.

    Hyperparameters are fixed before the official holdout is evaluated. Repeated
    calls are reproducibility checks, not independent replications or tuning.
    """
    started = time.perf_counter()
    arrays, dataset = _load_data()
    split = _select_split(arrays, case_id, evaluation, seed)
    model = make_pipeline(StandardScaler(), LinearSVC(C=1.0, dual="auto", max_iter=20000, random_state=seed))
    fit_started = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(split["X_train"], split["y_train"])
        predictions = model.predict(split["X_test"])
    computation_seconds = time.perf_counter() - fit_started
    metadata = _split_metadata(split)
    result = {
        "case_id": case_id, "evaluation": evaluation, "seed": seed,
        "claim": CLAIM, "split": metadata,
        "metrics": {
            "accuracy": float(accuracy_score(split["y_test"], predictions)),
            "macro_f1": float(f1_score(split["y_test"], predictions, average="macro", labels=list(range(1, 7)), zero_division=0)),
            "confusion_matrix": confusion_matrix(split["y_test"], predictions, labels=list(range(1, 7))).tolist(),
            "labels": ACTIVITIES,
            "n_correct": int(np.sum(predictions == split["y_test"])),
        },
        "model": {
            "name": "StandardScaler + LinearSVC",
            "parameters": {"C": 1.0, "dual": "auto", "max_iter": 20000, "random_state": seed},
            "preprocessing": "StandardScaler fitted only on the training partition; uses the dataset's supplied 561 features.",
            "sklearn_version": sklearn.__version__,
            "numpy_version": np.__version__,
            "hyperparameters_tuned_on_holdout": False,
        },
        "dataset": dict(dataset),
        "predictions_sha256": hashlib.sha256(np.asarray(predictions, dtype="<i8").tobytes()).hexdigest(),
        "warnings": [str(item.message) for item in captured],
        "limitations": [
            "This is a feasibility case, not an estimate of AI reviewer reliability.",
            "The data cover 30 adults aged 19 to 48, six activities, and a particular waist-mounted smartphone setup.",
            "The supplied feature windows overlap in time. Shuffled rows may share adjacent sensor context as well as participants.",
            "The row-split result and official holdout use different sample counts and participant populations. Their score difference does not isolate a single causal effect.",
            "The official holdout is a fixed confirmation set. Repeated runs with the same settings are not independent replication.",
        ],
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    result["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    result["artifact_sha256_scope"] = "Canonical sorted JSON before adding artifact_sha256, artifact_sha256_scope, computation_seconds and elapsed_seconds"
    result["computation_seconds"] = round(computation_seconds, 6)
    result["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return result
