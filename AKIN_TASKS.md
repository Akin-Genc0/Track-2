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

Current dev on the audited build: 50/50 practice correct, 0 unsafe clearances on those labels, 229/819 sent to review (28.0%).
Zain + Grok Bot are hardening `decide.py` / `hitfacts.py` for the unseen set — avoid editing those to prevent conflicts.

## 1. Submission + demo owner (highest priority)
- [ ] Find the submission portal (/submit on the hackathon site) and confirm exactly what it needs (repo link, video, README path).
- [x] Produce the portal demo (≤2 min): narrated Fathom captures, 1:39, `data/Clearsight-demo.mp4` on Akin's machine.
- [ ] Upload the MP4 to an approved link-sharing host and test playback signed out. Enter the team roster and contact email on `/submit`.
- [x] Prepare the separate three-minute Top 5 live script: [deck/PITCH.md](deck/PITCH.md).

## 2. Edge-case review (your judgement as a human analyst)
- [x] Check 20 sampled clearances against the data; priority cases and sampling method in [REVIEW_NOTES.md](REVIEW_NOTES.md).
- [x] Check 10 sampled reviews: insufficient evidence to change any of the ten.

## 3. README polish
- [x] Tighten the [system README](system/README.md) for judges and link the audit alongside the practice metrics.

Commit on `akin/work` and push; ping Zain when done.
