# Fathom — watchlist entity review

A static analyst desk for Track 2 sanctions / PEP / adverse-media hits. It does **not** decide cases. It reads the development data and the decision system’s `output/dev.jsonl` (or clearly marked sample predictions while that file is missing) and presents a review queue.

It does not modify anything in `/workspace/track2/`.

## Open it

From this folder:

```bash
python3 prepare.py          # rebuilds data/bundle.json from /workspace/track2
python3 serve.py            # http://127.0.0.1:8765/
```

Then open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) in a browser.

`serve.py` also maps `/track2/` onto the Track 2 folder (read-only) so the desk can pick up `output/dev.jsonl` as soon as it appears, and it rebuilds the bundle automatically.

Alternatively:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Do not open `index.html` as a `file://` URL — the browser will not be allowed to load `data/bundle.json`.

If you already have a predictions file, use **Load predictions** in the top bar, or drop it at `/workspace/track2/output/dev.jsonl`.

## What you will see

- Counts by decision, plus a practice-set decision score and unsafe-clearance count when labels exist (the 50 `practice_labels.jsonl` hits). The score is the share of review-baseline cost saved, using the brief’s cost matrix (an unsafe clear costs 60).
- Filters: cleared / true match / review / pending / labeled / disagreements, and a name or ID search.
- A side-by-side customer vs list-entry comparison with agree / conflict / insufficient highlighting on name, date of birth, nationality, countries and entity type.
- The decision reason, reason code, cited evidence records, and (for practice hits) the reference reason and file path.
- Keyboard: `J` / `K` next and previous, `1–4` filters, `L` labeled, `D` disagreements, `/` search, `?` help.

Until `output/dev.jsonl` exists, the 50 practice-label answers are loaded as **sample predictions** and a banner says so. That sample will score 100% on the practice set — it is not the team’s system.

## Files

| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js` | The desk |
| `prepare.py` | Builds a compact `data/bundle.json` (hits, alerts, candidate customers, KYC, notes, search results, labels, predictions) |
| `serve.py` | Tiny server + auto-refresh |
| `data/bundle.json` | Generated case file (~4 MB) |
| `screenshots/` | Headless captures of the desk |

## Hosted on Vercel (share without pulling)

`vercel.json` at the repo root tells Vercel to run `ui/build-static.sh`, which copies the page files and `output/dev.jsonl` into `_site/` and refuses to deploy if any dataset file ends up there.

- **No participant data is published.** On first visit the page asks for the organisers' workbook (`Screening Dev Set - browse.xlsx`) or a `dev/` folder of JSON Lines. `loader.js` reads it in the browser (a port of `tools/workbook.py`, `tools/xlsx_to_dev.py` and `prepare.py`), builds the same bundle the local server builds, and caches it in that browser. The file is never uploaded.
- The system's decisions (`output/dev.jsonl`) are included, so the desk shows real results. **Load file** in the sidebar still swaps in any other predictions file.
- Official-format data (wrapped alert fields, dict `details`, list `path`) is normalised in the browser exactly as `prepare.py` does it via `system/data.py`.
- Every feature works the same as with `serve.py`: filters, search, keyboard, case files, Tools (Screen a person, Link map with search, Analyst notes).
- **Use a different dataset** in the sidebar clears the cached copy.

To build the site locally: `sh ui/build-static.sh _site`, then serve `_site/` with any static server. The old GitHub Pages workflow now only runs by hand.
