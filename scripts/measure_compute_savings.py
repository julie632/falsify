"""Measure one explicitly limited deterministic post-original compute comparison.

Freeze the protocol with ``--prepare`` before executing ``--run``. This does not
measure agents, inference, human effort, or general scientific acceleration.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
from typing import Any

from falsify import science


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "demo/validation/compute-savings-protocol.json"
OUTPUT = "demo/validation/compute-savings.json"
REFERENCE = "demo/runs/83faf266dc944354b43b5b8ffc22bbd6/run.json"
SOURCES = ("scripts/measure_compute_savings.py", "falsify/science.py", "uv.lock")
POLICIES = ("audit_and_retain", "audit_and_always_rerun")
ORDERS = [list(POLICIES), list(reversed(POLICIES)), list(POLICIES)]
LIMITATIONS = [
    "This compares local deterministic scientific computation after the original clean-control evaluation already exists. Its cost is excluded from both paths.",
    "No LLM inference, Omnigent orchestration, network transport, startup, human effort, or end-to-end elapsed-time savings are measured.",
    "The explicit always-rerun comparator intentionally repeats an already valid evaluation. It is an artificial baseline, not the best available method.",
    "A fixed conditional rule can avoid the same redundant fit. No unique agent benefit or superiority over a fixed rule is established.",
    "Three repeated executions of the same fixed case characterize this local computation only. They are not independent scientific replications or a reviewer-reliability estimate.",
    "No overall speed multiplier, 10x discovery claim, dollar-cost saving, or human-time saving is established.",
    "Data loading and cache warm-up are excluded. No classifier fit is warmed before measurement; local scheduling and machine load can affect timings.",
    "The audit alone does not establish predictive performance. Both decisions also use the same already measured original metrics and their narrow study scope.",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text())


def save_new(path: str, value: dict[str, Any]) -> None:
    # Refuse to overwrite either the preregistered protocol or its results.
    with (ROOT / path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked_reference() -> dict[str, Any]:
    reference = load(REFERENCE)
    require(reference["status"] == "completed", "Reference is not completed.")
    require(reference["case_id"] == "participant_holdout", "Reference case differs.")
    require(reference["validation"]["protocol_verified"], "Reference protocol is unverified.")
    require(reference["verdict"]["status"] == "supported", "Reference conclusion differs.")
    require(reference["results"]["original"]["seed"] == 42, "Reference seed differs.")
    require(reference["results"]["original"]["split"]["overlap_count"] == 0, "Reference overlaps.")
    return reference


def prepare() -> None:
    reference = checked_reference()
    original = reference["results"]["original"]
    protocol = {
        "schema_version": 1,
        "title": "Frozen post-original clean-control compute comparison",
        "created_at": now(),
        "execution_mode": "deterministic_local_comparison",
        "question": "How much local computation does retaining a verified clean control avoid relative to explicitly rerunning the same classifier after the same audit?",
        "case_id": "participant_holdout",
        "seed": 42,
        "paired_repeats": 3,
        "fixed_order": ORDERS,
        "warmup": "Call prepare_data once before any timed path. Do not fit a classifier during warm-up.",
        "policies": {
            "audit_and_retain": ["audit_split(participant_holdout, seed=42)", "retain the supplied original metrics after checking zero overlap"],
            "audit_and_always_rerun": ["audit_split(participant_holdout, seed=42)", "run_experiment(participant_holdout, participant_holdout, seed=42)"],
        },
        "timing_scope": "perf_counter wall time and process_time CPU around each complete policy function, including its audit, optional rerun, validation and conclusion. Excludes data warm-up, original computation, imports and report writing.",
        "count_scope": "Scientific calls are actual audit_split and run_experiment invocations. Classifier fits count completed run_experiment invocations; the hashed science implementation fits exactly one pipeline per invocation.",
        "reference": {"path": REFERENCE, "sha256": sha256(REFERENCE), "run_id": reference["id"]},
        "source_sha256": {path: sha256(path) for path in SOURCES},
        "frozen_model": original["model"],
        "dataset": original["dataset"],
        "expected_metrics": original["metrics"],
        "expected_predictions_sha256": original["predictions_sha256"],
        "acceptance_rule": "Every audit has zero participant and row overlap and the same dataset hash and split as the recorded control. Every rerun must exactly match the recorded metrics, prediction hash, model and split. Both policies must retain the same narrow supported conclusion. Stop and mark failed on any mismatch; never tune, retry selectively or discard a failed measurement.",
        "summary_rule": "Report all pairs, per-policy medians and paired absolute differences in wall and process CPU seconds; report actual calls and classifier-fit counts. Do not report a speed multiplier.",
        "limitations": LIMITATIONS,
    }
    save_new(PROTOCOL, protocol)
    print(json.dumps({"status": "protocol_frozen", "path": PROTOCOL, "sha256": sha256(PROTOCOL)}))


def measure_policy(policy: str, original: dict[str, Any]) -> dict[str, Any]:
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    audit = science.audit_split("participant_holdout", seed=42)
    require(audit["split"] == original["split"], "Audit split does not match recorded control.")
    require(audit["dataset_sha256"] == original["dataset"]["sha256"], "Audit dataset hash differs.")
    require(audit["split"]["overlap_count"] == audit["split"]["row_overlap_count"] == 0, "Audit is not clean.")
    calls = [{"tool": "audit_split", "scientific_calls": 1, "classifier_fits": 0}]
    rerun: dict[str, Any] | None = None
    if policy == "audit_and_always_rerun":
        rerun = science.run_experiment("participant_holdout", "participant_holdout", seed=42)
        calls.append({"tool": "run_experiment", "scientific_calls": 1, "classifier_fits": 1})
        for key in ("metrics", "predictions_sha256", "model", "split", "dataset"):
            require(rerun[key] == original[key], f"Rerun {key} does not match recorded control.")
        require(not rerun["warnings"], "Rerun produced warnings.")
    else:
        require(policy == "audit_and_retain", "Unknown policy.")
    decision = {
        "status": "supported",
        "scope": original["claim"],
        "accuracy": original["metrics"]["accuracy"],
        "n_held_out_participants": original["split"]["n_test_participants"],
        "basis": "Already measured original metrics plus verified zero participant and row overlap. No broader deployment claim.",
    }
    cpu_seconds, wall_seconds = time.process_time() - cpu_start, time.perf_counter() - wall_start
    return {
        "policy": policy,
        "wall_seconds": wall_seconds,
        "process_cpu_seconds": cpu_seconds,
        "calls": calls,
        "scientific_calls": sum(call["scientific_calls"] for call in calls),
        "classifier_fits": sum(call["classifier_fits"] for call in calls),
        "decision": decision,
        "audit": {"dataset_sha256": audit["dataset_sha256"], "overlap_count": 0, "row_overlap_count": 0, "elapsed_seconds": audit["elapsed_seconds"]},
        "rerun": None if rerun is None else {
            "metrics": rerun["metrics"], "predictions_sha256": rerun["predictions_sha256"],
            "artifact_sha256": rerun["artifact_sha256"], "computation_seconds": rerun["computation_seconds"],
            "elapsed_seconds": rerun["elapsed_seconds"], "matches_recorded_control_exactly": True,
        },
    }


def run() -> None:
    require(not (ROOT / OUTPUT).exists(), "Results already exist; do not overwrite or selectively rerun.")
    protocol = load(PROTOCOL)
    require(protocol["fixed_order"] == ORDERS and protocol["seed"] == 42 and protocol["paired_repeats"] == 3, "Protocol configuration differs.")
    require(protocol["source_sha256"] == {path: sha256(path) for path in SOURCES}, "Source changed after protocol freeze.")
    require(protocol["reference"]["sha256"] == sha256(REFERENCE), "Recorded control changed after protocol freeze.")
    reference = checked_reference()
    original = reference["results"]["original"]
    report: dict[str, Any] = {
        "schema_version": 1, "status": "running", "started_at": now(),
        "execution_mode": "deterministic_local_comparison",
        "protocol": {"path": PROTOCOL, "sha256": sha256(PROTOCOL), "created_at": protocol["created_at"]},
        "reference": protocol["reference"], "source_sha256": protocol["source_sha256"],
        "environment": {"python": platform.python_version(), "operating_system": platform.system(), "architecture": platform.machine(), "numpy": science.np.__version__, "scikit_learn": science.sklearn.__version__},
        "dataset": {}, "pairs": [], "limitations": LIMITATIONS,
    }
    try:
        report["dataset"] = science.prepare_data()
        require(report["dataset"] == original["dataset"], "Warmed dataset provenance differs.")
        for index, order in enumerate(ORDERS, 1):
            pair: dict[str, Any] = {"repeat": index, "order": order, "measurements": []}
            report["pairs"].append(pair)
            for policy in order:
                measurement = measure_policy(policy, original)
                pair["measurements"].append(measurement)
                print(json.dumps({"repeat": index, "policy": policy, "wall_seconds": measurement["wall_seconds"], "process_cpu_seconds": measurement["process_cpu_seconds"]}), flush=True)
            by_policy = {row["policy"]: row for row in pair["measurements"]}
            require(by_policy[POLICIES[0]]["decision"] == by_policy[POLICIES[1]]["decision"], "Decisions differ.")
            pair["same_narrow_decision"] = True
            pair["seconds_avoided"] = {metric: by_policy[POLICIES[1]][metric] - by_policy[POLICIES[0]][metric] for metric in ("wall_seconds", "process_cpu_seconds")}
        report["summary"] = {
            "paired_repeats": 3,
            "per_policy": {
                policy: {
                    "median_wall_seconds": statistics.median(row["wall_seconds"] for pair in report["pairs"] for row in pair["measurements"] if row["policy"] == policy),
                    "median_process_cpu_seconds": statistics.median(row["process_cpu_seconds"] for pair in report["pairs"] for row in pair["measurements"] if row["policy"] == policy),
                    "scientific_calls_per_repeat": 1 if policy == POLICIES[0] else 2,
                    "classifier_fits_per_repeat": 0 if policy == POLICIES[0] else 1,
                } for policy in POLICIES
            },
            "median_paired_seconds_avoided": {metric: statistics.median(pair["seconds_avoided"][metric] for pair in report["pairs"]) for metric in ("wall_seconds", "process_cpu_seconds")},
            "scientific_calls_avoided_per_repeat": 1,
            "classifier_fits_avoided_per_repeat": 1,
            "all_reruns_match_recorded_control_exactly": True,
            "all_decisions_match": True,
            "overall_discovery_speedup_measured": False,
        }
        report["status"] = "completed"
    except Exception as error:
        report["status"] = "failed"
        # Only controlled validation messages are retained; no local paths or
        # unexpected dependency exception text belongs in a public result.
        report["error"] = {"type": type(error).__name__, "message": str(error) if type(error) is ValueError else "Measurement failed; inspect the local exception without publishing environment details."}
        raise
    finally:
        report["completed_at"] = now()
        save_new(OUTPUT, report)
    print(json.dumps({"status": report["status"], "output": OUTPUT, "summary": report["summary"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run", action="store_true")
    arguments = parser.parse_args()
    prepare() if arguments.prepare else run()


if __name__ == "__main__":
    main()
