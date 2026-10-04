"""Check evidence boundaries and real fitting on a small local fixture."""

import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from falsify import science


@pytest.fixture
def arrays():
    rng = np.random.default_rng(4)
    # Each participant contributes every activity, twice. Features carry a
    # simple label signal, but assertions do not depend on particular scores.
    result = {}
    for partition, subjects in (("train", [1, 2, 3, 4]), ("test", [5, 6])):
        labels = np.tile(np.tile(np.arange(1, 7), 2), len(subjects))
        features = rng.normal(size=(len(labels), 561)).astype(np.float32)
        features[:, :6] += np.eye(6)[labels - 1] * 4
        result[f"X_{partition}"] = features
        result[f"y_{partition}"] = labels
        result[f"subject_{partition}"] = np.repeat(subjects, 12)
    return result


@pytest.fixture
def local_data(monkeypatch, arrays):
    monkeypatch.setattr(science, "_load_data", lambda: (arrays, {"name": "test fixture", "sha256": "f" * 64}))
    return arrays


def test_row_split_separates_rows_but_not_people(local_data):
    audit = science.audit_split("row_split")
    assert audit["split"]["row_overlap_count"] == 0
    assert audit["split"]["overlap_participants"] == [1, 2, 3, 4]
    assert not audit["split_supports_unseen_participant_evaluation"]
    assert audit["required_followup"] == "run_participant_holdout"
    # Confirmation subjects must never enter the flawed development experiment.
    assert not ({5, 6} & set(audit["split"]["train_participants"] + audit["split"]["test_participants"]))


def test_holdout_and_repair_use_the_same_untouched_confirmation_population(local_data):
    clean = science._select_split(local_data, "participant_holdout", "original", 42)
    repair = science._select_split(local_data, "row_split", "participant_holdout", 42)
    for key in ("X_train", "X_test", "y_train", "y_test", "subject_train", "subject_test", "train_row_ids", "test_row_ids"):
        np.testing.assert_array_equal(clean[key], repair[key])
    assert not (set(repair["subject_train"]) & set(repair["subject_test"]))
    audit = science.audit_split("participant_holdout")
    assert audit["split_supports_unseen_participant_evaluation"]
    assert "does not establish" in audit["reason"]


def test_actual_predictions_produce_consistent_auditable_metrics(local_data):
    result = science.run_experiment("participant_holdout")
    matrix = np.array(result["metrics"]["confusion_matrix"])
    assert matrix.shape == (6, 6)
    assert matrix.sum() == result["split"]["n_test"]
    assert np.trace(matrix) == result["metrics"]["n_correct"]
    assert result["metrics"]["accuracy"] == np.trace(matrix) / matrix.sum()
    assert 0 <= result["metrics"]["macro_f1"] <= 1
    assert len(result["artifact_sha256"]) == 64
    assert result["model"]["hyperparameters_tuned_on_holdout"] is False
    json.dumps(result, allow_nan=False)


def test_fixed_protocol_is_reproducible(local_data):
    first = science.run_experiment("row_split")
    second = science.run_experiment("row_split")
    assert first["predictions_sha256"] == second["predictions_sha256"]
    assert first["artifact_sha256"] == second["artifact_sha256"]


@pytest.mark.parametrize("case,evaluation,seed", [
    ("unknown", "original", 42), ("row_split", "unknown", 42),
    ("row_split", "original", -1), ("row_split", "original", True),
])
def test_invalid_requests_are_rejected(local_data, case, evaluation, seed):
    with pytest.raises(ValueError):
        science.run_experiment(case, evaluation, seed)


def test_archive_reader_never_extracts_untrusted_paths(tmp_path: Path):
    archive = tmp_path / "fake.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escaped.txt", "must not be extracted")
    with pytest.raises(KeyError):
        science._read_arrays(archive)
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_malformed_official_partitions_are_rejected(arrays):
    arrays["subject_test"][0] = arrays["subject_train"][0]
    with pytest.raises(ValueError, match="share participants"):
        science._validate_arrays(arrays)
