"""Read-only health and evidence checks for the authenticated hosted demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-file", type=Path, required=True,
                        help="Private JSON file containing url, username and password")
    args = parser.parse_args()
    access = json.loads(args.access_file.read_text())
    base = access["url"].rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("Use HTTPS for website credentials")
    report: dict = {"url": base, "checks": []}
    with httpx.Client(base_url=base, timeout=20) as client:
        for path in ("/", "/api/status", "/api/runs", "/docs"):
            response = client.get(path)
            if response.status_code != 401:
                raise RuntimeError(f"Authentication was not required for {path}")
        report["checks"].append("Website and API require authentication")
        client.auth = (access["username"], access["password"])
        response = client.get("/api/status")
        response.raise_for_status()
        status = response.json()
        report["status"] = {key: status.get(key) for key in
                            ("version", "dataset_ready", "auth_ready", "active_run_id")}
        if not status["dataset_ready"]:
            raise RuntimeError("Dataset cache is unavailable")
        for run_id in ("06f519544cd443a194a44965a1246164", "83faf266dc944354b43b5b8ffc22bbd6"):
            response = client.get(f"/api/runs/{run_id}/export")
            response.raise_for_status()
            run = response.json()
            if run["id"] != run_id or run["status"] != "completed" or run["mode"] != "omnigent":
                raise RuntimeError("A verified historical replay is unavailable")
            source = Path(__file__).resolve().parents[1] / "demo" / "runs" / run_id / "run.json"
            if run != json.loads(source.read_text()):
                raise RuntimeError("Hosted replay differs from the reviewed source record")
        report["checks"].append("Both completed Omnigent replay exports are available")
        response = client.get("/")
        response.raise_for_status()
        if "Falsify" not in response.text:
            raise RuntimeError("Unexpected demo page")
        report["checks"].append("Demo page responds")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
