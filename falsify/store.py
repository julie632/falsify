"""Append-only event records with atomic snapshots for the local demo."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "artifacts" / "runs"
_lock = threading.RLock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(run_id: str) -> Path:
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("Invalid run identifier")
    return RUNS_DIR / run_id / "run.json"


def save(run: dict[str, Any]) -> None:
    with _lock:
        path = _path(run["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(run, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)


def read(run_id: str) -> dict[str, Any]:
    with _lock:
        return json.loads(_path(run_id).read_text(encoding="utf-8"))


def create(case_id: str, mode: str) -> dict[str, Any]:
    run = {
        "id": uuid.uuid4().hex,
        "case_id": case_id,
        "mode": mode,
        "status": "queued",
        "started_at": now(),
        "completed_at": None,
        "events": [],
        "results": {},
        "verdict": None,
        "error": None,
        "cancel_requested": False,
        "budget": {"max_tool_calls": 6, "max_agent_decisions": 6, "seed": 42},
        "usage": {"tool_calls": 0, "agent_decisions": 0, "cost_usd": None},
        "limitations": [
            "A controlled feasibility demonstration, not a population estimate of reviewer reliability.",
            "Invalid evaluation evidence does not prove that the underlying predictive claim is false.",
            "Reported metrics describe the specific recorded dataset, model, and split.",
        ],
    }
    save(run)
    return run


def update(run_id: str, **fields: Any) -> dict[str, Any]:
    with _lock:
        run = read(run_id)
        run.update(fields)
        save(run)
        return run


def event(run_id: str, role: str, type: str, title: str, detail: str = "", data: Any = None) -> str:
    with _lock:
        run = read(run_id)
        event_id = f"E{len(run['events']) + 1:03d}"
        run["events"].append({
            "id": event_id, "timestamp": now(), "role": role,
            "type": type, "title": title, "detail": detail, "data": data or {},
        })
        save(run)
        return event_id


def result(run_id: str, name: str, value: dict[str, Any]) -> None:
    with _lock:
        run = read(run_id)
        run["results"][name] = value
        save(run)


def all_runs() -> list[dict[str, Any]]:
    with _lock:
        if not RUNS_DIR.exists():
            return []
        records = []
        for path in RUNS_DIR.glob("*/run.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda r: r["started_at"], reverse=True)
