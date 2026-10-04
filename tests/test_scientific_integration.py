"""Behavioral checks at the evidence and orchestration boundary.

These fixtures deliberately vary evidence independently of the case label, so
the tests detect workflows that merely play a prewritten case narrative.
"""

import asyncio
import sys
import types

import pytest

from falsify import science, store
from falsify.workflow import ScientificTools, execute, make_verdict


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")


def install_evidence(monkeypatch, overlap: int):
    executed = []

    def experiment(case_id, evaluation="original", seed=42):
        executed.append((case_id, evaluation, seed))
        return {
            "case_id": case_id, "evaluation": evaluation,
            "claim": science.CLAIM,
            "model": {"name": "fixed classifier", "hyperparameters_tuned_on_holdout": False},
            "dataset": {"name": "synthetic integration fixture", "sha256": "f" * 64},
            "metrics": {"accuracy": 0.83, "macro_f1": 0.82},
            "split": {
                "overlap_count": overlap if evaluation == "original" else 0,
                "overlap_participants": list(range(1, overlap + 1)) if evaluation == "original" else [],
                "train_participants": [1, 2, 3], "test_participants": [1, 2, 3] if overlap else [4, 5],
                "n_train": 70, "n_test": 30,
            },
        }

    def audit(case_id, seed=42):
        return {"case_id": case_id, "split": {"overlap_count": overlap}}

    monkeypatch.setattr(science, "run_experiment", experiment)
    monkeypatch.setattr(science, "audit_split", audit)
    return executed


@pytest.mark.parametrize("case_id,overlap,needs_repair", [
    ("row_split", 0, False),
    ("participant_holdout", 3, True),
])
def test_local_next_action_follows_measured_overlap_not_case_label(
    isolated_store, monkeypatch, case_id, overlap, needs_repair,
):
    executed = install_evidence(monkeypatch, overlap)
    run = store.create(case_id, "local")
    asyncio.run(execute(run["id"], case_id, "local"))
    record = store.read(run["id"])
    assert record["status"] == "completed"
    assert ("corrected" in record["results"]) is needs_repair
    assert [item[1] for item in executed] == (["original", "participant_holdout"] if needs_repair else ["original"])
    assert record["results"]["original"]["metrics"]["accuracy"] == 0.83
    assert record["verdict"]["status"] == ("unsupported" if needs_repair else "supported")
    assert record["verdict"]["repair_status"] == ("evaluated" if needs_repair else "not_needed")
    assert all(event["data"].get("source") == "fixed_rule" for event in record["events"] if event["type"] in {"decision", "revision"})
    evidence = {event["id"] for event in record["events"] if event["type"] == "tool_result"}
    assert set(record["verdict"]["evidence_ids"]) <= evidence


def test_tool_budget_stops_before_the_seventh_computation(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 0)
    run = store.create("participant_holdout", "local")
    boundary = ScientificTools(run["id"], "participant_holdout")

    async def exercise():
        for _ in range(6):
            await boundary.dispatch("audit_split")
        with pytest.raises(ValueError, match="budget"):
            await boundary.dispatch("audit_split")

    asyncio.run(exercise())
    record = store.read(run["id"])
    assert record["usage"]["tool_calls"] == 6
    assert sum(event["type"] == "tool_result" for event in record["events"]) == 6


def test_original_agent_view_withholds_audit_but_ledger_keeps_full_provenance(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 3)
    run = store.create("row_split", "local")
    boundary = ScientificTools(run["id"], "row_split")
    agent_view = asyncio.run(boundary.dispatch("run_original"))
    assert agent_view["metrics"]["accuracy"] == 0.83
    assert agent_view["n_train"] == 70 and agent_view["n_test"] == 30
    assert "case_id" not in agent_view
    assert "split" not in agent_view
    assert "overlap_count" not in agent_view
    assert "train_participants" not in agent_view
    ledger = store.read(run["id"])
    full_result = ledger["results"]["original"]
    assert full_result["split"]["overlap_count"] == 3
    assert full_result["split"]["train_participants"] == [1, 2, 3]
    event = next(event for event in ledger["events"] if event["id"] == agent_view["evidence_id"])
    assert event["data"] == full_result


def test_live_claim_without_executed_evidence_cannot_complete(isolated_store, monkeypatch):
    async def ungrounded(**kwargs):
        return {
            "decision": {"action": "accept", "summary": "The classifier generalizes.", "evidence_ids": ["E999"]},
            "tool_outputs": [], "trace": [], "usage": {}, "mode": "omnigent", "session_id": "test-session",
        }

    monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=ungrounded))
    run = store.create("participant_holdout", "omnigent")
    asyncio.run(execute(run["id"], "participant_holdout", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] != "completed", "A model's JSON claim is not evidence that a scientific protocol executed."
    assert not record["verdict"] or record["verdict"]["status"] != "supported"


def install_live_protocol(monkeypatch, tool_names, action="accept", fabricated_id=False, cite_first_audit=False):
    async def protocol(**kwargs):
        results = []
        for tool in tool_names:
            results.append(await kwargs["dispatch_tool"](tool, {}))
        return {
            "decision": {
                "action": action, "summary": "Conclusion from the executed tests.",
                "reason": "The measured split determines the scope of the submitted evaluation.",
                "evidence_ids": ["E999"] if fabricated_id else [result["evidence_id"] for result in (results[:2] if cite_first_audit else results)],
                "next_experiment": "Evaluate on an independent recording cohort.",
            },
            "tool_outputs": results, "trace": [], "usage": {}, "mode": "omnigent", "session_id": "test-session",
        }

    monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=protocol))


