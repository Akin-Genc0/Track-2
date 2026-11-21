# Clearsight

**Clear the noise. Never clear a match.** Team Clearsight’s Track 2 sanctions-screening hackathon entry resolves customer records, compares watchlist evidence, and produces deterministic, cited decisions for analyst review. It runs locally with the Python standard library: no model, API key, or network access is needed. The slogan is our aim, not a guarantee; policy assumptions and parser limitations are documented in the [required system README](system/README.md).

## 30-second quickstart

```sh
git clone https://github.com/Akin-Genc0/Track-2 && cd Track-2
system/run /path/to/dev output/dev.jsonl        # ~15 s, Python 3 stdlib only, no key, no network
python3 /path/to/validate.py --data /path/to/dev --output output/dev.jsonl --score /path/to/dev/practice_labels.jsonl
make test                                       # data-free policy, loader and packaging tests
```

`system/run` works from any working directory and with spaces in either path. It reads only the data folder it is given and writes one JSON line per hit.

## Results (official `validate.py`, development set)

| Check | Result |
| --- | --- |
| Output validity | 819 lines read, 0 problems |
| Practice labels (50 hits) | **50/50 right decisions, 0 unsafe clearances**, decision score 100.0 |
| Reasons on right decisions | reason code 100%, customer record 100% |
| All 819 dev hits | 464 `DIFFERENT_ENTITY` · 125 `SAME_ENTITY` · 230 `REVIEW` (28% review rate) |
| Synthetic shadow sets (559 hits, seeds 7 and 21, `tools/shadow.py`) | 97.9% right, **0 unsafe**, score 0.965 |
| Reproducibility | byte-identical output across runs and any `PYTHONHASHSEED` |
| Run time and cost | about 15 s on one laptop core; $0 (no model calls) |

Practice and shadow scores are development feedback, not proof of unseen-set performance.

## How it works

```
 alerts.jsonl ─┐
               ▼
 ┌──────────────────────────┐   accounts / logins / emails → customers.jsonl
 │ 1. Resolve the customer  │   joint holders split by screened name + DOB;
 │    resolve.py            │   no link → name, DOB, country, city; >1 person → AMBIGUOUS
 └────────────┬─────────────┘
              ▼
 ┌──────────────────────────┐   accounts → onboarding → kyc_checks (approved only),
 │ 2. Profile the customer  │   email → notes; verified beats declared;
 │    profile.py            │   every fact carries the record IDs it came from
 └────────────┬─────────────┘
              ▼
 ┌──────────────────────────┐   names + aliases, entity type, DOBs, countries, death date,
 │ 3. Profile the listing   │   ages in profile text ("aged 45 in March 2019"),
 │    hitfacts.py           │   search results only when tied to this listing
 └────────────┬─────────────┘
              ▼
 ┌──────────────────────────┐   contradiction → DIFFERENT_ENTITY (DOB, temporal, location,
 │ 4. Decide (POLICY.md)    │   verified name, entity type, deceased); agreement with no
 │    decide.py             │   contradiction → SAME_ENTITY; anything else → REVIEW
 └────────────┬─────────────┘
              ▼
 ┌──────────────────────────┐   2–4 sentences from this hit's own facts;
 │ 5. Explain  explain.py   │   evidence = only the deciding record IDs
 └────────────┬─────────────┘
              ▼
       output/dev.jsonl
```

Full detail, three worked cases and honest limitations: [system/README.md](system/README.md).

## Safety design: REVIEW when unsure

An unsafe clearance costs 60; a needless review costs 2–3. The system is built around that asymmetry:

- **Clear only on a stated contradiction.** `DIFFERENT_ENTITY` needs a positive policy ground backed by cited records. Missing data is never a mismatch, and a year-only DOB still agrees with a full date.
- **Verified beats declared.** Rejected, failed or expired KYC checks are ignored, never used as evidence.
- **Ambiguity stays open.** If two plausible customers lead to different answers, the hit goes to `REVIEW / AMBIGUOUS_CUSTOMER_RECORD`. No customer found means `REVIEW` with `null`.
- **Fail closed.** Any exception, unreadable source or unparsed phrasing falls back to `REVIEW`, never to a clearance, and every hit still gets a line.
- **Tested against drift.** Rewording, schema-mutation and red-team tests (`tools/perturb.py`, `tools/unseen_sim.py`, `redteam/`) check that no change moves a decision towards clearing.

## Team Clearsight

- **Zain**: resolver, policy engine, evaluation tooling
- **Akin Genc** (`Akin-Genc0`): analyst desk UI, decision traces, docs
- **John Katsikis**: team member

## Full local workflow

Use Python 3.11 and run these commands from the repository root. **The dataset is for event participants only and must never be committed.** Obtain the official development folder from the event organisers and place it at `dev/` (already gitignored):

```sh
system/run dev output/dev.jsonl
python3 tools/score.py output/dev.jsonl dev/practice_labels.jsonl -v
python3 tools/check_submission.py output/dev.jsonl dev
# If you have the organisers' validate.py and output.schema.json:
# python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
make test
python3 ui/serve.py
```

Open http://127.0.0.1:8765/ for the analyst desk; stop the server with Ctrl-C. In another terminal, open the pitch:

```sh
open deck/index.html  # macOS; otherwise open this file in your browser
```

`make run score test` runs the same sequence against `dev/`; `make ui` starts the desk and `make deck` opens the pitch. Running the system regenerates the required `output/dev.jsonl` deliverable. You can run `make test` without any dataset.

Workbook conversion is optional. If you only have `Screening Dev Set - browse.xlsx`, place it in the repository root (gitignored) or set `TRACK2_XLSX` to its path, then run `python3 tools/xlsx_to_dev.py` (writes `data/dev/`) and pass `DATA_DIR=data/dev` to Make. The converter searches `$TRACK2_XLSX`, then `./Screening Dev Set - browse.xlsx`, then `~/Track-2-data/Screening Dev Set - browse.xlsx`.

## Repository map

| Path | Purpose |
| --- | --- |
| [system/README.md](system/README.md) | Required deliverable: architecture, policy decisions, evidence and limitations |
| [system/](system/) | Screening implementation and executable `run` entry point |
| [output/dev.jsonl](output/dev.jsonl) | Submitted development predictions |
| [deck/](deck/) | Pitch deck; start at [index.html](deck/index.html) |
| [ui/](ui/) | Local analyst review desk |
| [tests/](tests/) | Synthetic policy regression cases |
| [tools/](tools/) | Workbook conversion, local scoring and perturbation checks |
| [FORMAT.md](FORMAT.md) | Input/output format reference |
| `dev/` | Official development inputs (ignored by Git; never commit) |
| `data/dev/` | Optional workbook reconstruction (also ignored by Git) |

## Evaluation

Run the synthetic policy tests independently of the dataset. The local scorer compares predictions with the official practice labels, reporting decision accuracy, unsafe clearances, cost relative to reviewing every hit, reason-code/customer agreement and evidence overlap. Practice-set results are development feedback, not proof of unseen-set performance or real-world safety. See [system/README.md](system/README.md) for detailed evaluation and limitations. Optional robustness checks: `python3 tools/perturb.py dev`.

GitHub Actions runs only data-free policy tests and Python syntax checks on Python 3.11. It never needs the workbook or participant data. Participants can run the full pipeline locally using the quickstart above.

## License

The code is licensed under [MIT](LICENSE). The organisers’ workbook and third-party media remain subject to their respective rights; this code license does not grant rights to those assets.
