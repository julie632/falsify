# Falsify submission

[Judge demo, no login required](https://falsify.134-122-55-169.sslip.io) · [Public repository](https://github.com/julie632/falsify) · [Two-minute video](https://falsify.134-122-55-169.sslip.io/demo.mp4) · [Captions](https://falsify.134-122-55-169.sslip.io/demo.srt)

Falsify investigates whether an activity classifier's evaluation supports its claim about unseen people. A planner chooses a check, an operator executes it, and a separate reviewer changes the next experiment after seeing participant overlap. One flawed case and one valid control establish feasibility within a fixed public benchmark.

The website and repository are public. The judge demo requires no login, serves four reviewed investigations with exact evidence exports, and disables public writes. Anonymous access and isolation from private records were verified. The completed video and captions are uploaded; video and caption downloads returned HTTP 200 and matched their local SHA-256 hashes. The video is 120.000 seconds, 1920x1080 at 30 fps, H.264 with AAC audio, and passed complete decoding and eight-scene visual review. Caption timing is approximate.

## Challenge requirements

This checklist follows the supplied official *Agentic Scientific Discovery* challenge brief, pages 2-4. The original PDF is intentionally excluded from the public repository. Page 2 permits managed Databricks **or open-source Omnigent**. Falsify uses open-source Omnigent 0.16.0 with the Codex harness. It does not use managed Databricks, and that route's Databricks account requirement does not apply.

| Requirement | Evidence and status |
| --- | --- |
| Repository, p. 4 | [Public source](https://github.com/julie632/falsify) and [setup instructions](../README.md). Public visibility verified. |
| Omnigent orchestrates a live discovery workflow, p. 2 | Completed [hosted flawed investigation](../demo/validation/hosted-live-row_split.json) and [hosted valid control](../demo/validation/hosted-live-participant_holdout.json), with actual specialist sessions, tools, citations and updated decisions. [Integration explanation](omnigent-notes.md). |
| Agent specifications and policies, pp. 3-4 | [Executable specification](../agents/falsify.yaml), [roles, tool permissions and human gates](agent-policies.md). |
| Scientific question, hypothesis and at least two possible tests, pp. 2-3 | [Fixed scientific protocol](science-notes.md). The planner compares participant-ID audit with participant-held-out evaluation using information value and qualitative computation cost. Transferable signal and participant overlap are candidate explanations, not established findings. |
| Experiment changes the next decision, pp. 3-4 | In the flawed case, 21 shared participants trigger a fixed participant-held-out test. The clean control has zero overlap and is retained without a redundant repair. |
| Cited evidence, experiment code and results, p. 4 | [Scientific code](../falsify/science.py), [curated historical records](../demo/README.md), [hosted validation records](../demo/validation/README.md), and dataset citation below. |
| Two-minute demo, p. 4 | [Completed 120-second video](https://falsify.134-122-55-169.sslip.io/demo.mp4) and [captions](https://falsify.134-122-55-169.sslip.io/demo.srt), uploaded and verified. Recorded investigations are labeled as replay of actual Omnigent runs. |
| Bottleneck and measured improvement, p. 4 | Choosing whether another verification test adds information. Three paired deterministic comparisons avoided one redundant fit and a median 13.9 seconds of local computation against an explicit always-rerun comparator. Scope and limitations below. |
| Next experiment, p. 4 | Evaluate the frozen classifier on independently recruited participants under the same recording protocol. Separately, evaluate reviewer behavior on hidden defects and valid controls against fixed rules and ordinary review. These studies have not been run. |
| Uncertainty, controls, citations and human approval, pp. 3-4 | [Scientific limitations](science-notes.md), [agent policies](agent-policies.md), preserved source evidence and failed/disagreeing runs. Proposed hypotheses and future experiments are not presented as validated discoveries. |

The brief's rubric is 30% Omnigent orchestration, 25% breakthrough potential, 20% discovery acceleration and learning, 15% scientific rigor, and 10% creativity and responsibility. A 10x improvement is explicitly not required. The brief does not specify a submission portal, exact deadline, repository visibility requirement or media size limit; event logistics must be checked separately.

## Completed discovery loop

The question is whether the classifier generalizes to people absent from training, within this study's recording conditions. The planner considers transferable activity signal and participant overlap as competing explanations for a high score, then compares an ID audit with a costlier rerun. The operator runs the scientific tools, and the reviewer interprets their evidence.

| Hosted evidence | Original accuracy | Shared participants | Result and next decision |
| --- | ---: | ---: | --- |
| [Flawed case](../demo/validation/hosted-live-row_split.json) | 98.0508% | 21 | Original evidence unsupported. Execute the unchanged classifier on the official participant holdout: 96.1656% accuracy, zero overlap, nine unseen test participants. Propose an independent cohort next. |
| [Valid control](../demo/validation/hosted-live-participant_holdout.json) | 96.1656% | 0 | Retain the appropriate evaluation and its limited claim without a redundant classifier run. |

Both are actual Omnigent runs from October 4, 2026. They took 308.6 and 196.3 seconds respectively. These durations are execution observations, not an acceleration comparison. The video replays the separately identified historical laptop runs, whose exact records and timings differ and remain unchanged.

Invalid evaluation does not establish that the underlying predictive claim is false. The stronger test remains promising. The original and corrected evaluations differ in sample counts and populations, so their score difference does not isolate leakage's causal effect. The repair and clean control use the same official split and are not independent replications.

## Measured computation avoided

The [protocol](../demo/validation/compute-savings-protocol.json) was saved before measurement. The [script](../scripts/measure_compute_savings.py) ran three paired repeats on the development computer with a warm dataset, alternating policy order, seed 42 and the unchanged classifier. Every comparator rerun exactly matched the selected historical control's metrics, prediction hash, model, split and dataset. Both policies retained the same narrow conclusion.

| Policy after the original valid result already exists | Median wall time | Median process CPU | Scientific calls | Classifier fits |
| --- | ---: | ---: | ---: | ---: |
| Audit and retain | 0.00148 s | 0.00138 s | 1 | 0 |
| Audit and always rerun | 13.90821 s | 13.50012 s | 2 | 1 |

The [complete results](../demo/validation/compute-savings.json) show a median paired difference of **13.90618 seconds wall time** and **13.49874 seconds process CPU**, with one redundant fit and one scientific call avoided per repeat. Source, dataset, reference and protocol hashes accompany all measurements.

The comparator deliberately repeats a valid evaluation. It is an artificial baseline, not the best available method. A fixed conditional rule can avoid the same work. Original evaluation cost, inference, Omnigent orchestration, startup, network transport and human effort are excluded. No unique agent benefit, overall speed multiplier, dollar saving, human-time saving or 10x discovery improvement is established. Three identical-case repeats are timing observations, not independent scientific replications.

Approaching larger acceleration would require more candidate tests, repeated decision points where unnecessary work can be avoided, and a held-out comparison that includes inference overhead and decision quality. That is a proposed scaling path, not a demonstrated result.

## Sources and remaining validation

Dataset: Reyes-Ortiz, Anguita, Ghio, Oneto, and Parra (2013), [UCI Human Activity Recognition Using Smartphones](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones), [DOI 10.24432/C54S4K](https://doi.org/10.24432/C54S4K), CC BY 4.0. The records include the downloaded archive hash, feature-cache hash, split provenance, measured predictions and evidence references.

The benchmark covers 30 adults, six activities and a specific smartphone recording setup. Generalization to other populations, devices and environments remains untested. General reviewer reliability and superiority over simpler checks require a larger blinded evaluation. Humans must review evidence before broader claims or consequential use.
