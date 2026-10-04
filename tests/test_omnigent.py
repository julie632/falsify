"""Contract checks for the live runtime adapter. No paid inference in tests."""
import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from falsify.omnigent_adapter import AGENT_PATH, parse_decision, validate_protocol
from falsify import omnigent_adapter as adapter


def decision(**changes):
    return {"action": "reject", "reason": "The original split includes participant overlap.",
            "alternatives": [], "summary": "The evaluation does not establish the claim.",
            "next_experiment": "Evaluate a new recording cohort.",
            "evidence_ids": ["E1", "E2"], **changes}


def completed(role):
    return {"type": "session.child_session.updated",
            "child": {"tool": role, "busy": False, "current_task_status": "completed"}}


def test_structured_decision_rejects_unknown_action():
    import json
    with pytest.raises(ValidationError):
        parse_decision(json.dumps(decision(action="execute_shell")))


def test_no_fabricated_fallback_on_invalid_json():
    with pytest.raises(ValueError):
        parse_decision("I think it looks fine")


def test_protocol_requires_actual_computations_and_both_specialists():
    with pytest.raises(RuntimeError, match="both required"):
        validate_protocol([completed("planner")], [], decision())
    with pytest.raises(RuntimeError, match="original evaluation"):
        validate_protocol([completed("planner"), completed("reviewer")], [], decision())


def test_protocol_rejects_fabricated_evidence_ids():
    trace = [completed("planner"), completed("reviewer")]
    outputs = [{"tool": "run_original", "result": {"evidence_id": "E1"}},
               {"tool": "audit_split", "result": {"evidence_id": "E2"}}]
    with pytest.raises(RuntimeError, match="unrecorded"):
        validate_protocol(trace, outputs, decision(evidence_ids=["E999"]))
    assert validate_protocol(trace, outputs, decision()) == {"planner", "reviewer"}


def test_agent_spec_loads_real_specialists_and_bounded_science_tools():
    from omnigent.spec import load
    spec = load(AGENT_PATH)
    assert {s.name for s in spec.sub_agents} == {"planner", "reviewer"}
    assert {t.name for t in spec.local_tools} == {"run_original", "audit_split", "participant_holdout"}
    assert all(t.runtime.value == "server" for t in spec.local_tools)
    assert spec.os_env is None
    assert spec.spawn is False
    for specialist in spec.sub_agents:
        assert specialist.local_tools == []
        assert specialist.os_env is None
        assert specialist.spawn is False


@pytest.fixture
def runtime_stub(monkeypatch):
    """Only replace process/model I/O; exercise the real bridge and cleanup."""
    import omnigent.chat
    import omnigent_client

    state = SimpleNamespace(stopped=[], cancelled=False, script=None, create_hook=None,
                            original_wait=omnigent.chat._wait_for_server)
    server = SimpleNamespace(runner_id="test-runner", proc=SimpleNamespace(poll=lambda: None))
    monkeypatch.setattr(adapter, "_runtime_lock", asyncio.Lock())
    monkeypatch.setattr(adapter, "readiness", lambda: {
        "available": True, "codex_path": "/test/codex", "version": "0.16.0"})
    monkeypatch.setattr(omnigent.chat, "_start_local_server", lambda *a, **kw: server)
    monkeypatch.setattr(omnigent.chat, "_stop_local_server", state.stopped.append)
    monkeypatch.setattr(omnigent.chat, "_wait_for_server", lambda *a, **kw: None)
    monkeypatch.setattr(omnigent.chat, "_find_free_port", lambda: 12345)
    monkeypatch.setattr(omnigent.chat, "_server_headers", lambda **kw: {})
    monkeypatch.setattr(omnigent.chat, "_bundle_agent", lambda *a: b"unit-test")

    class Client:
        def __init__(self, **kwargs):
            self.sessions = self
            self.files = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def create(self, *args, **kwargs):
            if state.create_hook:
                await state.create_hook()
            return SimpleNamespace(id="test-session")

        async def bind_runner(self, *args, **kwargs):
            return SimpleNamespace(id="test-session")

        def for_session(self, *args):
            return SimpleNamespace(upload=None, get=None)

    class Chat:
        def __init__(self, **kwargs):
            pass

        async def send(self, prompt):
            async for event in state.script():
                yield SimpleNamespace(model_dump=lambda **kw: event)

        async def cancel(self):
            state.cancelled = True

    monkeypatch.setattr(omnigent_client, "OmnigentClient", Client)
    monkeypatch.setattr(omnigent_client, "SessionsChat", Chat)
    return state


