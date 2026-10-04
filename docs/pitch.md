# Falsify: your 90-second demo

You are the evidence lead. You do not need to explain the code. Your job is to make the claim precise, show what the experiment actually establishes, and stop the story from going further than the evidence.

## Before choosing the demo

The complete live Omnigent workflow has been verified in run `06f519544cd443a194a44965a1246164`. It completed real planner and reviewer delegations, executed all three scientific tools, and produced the original, audit, and corrected results below. It took 164 seconds on the development computer. The same scientific scores were also reproduced by the deterministic reference workflow, using the same dataset and settings.

| What you are showing | Say this |
| --- | --- |
| A new run in Live Omnigent mode | “Omnigent agents are making decisions now, and local tools are executing the tests.” |
| A previous completed Live Omnigent run | “This is a recorded replay of an actual Omnigent investigation.” |
| A new run in Deterministic local mode | “This is our fixed-rule reference, executing the scientific tests now.” |
| A previous completed Deterministic local run | “This is a recorded replay of our fixed-rule reference.” |

Replay means reviewing a saved run. It is not a fresh experiment. The mode badge identifies how the saved run was originally produced.

For the rehearsal, use **Explore the recorded evidence** near the top of the page. **Flawed evaluation** and **Valid control** open completed examples without starting model calls. Each button identifies whether its source is Omnigent or the fixed-rule reference. The chooser prefers a completed Omnigent example when the recorded protocol and split-rule checks pass. The full history, including failed development runs, remains below the ledger.

The known live flawed-case record is `06f519544cd443a194a44965a1246164`, and the known live clean control is `83faf266dc944354b43b5b8ffc22bbd6`. The control checked zero overlap and retained the evaluation without another classifier run. Verify the selected record's numbers, verdict, and export. A fresh run can take several minutes. The script below describes recorded replays, which do not depend on fresh inference finishing during the pitch.

The banner immediately above the scores says **Recorded replay** and identifies the original execution mode. The selector beside **Run new investigation** controls a future run; it does not change the source of the evidence already on screen. On the hosted site, replaying a saved investigation from the development computer does not prove fresh hosted AI inference works.

You can open a replay while a fresh investigation continues in the background. The new-run button stays locked to prevent starting another one. **View running investigation** returns to its progress. This lets you present the recorded fallback while waiting for new evidence.

The ledger initially shows key decisions and computations. **Show all events** reveals transport messages and repeated status updates. This is a display filter only; the export preserves the full record. Click a cited evidence ID to open its exact recorded details.

## Script and screen cues

The script is approximately 200 spoken words. Keep the pauses. Your teammate operates the screen while you speak.

**0:00–0:15 | Point to the claim.**

> A model can get a good score on the wrong test. Our question is: does this activity classifier work for people it has never seen, or are we testing it on familiar people?

**0:15–0:30 | Show the mode badge, then the original result.**

> Falsify investigates that gap. Here we are replaying an actual Omnigent investigation, with real computations. The original classifier achieved about 98 percent accuracy. That sounds promising, but the score alone cannot establish the claim.

**0:30–0:50 | Open the participant-audit evidence.**

> The useful first test is cheap: compare participant identifiers across training and testing. We found 21 people in both. Different recordings are not the same as different people. That evidence changes the next experiment: test on participants completely excluded from training.

**0:50–1:10 | Show the corrected result, then the valid control.**

> On that stronger test, accuracy is still about 96 percent. The promising result survives. What changes is our justification for believing it. Our clean control already separates participants, so the reviewer retains its result without an unnecessary repair.

**1:10–1:30 | Show the ledger and export link.**

> Omnigent coordinated a planner, an experiment operator, and a separate reviewer agent. Every test leaves inspectable evidence. These two cases demonstrate feasibility, not general reliability. Next, we would test more failure types and measure whether agents improve on the fixed-rule reference.

