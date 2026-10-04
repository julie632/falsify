# Falsify

A small scientific verification lab that asks whether an impressive machine-learning score supports the claim being made about it. Omnigent coordinates a planner, an experiment operator, and a separate reviewer agent. The tools execute real experiments on the public UCI Human Activity Recognition dataset.

The six-hour scope is deliberately narrow: one dataset, a participant-overlap defect, a valid control, and an evidence-driven follow-up. This is a working feasibility demonstration, not a benchmark of general agent reliability.

The password-protected [hosted demo](https://falsify.134-122-55-169.sslip.io/?run=df7fdb571ed140e7851c17517e13422e#results-heading) runs on the team's existing DigitalOcean droplet. Both fresh hosted AI cases completed on October 4, 2026, after the account owner completed the official device sign-in separately on the server. Hosted scientific computation and recorded replays are also verified. See [deployment status and operations](docs/deployment.md). Website login details are kept outside Git in `output/deployment/access.txt` on the development computer.

## Run the demo

For a new checkout, run `uv run python -m scripts.import_demo` once to load the two reviewed historical recordings. Their provenance and checksums are in [demo/README.md](demo/README.md).

From this project directory:

```sh
./scripts/start.sh
```

Open <http://127.0.0.1:8765>. Keep the terminal running. Use Control-C to stop it. The server listens only on this computer.

Choose a case and click **Run investigation**. The evidence ledger updates as work finishes. **Download evidence** exports the actual run record as JSON. Previous investigations are explicitly marked as recorded replay.

Prerequisites are Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/). They are already installed on the development computer. The launcher installs the locked project dependencies. The first scientific run downloads the public dataset if it is not cached.

For the live workflow, Omnigent 0.16.0 uses the existing official Codex CLI sign-in. No new Omnigent account or separate API key is needed for this configured local route. Inference consumes the signed-in account's allowance; the runtime does not report a per-run dollar cost. If authentication is unavailable, the UI disables live mode.

## Two honest execution modes

| Mode | What happens |
| --- | --- |
| Live Omnigent | Actual specialist agent sessions choose and review tests. The local scientific tools run the classifier and inspect the split. |
| Deterministic local | A fixed decision rule runs the same scientific tools without model inference. Useful as a reproducible reference and an offline demo fallback. |

A failed live run remains failed. It is never silently replaced by a deterministic run.

## Verified runs

Both cases completed with actual Omnigent specialist sessions on the Linux droplet on October 4, 2026:

| Case | Hosted run ID | Scientific calls / specialist dispatches | Elapsed |
| --- | --- | ---: | ---: |
| Flawed evaluation | `df7fdb571ed140e7851c17517e13422e` | 3 / 3 | 308.6 seconds |
| Valid control | `ba03b3d5ebc646e79ae9c166025b9237` | 2 / 2 | 196.3 seconds |

The [hosted flawed-case evidence](demo/validation/hosted-live-row_split.json) records 98.0508% original accuracy and 21 shared participants. The reviewer requested a held-out evaluation, then rejected the original evidence while recognizing the repaired result: 96.1656% accuracy on nine unseen participants. The [hosted control evidence](demo/validation/hosted-live-participant_holdout.json) records the same held-out result, zero overlap, and acceptance within the tested scope without a redundant correction. Both conclusions agree with the fixed split rule.

