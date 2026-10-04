# Verified historical replays

This package contains two successful **live Omnigent investigations recorded on
October 3, 2026**. Importing them makes them available in the application's run
history. Importing or viewing these files performs no model inference and does
not rerun the scientific computations.

From the project root:

```sh
uv run python -m scripts.import_demo
./scripts/start.sh
```

Open the local application and select a recorded investigation from its history.
The interface labels historical records as **Recorded replay**. Their original
`mode: omnigent` identifies how they were created, not what happens when they
are viewed. Live operation on a new machine requires its own model authentication.

The importer uses only Python's standard library, so it can also be run with
`python3 scripts/import_demo.py`. It checks the manifest checksum, run identity,
case, live mode, completed status, and recorded protocol verification. An
identical existing run is left untouched. A different existing run with the
same identifier causes the import to stop rather than overwrite evidence.

## Included recordings

| Run | Case | Actual recorded outcome |
| --- | --- | --- |
| `06f519544cd443a194a44965a1246164` | Flawed participant-overlapping evaluation | The agents audited 21 shared participants, requested a participant-held-out evaluation, and retained rejection of the original evidence after completing the correction. |
| `83faf266dc944354b43b5b8ffc22bbd6` | Clean participant-held-out control | The agents verified zero shared participants and retained the original evaluation without a redundant correction. |

The first recording contains an original accuracy of 98.0054% and a corrected
accuracy of 96.1656%. The clean control also records 96.1656%, because it uses
the same fixed classifier and official participant-held-out partition.

## Provenance and interpretation

The JSON files are byte-for-byte copies of the original completed local run
records. Their event sequences, model outputs, numerical measurements, IDs,
timestamps, and usage reports have not been rewritten. `manifest.json` records
whole-file SHA-256 checksums. These hashes detect changes to the packaged bytes;
they are not an independent attestation of scientific validity.

The recordings include actual specialist delegation events and scientific tool
outputs. Experiment artifact hashes and confusion-matrix totals were checked
against the recorded results. These two cases demonstrate feasibility. They do
not establish general reviewer reliability, statistical superiority, or an
optimal strategy for spending a testing budget.

The corrected and clean evaluations use the same confirmation set. They are
not independent replications. The clean agent's suggested next step repeats
that same split and seed, which would check reproducibility rather than provide
new evidence about generalization. That suggestion is preserved as part of the
historical agent output. Different numerical-library builds can produce small
changes in fresh runs, so report newly measured values instead of expecting
every platform to reproduce a historical score exactly.

## Data and privacy review

Only these two reviewed run records are packaged. No credentials, personal
filesystem paths, resume content, email addresses, account identifiers, or
private loopback tool endpoints were found in their string fields. The records
retain internal runtime session/task identifiers, timestamps, process IDs,
software versions, token usage, and anonymous identifiers from the public
dataset. Raw sensor recordings and model authentication files are not included.

The underlying data are [UCI Human Activity Recognition Using Smartphones](https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones),
Reyes-Ortiz, Anguita, Ghio, Oneto, and Parra (2013), DOI
[10.24432/C54S4K](https://doi.org/10.24432/C54S4K), licensed under CC BY 4.0.
Full source attribution and dataset checksums are preserved in the run records.
