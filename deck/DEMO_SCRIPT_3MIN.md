# Clearsight: 3-minute live demo script

Pace is about 140 words a minute, and the timings are cumulative. **Bold** lines are what you say, word for word. Lines marked ▶ are what you do on screen.
Every number and hit ID below was checked against `output/dev.jsonl` at 60f640f and the official `validate.py` (see "Source of every number" at the end).

---

## Before you walk on (setup, not timed)

```sh
ln -sfn ~/Track-2-data/screening/dev dev   # the UI reads ./dev (gitignored; never commit it)
python3 ui/serve.py                          # http://127.0.0.1:8765/
```

- Open four browser tabs in this order:
  1. `http://127.0.0.1:8765/#H-4D76E3`
  2. `http://127.0.0.1:8765/#H-C864DC`
  3. `http://127.0.0.1:8765/#H-13E1CF`
  4. `http://127.0.0.1:8765/#H-009799`
- Keep a terminal ready with the official scorer command already typed (step 5).
- Check that the top bar shows real predictions and no "sample predictions" banner: practice score 100, 0 unsafe.
- Fallback if the laptop or Wi-Fi fails: `ui/screenshots/02-sanctions-match-ghani.png`, `03-cleared-temporal.png` and `05-ambiguous-review.png`, plus deck slides 5 and 6.

---

## 1. Hook: the problem (0:00–0:20)

▶ Deck slide 2 (cost table), or the Fathom queue on tab 1.

**"Every bank screens every customer against sanctions lists, and nearly every hit is noise. Analysts burn hours clearing them. But one wrong clearance means you have just banked a sanctioned drug trafficker. The scoring here says exactly that: a wrong clear costs 60 points and every other mistake costs 2 or 3. So the job isn't to clear everything. It's to clear only what you can prove."**

## 2. What we built (0:20–0:40)

▶ Stay on Fathom and point at the counts in the top bar.

**"We're Clearsight. Our engine reads all 819 dev hits, finds the right customer among 72,265 records, and returns a decision, a reason code, a plain-English reason and the exact record IDs behind it. It's plain Python with no model and no network, and the output is identical on every run. This is Fathom, our analyst desk, showing those decisions."**

## 3. Live walkthrough (0:40–1:55)

### Hit 1: same name, opposite answers (0:40–1:10)

▶ Tab 1: **H-4D76E3**. Point at the list entry: OFAC SDN, match score 100.

**"Mohammad Nadeem Ghani is on the US Treasury's sanctions list for drug trafficking and money laundering. This customer's date of birth, 17 February 1968, fits the list's February 1968. Both are linked to Pakistan and the UK, and the names agree. True match, and it cites NOTE-4E8A14 so an auditor can check it."**

▶ Tab 2: **H-C864DC**. Same list entry, same match score of 100.

**"Same list entry, same 100 percent name score, different customer. This one's verified ID check, KYC-68E6D6, says born in 1993. Someone born in 1993 can't be a man born in February 1968, so we clear it, and we cite only that one record. The name score can't tell these two apart. The facts can."**

### Hit 2: a clearance a junior analyst would miss (1:10–1:30)

▶ Tab 3: **H-13E1CF**. Abdul Rahman, adverse media, drug-trafficking arrest.

**"Abdul Rahman, arrested for drug trafficking in January 2020. It's a very common name. Our customer was born in August 2007 according to KYC-358C76, so they were at most 12 when the activity was reported. That's a temporal impossibility, so we clear it. This one is in the practice labels, and we match the reference decision, code and evidence."**

### Hit 3: the one we refuse to clear (1:30–1:55)

▶ Tab 4: **H-009799**. James Gus Oliver, FINRA enforcement.

**"This is the case that matters most. Two different customers fit this alert. One would clear on location. The other has a matching name and a US tie, so they need a review. An earlier build of ours cleared this one: it read a month-only date as a dated report. Our own audit caught it, we tightened the rule, and now it goes to review as an ambiguous customer. When we're unsure, a human decides."**

## 4. Safety design (1:55–2:20)

▶ Deck slide 3, or just talk over Fathom.

**"Safety is built into the code as three rules. Clear only on a hard contradiction: date of birth, verified name, location, entity type, date of death or a timeline impossibility. Confirm only when the facts agree. Everything else goes to review. If the parser doesn't understand a sentence, we lose that fact, and a missing fact can only push a hit toward review, never toward a clear. If any hit errors out, it falls back to review."**

## 5. Results (2:20–2:45)

