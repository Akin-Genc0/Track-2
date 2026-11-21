# Clearsight

**Clear the noise. Never clear a match.** Team Clearsight’s Track 2 sanctions-screening hackathon entry resolves customer records, compares watchlist evidence, and produces deterministic, cited decisions for analyst review. It runs locally with the Python standard library: no model, API key, or network access is needed. The slogan is our aim, not a guarantee; policy assumptions and parser limitations are documented in the [required system README](system/README.md).

## Quickstart

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
