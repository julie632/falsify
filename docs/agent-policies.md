# Agent specifications and policies

The [executable specification](../agents/falsify.yaml) defines three roles coordinated by open-source Omnigent. The human supplies the objective, selects the case, and sets the allowed computation budget. The agents investigate one fixed public dataset and one predefined evaluation defect.

| Role | Decision and inputs | Tools and output |
| --- | --- | --- |
| Planner | Receives the claim, available tests and remaining budget. Compares information value and qualitative computation cost of participant audit versus held-out evaluation. | No external tools. Returns a structured recommended test, reasons, alternatives and next experiment. |
| Experiment operator | Receives the plan and actual results. Executes the selected allowed test and an executable reviewer-requested follow-up within budget. | `run_original`, `audit_split`, `participant_holdout`, and declared planner/reviewer handoffs. Preserves actual measurements and evidence IDs; returns a cited conclusion. |
| Reviewer | Receives executed evidence, provenance and remaining budget in a separate model session. Rules on the original evaluation and whether another test adds information. | No external tools. Returns a structured ruling, reasons, alternatives and next experiment. A corrected result does not retrospectively validate the original evaluation. |

## Enforced computational boundaries

Scientific tools accept the fixed seed 42; the trusted application fixes dataset and case paths. Native shell, filesystem, web search, skills and arbitrary spawning are disabled for the research agents. The adapter enforces scientific-call, specialist-dispatch and elapsed-time budgets. A completed live run requires executed original and audit results, completed planner and reviewer sessions, and citations to recorded evidence. Malformed or missing evidence fails validation. See the [integration implementation](../falsify/omnigent_adapter.py), [workflow](../falsify/workflow.py), and [integration notes](omnigent-notes.md).

These controls bound a research demonstration. They are not a hostile-code sandbox or a hard financial guarantee. Model inference uses an authorized Codex account; complete per-run dollar cost is not reported. No zero-dollar inference claim is made.

## Human approval and review gates

Human operators set the scientific objective and approve changes to the allowed tools or evaluation protocol. The agent tool surface contains no mechanism to recruit participants, contact people, operate a physical laboratory, make purchases, publish findings, deploy code or act on an individual. Those consequential actions remain outside this workflow and require separate human authorization. There is no claim that an unimplemented approval dialog mediates them; the available tools do not offer those actions.

If the AI review disagrees with the fixed participant-separation rule, the application preserves and flags the disagreement. A human must resolve it before relying on that conclusion. Humans review scientific scope and evidence before public claims, broader deployment or real-world use. Releasing this hackathon source and demonstration is a human publication decision, not an agent scientific tool action.

An independently recruited cohort is a proposed future study. It requires an appropriate study plan and human approvals before recruitment or collection. No such study is performed by the current tools.

## Evidence and interpretation policy

- Keep evaluation rules fixed before final runs. Do not choose models, parameters, seeds or claims based on confirmation results.
- Label candidate explanations as AI-generated hypotheses, not findings. Label proposed experiments as future work until executed.
- Distinguish new live Omnigent runs, deterministic local execution and recorded replay. Replaying a genuine prior run performs no new inference or experiment.
- Retain failed runs and disagreeing judgments. Never silently replace failed inference with a deterministic result carrying an Omnigent label.
- Cite actual tool evidence for numerical claims. Preserve dataset, split, model and prediction provenance; do not invent metrics or costs.
- An invalid evaluation does not prove the predictive claim false. Preserve promising corrected evidence within its actual tested scope.
- The clean control checks that valid evidence can be retained. It and the corrected case share one confirmation split, so they are not independent replications.
- The compute comparison measures only local work avoided against an explicit redundant-rerun baseline. A fixed rule can achieve the same saving; no agent superiority or overall speed multiplier is established.
- Exclude credentials, original PDFs, resumes, raw datasets and runtime caches from the submission. Include only reviewed source and deliberately curated evidence.

Broader scientific claims require independent participant validation. Claims about reviewer reliability require a larger hidden-answer evaluation containing both defects and valid controls, with fixed rules and human review as comparators. See the [scientific protocol](science-notes.md) and [submission evidence](submission.md).
