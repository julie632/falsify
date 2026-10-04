"""Real Omnigent runtime orchestration using the existing Codex login.

Only the lifecycle bootstrap uses pinned Omnigent private APIs. Inference,
subagent dispatch, client tool execution and streaming use its actual runtime
and official client SDK. There is no synthetic agent or fallback verdict.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import os
import shutil
import secrets
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

PROJECT = Path(__file__).resolve().parents[1]
AGENT_PATH = PROJECT / "agents" / "falsify.yaml"
APP_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")
_runtime_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def _bridge_request(name: str, seed: int = 42) -> dict:
    """The Omnigent runner calls only this capability-limited local bridge."""
    import httpx
    endpoint = os.environ.get("FALSIFY_BRIDGE_URL")
    if not endpoint:
        raise RuntimeError("No active Falsify experiment bridge")
    response = httpx.post(endpoint, json={"name": name, "arguments": {"seed": seed}}, timeout=125)
    response.raise_for_status()
    return response.json()


def scientific_run_original(seed: int = 42) -> dict:
    """Execute the fixed original evaluation and return actual evidence."""
    return _bridge_request("run_original", seed)


def scientific_audit_split(seed: int = 42) -> dict:
    """Audit participant separation in the fixed submitted evaluation."""
    return _bridge_request("audit_split", seed)


def scientific_participant_holdout(seed: int = 42) -> dict:
    """Run the fixed participant-held-out evaluation and return actual evidence."""
    return _bridge_request("participant_holdout", seed)


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test: str
    reason: str
    estimated_cost: str


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["audit_split", "participant_holdout", "accept", "reject", "inconclusive"]
    reason: str = Field(min_length=1)
    alternatives: list[Alternative] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    next_experiment: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


def parse_decision(text: str) -> dict[str, Any]:
    """Validate JSON without silently inventing a decision on malformed output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        candidates = []
        for index, char in enumerate(stripped):
            if char == "{":
                try:
                    candidate, _ = decoder.raw_decode(stripped[index:])
                    if isinstance(candidate, dict) and "action" in candidate:
                        candidates.append(candidate)
                except json.JSONDecodeError:
                    pass
        if not candidates:
            raise ValueError("Omnigent returned no valid structured decision")
        payload = candidates[-1]
    return Decision.model_validate(payload).model_dump()


def validate_protocol(trace: list[dict], outputs: list[dict], decision: dict) -> set[str]:
    """Require completed real specialists and actual original/audit evidence."""
    completed = {
        event.get("child", {}).get("tool")
        for event in trace
        if event.get("type") == "session.child_session.updated"
        and event.get("child", {}).get("current_task_status") == "completed"
        and not event.get("child", {}).get("busy")
    }
    if not {"planner", "reviewer"}.issubset(completed):
        raise RuntimeError("Omnigent did not complete both required specialist delegations")
    if not {"run_original", "audit_split"}.issubset({item["tool"] for item in outputs}):
        raise RuntimeError("Omnigent did not execute the required original evaluation and split audit")
    recorded = {item["result"].get("evidence_id") for item in outputs}
    if not decision.get("evidence_ids") or not set(decision["evidence_ids"]).issubset(recorded):
        raise RuntimeError("Omnigent's final evidence citations are missing or unrecorded")
    return completed


def readiness() -> dict[str, Any]:
    """Report installed components without reading or exposing credentials."""
    requested = os.environ.get("OMNIGENT_CODEX_PATH")
    binary = shutil.which(requested or "codex")
    if not requested and not binary and APP_CODEX.is_file() and os.access(APP_CODEX, os.X_OK):
        binary = str(APP_CODEX)
    try:
        installed = version("omnigent")
    except Exception:
        installed = None
    return {"installed": installed is not None, "version": installed,
            "codex_path": binary, "available": installed == "0.16.0" and bool(binary),
            "authentication": "Existing Codex CLI login; checked when inference runs"}


def runtime_status() -> dict[str, Any]:
    status = readiness()
    return {**status, "omnigent_available": status["available"],
            "integration_status": "ready" if status["available"] else "unavailable"}