@pytest.mark.parametrize("budget", [
    {"max_tool_calls": 0}, {"max_agent_decisions": -1},
    {"max_tool_calls": True}, {"timeout_seconds": float("nan")},
    {"timeout_seconds": float("inf")}, {"tool_timeout_seconds": 0},
])
def test_invalid_budgets_fail_before_starting_runtime(budget):
    with pytest.raises(ValueError):
        asyncio.run(adapter.run_discovery({"case_id": "C-01"}, lambda *args: {}, budget=budget))


def test_explicit_missing_codex_binary_is_not_reported_ready(monkeypatch):
    monkeypatch.setenv("OMNIGENT_CODEX_PATH", "/does-not-exist/falsify-codex")
    assert adapter.readiness()["available"] is False


def test_cold_start_obeys_deadline_and_restores_environment(runtime_stub, monkeypatch):
    import time
    monkeypatch.setenv("FALSIFY_BRIDGE_URL", "previous-value")
    async def run():
        entered = asyncio.Event()
        async def blocked_create():
            entered.set()
            await asyncio.Event().wait()
        runtime_stub.create_hook = blocked_create
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(adapter.run_discovery(
                {"case_id": "C-01"}, lambda *args: {},
                budget={"timeout_seconds": 0.03}), timeout=1)
        assert entered.is_set()
        assert time.monotonic() - start < 0.5
        assert len(runtime_stub.stopped) == 1
        assert os.environ["FALSIFY_BRIDGE_URL"] == "previous-value"
    asyncio.run(run())


@pytest.mark.parametrize("run_timeout,expected_timeout,reaches_sdk", [
    (600, 180, True),
    (30, 30, False),
])
def test_server_readiness_allows_slow_cold_start_within_run_budget(
        runtime_stub, monkeypatch, run_timeout, expected_timeout, reaches_sdk):
    """Exercise Omnigent's real polling loop with a 75-second simulated boot."""
    import omnigent.chat

    clock = SimpleNamespace(elapsed=0.0)
    recorded_timeouts = []
    def sleep(seconds):
        clock.elapsed += seconds
    def get_status(*args, **kwargs):
        return SimpleNamespace(status_code=200 if clock.elapsed >= 75 else 503,
                               json=lambda: {"online": True})
    def startup_failure(server):
        raise RuntimeError("server readiness deadline reached")
    def wait_for_server(port, server, timeout=45.0):
        recorded_timeouts.append(timeout)
        runtime_stub.original_wait(port, server, timeout=timeout)
    async def sdk_reached():
        raise RuntimeError("SDK setup reached")

    # Replace this module's clock, not Python's shared time module or the
    # event loop clock. This performs no wall-clock waiting or network I/O.
    monkeypatch.setattr(omnigent.chat, "time", SimpleNamespace(
        monotonic=lambda: clock.elapsed, sleep=sleep))
    monkeypatch.setattr(omnigent.chat, "_server_get", get_status)
    monkeypatch.setattr(omnigent.chat, "_raise_server_failed", startup_failure)
    monkeypatch.setattr(omnigent.chat, "_wait_for_server", wait_for_server)
    runtime_stub.create_hook = sdk_reached
    expected_error = "SDK setup reached" if reaches_sdk else "server readiness deadline reached"
    with pytest.raises(RuntimeError, match=expected_error):
        asyncio.run(adapter.run_discovery({"case_id": "C-01"}, lambda *args: {},
                                          budget={"timeout_seconds": run_timeout}))
    assert recorded_timeouts == [expected_timeout]
    assert (clock.elapsed >= 75) is reaches_sdk
    assert len(runtime_stub.stopped) == 1


