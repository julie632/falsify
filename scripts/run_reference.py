"""Run both deterministic reference cases and retain their evidence records."""
import asyncio
import json

from falsify import store
from falsify.workflow import execute


async def main():
    for case_id in ("row_split", "participant_holdout"):
        run = store.create(case_id, "local")
        await execute(run["id"], case_id, "local")
        result = store.read(run["id"])
        print(json.dumps({"id": result["id"], "case_id": case_id, "status": result["status"], "verdict": result["verdict"], "error": result["error"]}, indent=2))
        if result["status"] != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
