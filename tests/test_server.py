import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from falsify import server, store


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