@pytest.mark.parametrize("tool_names", [("audit_split",), ("run_original",)])
def test_live_protocol_requires_original_measurement_and_split_audit(
    isolated_store, monkeypatch, tool_names,
):
    install_evidence(monkeypatch, 0)
    install_live_protocol(monkeypatch, tool_names)
    run = store.create("participant_holdout", "omnigent")
    asyncio.run(execute(run["id"], "participant_holdout", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] != "completed"
    assert not record["verdict"] or record["verdict"]["status"] != "supported"
    assert "requires measured original and audit" in record["error"]


def test_live_verdict_cannot_cite_unrecorded_evidence(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 0)
    install_live_protocol(monkeypatch, ["run_original", "audit_split"], fabricated_id=True)
    run = store.create("participant_holdout", "omnigent")
    asyncio.run(execute(run["id"], "participant_holdout", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] != "completed"
    assert not record["verdict"] or "E999" not in record["verdict"].get("evidence_ids", [])
    assert "evidence IDs" in record["error"]


def test_live_valid_control_does_not_require_a_redundant_correction(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 0)
    install_live_protocol(monkeypatch, ["run_original", "audit_split"])
    run = store.create("participant_holdout", "omnigent")
    asyncio.run(execute(run["id"], "participant_holdout", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] == "completed"
    assert "corrected" not in record["results"]
    assert record["verdict"]["status"] == "supported"
    assert record["verdict"]["repair_status"] == "not_needed"


def test_correction_preserves_reviewers_rejection_of_original_evidence(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 3)
    install_live_protocol(monkeypatch, ["run_original", "audit_split", "participant_holdout"], action="reject")
    run = store.create("row_split", "omnigent")
    asyncio.run(execute(run["id"], "row_split", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] == "completed"
    assert record["results"]["corrected"]["split"]["overlap_count"] == 0
    assert record["verdict"]["status"] == "unsupported"
    assert record["verdict"]["repair_status"] == "evaluated"


def test_wrong_ai_judgment_remains_visible_as_disagreement(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 3)
    install_live_protocol(monkeypatch, ["run_original", "audit_split"], action="accept")
    run = store.create("row_split", "omnigent")
    asyncio.run(execute(run["id"], "row_split", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] == "completed"
    assert record["verdict"]["status"] == "supported"
    assert record["validation"]["agrees_with_split_rule"] is False
    assert record["validation"]["deterministic_reference_status"] == "unsupported"
    assert any(event["type"] == "disagreement" for event in record["events"])


def test_repeated_audit_can_cite_its_first_recorded_evidence(isolated_store, monkeypatch):
    install_evidence(monkeypatch, 0)
    install_live_protocol(monkeypatch, ["run_original", "audit_split", "audit_split"], cite_first_audit=True)
    run = store.create("participant_holdout", "omnigent")
    asyncio.run(execute(run["id"], "participant_holdout", "omnigent"))
    record = store.read(run["id"])
    assert record["status"] == "completed"
    evidence = [event for event in record["events"] if event["type"] == "tool_result"]
    assert len(evidence) == 3
    assert evidence[1]["id"] in record["verdict"]["evidence_ids"]
    assert evidence[2]["id"] not in record["verdict"]["evidence_ids"]
    assert evidence[1]["data"] == evidence[2]["data"]


@pytest.mark.parametrize("audit", [
    {}, {"split": {}}, {"split": {"overlap_count": -1}},
    {"split": {"overlap_count": False}}, {"split": {"overlap_count": 0.0}},
    {"split": {"overlap_count": 0, "overlap_participants": [1]}},
    {"split": {"overlap_participants": [1, 1]}},
])
def test_missing_or_inconsistent_audit_is_not_treated_as_valid(audit):
    with pytest.raises(ValueError, match="audit"):
        make_verdict({"metrics": {"accuracy": 0.99}}, audit, None, ["E001"])


def test_explicit_empty_overlap_list_is_real_evidence_of_separation():
    verdict = make_verdict({"metrics": {"accuracy": 0.83}}, {"split": {"overlap_participants": []}}, None, ["E001"])
    assert verdict["status"] == "supported"
    assert verdict["repair_status"] == "not_needed"


@pytest.mark.parametrize("original_score,corrected_score", [(0.98, 0.96), (0.90, 0.95), (0.96, 0.96)])
def test_original_validity_does_not_depend_on_a_performance_collapse(original_score, corrected_score):
    verdict = make_verdict(
        {"metrics": {"accuracy": original_score}},
        {"split": {"overlap_count": 21}},
        {"metrics": {"accuracy": corrected_score}, "split": {"overlap_count": 0}},
        ["E001", "E002", "E003"],
    )
    assert verdict["status"] == "unsupported"
    assert verdict["repair_status"] == "evaluated"
    assert "held-out participants" in verdict["repaired_claim"]


@pytest.mark.parametrize("cancel_at", ["original", "participant_holdout"])
def test_cancel_during_computation_preserves_evidence_without_final_verdict(
    isolated_store, monkeypatch, cancel_at,
):
    executed = install_evidence(monkeypatch, 3)
    run = store.create("row_split", "local")
    calculate = science.run_experiment

    def finish_then_cancel(case_id, evaluation="original", seed=42):
        result = calculate(case_id, evaluation=evaluation, seed=seed)
        if evaluation == cancel_at:
            store.update(run["id"], cancel_requested=True)
        return result

    monkeypatch.setattr(science, "run_experiment", finish_then_cancel)
    asyncio.run(execute(run["id"], "row_split", "local"))
    record = store.read(run["id"])
    assert record["status"] == "cancelled"
    assert record["verdict"] is None
    assert record["completed_at"]
    assert "original" in record["results"]
    assert ("corrected" in record["results"]) == (cancel_at == "participant_holdout")
    assert len(executed) == (1 if cancel_at == "original" else 2)
    assert not any(event["type"] == "verdict" for event in record["events"])
