# Reviewed live integration evidence

## Fresh hosted Linux cases

These unchanged exports were produced by new live Omnigent investigations on the DigitalOcean droplet on October 4, 2026, after the account owner completed a separate official Codex device-code login. They are separate from the historical presentation replays imported by `scripts/import_demo.py`.

| Record | Run ID | Result |
| --- | --- | --- |
| [hosted-live-row_split.json](hosted-live-row_split.json) | `df7fdb571ed140e7851c17517e13422e` | 308.6 seconds, three scientific calls and three specialist dispatches. Rejected original evidence with 21 shared participants, then interpreted a measured correction with zero overlap. |
| [hosted-live-participant_holdout.json](hosted-live-participant_holdout.json) | `ba03b3d5ebc646e79ae9c166025b9237` | 196.3 seconds, two scientific calls and two specialist dispatches. Retained the valid original evaluation without redundant correction. |

Both records contain actual completed planner and reviewer sessions, valid citations, and reviewer/reference agreement. Their scores and sample counts were independently checked against the recorded confusion matrices. Original flawed accuracy is 98.0508%; corrected and clean-control accuracy is 96.1656%. Hosted held-out macro F1 is 0.9621130919578866. The correction and control use the same official split and are not independent replications.

The first hosted attempt failed before inference at the upstream 45-second readiness timeout. The two successful runs followed an infrastructure fix: an explicit bounded readiness wait and precompiled dependency bytecode. Evaluation rules and agent prompts were unchanged. The failed record remains on the server and in ignored local deployment output.

The selected exports were reviewed for credentials, account identifiers, emails, personal paths, and private bridge URLs. They retain anonymous public-dataset identifiers and internal runtime identifiers. The dataset attribution and limitations in [the replay README](../README.md) apply. These are integration checks, not a general AI-review reliability estimate.

SHA-256:

- `hosted-live-row_split.json`: `b4725a382015e5ba3b593852d577cdcb99a3d87c62e502d930b1ce9366ae43c8`
- `hosted-live-participant_holdout.json`: `bde7cf4a82e8149f281fa81bfdd4fd0b54316420f57a6707f6ff5627b99e3402`

## Overnight local regression

`overnight-live.json` is the unchanged successful local Omnigent run `e20e5568e66941918705c4373cb46a24`, started at 03:27 UTC on October 4, 2026. It repeated the flawed case after the first lifecycle fixes: three actual scientific tool calls, three specialist dispatches, 175.4 seconds, original evidence rejected, correction executed, and reviewer/reference agreement. The final repeated-cancellation startup safeguard was added afterward and covered by an isolated regression test.

This is historical local integration evidence, not a hosted Linux AI run. It is intentionally separate from the two presentation replays imported by `scripts/import_demo.py`. It was reviewed for credentials, email addresses, personal paths, and private bridge URLs before inclusion. It retains anonymous public-dataset identifiers and internal runtime identifiers. The same dataset attribution and limitations in [the replay README](../README.md) apply.

SHA-256: `2ffeac692085266477dc223d5c630cd79b7a4ca72892ebc05d0fedf3b584438c`
