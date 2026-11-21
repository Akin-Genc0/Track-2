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

- **Header**: hits, cleared, matches, review, practice labels correct (`50/50`) and unsafe clears. All are computed from the bundle, none are hard-coded.
- **Verdict band** on every hit: a stamp with **SAME / DIFFERENT / REVIEW** and the reason code, next to Name, Date of birth and Countries tiles. Each tile is in one of three states that differ in shape as well as shade: **= agrees** (solid), **≠ contradicts** (ink fill, hatched), **? unknown** (dotted, empty). A missing fact is never drawn as a mismatch. Facts that the reason code asserts take precedence over the desk's own heuristics.
- **Side-by-side table** for customer vs list entry. The core facts come first, and weak fields that are still unknown fold under "more fields".
- **Clickable evidence**: every record ID (`CUS-`, `KYC-`, `NOTE-`, `SR-`, …) in the reason, table or path is a button. It scrolls to the source record's card and flashes it once.
- **Filters with live counts** (All / Same / Different / Review / Labeled / Disagrees) and search by name, ID or reason code, with an empty state when nothing matches.
- **Keyboard**: `J` / `K` next and previous hit (arrow keys while the queue has focus), `1–4` for all / same / different / review, `L` labeled, `D` disagreements, `/` search (`Enter` returns to the queue), `Esc` to clear, `?` for help. A hint bar sits under the queue.
- **Motion** follows Emil Kowalski's rules (see `UX_PLAN.md`): 180–220ms with a strong ease-out, transform and opacity only, and pointer selection only. Keyboard navigation swaps instantly. `prefers-reduced-motion` keeps the fades and drops the movement.

Until `output/dev.jsonl` exists, the 50 practice-label answers are loaded as **sample predictions** and a banner says so. That sample will score 100% on the practice set — it is not the team’s system.

## Files

| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js` | The desk |
| `prepare.py` | Builds a compact `data/bundle.json` (hits, alerts, candidate customers, KYC, notes, search results, labels, predictions) |
| `serve.py` | Tiny server + auto-refresh |
| `data/bundle.json` | Generated case file (~4 MB) |
| `UX_PLAN.md` | Motion and clarity audit, and the plan this design follows |
| `screenshots/` | Headless captures of the desk (1440×900) |
