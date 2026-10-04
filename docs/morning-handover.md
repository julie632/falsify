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

Overnight follow-ups are scheduled every 30 minutes until 08:00 America/New_York on October 4, 2026. This computer and the Codex app must remain available for those local follow-ups. The DigitalOcean site runs independently. A temporary AC-powered keep-awake assertion is set to expire at the same morning deadline; closing the laptop lid or disconnecting power can still prevent local follow-ups.

## Verification record

- Automated suite: 69 tests pass. Covered malformed audit evidence, evidence citations, disagreement retention, run concurrency, restart recovery, cleanup failures, thread draining, and repeated cancellation.
- Fresh local live regression: `e20e5568e66941918705c4373cb46a24`, completed in 175.4 seconds with three scientific calls and three specialist dispatches. Original evidence unsupported, correction executed with zero overlap, reviewer/reference agreement true. Reviewed unchanged record: [overnight-live.json](../demo/validation/overnight-live.json).
- Local live measurements: 98.0054% original accuracy, 96.1656% corrected accuracy, with 21 and zero shared participants respectively.
- Both historical hosted replay exports match the reviewed source records. Unauthenticated website, API, and documentation requests return 401.
- Final browser rehearsal passed: replay selection, source labels, score cards, exact evidence-link expansion, all-event toggle, original-preserving clean control, complete JSON download, and viewing replay while a fresh run continues. The new-run button unlocks when the background run finishes. No browser console errors were observed.
- Fresh browser-started local control: `f5e714b3b4e14ece8d462b8d48251583`, completed with a supported scoped conclusion and no redundant correction.
- Updated Linux/amd64 image: `sha256:07e791e8d9184b71d953117fc7540c0de28d43fa3277c099050c0a6cfc10c3b1`. Its hosted HTML, JavaScript, and CSS match the rehearsed source exactly.
- Hosted cancellation during real CPU computation passed. It retained the finished original measurement, rejected a concurrent start while draining, and recorded cancellation without a scientific verdict.
- Fresh hosted flawed case: `e17a646b9bc841d8b005a406ff8d4cde`, completed with three scientific calls, 98.0508% original accuracy, 21 overlapping participants, a zero-overlap correction, and rejection of the original evidence.
- Fresh hosted clean control: `89de0ed64b2e4eb690e492b68e9b50c1`, completed with two scientific calls, 96.1656% accuracy, zero overlap, and the original evaluation retained without repair.
- Restart-persistence check passed: the dataset and both new complete scientific exports survived unchanged. The app is healthy, runs as UID 10001, has zero OOM events and zero automatic restarts, and has no active job. The existing `claude-remote` service is active.
- Private GitHub backup is pushed. Original PDFs, resume, website credentials, model authentication, raw data, caches, and unreviewed run history remain excluded.

Final verification completed: 2026-10-04 03:42 UTC. The only unresolved deployment capability is fresh server-side AI inference, which still requires the account owner’s Codex login and subsequent Linux integration test.
