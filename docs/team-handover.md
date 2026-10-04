# Team handover

## Working arrangement

Keep the current Codex chat as the implementation coordinator. There is no need to open three more engineering chats. The coordinator has already split work among a scientific engine agent, an Omnigent integration agent, and a browser interface agent, and owns integration and verification.

Those agents work during the active task. This arrangement does not create an unattended scheduled service that keeps working after the chat ends. Continue here for changes or submission preparation.

## Software and accounts

| Need | Choice | Action now |
| --- | --- | --- |
| Engineering and coordination | Existing Codex desktop app | Already available |
| Scientific computation | Local Python, uv, scikit-learn | Installed in the project environment |
| Agent orchestration | Omnigent 0.16.0 | Installed and pinned |
| Model authentication | Existing Codex CLI sign-in | No new account or API key for this route |
| User interface | Local browser | Open http://127.0.0.1:8765 |
| Sharing source or submission | Event's required destination | Wait until the source and submission are ready |

Avoid buying infrastructure for this POC. Local scientific execution does not require paid APIs. Live inference uses the existing subscription allowance, with no reliable per-run dollar cost supplied by the runtime. Do not describe it as free or as zero-dollar inference.

## Your sister's contribution

Her useful role is evidence editor and skeptical reviewer. No coding knowledge is required. She can independently check whether the final words follow from the measurements and make the presentation comprehensible to a judge.

Suggested first 45 minutes:

1. Read the claim and the short explanation below.
2. Review a completed flawed run and its corrected evaluation.
3. Review the valid control. The system must be capable of retaining valid evidence.
4. Write three sentences: what was claimed, what evidence was missing, and what changed after the next test.
5. Rehearse the demonstration and interrupt whenever a sentence overstates what the experiment proves.

She should understand these five terms:

- **Training data:** examples used to fit the classifier.
- **Test data:** examples used to measure its predictions.
- **Participant overlap:** the same people contribute examples to both groups, even when the exact rows are different.
- **Held-out participant:** a person whose recordings were absent from training.
- **Evidence scope:** the population and conditions the experiment actually addresses.

The legal analogy is the relationship between a proposition and the evidence admitted to support it. A result can be genuine and still fail to establish the proposition at issue. Here, predicting fresh recordings from familiar people does not by itself establish performance on unfamiliar people.

Optional separate chat prompt, if she wants her own tutor:

> You are my evidence editor and hackathon presentation coach. I am a law student at UvA with no programming background. Our project, Falsify, uses Omnigent agents to assess whether a machine-learning evaluation supports a claim about unseen people. Read README.md and docs/science-notes.md in this project. Teach me the five essential concepts in plain language, then help me inspect the latest completed run records in artifacts/runs. Distinguish deterministic local runs from actual Omnigent runs. Draft a 90-second pitch and five skeptical judge questions with evidence-based answers. Do not change code or invent outcomes. Never use em dashes. Keep the scope to one public dataset, one participant-overlap defect, and one clean control. Do not claim statistical validation or superiority over other methods. Save the reviewed pitch to docs/pitch.md and tell the implementation coordinator what you found when I ask you to report back.

If this chat is opened in the same project, its output can be read here. Tell the coordinator the chat title if you want it actively managed here; no copying of engineering tasks is necessary.

## A 90-second demo outline

1. **Claim:** “This classifier works for people it has never seen.” Show the actual original score.
2. **Challenge:** “A high score alone does not show that the test matches that claim.” Show the planner comparing two tests.
3. **Evidence:** Show the audit identifying participants in both training and testing.
4. **Adaptation:** Show the reviewer requesting a participant-held-out evaluation and the actual new result.
5. **Conclusion:** “The original evidence was inadequate. The better test still produces a promising result, now with a more defensible scope.”
6. **Control:** Show a recorded valid control, clearly labeled. It should retain the valid design rather than invent a problem.

The bottleneck being demonstrated is choosing the next useful verification step under a budget. The bounded workflow already tells the agents which scientific issue to investigate. We have not demonstrated general autonomous discovery, a new statistical method, or a learned optimal testing policy.

## Before submission

Check the event's final format and deadline, select the completed live run records, rehearse once, and prepare the required repository and video. Publishing or submission is a separate action from getting the local POC working. Preserve one completed run as an explicitly labeled replay in case inference is slow during judging.
