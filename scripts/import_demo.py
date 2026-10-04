"""Import two checked historical live recordings without running inference."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
EXPECTED_RUNS = {
    "06f519544cd443a194a44965a1246164": "row_split",
    "83faf266dc944354b43b5b8ffc22bbd6": "participant_holdout",
}


def load_replays() -> list[tuple[str, bytes]]:
    manifest = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("runs", [])
    if manifest.get("format_version") != 1 or len(entries) != len(EXPECTED_RUNS):
        raise ValueError("Unsupported replay manifest")
    if {entry.get("id") for entry in entries} != set(EXPECTED_RUNS):
        raise ValueError("Replay manifest does not contain the two reviewed run identities")
    replays = []
    for entry in entries:
        run_id = entry["id"]
        relative = f"runs/{run_id}/run.json"
        if entry.get("file") != relative or entry.get("case_id") != EXPECTED_RUNS[run_id]:
            raise ValueError(f"Unexpected replay identity or source path: {run_id}")
        payload = (DEMO / relative).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            raise ValueError(f"Replay checksum mismatch: {run_id}")
        run = json.loads(payload)
        if (
            run.get("id") != run_id
            or run.get("case_id") != EXPECTED_RUNS[run_id]
            or run.get("mode") != "omnigent"
            or run.get("status") != "completed"
            or not run.get("validation", {}).get("protocol_verified")
        ):
            raise ValueError(f"Replay is not the expected completed live investigation: {run_id}")
        replays.append((run_id, payload))
    return replays


def import_replays(runs_dir: Path) -> list[tuple[str, str]]:
    replays = load_replays()
    # Preflight both records before writing either. Existing historical evidence
    # is never replaced, even if it uses one of the expected identifiers.
    for run_id, payload in replays:
        destination = runs_dir / run_id / "run.json"
        if destination.exists() and destination.read_bytes() != payload:
            raise ValueError(f"Refusing to replace a different existing run: {destination}")
    outcomes = []
    for run_id, payload in replays:
        destination = runs_dir / run_id / "run.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("xb") as stream:
                stream.write(payload)
            action = "imported"
        except FileExistsError:
            if destination.read_bytes() != payload:
                raise ValueError(f"Refusing to replace a different existing run: {destination}")
            action = "already present, identical"
        outcomes.append((run_id, action))
    return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-dir", type=Path, default=ROOT / "artifacts" / "runs",
        help="Destination run directory (default: this project's artifacts/runs)",
    )
    args = parser.parse_args()
    try:
        outcomes = import_replays(args.runs_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Replay import stopped: {exc}\n")
    for run_id, action in outcomes:
        print(f"{run_id}: {action}")
    print("These are historical recordings. No new experiment or model inference was run.")


if __name__ == "__main__":
    main()