@pytest.mark.parametrize("interrupt", ["deadline", "cancel"])
def test_active_readiness_poll_obeys_outer_deadline_and_cancellation(
        runtime_stub, monkeypatch, interrupt):
    import omnigent.chat
    import threading
    import time

    entered = threading.Event()
    stopped = threading.Event()
    def wait_for_server(*args, **kwargs):
        entered.set()
        assert stopped.wait(timeout=1)
    def stop_server(server):
        runtime_stub.stopped.append(server)
        stopped.set()
    monkeypatch.setattr(omnigent.chat, "_wait_for_server", wait_for_server)
    monkeypatch.setattr(omnigent.chat, "_stop_local_server", stop_server)
    async def run():
        started = time.monotonic()
        task = asyncio.create_task(adapter.run_discovery(
            {"case_id": "C-01"}, lambda *args: {},
            budget={"timeout_seconds": 0.03 if interrupt == "deadline" else 30}))
        assert await asyncio.to_thread(entered.wait, 1)
        if interrupt == "cancel":
            task.cancel()
        expected = asyncio.CancelledError if interrupt == "cancel" else TimeoutError
        with pytest.raises(expected):
            await asyncio.wait_for(task, timeout=1)
        assert time.monotonic() - started < 0.5
        assert stopped.is_set()
        assert len(runtime_stub.stopped) == 1
    asyncio.run(run())


def test_cancelled_subprocess_start_recovers_and_stops_handle():
    import threading
    async def run():
        started = threading.Event()
        release = threading.Event()
        handle = object()
        stopped = []
        def start(*args, **kwargs):
            started.set()
            release.wait(timeout=1)
            return handle
        task = asyncio.create_task(adapter._start_server_safely(start, stopped.append, 12345))
        await asyncio.to_thread(started.wait, 1)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped == [handle]
    asyncio.run(run())


def test_repeated_cancellation_cannot_orphan_starting_runtime():
    import threading
    async def run():
        started = threading.Event()
        release_start = threading.Event()
        stopping = threading.Event()
        release_stop = threading.Event()
        stopped = []
        handle = object()
        def start(*args, **kwargs):
            started.set()
            release_start.wait(timeout=2)
            return handle
        def stop(server):
            stopping.set()
            release_stop.wait(timeout=2)
            stopped.append(server)
        task = asyncio.create_task(adapter._start_server_safely(start, stop, 12345))
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release_start.set()
        assert await asyncio.to_thread(stopping.wait, 1)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release_stop.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped == [handle]
    asyncio.run(run())


def test_cleanup_failure_still_restores_environment(runtime_stub, monkeypatch):
    import omnigent.chat
    monkeypatch.setenv("FALSIFY_BRIDGE_URL", "previous-value")
    async def failing_create():
        raise RuntimeError("create failed")
    def failing_stop(server):
        raise OSError("stop failed")
    runtime_stub.create_hook = failing_create
    monkeypatch.setattr(omnigent.chat, "_stop_local_server", failing_stop)
    with pytest.raises(RuntimeError, match="create failed"):
        asyncio.run(adapter.run_discovery({"case_id": "C-01"}, lambda *args: {}))
    assert os.environ["FALSIFY_BRIDGE_URL"] == "previous-value"


