# Omnigent integration

Falsify uses the real `omnigent==0.16.0` runtime, local server, runner,
Codex harness and declared specialist agents. The operator delegates to an
separate planner and reviewer using Omnigent's `sys_session_send` mechanism.
Real child session IDs, completed specialist events, requested computations,
and final evidence are retained in the run ledger.

The Python integration is `falsify.omnigent_adapter.run_discovery`. It bootstraps
an ephemeral local server using the pinned version's CLI lifecycle helpers and
streams its official `OmnigentClient` / `SessionsChat` API. Private bootstrap
helpers are isolated in this adapter. Upgrade Omnigent only after a live smoke
test because those helpers are not a stable public API.

The installed Codex CLI uses the user's existing ChatGPT sign-in. Falsify does
not read or export credential contents and does not require an OpenAI API key.
Inference consumes the signed-in subscription's allowance. Dollar cost is
reported as unknown, not an invented zero. Provider token usage is preserved
when available and may not aggregate every child session or background call.
The experiment explicitly selects `gpt-6-luna`. Low reasoning effort is supplied
through the session creation API because the v0.16.0 flat YAML compatibility
loader does not preserve the documented executor reasoning-effort property.

Only three experiment functions are exposed: run_original, audit_split, and
participant_holdout. Their case and paths are fixed by the trusted application;
the only parameter is seed 42. The Omnigent runner invokes server-side Python
functions, which call a random capability-protected loopback bridge. The bridge
returns results from the application's allowlisted ScientificTools callback.
No remote endpoint receives private datasets or local file contents through
this bridge. The public benchmark results and claim are sent to the model.

Why a local bridge: v0.16.0 exposed client-runtime tools in the model schema
but its session-native dispatch attempted to find them in the server's local
dispatch table. A live test failed explicitly with that error. The documented
server Python callable route was used instead. Failed experiments remain
visible as development artifacts and are not successful scientific results.

Native Codex tools and web search are disabled. No OS environment, terminal,
arbitrary spawning, MCP server, or filesystem tool is granted in the agent spec.
The application enforces a scientific-call limit and a wall-clock timeout.
It monitors real specialist dispatch IDs and cancels if their budget is
exceeded. This is a bounded research demo, not a hostile-code sandbox or a
hard financial spending guarantee. The native harness processes use the
official CLI's authentication and Omnigent's session management.

A completed run must contain actual original and audit results, completed
planner and reviewer sessions, and evidence citations referring to the results.
Malformed JSON, missing computations or invented evidence identifiers fail
validation. The application never converts a failed agent run into a
deterministic run while retaining an Omnigent label.

The agents retain discretion over the verification choice and conclusion.
A fixed scientific model and deterministic experiment functions make results
reproducible. The system does not hard-code the AI reviewer's verdict.
The reviewer is a separate model session receiving the operator's supplied
evidence. This is not an independently blinded comparison study.

## Live validation

On 2026-10-03, run `06f519544cd443a194a44965a1246164` completed the actual
three-agent loop in 163.94 seconds. Omnigent parent session
`eb856fb7b96e40129cae6c08c730bd7f` delegated to planner
`a28bd3b8c0f049bdab878b8f8bcd27a0` and reviewer
`c6c90b9f09054798b2c755f5bf05ec8d` (two reviewer dispatches).
The run executed the original evaluation, participant audit and corrected
evaluation. Recorded accuracy was 98.0054% in the original evaluation and
96.1656% with participants held out. The reviewer rejected the original
evidence and separately described the repaired evidence's narrower support.
These score differences do not isolate the causal effect of participant
overlap, because the participant populations and sample counts differ.

The ledger is `artifacts/runs/06f519544cd443a194a44965a1246164/run.json`.
It records three scientific calls, three specialist dispatches, all three
valid evidence references, and real runtime child-session events.

The clean control then completed as run
`83faf266dc944354b43b5b8ffc22bbd6` in 117.16 seconds. Parent session
`9de3e475cb504ffd9953b73a73d500df` recorded two specialist dispatches and
two scientific calls. The reviewer retained the narrowly scoped claim after
96.1656% accuracy and zero participant overlap were computed. Its ledger is
`artifacts/runs/83faf266dc944354b43b5b8ffc22bbd6/run.json`.
These are two controlled feasibility cases, not a reliability rate estimate.

A separate harmless native-shell boundary probe through the same Omnigent
Codex harness settings returned `{"native_shell_available":false}`. No shell
execution was observed. This is a capability smoke check, not a security audit.

Earlier failed startup and missing-tool attempts are retained as development
history. Explicit client setup timeout of 120 seconds avoids the SDK's default
30-second cold-start timeout. Full runs have a 600-second ceiling, with actual
scientific tools and specialist delegation counts bounded separately.

Primary sources checked during implementation:

- [Omnigent v0.16.0 source](https://github.com/omnigent-ai/omnigent/tree/v0.16.0)
- [Agent YAML specification](https://github.com/omnigent-ai/omnigent/blob/v0.16.0/docs/AGENT_YAML_SPEC.md)
- [Codex executor implementation](https://github.com/omnigent-ai/omnigent/blob/v0.16.0/omnigent/inner/codex_executor.py)
- [SessionsChat implementation](https://github.com/omnigent-ai/omnigent/blob/v0.16.0/sdks/python-client/omnigent_client/_sessions_chat.py)