If a new live reviewer disagrees with the fixed split rule, show it as an observed disagreement requiring human review. Do not present that outcome as a successful verification. If demonstrating the deterministic reference instead, name that mode and explain that it executes a fixed rule without agent inference.

## Numbers you can defend

| Evaluation | Accuracy | Macro F1 | Shared participants |
| --- | ---: | ---: | ---: |
| Shuffled recordings | 98.01% | 98.15% | 21 |
| Official participant holdout | 96.17% | 96.21% | 0 |

Accuracy is the proportion of correct activity predictions. It is the large score on the screen. Macro F1 is a separate measure that gives each activity class equal weight and appears beneath the measured score. The script uses rounded accuracy. The valid control's second card explicitly retains the original result; it is not an independent rerun.

These exact figures belong to the verified development-computer records. The Linux deterministic run produced 98.05% original accuracy, differing by one prediction, while its held-out result remained 96.17%. Read the numbers from the selected run and keep the spoken approximation “about 98 percent” rather than promising exact agreement across computers.

The two evaluations have different sample counts and participant populations. The score difference does not isolate the causal effect of participant overlap. The corrected evaluation and the valid control use the same official split, so they are not independent replications.

The supported claim stays narrow: performance on this benchmark's held-out participants, within its recording conditions. It does not establish performance on every person, device, or deployment setting.

## Five questions judges may ask

**1. Why use agents when a simple rule can detect participant overlap?**

> For this particular defect, a simple rule is strong. We include it as our reference. The research question is whether agents can choose the right check from a broader set of possibilities, interpret the result against the claim, and choose a useful follow-up. This small demonstration does not prove that agents outperform the rule.

**2. What did you actually discover if accuracy stayed high?**

> The original evidence did not establish performance on new people. A more appropriate evaluation still produced a strong result. We learned that the predictive finding can survive while its original justification fails. The valid control also demonstrates that a reviewer should preserve appropriate evidence.

**3. Does this prove your AI reviewers are reliable?**

> No. We have two deliberately constructed cases and a fixed classifier. We need a separate, held-out collection of valid and flawed analyses, comparisons against ordinary review and fixed checks, and repeated runs. We would measure both unsupported claims accepted and valid findings incorrectly rejected.

**4. How do you know the experiment happened rather than the AI inventing an answer?**

> The tools execute the computations, and the record includes the actual scores, participant split, dataset hashes, and evidence identifiers. Live conclusions must cite recorded evidence. We show the execution mode, preserve failed runs, and flag disagreements between an AI verdict and the fixed split rule. We do not replace a failed live run with a local success under the same label.

**5. What is the next experiment, and what would it cost?**

> Scientifically, a separately collected participant cohort would test transfer beyond this benchmark. For reviewer evaluation, we would add different planted defects and valid controls with a hidden answer key. The local classifier uses CPU computation. Our configured live route uses the existing Codex sign-in and its allowance; a per-run dollar cost is not reported. We bound tool calls, specialist dispatches, and run time, then use measured usage to plan the next study.

## Optional 15-minute rehearsal

1. **Minutes 0–3: explain the claim back.** Without looking at the script, explain why new recordings from familiar people do not establish performance on unfamiliar people. Your teammate checks the technical accuracy.
2. **Minutes 3–6: find the evidence.** Locate the original score, audit with 21 shared participants, participant-held-out result, and valid control. Open an evidence detail and identify the mode badge. Download one record so you know where the proof lives.
3. **Minutes 6–9: perform the 90-second demo twice.** One person speaks and the other operates the screen. Time it. Remove sentences rather than speaking faster.
4. **Minutes 9–12: practice three objections.** Have your teammate choose three questions from the list. Begin each answer with the direct answer, then give one supporting fact.
5. **Minutes 12–15: practice the fallback.** Open a verified saved run. Say “recorded replay” and name its original mode. If the live integration is unverified or fails, explain that plainly and show what the scientific reference does establish.

Before recording, check each spoken claim against the selected run. Leave out any result that the selected run did not actually produce.