def test_parallel_bridge_calls_have_unique_ids_and_share_budget(runtime_stub):
    import httpx
    seen = []
    async def dispatch(name, args):
        seen.append(name)
        await asyncio.sleep(0.01)
        return {"evidence_id": "E1" if name == "run_original" else "E2"}
    async def stream():
        yield completed("planner")
        async with httpx.AsyncClient() as client:
            responses = await asyncio.gather(*[
                client.post(os.environ["FALSIFY_BRIDGE_URL"], json={"name": name, "arguments": {"seed": 42}})
                for name in ("run_original", "audit_split", "participant_holdout")])
        assert sorted(response.status_code for response in responses) == [200, 200, 400]
        assert all(response.json()["verification_budget"]["remaining_scientific_calls"] == 0
                   for response in responses if response.status_code == 200)
        yield completed("reviewer")
        yield {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(decision())}]}]}}
    runtime_stub.script = stream
    outcome = asyncio.run(adapter.run_discovery(
        {"case_id": "C-01"}, dispatch, budget={"max_tool_calls": 2}))
    assert seen == ["run_original", "audit_split"]
    assert {item["call_id"] for item in outcome["tool_outputs"]} == {"bridge-1", "bridge-2"}
    assert outcome["usage"]["tool_calls"] == 2


def test_timed_out_tool_is_cancelled_without_late_evidence(runtime_stub):
    import httpx
    cancelled = []
    async def dispatch(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
    async def stream():
        async with httpx.AsyncClient() as client:
            response = await client.post(os.environ["FALSIFY_BRIDGE_URL"],
                                         json={"name": "run_original", "arguments": {}})
        assert response.status_code == 400
        assert "TimeoutError" in response.json()["error"]
        raise RuntimeError("test protocol ends")
        yield  # Make this a stream without generating model output.
    runtime_stub.script = stream
    with pytest.raises(RuntimeError, match="test protocol ends"):
        asyncio.run(adapter.run_discovery({"case_id": "C-01"}, dispatch,
                                          budget={"tool_timeout_seconds": 0.01}))
    assert cancelled == [True]
    assert runtime_stub.cancelled
    assert len(runtime_stub.stopped) == 1


def test_run_failure_cancels_an_accepted_bridge_request(runtime_stub):
    import httpx
    async def run():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        request = None
        async def dispatch(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async with httpx.AsyncClient() as client:
            async def stream():
                nonlocal request
                request = asyncio.create_task(client.post(os.environ["FALSIFY_BRIDGE_URL"],
                    json={"name": "run_original", "arguments": {}}))
                await started.wait()
                raise RuntimeError("stream failed")
                yield
            runtime_stub.script = stream
            with pytest.raises(RuntimeError, match="stream failed"):
                await adapter.run_discovery({"case_id": "C-01"}, dispatch)
            assert cancelled.is_set()
            await asyncio.gather(request, return_exceptions=True)
        assert len(runtime_stub.stopped) == 1
    asyncio.run(run())


def test_cancellation_drains_cpu_before_return_and_skips_late_write(runtime_stub):
    import httpx
    import threading
    from falsify.workflow import _run_blocking
    async def run():
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        late_writes = []
        request = None
        def compute():
            started.set()
            release.wait(timeout=2)
            finished.set()
            return {"evidence_id": "E1"}
        async def dispatch(*args):
            result = await _run_blocking(compute)
            late_writes.append(result)
            return result
        async with httpx.AsyncClient() as client:
            async def stream():
                nonlocal request
                request = asyncio.create_task(client.post(os.environ["FALSIFY_BRIDGE_URL"],
                    json={"name": "run_original", "arguments": {}}))
                await asyncio.Event().wait()
                yield
            runtime_stub.script = stream
            run_task = asyncio.create_task(adapter.run_discovery({"case_id": "C-01"}, dispatch))
            assert await asyncio.to_thread(started.wait, 1)
            run_task.cancel()
            await asyncio.sleep(0.02)
            assert not run_task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await run_task
            assert finished.is_set()
            assert late_writes == []
            await asyncio.gather(request, return_exceptions=True)
        assert len(runtime_stub.stopped) == 1
    asyncio.run(run())
