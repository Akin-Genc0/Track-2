# Akin's tasks (Team Clearsight, Track 2, code freeze 17:00)

## RIGHT NOW (12:15 plan from Zain + Grok Bot)
1. **Submission portal (checked by Grok Bot):** /submit needs (a) the public GitHub repo (it's already public; judges auto-analyse the LATEST commit, so we merge everything to `main` by 16:30), (b) a **2-minute** video link (YouTube unlisted / Loom / Drive 'anyone with link'), (c) team names + a contact email. One submission per team, name: Clearsight, Track 2.
2. **Demo video (2 min MAX, not 3):** run `python3 tools/xlsx_to_dev.py && system/run data/dev output/dev.jsonl && python3 ui/serve.py`, open http://127.0.0.1:8765 and screen-record Fathom following `deck/PITCH.md`. Show one SAME_ENTITY, one DIFFERENT_ENTITY and one REVIEW case, plus the cited evidence.
3. **Hand-check 20 clearances** (section 2 below). Put any hit_ids that look unsafe in `REVIEW_NOTES.md` and push.

Timeline: everything gets merged to `main` by about 16:30. Don't edit `system/decide.py` or `system/hitfacts.py`; Grok Bot + T3 agents are changing those.

---

The working system is on `bot/core-system` (this branch is based on it). Run it:

```sh
python3 tools/xlsx_to_dev.py   # rebuild data/dev from the dataset sheet (see FORMAT.md)
system/run data/dev output/dev.jsonl
python3 tools/score.py output/dev.jsonl data/dev/practice_labels.jsonl -v
```

Current dev: 50/50 practice correct, 0 unsafe clearances, 26.5% review rate.
Zain + Grok Bot are hardening `decide.py` / `hitfacts.py` for the unseen set — avoid editing those to prevent conflicts.

## 1. Submission + demo owner (highest priority)
- [ ] Find the submission portal (/submit on the hackathon site) and confirm exactly what it needs (repo link, video, README path).
- [ ] Record the demo video (≤3 min): problem → one SAME / one DIFFERENT / one REVIEW case → how evidence is cited → determinism → stats.
- [ ] Write the 3-minute live pitch script for the Top 5 demo.

## 2. Edge-case review (your judgement as a human analyst)
- [ ] Open `output/dev.jsonl`, pick 20 DIFFERENT_ENTITY decisions at random and check each against the data. Any that look unsafe (could actually be the customer) → note the hit_id in `REVIEW_NOTES.md`.
- [ ] Do the same for 10 REVIEW decisions — could any be safely decided?

## 3. README polish
- [ ] Read `system/README.md` as a judge would (Google sanctions, Checkout, Visa, AmEx, UBS). Tighten wording, make sure the architecture section answers: how people are resolved on both sides, how evidence is represented, how it stays deterministic, what it's honest about missing.

Commit on `akin/work` and push; ping Zain when done.
