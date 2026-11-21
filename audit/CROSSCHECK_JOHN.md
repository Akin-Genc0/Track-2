# Cross-check against John's engine and an unsafe-clear audit

Base: `bot/crosscheck3` at 3e63dfc (output 465 DE / 125 SAME / 229 REVIEW; official `validate.py` on practice: 50/50, 0 unsafe).
John: `origin/john` 8081c31, `predictions.jsonl` (819 rows; on practice it also scores 50/50 with 0 unsafe, though `validate.py` flags one empty reason on line 50).

## 1. Disagreement matrix (819 hits, joined on hit_id)

| ours \ John | DIFFERENT_ENTITY | SAME_ENTITY | REVIEW |
|---|---|---|---|
| **DIFFERENT_ENTITY** | 462 | 2 | 1 |
| **SAME_ENTITY** | 0 | 123 | 2 |
| **REVIEW** | 2 | 0 | 227 |

812/819 agree. None of the 7 disagreements is a practice hit.

## 2. The 7 disagreements, judged against POLICY.md

Ours = DIFFERENT_ENTITY, John = SAME/REVIEW (the possible unsafe clears; 3 hits):

| hit | ours | John | verdict |
|---|---|---|---|
| H-009799 | DE TEMPORAL (AMBIGUOUS: CUS-018587, CUS-489904) | REVIEW AMBIGUOUS | **John right: an unsafe clear.** The only "dated reports" are `According to FINRA; January 1997:` and `; December 1998:`. These are month-only, but §5 says dated reports are *exactly* the `…; September 10, 2025:` form. Without them, CUS-018587 (KYC-EB6D3E) has the name agreeing, no hit DOB and a US tie in the notes, so REVIEW. The two people disagree, so the hit is REVIEW AMBIGUOUS. Fixed (below). |
| H-124BB8 | DE NAME_MISMATCH_VERIFIED (CUS-157927, KYC-19EDAD) | SAME NAME_LOCATION | **Ours right.** Verified name "Starling Logistics Ltd" against "ST Logistics (UK) Ltd.": the brackets and legal form are dropped. `st` has fewer than 4 letters, so it must match exactly and does not. That leaves 1 matching part, and the shorter name is not fully covered. The alias "Chartered Material Services" doesn't match either. |
| H-4A2E8B | DE DOB_MISMATCH (CUS-530254, NOTE-69BF3E) | SAME NAME_DOB_LOCATION | **Ours right, small residual risk.** Customer 1962-06-10 against hit `dobs` 1962-09-10: same year and day, different month, so §6 contradicts it. John also counts 1961/1962 from the BOP block's "Age: 55 … as of December 13, 2017". The practice label for the same profile (H-58A39C) gives the hit's DOB list as only "1962-09-10", so the reference generator uses `dobs` and ignores that block. Kept. |

Ours = not DE, John = DE (unsafe for John, not us; 2 hits):

| hit | ours | John | verdict |
|---|---|---|---|
| H-8A1D28 | REVIEW | DE LOCATION | Ours right: NOTE-C1E05D says the customer lived and worked in Nigeria 2014–2022, so the Nigeria tie blocks the location clear. |
| H-15D291 | REVIEW | DE LOCATION | Ours right: NOTE-AA57EF says the customer lived in the US 2015–2016. |

SAME vs REVIEW (2 hits): H-792AF1 and H-8AB284. **Ours right.** John misses the first-paragraph age sentences: "Mark E Phillips, at 24, … May 1999" gives 1974/75, and "November 1981 … Pere Punti, then 37" gives 1943/44. Both agree with the customers' verified DOBs (NOTE-2A2EF3, KYC-911CAB).

## 3. Independent audit: 40 non-practice DE decisions, stratified by reason code

Non-practice DE population: LOCATION 199, NAME_MISMATCH_VERIFIED 121, DOB 88, TEMPORAL 24, DECEASED 4, ENTITY_TYPE 1.
Sample (seeded): 12 LOCATION, 10 DOB, 8 NAME, 5 TEMPORAL, 4 DECEASED, 1 ENTITY_TYPE.

