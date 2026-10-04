"""Verify private operator access or public, read-only judging access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = {
    "df7fdb571ed140e7851c17517e13422e": ROOT / "demo/validation/hosted-live-row_split.json",
    "ba03b3d5ebc646e79ae9c166025b9237": ROOT / "demo/validation/hosted-live-participant_holdout.json",
    "06f519544cd443a194a44965a1246164": ROOT / "demo/runs/06f519544cd443a194a44965a1246164/run.json",
    "83faf266dc944354b43b5b8ffc22bbd6": ROOT / "demo/runs/83faf266dc944354b43b5b8ffc22bbd6/run.json",
}


def check_public(client: httpx.Client, report: dict) -> None:
    for path in ("/", "/api/status", "/api/runs", "/api/cases", "/docs"):
        response = client.get(path)
        if response.status_code != 200 or response.headers.get("www-authenticate"):
            raise RuntimeError(f"Public judging route requires login or failed: {path}")
    status = client.get("/api/status").json()
    if status.get("public_demo") is not True or status.get("read_only") is not True:
        raise RuntimeError("Public read-only mode is not active; refusing mutation probes")
    if not status.get("recorded_evidence_available"):
        raise RuntimeError("No reviewed public evidence is available")
    if status.get("capabilities", {}).get("start_runs") is not False:
        raise RuntimeError("Public mode advertises experiment execution")
    for field in ("auth_ready", "auth_method", "codex_path", "active_run_id", "authentication"):
        if field in status:
            raise RuntimeError(f"Public status exposes operator detail: {field}")
    report["status"] = status
    listing = client.get("/api/runs").json()["runs"]
    if {run["id"] for run in listing} != set(REVIEWED):
        raise RuntimeError("Public listing does not match the four explicitly reviewed records")
    for run_id, source in REVIEWED.items():
        for suffix in ("", "/export"):
            response = client.get(f"/api/runs/{run_id}{suffix}")
            response.raise_for_status()
            if response.json() != json.loads(source.read_text()):
                raise RuntimeError(f"Public evidence differs from its reviewed source: {run_id}")
    for suffix in ("", "/export"):
        response = client.get(f"/api/runs/151b7c86147f4cf99bb6cf8e7dd189a2{suffix}")
        if response.status_code != 404:
            raise RuntimeError("An unreviewed run is publicly accessible")
    # Valid inputs prove the public execution gate, not just request validation.
    response = client.post("/api/runs", json={"case_id": "participant_holdout", "mode": "local"})
    if response.status_code not in (403, 405):
        raise RuntimeError("Public site did not block experiment creation")
    response = client.post("/api/runs/df7fdb571ed140e7851c17517e13422e/cancel")
    if response.status_code not in (403, 405):
        raise RuntimeError("Public site did not block cancellation")
    for path in ("/.env", "/data/uci-har.zip", "/artifacts/runs", "/output/deployment/access.json"):
        if client.get(path).status_code != 404:
            raise RuntimeError(f"A private workspace path is exposed: {path}")
    report["checks"] += [
        "Judging routes open without authentication",
        "Exactly four reviewed Omnigent replays and unchanged exports are public",
        "Unreviewed records and private workspace paths are unavailable",
        "New experiments and cancellation are blocked",
        "Public status omits operator account and runtime details",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-file", type=Path,
                        help="Private JSON file containing url, username and password")
    parser.add_argument("--url", help="HTTPS public demo URL")
    parser.add_argument("--public", action="store_true", help="Check no-login reviewed replay mode")
    args = parser.parse_args()
    if args.public:
        if not args.url or args.access_file:
            parser.error("Public checks require --url and no credentials")
        access = {}
        base = args.url.rstrip("/")
    else:
        if not args.access_file or args.url:
            parser.error("Private checks require --access-file")
        access = json.loads(args.access_file.read_text())
        base = access["url"].rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("Use HTTPS for website credentials")
    report: dict = {"url": base, "checks": []}
    with httpx.Client(base_url=base, timeout=20) as client:
        if args.public:
            check_public(client, report)
            print(json.dumps(report, indent=2))
            return
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
