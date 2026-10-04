import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from falsify import server, store


@pytest.fixture(autouse=True)
def private_mode_by_default(monkeypatch):
    monkeypatch.delenv("FALSIFY_PUBLIC_DEMO", raising=False)
    monkeypatch.delenv("FALSIFY_PUBLIC_RUN_IDS", raising=False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(server, "tasks", {})
    monkeypatch.setattr(server, "check_auth", lambda: {"auth_ready": False, "auth_method": "test"})
    with TestClient(server.app) as instance:
        yield instance


def test_live_requires_model_authentication_and_does_not_fallback(client):
    response = client.post("/api/runs", json={"case_id": "row_split", "mode": "omnigent"})
    assert response.status_code == 503
    assert store.all_runs() == []


def test_run_inputs_reject_arbitrary_cases_and_fields(client):
    for payload in ({"case_id": "arbitrary"}, {"case_id": "row_split", "seed": 3}, {"case_id": "row_split", "mode": "pretend"}):
        assert client.post("/api/runs", json=payload).status_code == 422
    assert client.get("/api/runs/not-a-run").status_code == 404


def test_export_retains_evidence_and_failure_state(client):
    run = store.create("row_split", "local")
    store.event(run["id"], "operator", "tool_result", "Measured", data={"accuracy": 0.4})
    store.update(run["id"], status="failed", error="Fixture failure")
    response = client.get(f'/api/runs/{run["id"]}/export')
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    exported = json.loads(response.content)
    assert exported["status"] == "failed"
    assert exported["events"][0]["data"]["accuracy"] == 0.4
    assert client.post(f'/api/runs/{run["id"]}/cancel').status_code == 409


def test_concurrent_run_is_rejected_without_duplicate_job(client, monkeypatch):
    class Pending:
        def done(self):
            return False

        def cancel(self):
            return None

        def cancelling(self):
            return 0

        def __await__(self):
            async def finish():
                return None
            return finish().__await__()

    monkeypatch.setattr(server, "tasks", {"running": Pending()})
    assert client.post("/api/runs", json={"case_id": "row_split", "mode": "local"}).status_code == 409
    assert store.all_runs() == []


@pytest.mark.parametrize("mode,state,should_interrupt", [
    ("omnigent", "running", True),
    ("omnigent", "queued", False),
    ("local", "running", False),
])
def test_cancel_interrupts_live_wait_but_keeps_queued_and_local_cleanup(mode, state, should_interrupt, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")
    run = store.create("row_split", mode)
    store.update(run["id"], status=state)

    class ActiveTask:
        interrupted = False
        cancel_calls = 0

        def done(self):
            return False

        def cancel(self):
            self.interrupted = True
            self.cancel_calls += 1

        def cancelling(self):
            return int(self.interrupted)

    task = ActiveTask()
    monkeypatch.setattr(server, "tasks", {run["id"]: task})
    assert asyncio.run(server.cancel_run(run["id"])) == {"cancel_requested": True}
    assert store.read(run["id"])["cancel_requested"]
    assert task.interrupted is should_interrupt
    asyncio.run(server.cancel_run(run["id"]))
    assert task.cancel_calls == int(should_interrupt)


def test_dedicated_restart_recovers_runs_even_when_container_reuses_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(server, "tasks", {})
    monkeypatch.setattr(server, "check_auth", lambda: {"auth_ready": False, "auth_method": "test"})
    monkeypatch.setenv("FALSIFY_DEDICATED_SERVER", "1")
    interrupted = store.create("row_split", "local")
    completed = store.create("participant_holdout", "local")
    store.update(interrupted["id"], status="running", owner_pid=os.getpid())
    store.update(completed["id"], status="completed", owner_pid=os.getpid())
    with TestClient(server.app):
        assert store.read(interrupted["id"])["status"] == "failed"
        assert "restarted" in store.read(interrupted["id"])["error"]
        assert store.read(completed["id"])["status"] == "completed"


def reviewed_run():
    """Copy actual curated evidence under its original identity for API tests."""
    path = server.ROOT / "demo" / "runs" / "06f519544cd443a194a44965a1246164" / "run.json"
    run = json.loads(path.read_text())
    store.save(run)
    return run


def test_public_exports_only_explicitly_reviewed_completed_omnigent_evidence(client, monkeypatch):
    reviewed = reviewed_run()
    private = store.create("row_split", "local")
    monkeypatch.setenv("FALSIFY_PUBLIC_DEMO", "1")
    monkeypatch.setenv("FALSIFY_PUBLIC_RUN_IDS", reviewed["id"])
    assert client.get("/api/runs").json() == {"runs": [reviewed]}
    assert client.get(f'/api/runs/{reviewed["id"]}').json() == reviewed
    exported = client.get(f'/api/runs/{reviewed["id"]}/export')
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.json() == reviewed
    for run_id in (private["id"], "f" * 32, "not-a-run"):
        assert client.get(f"/api/runs/{run_id}").status_code == 404
        assert client.get(f"/api/runs/{run_id}/export").status_code == 404


@pytest.mark.parametrize("allowlist", [None, "", " ", "../private", "06f519544cd443a194a44965a1246164,invalid", "06f519544cd443a194a44965a1246164,"])
def test_public_missing_or_malformed_allowlist_fails_closed(client, monkeypatch, allowlist):
    reviewed = reviewed_run()
    monkeypatch.setenv("FALSIFY_PUBLIC_DEMO", "1")
    if allowlist is not None:
        monkeypatch.setenv("FALSIFY_PUBLIC_RUN_IDS", allowlist)

    def forbidden_read(run_id):
        pytest.fail("A missing or malformed public allowlist must not read any stored record")

    monkeypatch.setattr(store, "read", forbidden_read)
    assert client.get("/api/runs").json() == {"runs": []}
    assert client.get(f'/api/runs/{reviewed["id"]}').status_code == 404
    assert client.get(f'/api/runs/{reviewed["id"]}/export').status_code == 404
    assert client.get("/api/status").json()["recorded_evidence_available"] is False


@pytest.mark.parametrize("changed", [
    {"status": "running"},
    {"status": "failed"},
    {"mode": "local"},
    {"validation": {}},
    {"validation": {"protocol_verified": False, "agrees_with_split_rule": True}},
    {"validation": {"protocol_verified": True, "agrees_with_split_rule": False}},
])
def test_public_allowlist_does_not_expose_incomplete_or_unverified_runs(client, monkeypatch, changed):
    reviewed = reviewed_run()
    store.update(reviewed["id"], **changed)
    monkeypatch.setenv("FALSIFY_PUBLIC_DEMO", "1")
    monkeypatch.setenv("FALSIFY_PUBLIC_RUN_IDS", reviewed["id"])
    assert client.get("/api/runs").json() == {"runs": []}
    assert client.get(f'/api/runs/{reviewed["id"]}').status_code == 404
    assert client.get(f'/api/runs/{reviewed["id"]}/export').status_code == 404


def test_public_mode_rejects_start_and_cancel_without_mutation(client, monkeypatch):
    reviewed = reviewed_run()
    private = store.create("row_split", "omnigent")
    store.update(private["id"], status="running")
    before = store.all_runs()
    monkeypatch.setenv("FALSIFY_PUBLIC_DEMO", "1")
    monkeypatch.setenv("FALSIFY_PUBLIC_RUN_IDS", reviewed["id"])

    async def forbidden_execute(*args):
        pytest.fail("Public viewers cannot execute experiments")

    monkeypatch.setattr(server, "execute", forbidden_execute)
    for mode in ("local", "omnigent"):
        assert client.post("/api/runs", json={"case_id": "row_split", "mode": mode}).status_code == 403
    for run_id in (reviewed["id"], private["id"], "f" * 32):
        assert client.post(f"/api/runs/{run_id}/cancel").status_code == 403
    assert store.all_runs() == before
    assert server.tasks == {}


def test_public_startup_and_status_avoid_private_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(server, "tasks", {})
    private = store.create("row_split", "omnigent")
    store.update(private["id"], status="running", owner_pid=os.getpid())
    monkeypatch.setenv("FALSIFY_PUBLIC_DEMO", "1")
    monkeypatch.setenv("FALSIFY_DEDICATED_SERVER", "1")

    def forbidden_probe():
        pytest.fail("Public evidence viewing must not probe accounts or enumerate private runs")

    monkeypatch.setattr(server, "check_auth", forbidden_probe)
    monkeypatch.setattr(store, "all_runs", forbidden_probe)
    with TestClient(server.app) as public_client:
        response = public_client.get("/api/status")
        assert response.status_code == 200
        assert response.json() == {
            "public_demo": True,
            "read_only": True,
            "presentation_mode": "recorded_replay",
            "recorded_evidence_available": False,
            "capabilities": {"view_replays": True, "export_evidence": True, "start_runs": False, "cancel_runs": False},
            "version": server.__version__,
        }
        assert public_client.get("/api/runs").json() == {"runs": []}
    assert store.read(private["id"])["status"] == "running"


def test_default_mode_can_still_start_local_experiments(client, monkeypatch):
    executed = []

    async def finish(run_id, case_id, mode):
        executed.append((run_id, case_id, mode))
        store.update(run_id, status="completed")

    monkeypatch.setattr(server, "execute", finish)
    status = client.get("/api/status").json()
    assert status["public_demo"] is False
    assert status["capabilities"]["start_runs"] is True
    response = client.post("/api/runs", json={"case_id": "row_split", "mode": "local"})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}").status_code == 200
    assert executed == [(run_id, "row_split", "local")]
