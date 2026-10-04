"""Loopback-only web API for the Falsify experiment."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from falsify import __version__, store
from falsify.workflow import execute

ROOT = Path(__file__).resolve().parents[1]
tasks: dict[str, asyncio.Task] = {}
authentication = {"auth_ready": False, "auth_method": "not_checked"}


def check_auth() -> dict:
    bundled = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")
    binary = shutil.which("codex") or (str(bundled) if bundled.exists() else None)
    if not binary:
        return {"auth_ready": False, "auth_method": "codex_not_installed"}
    try:
        result = subprocess.run([binary, "login", "status"], capture_output=True, text=True, timeout=12)
        ready = result.returncode == 0 and "logged in" in (result.stdout + result.stderr).lower()
        return {"auth_ready": ready, "auth_method": "existing_codex_sign_in" if ready else "sign_in_required"}
    except (OSError, subprocess.TimeoutExpired):
        return {"auth_ready": False, "auth_method": "status_unavailable"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    authentication.update(await asyncio.to_thread(check_auth))
    dedicated = os.environ.get("FALSIFY_DEDICATED_SERVER") == "1"
    for run in store.all_runs():
        if run["status"] in {"queued", "running"}:
            owner = run.get("owner_pid")
            try:
                if owner and not dedicated:
                    os.kill(owner, 0)
                    continue
            except (ProcessLookupError, PermissionError):
                pass
            message = "The dedicated server restarted before this experiment completed." if dedicated else "The process running this experiment exited before completion."
            store.update(run["id"], status="failed", error=message, completed_at=store.now())
    yield
    pending = list(tasks.values())
    for task in pending:
        if not task.done() and not task.cancelling():
            task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


app = FastAPI(title="Falsify Lab", version=__version__, lifespan=lifespan)


class StartRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: Literal["row_split", "participant_holdout"]
    mode: Literal["local", "omnigent"] = "local"


@app.get("/api/status")
async def status():
    active = next((run_id for run_id, task in tasks.items() if not task.done()), None)
    try:
        from falsify.omnigent_adapter import runtime_status
        integration = runtime_status()
    except (ImportError, AttributeError):
        integration = {"omnigent_available": False, "integration_status": "being_configured"}
    return {
        "dataset_ready": (ROOT / "data" / "uci-har-manifest.json").exists(),
        "active_run_id": active,
        "omnigent_installed": importlib.util.find_spec("omnigent") is not None,
        **authentication,
        **integration,
        "omnigent_version": integration.get("version"),
        "version": __version__,
    }


@app.get("/api/cases")
def cases():
    from falsify.science import list_cases
    return {"cases": list_cases()}


@app.get("/api/runs")
def runs():
    return {"runs": store.all_runs()[:30]}


@app.post("/api/runs", status_code=202)
async def start_run(body: StartRun):
    if any(not task.done() for task in tasks.values()):
        raise HTTPException(409, "An experiment is already running. Wait for it to finish before starting another.")
    if body.mode == "omnigent":
        current = await status()
        if not current.get("omnigent_available") or not current.get("auth_ready"):
            raise HTTPException(503, "Omnigent or model authentication is not ready. The deterministic local reference remains available.")
    run = store.create(body.case_id, body.mode)
    tasks[run["id"]] = asyncio.create_task(execute(run["id"], body.case_id, body.mode))
    return {"run_id": run["id"]}


def get_run(run_id: str):
    try:
        return store.read(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Run not found")


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    return get_run(run_id)


@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str):
    run = get_run(run_id)
    return Response(
        json.dumps(run, indent=2, allow_nan=False), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="falsify-{run_id[:8]}.json"'},
    )


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = get_run(run_id)
    if run["status"] not in {"queued", "running"}:
        raise HTTPException(409, "This run has already finished")
    store.update(run_id, cancel_requested=True)
    # Live inference can be waiting without another tool call to observe the
    # flag. Its adapter drains accepted computations during task cancellation.
    # Queued runs must enter execute first so they record a terminal state.
    task = tasks.get(run_id)
    if run["mode"] == "omnigent" and run["status"] == "running" and task and not task.done() and not task.cancelling():
        task.cancel()
    return {"cancel_requested": True}


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