Earlier macOS runs `06f519544cd443a194a44965a1246164` and `83faf266dc944354b43b5b8ffc22bbd6`, recorded on October 3, remain unchanged in the [historical replay package](demo/README.md). Import that package to view its [flawed-case replay](http://127.0.0.1:8765/?run=06f519544cd443a194a44965a1246164#results-heading) and [clean-control replay](http://127.0.0.1:8765/?run=83faf266dc944354b43b5b8ffc22bbd6#results-heading) locally.

The 73-test automated suite covers evidence validation, real specialist completion checks, tool boundaries, disagreement retention, cancellation cleanup, and API validation. Tests use fixtures; live records provide separate integration evidence. Current verification details are in the [morning handover](docs/morning-handover.md).

The first hosted startup attempt failed before inference because the SDK's readiness check defaulted to 45 seconds. Dependency bytecode is now compiled during the container build, and readiness allows up to 180 seconds within the existing ten-minute run deadline. Failed attempts remain recorded. The working setup uses `gpt-6-luna` with low reasoning effort; model latency and subscription allowance can still affect new runs. Cleanup may drain accepted computation after the deadline.

## Scientific protocol

The claim is: **The activity classifier generalizes to people absent from its training data, within this study's recording conditions.**

1. The planner compares a cheap participant-overlap audit with a more expensive participant-held-out evaluation.
2. The operator measures the original classifier score. The agent-facing summary withholds participant metadata until an audit is requested; the full result remains in the evidence ledger.
3. The audit checks participant identifiers in the actual partitions.
4. The reviewer decides whether the evidence supports the original claim and whether another experiment earns its cost.
5. If requested, the operator reruns the unchanged classifier on the official participant-separated split, and the reviewer updates the conclusion.

**Flawed evaluation:** a stratified random split of recordings from the dataset's official training pool. Different recordings from the same people appear in both partitions. The official held-out participants remain untouched until the repair test.

**Valid control:** the dataset authors' official train/test split, which separates participants.

The classifier is a training-fitted StandardScaler and LinearSVC, with a fixed seed and settings. Model settings are not optimized against the held-out results.

Initial measured reference results on this computer:

| Evaluation | Accuracy | Macro F1 | Participants shared across train/test |
| --- | ---: | ---: | ---: |
| Shuffled recordings | 98.01% | 98.15% | 21 |
| Official participant-held-out split | 96.17% | 96.21% | 0 |

The promising predictive result survives the better test. The original evaluation nevertheless cannot establish generalization to unseen people. The score difference is descriptive, not an isolated causal estimate of leakage, because training sizes and test populations differ. The corrected result and the clean control use the same official split, so they are not independent replications.

## Evidence and boundaries

Run records live in `artifacts/runs/`. They preserve actual tool results, dataset hashes, split provenance, evidence IDs, agent events, final decisions, failures, and usage when reported. Live decisions must cite recorded evidence. A wrong AI judgment is retained and flagged when it disagrees with the fixed participant-separation rule.

The application limits the tools to the fixed dataset and three named computations. Native shell, browsing, and skills are disabled in the research agents. Tool executions, specialist dispatches, and wall time are bounded. The browser UI is intended for local use and is not a production multi-user service.

Dataset files, runtime caches, credentials, original PDFs, and the private resume are excluded from Git. Do not publish the entire workspace folder. Only reviewed source and the explicitly curated historical replay package belong in a submission repository.

## Development and handover

```sh
uv run pytest -q
uv run python -m scripts.prepare_data
uv run python -m scripts.run_reference
```

- `falsify/science.py`: data preparation, fixed evaluation, and split audit.
- `falsify/workflow.py`: scientific tool boundary, evidence validation, and reference workflow.
- `falsify/omnigent_adapter.py` and `agents/falsify.yaml`: actual Omnigent orchestration.
- `falsify/server.py`: local API and run lifecycle.
- `static/`: browser interface.
- [Morning demo handover](docs/morning-handover.md): hosted access, the preferred rehearsal route, and current verification.
- [Team handover](docs/team-handover.md): responsibilities, optional chat prompt, and demo narrative.
- [Demo script](docs/pitch.md): 90-second pitch, judge questions, and rehearsal steps.
- [Scientific notes](docs/science-notes.md): data and methodological details.
- [Omnigent notes](docs/omnigent-notes.md): integration details and limitations.

Data attribution: Anguita, D., Ghio, A., Oneto, L., Parra, X., and Reyes-Ortiz, J. L. (2013), [Human Activity Recognition Using Smartphones](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones), UCI Machine Learning Repository, DOI [10.24432/C54S4K](https://doi.org/10.24432/C54S4K), CC BY 4.0.