| code | hits | finding |
|---|---|---|
| LOCATION | H-732DED, H-E3C4E3, H-4D89A9, H-DBFE06, H-043339, H-C417BC, H-1A98B8, H-84C44F, H-14A67F, H-184EAC, H-AF6CD2, H-239BBB | All correct. Customer countries come from all linked records (e.g. CUS-553603 + CUS-435654, same phone and DOB), approved checks and residence notes (NOTE-B492AD Portugal). None share a country with the hit. Where the name agrees, the DOB does not (H-AF6CD2: 1983-04-27 against 1983-08-28 / 1982 / 1985). |
| DOB | H-CD0602, H-C864DC, H-8E3FA2, H-806C8A, H-B919AD, H-9A0CFC, H-FB1E2D, H-E40256, H-75A4DD, H-D473EA | All correct. The search-result DOBs (SR-4BFF79, SR-F2D13D, SR-DBC85C) match the listing phrase and a hit country. H-8E3FA2: 1981 against 1978/79 is more than 1 year out. H-75A4DD: same month, different day. |
| NAME | H-4404CB, H-94363A, H-831876, H-92814C, H-AF063F, H-3205C2, H-A8B1C3, H-EB69BA | Decisions correct. H-3205C2 (Markus Müller / Mark Mueller): mark and markus are in *different* groups in name_variants, so the name mismatch stands. The DE→US location mismatch also clears it. |
| TEMPORAL | H-D6AE72, H-009799, H-7BF47E, H-16B821, H-3A7B8E | **H-009799 and H-3A7B8E use the month-only report.** H-3A7B8E is still DE through LOCATION (UK against US). H-009799 is the unsafe clear above. The other three use full-date reports. |
| DECEASED | H-F51C73, H-167095, H-BD709E, H-C85D81 | All correct: structured `deceased_date` before `screened_at`. |
| ENTITY_TYPE | H-5EEC5A | Correct. |

Extra sweep: on every DE, I looked for customer notes that name one of the hit's countries. There were 32 matches, all on DOB, NAME, TEMPORAL or DECEASED clears and none on a LOCATION clear. So there is no location leak.

## 4. Fixes (general, not hit-specific)

1. **Dated reports need a full date** (`system/hitfacts.py`). Only `According to …; <Month D, YYYY>:` lines now feed the time contradiction. Month-only and year-only lines no longer clear. On dev the only decision change is H-009799, DE TEMPORAL → REVIEW AMBIGUOUS_CUSTOMER_RECORD. H-DC6F0F and H-3A7B8E stay DE but switch to LOCATION_MISMATCH. H-E31B13 stays TEMPORAL with a full-date report. New test `month_only_report` in `tests/test_policy.py`: it fails on 3e63dfc and passes now.
2. **No variant list, no name clear for people** (`system/decide.py`). Despite the comment in `data.py`, a data room without `name_variants.json` loads *no* groups. "Mide" vs "Olumide" and "Tunde" vs "Babatunde" then become NAME_MISMATCH_VERIFIED clears. I found this when `tools/shadow.py gen` ran without `./dev`: it exits before copying the variants file, but the data room it already wrote stays behind. Individuals are now never cleared on name when no groups are loaded. Dev output is unchanged. On shadow seed 7 with the variants file removed, unsafe goes from 4 to 1.

## 5. Gates (final tree)

- Official `validate.py` on practice: 819 lines, 0 problems, **50/50, 0 unsafe**, reason code 100%, customer record 100%.
- `make test`: test_policy 24/24, test_ages 21/21, loader / runner_boundary / real_format OK. (`python3 -m unittest discover tests` shows an import "error" for test_policy because it is a script that calls `sys.exit(0)`. This is unchanged from before.)
- `tools/check_submission.py output/dev.jsonl <dev>`: PASS.
- `tools/shadow.py` (with `./dev` present) seeds 7, 21, 1, 2, 3: **0 unsafe** on all, scores 0.965 / 0.965 / 0.962 / 0.962 / 0.962. Base and fix give byte-identical output.
- `redteam/run_all.py --strict`: only the 2 known F12 cases fail, as before.
- `output/dev.jsonl` regenerated: **464 DE / 125 SAME / 230 REVIEW** (was 465 / 125 / 229).

## Note for running shadow

`tools/shadow.py gen` needs the official folder at `./dev` (a symlink works; `dev/` is gitignored). Without it, the data room is written but has no `name_variants.json`, and every score you get from it is misleading.
