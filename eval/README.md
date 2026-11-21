# Track 2 evaluation harness

Python 3.11 standard library only. No decision system or model calls.
Run from the repository root:

```sh
python3.11 eval/validate.py output/dev.jsonl --hits data/browse/hits.jsonl
python3.11 eval/validate.py output/dev.jsonl --hits data/browse/hits.jsonl --score data/browse/practice_labels.jsonl
python3.11 eval/repro.py --data data/dev --hits data/dev/hits.jsonl -- system/run '{data}' '{output}'
python3.11 -m unittest discover -s eval -v
```

Validation requires the seven brief fields, their types, unique hit IDs, strict JSON
(no duplicate keys or nonfinite constants), and a policy-compatible decision/reason
code. `--hits` additionally checks complete coverage and alert associations. Additional
fields are permitted: the brief does not prohibit them. Evidence is an array of IDs;
semantic evidence correctness and whether a customer record really identifies the
person require human review. Sentence count is a warning using punctuation boundaries,
since initials and abbreviations prevent reliable sentence validation with a regex.
A valid schema does not certify factual correctness or the two-to-four-sentence rule.

The cost matrix (rows truth; columns DIFFERENT_ENTITY, SAME_ENTITY, REVIEW) is:

| Truth | Different | Same | Review |
|---|---:|---:|---:|
| DIFFERENT_ENTITY | 0 | 3 | 3 |
| SAME_ENTITY | 60 | 0 | 2 |
| REVIEW | 60 | 2 | 0 |

`decision_score = max(0, 1 - cost / all_review_cost)` is a fraction, not the final
competition score. A zero baseline yields null (undefined). All other undefined
ratios also yield null. Scoring uses only supplied label IDs; every labeled hit must
have a prediction. Extra predictions are counted as unscored. Supply only scoreable
labels; unsupported/unknown label decisions fail rather than silently disappearing.
Labels require `hit_id`, `decision`, and optionally `alert_id`, plus either an array
`reason_codes` of accepted alternatives or a single `reason_code`. Other label fields
are retained but not scored. Practice label arrays are supported directly.

Metrics use the labeled subset: unsafe clearances count DIFFERENT_ENTITY predictions
whose truth is SAME_ENTITY **or REVIEW**; review rate divides reviews by labeled hits;
same-entity recall divides correctly confirmed matches by true matches; clearance
precision divides correct clearances by all clearances. False positives cleared divides
correct clearances by true DIFFERENT_ENTITY hits. Reason-code accuracy requires both
the right decision and an accepted code, divided by labels with reason annotations.
A separate metric restricts that denominator to correct decisions with annotations.
Neither metric measures prose, evidence selection, or resolved-customer correctness;
the judges' 25% reasons component and final weighted score cannot be reproduced here.

Reproducibility executes the supplied argv without a shell five times, sequentially,
with a fresh output path per run. It inherits the current directory and environment.
Use `{data}` and `{output}` placeholders (quote them in the shell). Commands must write
the specified output file; stdout is not treated as predictions. Default timeout is
1800 seconds per run; change with `--timeout`. Outputs are validated, then compared by
hit ID, ignoring ordering, prose and evidence differences. Missing/extra hits and changes
to decisions or reason codes are reported against run 1. Temporary output files are
removed. Exit codes: 0 success, 1 validation/reproducibility mismatch, 2 input/run error.
Run commands only if you intend their side effects; the harness is not a sandbox.

## Data provenance and current limitation

Source brief: https://docs.google.com/document/d/1L0dvhyJ4JOLhOu0g3uOXGM_7UgwgZaDrfbWS7RwPX5I/edit

The brief's text and HTML exports on 2026-11-21 contained no data-room hyperlink.
The repository already supplied `Screening Dev Set - browse.xlsx`. Its Policy tab
provides the reason-code table used here. Its contents were recovered locally with:

```sh
python3.11 eval/import_workbook.py 'Screening Dev Set - browse.xlsx' data/browse
```

This creates all nine table exports, POLICY.md, reconstructed name_variants.json,
and the 50 practice labels. Name variant keys are a local reconstruction, not a claim
about the original JSON schema. Spreadsheet list fields remain flattened strings
except the three practice label list columns. The workbook says texts may be truncated
at 32,000 characters. These exports are for evaluation/browsing, not substitutes for
the original decision-system input. Obtain the participant data-room archive and put
its original files in data/dev when available. All data/ is ignored, regardless of size,
as the brief prohibits committing participant data. The pre-existing tracked workbook
is left untouched; ignoring data/ does not remove it from repository history.
