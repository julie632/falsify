# Morning demo handover

The demo runs at [Falsify on DigitalOcean](https://falsify.134-122-55-169.sslip.io/?run=06f519544cd443a194a44965a1246164#results-heading). Website login details are in the private local file `output/deployment/access.txt`. Keep that file outside Git.

The source repository is [julie632/falsify](https://github.com/julie632/falsify). It must remain private until Julie explicitly requests a visibility change. The overnight automation does not publish it in the morning.

## Rehearse this route first

1. Open the hosted demo and sign in with the website credentials.
2. Select **Flawed evaluation** in the completed examples. Explain that this is a recorded result from a real Omnigent investigation, not a new agent run.
3. Show the original score, the 21 overlapping participants, and the corrected evaluation with zero overlap. Click a cited evidence ID and inspect its recorded data.
4. Open the **Valid control** example. Its original split passes, so the agents retain it without a redundant repair.
5. Download the evidence JSON to show that measurements, decisions, citations, and provenance are inspectable.
6. If judges want fresh computation, select **Deterministic local**, choose a case, and run it. This executes the real scientific tools on the server without model inference. Describe the fixed decision rule accurately.

Use the [90-second pitch](pitch.md). The crucial point: an impressive score can come from an evaluation that does not test its claim. Finding that mismatch does not prove the predictive claim false. The corrected result remains promising, within this benchmark's scope.

## Fresh AI runs need one account action

**The server's Codex account is not signed in.** Website access and model authentication are separate. The public demo therefore offers verified recorded AI investigations and fresh deterministic experiments. It must not be described as having passed a fresh server-side AI investigation.

When ready, ask this chat: “Start a fresh server Codex device login and help me finish it.” Complete the official login yourself, then let the agent verify model access and both full cases on Linux. Old device codes expire. No laptop credentials should be copied to the server.

The development computer already has an authorized Codex session and previously completed both real Omnigent cases. Local launch:

```sh
./scripts/start.sh
```

Open <http://127.0.0.1:8765>. New live runs consume account allowance and may take several minutes. The confirmed replay route avoids a presentation depending on provider latency.

## Recovery and checks

Read-only hosted checks, without exposing the password:

```sh
uv run python -m scripts.check_demo --access-file output/deployment/access.json
```

If the hosted site is unavailable, use the local app. On a new checkout, import the deliberately reviewed historical records before starting:

```sh
uv sync --frozen
uv run python -m scripts.import_demo
./scripts/start.sh
```

Deployment operations and the separate server login commands are in [deployment.md](deployment.md). Preserve the existing `claude-remote` service and Docker data volumes. The dataset and evidence persist across normal app restarts.

Overnight follow-ups are scheduled every 30 minutes until 08:00 America/New_York on October 4, 2026. This computer and the Codex app must remain available for those local follow-ups. The DigitalOcean site runs independently.

## Verification record

- Automated suite: 69 tests pass. Covered malformed audit evidence, evidence citations, disagreement retention, run concurrency, restart recovery, cleanup failures, thread draining, and repeated cancellation.
- Fresh local live regression: `e20e5568e66941918705c4373cb46a24`, completed in 175.4 seconds with three scientific calls and three specialist dispatches. Original evidence unsupported, correction executed with zero overlap, reviewer/reference agreement true. Reviewed unchanged record: [overnight-live.json](../demo/validation/overnight-live.json).
- Local live measurements: 98.0054% original accuracy, 96.1656% corrected accuracy, with 21 and zero shared participants respectively.
- Both historical hosted replay exports match the reviewed source records. Unauthenticated website, API, and documentation requests return 401.
- Final image deployment and browser rehearsal are being completed; their results will be added here.
