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

Per hit, top to bottom, in the order a reviewer needs it:

1. **Decision stamp**: Cleared / True match / Review, the raw decision (`DIFFERENT_ENTITY` …) and the reason code.
2. **Deciding facts**: Date of birth, Country, Name and Entity type tiles, each in one of three states that differ in shape as well as shade: **= Match** (solid), **≠ Contradicts** (ink pill), **? Unknown** (dashed). A missing fact is never drawn as a mismatch. Facts the reason code asserts win over the desk's own parsing and are marked *Deciding fact*.
3. **Reason**: the system's 2–4 sentence reason, the rule behind its code, the **cited records** as buttons, and one safety line (cleared only on a contradiction; review when unsure).
4. **Side by side**: customer vs list entry. Weak fields that are still unknown fold under "more fields".
5. **Evidence records**: cited cards first. Every record ID on the page (`CUS-`, `KYC-`, `NOTE-`, `SR-`, …) jumps to its card and rings it once.

The header carries counts, practice labels answered correctly (`50/50`) and **unsafe clears** (`0`, with "unsure → Review"). All are computed from the bundle.

- Filters with live counts (All / Cleared / True match / Review / Labeled / Disagrees) and search by name, ID or reason code, with an empty state and a one-click reset.
- Keyboard: `J` / `K` next and previous (arrow keys while the queue has focus), `1–4` all / cleared / true match / review, `L` labeled, `D` disagreements, `/` search (`Enter` returns to the queue), `Esc` clear, `?` help.
- Motion: 150–250ms ease-out, transform and opacity only, pointer selection only; `J`/`K` swaps instantly. `prefers-reduced-motion` turns it off.
- Muted text is at least 4.5:1 on every surface, nothing is smaller than 11px, and controls share 28/32px heights and one focus ring. No horizontal overflow at 1280×800 or 1440×900.

Until `output/dev.jsonl` exists, the 50 practice-label answers are loaded as **sample predictions** and a banner says so. That sample will score 100% on the practice set — it is not the team’s system.

## Files

| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js` | The desk |
| `prepare.py` | Builds a compact `data/bundle.json` (hits, alerts, candidate customers, KYC, notes, search results, labels, predictions) |
| `serve.py` | Tiny server + auto-refresh |
| `data/bundle.json` | Generated case file (~4 MB) |
| `screenshots/` | Headless Chrome captures at 1440×900 (and `*-1280-*` at 1280×800) |