▶ Terminal: run the official scorer.

```sh
python3 ~/Track-2-data/screening/validate.py --data ~/Track-2-data/screening/dev --output output/dev.jsonl --score ~/Track-2-data/screening/dev/practice_labels.jsonl
```

**"This is the organisers' own scorer: 819 lines, zero problems, 50 out of 50 practice decisions correct and zero unsafe clearances. The reason code and customer record are right on every one. We also tried to break it. We reworded our own data 16 different ways, and not one decision moved toward clearing. On 559 synthetic hits with brand-new customers we never saw, we got 97.9 percent right with zero unsafe clears."**

## 6. Why we win (2:45–3:00)

▶ Back to Fathom on H-009799.

**"We clear 57 percent of the queue, every clear backed by a record ID you can open, and zero unsafe clears on every labelled set we have. The test runs five times, and we give the same answer every time. Clearsight clears the noise and never clears a match. Thank you."**

---

## Timing check

| Segment | Window | Words (approx.) |
|---|---|---|
| Hook | 0:00–0:20 | 75 |
| What we built | 0:20–0:40 | 60 |
| Ghani pair | 0:40–1:10 | 115 |
| Abdul Rahman | 1:10–1:30 | 65 |
| James Gus Oliver | 1:30–1:55 | 75 |
| Safety | 1:55–2:20 | 75 |
| Results | 2:20–2:45 | 80 |
| Close | 2:45–3:00 | 50 |

If you're running long, cut the Abdul Rahman segment (1:10–1:30). Never cut H-009799: it's the safety story.

## Source of every number (re-verify before going on stage)

| Claim | Value | How to reproduce |
|---|---|---|
| Dev set | 819 hits, 440 alerts, 72,265 customers | `wc -l dev/hits.jsonl dev/alerts.jsonl dev/customers.jsonl` |
| Official scorer | 819 lines, 0 problems; 50/50 right; 0 unsafe; decision score 100.0; code and customer 100% | `validate.py` command above |
| Practice mix | 28 DIFFERENT, 12 SAME, 10 REVIEW; all-review cost 108, ours 0 | `python3 tools/score.py output/dev.jsonl dev/practice_labels.jsonl -v` |
| Dev decisions | 464 DIFFERENT (56.7%) / 125 SAME (15.3%) / 230 REVIEW (28.1%) | count `decision` in `output/dev.jsonl` |
| Determinism | two fresh runs byte-identical to each other and to the committed `output/dev.jsonl` | `system/run dev /tmp/a.jsonl` twice, then `cmp` |
| Runtime | about 16 s for 819 hits on a laptop (15.9 s wall clock) | `time system/run dev /tmp/a.jsonl` |
| Rewordings | 16 single rewordings with 0 flips toward clearing; "all" combined: 4/819 flips, all to REVIEW | `python3 tools/perturb.py dev` |
| Shadow set | 559 synthetic hits (seed 7): 547 correct (97.9%), 0 unsafe, score 0.965; all 12 errors are DIFFERENT→REVIEW | `tools/shadow.py gen <dir> 7`, `system/run <dir> p.jsonl`, `tools/shadow.py score <dir> p.jsonl` |
| Tests | 59 checks: 24 policy, 21 age parser, 14 unit | `make test` |
| H-4D76E3 | SAME / NAME_DOB_LOCATION_MATCH, CUS-970916, evidence NOTE-4E8A14, CUS-906311, CUS-970916 | `grep H-4D76E3 output/dev.jsonl` |
| H-C864DC | DIFFERENT / DOB_MISMATCH, CUS-553603, evidence KYC-68E6D6 | `grep H-C864DC output/dev.jsonl` |
| H-13E1CF | DIFFERENT / TEMPORAL_IMPOSSIBILITY, CUS-364225, practice-labelled and correct | `grep H-13E1CF output/dev.jsonl` |
| H-009799 | REVIEW / AMBIGUOUS_CUSTOMER_RECORD (CUS-018587 REVIEW, CUS-489904 DIFFERENT); fixed in 60f640f | `grep H-009799 output/dev.jsonl`; `audit/CROSSCHECK_JOHN.md` |

**Stale numbers in `deck/index.html` and `deck/PITCH.md`** (the lead owns the deck, so fix them there): "~6 s" is now about 16 s; "465 / 229" is now 464 / 230; "56.8%" is now 56.7%; "23 policy tests" is now 24; "17 rewordings" is 16 single rewordings plus 2 combined runs. Every other number on the results and robustness slides still holds.
