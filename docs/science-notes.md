# Falsify experiment protocol

The claim is that a classifier generalizes to people absent from its training
data, within this study's recording conditions. This is a claim about the target
population of an evaluation. It is not a claim about all people or deployment.

The data are the UCI Human Activity Recognition Using Smartphones dataset:
[official source](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones),
[DOI](https://doi.org/10.24432/C54S4K). Reyes-Ortiz, Anguita, Ghio, Oneto, and
Parra (2013). The current source licenses the dataset under CC BY 4.0.

## Cases and fixed protocol

- Case A (`row_split`): split only the official training pool into 70% training
  and 30% evaluation recordings, stratified by activity, with seed 42. Training
  and evaluation rows differ but participants can appear in both partitions.
- Case B (`participant_holdout`): use the dataset authors' original partitions.
  These contain disjoint participants. This control checks that the reviewer can
  retain an appropriate evaluation without demanding an unnecessary repair.
- Repair for Case A: use the same official partitions as Case B. The official
  test population is not included in Case A's initial training or test samples.
- Model: StandardScaler, fitted only on the training partition, followed by
  LinearSVC with C=1, dual=auto, max_iter=20000, and random_state=42.
- Record accuracy, macro F1, the six-class confusion matrix, row counts,
  participant overlap, dataset hashes, configuration, library versions, and time.

These choices were fixed before examining confirmation scores. Do not choose
features, models, parameters, seeds, or claims using the official test results.
Running the same fixed experiment twice checks reproducibility. It does not
create two independent scientific replications. Case B and the repaired Case A
share the same confirmation result and must not be counted as separate evidence.

## Interpretation boundaries

Participant overlap makes the new-person claim unsupported by that split even
if the reported score is high. It does not prove that the classifier is poor.
Disjoint participants permit measuring performance on the held-out participants;
the overlap audit alone cannot establish adequate performance.

The initial and corrected evaluations have different training sample counts and
test populations. Their score difference is descriptive. It is not an isolated
causal estimate of participant leakage. The original sensor windows overlap in
time, which creates an additional source of dependence in shuffled recordings.

The dataset contains 30 people aged 19 to 48 performing six activities with a
specific waist-mounted smartphone. Successful classification in that setting
does not establish performance for other devices, populations, or environments.

This two-case demonstration establishes that the workflow can execute a useful
check and make an evidence-based next decision. It cannot estimate AI review
reliability, compare agent architectures, or establish superiority over a fixed
checklist. A blinded, larger case collection would be needed for those questions.

## Files and provenance

The first request downloads the public UCI ZIP under `data/`. The reader loads
only the six required numeric members in memory and does not extract ZIP paths.
It caches numeric arrays with an integrity hash, with pickle disabled on load.
Set `FALSIFY_DATA_DIR` to use another cache directory. No paid inference is
needed for data preparation, overlap audits, or classifier fitting.

The recorded archive SHA-256 identifies the bytes actually downloaded. It is
not a publisher-signed authenticity guarantee. Each experiment records a hash
of its deterministic evidence payload and its predictions. Wall-clock timing
is excluded from the deterministic evidence hash.

## First observed smoke run

The fixed protocol was executed locally on October 3, 2026 with scikit-learn
1.9.1. Case A produced 98.0054% accuracy (2,162 of 2,206 recordings), macro F1
0.981512, and 21 shared participants. The official participant holdout produced
96.1656% accuracy (2,834 of 2,947 recordings), macro F1 0.962131, and no shared
participants. The corrected Case A and clean Case B returned identical
confusion matrices. Each model fit and prediction took approximately 13 to 14
seconds on the development machine, with no convergence warnings.

The result is useful because performance remains strong after the evaluation
is corrected. Falsify should retain that finding with better evidence and a
limited claim. It should not imply that every flawed evaluation must produce a
large performance collapse. These numbers are observations from a smoke run;
the application writes its own run artifacts when its workflow executes.
