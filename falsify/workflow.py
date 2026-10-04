"""Scientific tool boundary and explicit local reference workflow."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from falsify import store


class RunCancelled(Exception):
    pass


async def _run_blocking(function, *args, **kwargs):
    """Drain fixed CPU work before propagating cancellation to its caller."""
    pending = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        # Python cannot interrupt a thread. Drain it before another run can
        # start, then raise before the caller writes late ledger evidence.
        while not pending.done():
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not pending.cancelled():
            pending.exception()  # Retrieve errors without hiding cancellation.
        raise


def _check_cancelled(run_id: str) -> None:
    if store.read(run_id).get("cancel_requested"):
        raise RunCancelled("Run cancelled by user")


def _overlap_count(audit: dict) -> int:
    """Missing or inconsistent audit data must never imply a clean split."""
    split = audit.get("split", audit)
    if not isinstance(split, dict):
        raise ValueError("The split audit must contain participant-overlap evidence")
    participants = split.get("overlap_participants")
    count = split.get("overlap_count")
    if participants is not None:
        if not isinstance(participants, list) or any(not isinstance(p, int) or isinstance(p, bool) for p in participants):
            raise ValueError("The split audit contains invalid participant identifiers")
        if len(set(participants)) != len(participants):
            raise ValueError("The split audit contains duplicate participant identifiers")
        if count is None:
            count = len(participants)
        elif count != len(participants):
            raise ValueError("The split audit overlap count disagrees with its participant list")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("The split audit must report a nonnegative participant-overlap count")
    return count


def _validate_live_outcome(outcome: dict, tools: "ScientificTools", run: dict) -> None:
    """Reject claims of executed work without evidence, not wrong scientific judgments."""
    if outcome.get("mode") != "omnigent" or not outcome.get("session_id"):
        raise RuntimeError("The live run has no verifiable Omnigent session")
    if not {"original", "audit"}.issubset(run.get("results", {})):
        raise RuntimeError("The live protocol requires measured original and audit results")
    _overlap_count(run["results"]["audit"])
    decision = outcome.get("decision", {})
    ids = decision.get("evidence_ids")
    if not isinstance(ids, list) or not ids:
        raise RuntimeError("The live verdict must cite recorded evidence IDs")
    recorded = {eid for values in tools.evidence_history.values() for eid in values}
    if not set(ids).issubset(recorded):
        raise RuntimeError("The live verdict cites evidence IDs that were not produced by its tools")
    if not set(tools.evidence_history.get("audit", [])).intersection(ids):
        raise RuntimeError("The live verdict must cite the participant audit evidence")
    if decision.get("action") not in {"accept", "reject", "inconclusive"}:
        raise RuntimeError("The live run did not reach a valid final review action")


class ScientificTools:
    def __init__(self, run_id: str, case_id: str):
        self.run_id = run_id
        self.case_id = case_id
        self.calls = 0
        self.evidence: dict[str, str] = {}
        self.evidence_history: dict[str, list[str]] = {}

    def emit(self, role: str, type: str, title: str, detail: str = "", data: Any = None) -> str:
        return store.event(self.run_id, role, type, title, detail, data)

    async def dispatch(self, name: str, arguments: dict | None = None) -> dict:
        from falsify.science import audit_split, run_experiment

        _check_cancelled(self.run_id)
        if name not in {"run_original", "audit_split", "participant_holdout"}:
            self.emit("policy", "denied", "Tool request denied", "Only the registered scientific tests are allowed.", {"tool": name})
            raise ValueError("Tool is outside the experiment allowlist")
        if arguments and any(k not in {"seed"} for k in arguments):
            raise ValueError("The case and data paths are fixed by the trusted runner")
        if arguments and arguments.get("seed", 42) != 42:
            raise ValueError("The predeclared seed is fixed at 42")
        if self.calls >= 6:
            raise ValueError("Experiment tool-call budget exhausted")
        self.calls += 1
        current = store.read(self.run_id)
        current["usage"]["tool_calls"] = self.calls
        store.save(current)
        labels = {
            "run_original": ("Run the submitted evaluation", "Training and evaluating the fixed classifier on the submitted split."),
            "audit_split": ("Audit participant separation", "Comparing participant identifiers across the training and test partitions."),
            "participant_holdout": ("Evaluate on held-out participants", "Running the fixed model with the official participant-separated split."),
        }
        title, detail = labels[name]
        self.emit("operator", "tool_started", title, detail, {"tool": name})
        if name == "audit_split":
            outcome = await _run_blocking(audit_split, self.case_id, seed=42)
            key = "audit"
        else:
            evaluation = "original" if name == "run_original" else "participant_holdout"
            outcome = await _run_blocking(run_experiment, self.case_id, evaluation=evaluation, seed=42)
            key = "original" if name == "run_original" else "corrected"
        store.result(self.run_id, key, outcome)
        eid = self.emit("operator", "tool_result", f"{title}: evidence recorded", "This result was computed locally from the public UCI HAR dataset.", outcome)
        self.evidence[key] = eid
        self.evidence_history.setdefault(key, []).append(eid)
        # A local numerical worker finishes its current computation before
        # cooperative cancellation. Keep that evidence, then stop the workflow.
        _check_cancelled(self.run_id)
        if name == "run_original":
            # The ledger retains complete provenance. The agent must request
            # the audit to learn whether the split matches the claimed people.
            return {
                "claim": outcome["claim"], "metrics": outcome["metrics"],
                "model": outcome["model"], "dataset": outcome["dataset"],
                "n_train": outcome["split"]["n_train"],
                "n_test": outcome["split"]["n_test"],
                "evidence_id": eid,
                "evaluation_design": "Participant separation has not yet been audited. Request audit_split to inspect it.",
            }
        return {**outcome, "evidence_id": eid}


def make_verdict(original: dict, audit: dict, corrected: dict | None, evidence_ids: list[str]) -> dict:
    overlap = _overlap_count(audit)
    if overlap:
        return {
            "status": "unsupported",
            "summary": "The submitted evaluation does not establish performance on unseen people. Participants occur in both training and testing.",
            "evidence_ids": evidence_ids,
            "next_experiment": "Repeat the participant-held-out evaluation on an independent recording cohort before making a broader deployment claim.",
            "repair_status": "evaluated" if corrected else "pending",
            "repaired_claim": "The corrected score describes performance on the benchmark's held-out participants; it does not establish performance in all real-world settings." if corrected else None,
        }
    return {
        "status": "supported",
        "summary": "The participant-separation check passes. This evaluation addresses performance on the benchmark's held-out participants; its measured score is reported separately.",
        "evidence_ids": evidence_ids,
        "next_experiment": "Evaluate on a separately collected cohort to test transfer beyond this benchmark.",
        "repair_status": "not_needed",
        "repaired_claim": None,
    }


async def local_reference(run_id: str, case_id: str) -> None:
    """A transparent deterministic baseline, never represented as a live AI lab."""
    tools = ScientificTools(run_id, case_id)
    tools.emit("system", "mode", "Deterministic local reference", "A fixed procedure runs the real experiments. This mode makes no LLM calls and is not the Omnigent submission workflow.")
    original = await tools.dispatch("run_original")
    tools.emit("planner", "decision", "Choose the participant-overlap audit", "For a claim about new people, inspect the split before paying for a full rerun.", {
        "source": "fixed_rule",
        "alternatives": [
            {"test": "audit_split", "reason": "Direct, inexpensive check of whether the submitted split matches the claimed population."},
            {"test": "participant_holdout", "reason": "A more costly model evaluation that provides performance for the stated population."},
        ],
    })
    audit = await tools.dispatch("audit_split")
    overlap = _overlap_count(audit)
    corrected = None
    if overlap:
        tools.emit("reviewer", "revision", "The evidence changes the next test", f"The audit found {overlap} overlapping participants. The next action is a participant-held-out evaluation, with model settings unchanged.", {"source": "fixed_rule", "evidence_id": tools.evidence["audit"]})
        corrected = await tools.dispatch("participant_holdout")
    else:
        tools.emit("reviewer", "decision", "Retain the valid control", "No participants overlap. A repair is unnecessary; retain the result within the tested scope.", {"source": "fixed_rule", "evidence_id": tools.evidence["audit"]})
    _check_cancelled(run_id)
    verdict = make_verdict(original, audit, corrected, list(tools.evidence.values()))
    store.update(run_id, verdict=verdict)
    tools.emit("reviewer", "verdict", "Evidence review complete", verdict["summary"], verdict)


async def execute(run_id: str, case_id: str, mode: str) -> None:
    store.update(run_id, status="running", owner_pid=os.getpid(), error=None)
    try:
        _check_cancelled(run_id)
        if mode == "local":
            await local_reference(run_id, case_id)
        else:
            from falsify.omnigent_adapter import run_discovery
            from falsify.science import CLAIM
            tools = ScientificTools(run_id, case_id)
            outcome = await run_discovery(
                context={"case_id": "C-01", "claim": CLAIM, "seed": 42},
                dispatch_tool=tools.dispatch,
                emit_event=tools.emit,
                budget={"max_tool_calls": 6, "max_agent_decisions": 6, "timeout_seconds": 600},
            )
            _check_cancelled(run_id)
            current = store.read(run_id)
            _validate_live_outcome(outcome, tools, current)
            decision = outcome.get("decision", {})
            action = decision.get("action", "inconclusive")
            verdict = {
                "status": {"accept": "supported", "reject": "unsupported"}.get(action, "inconclusive"),
                "summary": decision.get("summary") or decision.get("reason") or "The reviewer did not establish a supported conclusion.",
                "reason": decision.get("reason"),
                "evidence_ids": decision["evidence_ids"],
                "next_experiment": decision.get("next_experiment", "Review the complete evidence before proceeding."),
                "source": "omnigent_reviewer",
            }
            verdict["repair_status"] = "evaluated" if "corrected" in current["results"] else "not_needed" if action == "accept" else "pending"
            reference = make_verdict(current["results"]["original"], current["results"]["audit"], current["results"].get("corrected"), list(tools.evidence.values()))
            validation = {
                "protocol_verified": True,
                "deterministic_reference_status": reference["status"],
                "agrees_with_split_rule": verdict["status"] == reference["status"],
                "note": "The reference checks the declared participant-separation requirement. A disagreement is retained as an observed AI-review outcome.",
            }
            usage = {**current["usage"], **outcome.get("usage", {})}
            store.update(run_id, verdict=verdict, usage=usage, validation=validation, orchestration={
                "session_id": outcome.get("session_id"),
                "mode": outcome.get("mode"),
                "trace": outcome.get("trace", []),
            })
            tools.emit("reviewer", "verdict", "Omnigent review complete", verdict["summary"], verdict)
            if not validation["agrees_with_split_rule"]:
                tools.emit("evaluator", "disagreement", "Review disagrees with the fixed split rule", "The AI verdict is preserved. The observed disagreement requires human review before using this conclusion.", validation)
        _check_cancelled(run_id)
        if not store.read(run_id).get("verdict"):
            raise RuntimeError("The workflow ended without a recorded verdict")
        store.update(run_id, status="completed", error=None, completed_at=store.now())
    except RunCancelled as exc:
        store.event(run_id, "system", "cancelled", "Run cancelled", str(exc))
        store.update(run_id, status="cancelled", verdict=None, error=str(exc), completed_at=store.now())
    except asyncio.CancelledError:
        message = "Execution stopped before completion. Previously recorded scientific evidence was retained."
        store.event(run_id, "system", "cancelled", "Run cancelled", message)
        store.update(run_id, status="cancelled", verdict=None, error=message, completed_at=store.now())
        raise
    except Exception as exc:
        # Do not fall back to a local run while retaining an Omnigent label.
        message = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, TimeoutError) or type(exc).__name__ in {"ReadTimeout", "ConnectTimeout"}:
            message = "The live runtime exceeded its wait limit. Completed evidence is preserved. You can review it or start a new run."
        store.event(run_id, "system", "error", "Run needs attention", message)
        store.update(run_id, status="failed", error=message, completed_at=store.now())
