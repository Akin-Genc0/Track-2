# Reason honesty audit (40 lines, every reason code)

**Question.** Does each reason state this hit's own facts, say what is missing where that matters, and cite only the records that
decided it?

**Sample.** 40 lines of `output/dev.jsonl` at main c7fd5d3, covering all 11 reason codes. Within each code, hits are ranked by SHA-256
of `reason-honesty-v1|<hit_id>` and taken in order: the single ENTITY_TYPE_MISMATCH line, 3 DECEASED, 3 NAME_DOB_MATCH, and the other
33 spread over the 8 remaining codes (5 for LOCATION_MISMATCH, 4 for each of the rest). The seed is fixed, so lines were not picked by
outcome. Sampled hits: H-167095, H-BD709E, H-C85D81, H-5EEC5A, H-FC00CD, H-32F871, H-DFB2B9, H-573307, H-DC6F0F, H-4C4C40, H-D6500B,
H-0A78C7, H-B5160F, H-FF3096, H-7D0FAB, H-787BB9, H-F50B21, H-69E217, H-6AD21E, H-6E0574, H-8E3FA2, H-63D89C, H-3A6138, H-B919AD,
H-8C2C2E, H-EAF7D9, H-4D76E3, H-B79C82, H-97993F, H-A53736, H-7FA297, H-33106C, H-16B821, H-D9BFBD, H-765FED, H-B6A2ED, H-BC3D73,
H-9AD76C, H-FAF2D2, H-EDED17.

## Result

| Check | Before | After the fix | Notes |
| --- | --- | --- | --- |
| States this hit's own facts (dates, countries, names, record IDs) | 40/40 | 40/40 | No generic or copied text. The values come from this hit and this customer |
| Says what is missing where it matters | 32/40 | 38/40 | The 6 fixed lines and the 2 still open are listed below |
| Cites only the deciding records | 40/40 | 40/40 | Every cited ID is the source of a fact the reason states. Clears with several contradictions cite each one they state |
| 2 to 4 sentences | 40/40 | 40/40 | `tools/check_submission.py` passes on all 819 lines |

**Fixed in `system/decide.py` (`Decider.decide_person`). Wording only: decisions, codes, customers and evidence are identical to main on all 819 lines.**

1. **A review did not say which date of birth was missing.** H-B5160F, H-FF3096 and H-787BB9 said "the date of birth cannot be
   compared with it". They now say "the hit gives no date of birth to compare with the customer's". Where the customer has none,
   or neither side has one, the reason says that instead. This changed 190 dev reviews.
2. **A NAME_DOB_MATCH confirmation did not say why no country was compared.** H-FC00CD, H-32F871 and H-DFB2B9 named only the date
   of birth and the name. They now add, for example, "No country could be compared because the hit lists no country, so the match
   rests on name and date of birth." This changed 4 dev reasons.

Both are pinned by `tests/test_policy.py` cases 25 (`review_says_hit_dob_missing`, `name_dob_match_says_country_missing`).

**Still open (wording only).** On two `AMBIGUOUS_CUSTOMER_RECORD` reviews (H-9AD76C, H-EDED17), a candidate that would be left
for review is summarised as "nothing settles it". The decisive fact, that several people fit and lead to different decisions, is
stated, and the cleared or confirmed candidate's own fact is quoted. The four-sentence cap leaves no room for a fifth sentence on
what that candidate lacks. 13 of the 819 dev lines use the phrase.

**Evidence and wording.** Across all 819 lines, 451 of the 1,695 cited IDs appear word for word in the reason. The others are the
sources of facts the reason states without naming the record: mostly customer records (CUS-…) and the checks behind a shared or
contradicting country. This follows the rules in system/README.md, "How evidence is represented". It matches the practice
references: evidence agrees on all 50 (Jaccard 1.00). No line has empty evidence.

**Gates after the fix.** Practice 50/50, 0 unsafe, reason code and customer record 100%. Shadow seeds 7 and 21 both score 0.965
with 0 unsafe. `redteam/run_all.py --strict` gives 34 FIXED, 12 HOLDS and 2 VULNERABLE (F12, unchanged). `make test` passes. The
output is byte-identical across `PYTHONHASHSEED` values.
