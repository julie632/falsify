import asyncio

import pytest

from falsify import store
from falsify.workflow import ScientificTools, execute


@pytest.fixture
def run_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RUNS_DIR", tmp_path / "runs")
    return store


def test_tool_boundary_rejects_arbitrary_tools_and_seed_changes(run_store):
    run = store.create("row_split", "local")
    tools = ScientificTools(run["id"], "row_split")
    with pytest.raises(ValueError, match="allowlist"):
        asyncio.run(tools.dispatch("read_answer_key"))
    with pytest.raises(ValueError, match="fixed"):
        asyncio.run(tools.dispatch("run_original", {"case_id": "participant_holdout"}))
    with pytest.raises(ValueError, match="seed"):
        asyncio.run(tools.dispatch("run_original", {"seed": 123}))
    assert tools.calls == 0
    assert store.read(run["id"])["events"][0]["type"] == "denied"


def test_no_silent_local_fallback_on_live_integration_failure(run_store, monkeypatch):
    import sys
    import types

    async def unavailable(**kwargs):
        raise RuntimeError("integration unavailable")

    monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=unavailable))
    run = store.create("row_split", "omnigent")
    asyncio.run(execute(run["id"], "row_split", "omnigent"))
    result = store.read(run["id"])
    assert result["status"] == "failed"
    assert result["mode"] == "omnigent"
    assert result["results"] == {}
    assert "integration unavailable" in result["error"]


def test_store_rejects_path_traversal_and_preserves_event_sequence(run_store):
    with pytest.raises(ValueError):
        store.read("../outside")
    run = store.create("row_split", "local")
    assert store.event(run["id"], "planner", "decision", "First") == "E001"
    assert store.event(run["id"], "operator", "tool_result", "Second") == "E002"
    assert [e["id"] for e in store.read(run["id"])["events"]] == ["E001", "E002"]


def test_cancel_before_start_does_not_enter_live_runtime(run_store, monkeypatch):
    import sys
    import types

    async def forbidden(**kwargs):
        pytest.fail("A pre-cancelled run must not start inference")

    monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=forbidden))
    run = store.create("row_split", "omnigent")
    store.update(run["id"], cancel_requested=True)
    asyncio.run(execute(run["id"], "row_split", "omnigent"))
    result = store.read(run["id"])
    assert result["status"] == "cancelled"
    assert result["results"] == {}
    assert result["verdict"] is None


def test_task_cancellation_records_terminal_state_and_propagates(run_store, monkeypatch):
    import sys
    import types

    async def exercise():
        entered_runtime = asyncio.Event()

        async def blocked(**kwargs):
            entered_runtime.set()
            await asyncio.Event().wait()

        monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=blocked))
        run = store.create("row_split", "omnigent")
        task = asyncio.create_task(execute(run["id"], "row_split", "omnigent"))
        await asyncio.wait_for(entered_runtime.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        result = store.read(run["id"])
        assert result["status"] == "cancelled"
        assert result["completed_at"]
        assert result["verdict"] is None
        assert result["events"][-1]["type"] == "cancelled"

    asyncio.run(exercise())


def test_cancelled_live_response_is_not_published_as_a_verdict(run_store, monkeypatch):
    import sys
    import types

    run = store.create("row_split", "omnigent")

    async def completed_after_cancel(**kwargs):
        store.update(run["id"], cancel_requested=True)
        return {"mode": "omnigent", "session_id": "fixture", "decision": {"action": "accept"}}

    monkeypatch.setitem(sys.modules, "falsify.omnigent_adapter", types.SimpleNamespace(run_discovery=completed_after_cancel))
    asyncio.run(execute(run["id"], "row_split", "omnigent"))
    result = store.read(run["id"])
    assert result["status"] == "cancelled"
    assert result["verdict"] is None
    assert not any(event["type"] == "verdict" for event in result["events"])