async def _notify(callback: Callable | None, role: str, kind: str,
                  title: str, detail: str, data: dict) -> None:
    if callback is not None:
        value = callback(role, kind, title, detail, data)
        if inspect.isawaitable(value):
            await value


def _event_dict(event: Any) -> dict:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json", exclude_none=True)
    return {"type": type(event).__name__, "detail": str(event)}


def _final_text(event: dict) -> str | None:
    if event.get("type") == "response.output_item.done":
        item = event.get("item", {})
        if item.get("type") == "message" and item.get("role") == "assistant":
            texts = [c.get("text", "") for c in item.get("content", [])
                     if isinstance(c, dict) and c.get("type") in ("output_text", "text")]
            return "".join(texts) or None
    if event.get("type") == "response.completed":
        output = event.get("response", {}).get("output", [])
        texts = [c.get("text", "") for item in output if isinstance(item, dict)
                 and item.get("type") == "message" for c in item.get("content", [])
                 if isinstance(c, dict) and c.get("type") in ("output_text", "text")]
        return "".join(texts) or None
    return None


def _validated_limits(budget: dict[str, Any] | None) -> dict[str, Any]:
    limits = {"max_tool_calls": 3, "max_agent_decisions": 6,
              "timeout_seconds": 300, "tool_timeout_seconds": 120, **(budget or {})}
    for name in ("max_tool_calls", "max_agent_decisions"):
        value = limits[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
        limits[name] = min(value, 6)
    for name, maximum in (("timeout_seconds", 600), ("tool_timeout_seconds", 120)):
        value = limits[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        limits[name] = min(float(value), maximum)
    return limits


async def _start_server_safely(start: Callable, stop: Callable, port: int) -> Any:
    """Retain the subprocess handle if cancellation arrives during Popen setup."""
    task = asyncio.create_task(asyncio.to_thread(start, AGENT_PATH, port, ephemeral=True))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Cancelling to_thread cannot stop its thread. Recover its handle and
        # stop both processes before releasing the temporary environment.
        # Repeated cancel requests must not discard either thread's handle.
        async def drain(pending: asyncio.Task) -> Any:
            while True:
                try:
                    return await asyncio.shield(pending)
                except asyncio.CancelledError:
                    if pending.cancelled():
                        raise
        try:
            server = await drain(task)
            await drain(asyncio.create_task(asyncio.to_thread(stop, server)))
        except Exception:
            logger.exception("Omnigent startup cleanup failed")
        raise


async def run_discovery(
    context: dict[str, Any],
    dispatch_tool: Callable[[str, dict], Awaitable[dict]],
    emit_event: Callable | None = None,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one case with actual Omnigent planner, operator and reviewer agents.

    ``context`` must include case_id and claim. Tool callbacks may be sync or
    async. The deadline covers queueing, startup and inference; process cleanup
    may add a short grace period. All scientific evidence must be computed.
    Existing subscription inference consumes the signed-in account's allowance.
    """
    if not context.get("case_id"):
        raise ValueError("context.case_id is required")
    limits = _validated_limits(budget)
    async with asyncio.timeout(limits["timeout_seconds"]):
        return await _run_discovery(context, dispatch_tool, emit_event, limits)


async def _run_discovery(context: dict, dispatch_tool: Callable,
                         emit_event: Callable | None, limits: dict) -> dict:
    status = readiness()
    if not status["available"]:
        raise RuntimeError("Install omnigent==0.16.0 and sign in with the official Codex CLI")

    # Omnigent's bootstrap reads environment at subprocess creation. A lock
    # makes this temporary configuration safe across concurrent dashboard runs.
    async with _runtime_lock:
        from omnigent.chat import (_bundle_agent, _find_free_port, _server_headers,
                                   _start_local_server, _stop_local_server, _wait_for_server)
        from omnigent_client import OmnigentClient, SessionsChat

        trace: list[dict] = []
        outputs: list[dict] = []
        dispatch_ids: set[str] = set()
        usage: dict[str, Any] = {"billing": "existing_codex_subscription", "cost_usd": None,
                                 "token_scope": "Provider report for operator; may exclude child or background usage"}
        started = time.monotonic()
        attempted_calls = 0
        async def callback(info: Any) -> str:
            nonlocal attempted_calls
            name, args = info.name, dict(info.arguments)
            if name not in {"audit_split", "run_original", "participant_holdout"}:
                raise ValueError(f"Tool {name!r} is not allowlisted")
            if set(args) - {"seed"} or args.get("seed", 42) != 42:
                raise ValueError("The scientific case and seed are fixed")
            if attempted_calls >= limits["max_tool_calls"]:
                raise RuntimeError("Scientific tool-call budget exhausted")
            attempted_calls += 1
            call_id = f"bridge-{attempted_calls}"
            await _notify(emit_event, "operator", "tool_started", name,
                          "Omnigent selected and requested a real local computation.", args)
            async with asyncio.timeout(limits["tool_timeout_seconds"]):
                if inspect.iscoroutinefunction(dispatch_tool):
                    result = await dispatch_tool(name, args)
                else:
                    from falsify.workflow import _run_blocking
                    value = await _run_blocking(dispatch_tool, name, args)
                    result = await value if inspect.isawaitable(value) else value
            result = {**result, "verification_budget": {
                "remaining_scientific_calls": limits["max_tool_calls"] - attempted_calls,
                "max_scientific_calls": limits["max_tool_calls"],
                "used_scientific_calls": attempted_calls,
            }}
            output = {"tool": name, "arguments": args, "result": result,
                      "call_id": call_id}
            outputs.append(output)
            trace.append({"type": "falsify.tool_result", **output})
            await _notify(emit_event, "operator", "tool_completed", name,
                          "The computation returned actual evidence.", output)
            return json.dumps(result)

        nonce = secrets.token_urlsafe(32)
        bridge_tasks: set[asyncio.Task] = set()
        async def handle_bridge(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            from types import SimpleNamespace
            try:
                try:
                    raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
                    lines = raw.decode("ascii").split("\r\n")
                    if lines[0] != f"POST /{nonce} HTTP/1.1":
                        raise ValueError("Invalid experiment bridge capability")
                    headers = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
                    count = int(next((v for k,v in headers.items() if k.lower() == "content-length"), "0"))
                    if not 0 < count <= 2048:
                        raise ValueError("Invalid experiment bridge request size")
                    payload = json.loads(await asyncio.wait_for(reader.readexactly(count), timeout=5))
                    body = await callback(SimpleNamespace(name=payload["name"], arguments=payload["arguments"]))
                    status_line = "200 OK"
                except Exception as exc:
                    body = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
                    status_line = "400 Bad Request"
                data = body.encode()
                writer.write(f"HTTP/1.1 {status_line}\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n".encode()+data)
                await writer.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                # The scientific coroutine drains its fixed CPU work before
                # propagating cancellation, without writing late evidence.
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):
                    pass

        def accept_bridge(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            task = asyncio.create_task(handle_bridge(reader, writer))
            bridge_tasks.add(task)
            task.add_done_callback(bridge_tasks.discard)

        bridge = await asyncio.start_server(accept_bridge, "127.0.0.1", 0, limit=8192)
        bridge_port = bridge.sockets[0].getsockname()[1]
        configured = {
            "OMNIGENT_CODEX_PATH": status["codex_path"],
            "FALSIFY_BRIDGE_URL": f"http://127.0.0.1:{bridge_port}/{nonce}",
            "HARNESS_CODEX_DISABLE_NATIVE_TOOLS": "1",
            "HARNESS_CODEX_ENABLE_WEB_SEARCH": "0",
            "HARNESS_CODEX_MINIMAL_CONFIG": "1",
            "OMNIGENT_NO_UPDATE_CHECK": "1",
        }
        previous = {key: os.environ.get(key) for key in configured}
        server = None
        chat = None
        session_id = None
        try:
            os.environ.update(configured)
            port = _find_free_port()
            await _notify(emit_event, "operator", "runtime", "Starting Omnigent",
                          "Launching a local Omnigent server and Codex harness.", {})
            server = await _start_server_safely(_start_local_server, _stop_local_server, port)
            await asyncio.to_thread(_wait_for_server, port, server)
            base_url = f"http://127.0.0.1:{port}"
            headers = {**_server_headers(runner_id=server.runner_id),
                       "x-omnigent-background-session-titles": "off"}
            async with OmnigentClient(base_url=base_url, headers=headers, timeout=120) as client:
                created = await client.sessions.create(_bundle_agent(AGENT_PATH),
                                                       filename="falsify.tar.gz", workspace=str(PROJECT),
                                                       reasoning_effort="low")
                bound = await client.sessions.bind_runner(created.id, runner_id=server.runner_id)
                session_id = bound.id

                session_files = client.files.for_session(bound.id)
                chat = SessionsChat(namespace=client.sessions, session=bound,
                                    files_uploader=session_files.upload, files_getter=session_files.get)
                prompt = json.dumps({"experiment": context, "budget": limits,
                                     "instruction": "Run the bounded verification protocol. Delegate to both declared specialists."})
                final = None
                async with asyncio.timeout(limits["timeout_seconds"]):
                    async for item in chat.send(prompt):
                        event = _event_dict(item)
                        event_type = event.get("type", "unknown")
                        event_item = event.get("item", {})
                        if event_item.get("type") == "function_call" and event_item.get("name") == "sys_session_send":
                            call_id = event_item.get("call_id")
                            if call_id:
                                dispatch_ids.add(call_id)
                                if len(dispatch_ids) > int(limits.get("max_agent_decisions", 6)):
                                    raise RuntimeError("Specialist delegation budget exhausted")
                        # Preserve externally observable events, never hidden reasoning.
                        if "reasoning" not in event_type and not event_type.endswith(".delta") and "heartbeat" not in event_type:
                            trace.append(event)
                            if "tool" in event_type or "output_item" in event_type or "subagent" in event_type:
                                await _notify(emit_event, "operator", "omnigent_event", "Omnigent orchestration",
                                              event_type, event)
                            if event_type == "session.child_session.updated":
                                child = event.get("child", {})
                                role = child.get("tool", "specialist")
                                if child.get("current_task_status") == "completed":
                                    await _notify(emit_event, role, "delegation_completed", f"{role.title()} completed",
                                                  child.get("last_message_preview", "The specialist returned its assessment."), event)
                        text = _final_text(event)
                        if text:
                            final = text
                        if event_type == "response.completed":
                            reported = event.get("response", {}).get("usage")
                            if reported:
                                usage["reported"] = reported
                        if event_type in {"response.failed", "response.error", "response.cancelled"}:
                            raise RuntimeError(f"Omnigent run failed: {json.dumps(event)[:700]}")
                if not final:
                    raise RuntimeError("Omnigent completed without a final result")
                decision = parse_decision(final)
                if decision["action"] not in {"accept", "reject", "inconclusive"}:
                    raise RuntimeError("Omnigent did not reach a final verdict within the bounded run")
                validate_protocol(trace, outputs, decision)
                usage["agent_decisions"] = len(dispatch_ids)
                usage["tool_calls"] = len(outputs)
                await _notify(emit_event, "reviewer", "decision", "Evidence reviewed",
                              decision["summary"], decision)
                return {"decision": decision, "case_id": context["case_id"], "role": "reviewer",
                        "session_id": session_id, "mode": "omnigent", "trace": trace,
                        "usage": usage, "tool_outputs": outputs,
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                        "omnigent_version": status["version"]}
        except BaseException:
            if chat is not None:
                try:
                    await asyncio.wait_for(chat.cancel(), timeout=5)
                except Exception:
                    pass
            raise
        finally:
            original_error = sys.exc_info()[1]
            try:
                bridge.close()
                pending = list(bridge_tasks)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                await bridge.wait_closed()
            finally:
                try:
                    if server is not None:
                        try:
                            await asyncio.to_thread(_stop_local_server, server)
                        except Exception:
                            if original_error is None:
                                raise
                            logger.exception("Omnigent cleanup failed after a run error")
                finally:
                    for key, value in previous.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
