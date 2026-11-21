# Reasons audit (bot/reasons2)

Baseline: main 60f640f. Scope: reason text and evidence only. No decision, reason code or customer record changed (checked over all 819 dev hits and a 559-hit shadow set).

## Sample

- All 50 practice hits, compared with `reference_reason` and the label evidence.
- 45 non-practice hits stratified by reason code (5 per code, plus every DECEASED, ENTITY_TYPE_MISMATCH and NAME_DOB_MATCH hit), and all 16 AMBIGUOUS_CUSTOMER_RECORD hits.
- Mechanical checks on all 819 rows: sentence count, hedging words, record IDs named in the reason but missing from the evidence.

## Findings at baseline

| Check | Result |
|---|---|
| Reason code fits the policy (practice) | 50/50 |
| Evidence equals the label evidence (practice) | 50/50 exact, nothing extra, nothing missing |
| Reason text equals the reference (practice) | 22/50 word for word (22/50 after too); the rest differ only by an added context sentence, an ambiguity prefix or sentence order |
| 2 to 4 sentences | 819/819 |
| Hedging (may, might, likely, appears ...) | 0 |
| IDs named in the reason but not in the evidence | 20 rows, all with several people fitting the alert |

Problems found:

1. **AMBIGUOUS_CUSTOMER_RECORD reasons** were one run-on sentence that printed raw enum values (`CUS-1: DIFFERENT_ENTITY (NAME_MISMATCH_VERIFIED); ...`). They gave no deciding fact for any candidate, and they named candidate CUS IDs that the evidence left out.
2. **Several people, all cleared**: the reason gave only the first person's contradiction while the evidence cited every person's source (for example H-B919AD, which cites NOTE-0C692B without ever mentioning it).
3. **Context sentence on single-fact clearances**: "Apart from this, the customer's name agrees ...; the country difference is enough ..." puts agreeing facts first and the ground last. For LOCATION_MISMATCH it never said *why* a country difference is enough. Principle 6 says it is enough only when the name and date of birth do not both agree.
4. **TEMPORAL_IMPOSSIBILITY plus DOB_MISMATCH** repeated the customer's date of birth and source in two sentences in a row.
5. **Latent bug**: a customer born after the earliest report would have printed "at most 0" (clamped). No dev hit has this.
6. Raw enum values ("each leads to SAME_ENTITY") appeared in the prefix used when several people lead to the same decision.

## Changes

- `explain.py`: `explain()` also returns `lead`, the first deciding sentence. New `explain_candidates()` writes 3 or 4 sentences: who fits; what the hit would be for each person, in plain words grouped by ground; the deciding fact (with source ID) for one person it would confirm and one it would clear. Evidence adds each candidate's own CUS record. New `explain_each_cleared()` gives each person's own contradiction, and groups the rest in a 4th sentence when more than 3 people fit.
- `decide.py`: the context sentence now states the ground first ("The country difference alone clears the hit under the policy, because the name and date of birth do not both agree: ..."). When the timing sentence is shown, the DOB sentence no longer repeats the customer's date. "were not yet born" replaces a clamped age of 0.
- `screen.py`: wires in both renderers and turns enum values in the same-decision prefix into plain words.

## Before / after

H-0F3C96 (AMBIGUOUS_CUSTOMER_RECORD)
- Before: "3 different people in the system of record fit the alert (CUS-205759, CUS-390024, CUS-623367) and they lead to different decisions: CUS-205759: DIFFERENT_ENTITY (NAME_MISMATCH_VERIFIED); CUS-390024: REVIEW (INSUFFICIENT_DATA); CUS-623367: REVIEW (INSUFFICIENT_DATA). A person must decide which customer was screened." CUS-205759 was missing from the evidence.
- After: "3 different people in the system of record fit the alert (CUS-205759, CUS-390024, CUS-623367) and they lead to different decisions, so a person must decide which customer was screened. The hit would be cleared for CUS-205759 (verified legal name does not match) and left for review for CUS-390024 and CUS-623367 (nothing settles it). For CUS-205759, the customer's verified name is Matteo Romano (KYC-FB41DD), which does not match the hit's name Philippe Mathieu." The evidence now includes CUS-205759.

H-B919AD (DOB_MISMATCH, two people)
- Before: "... each leads to DIFFERENT_ENTITY. The customer's date of birth is 1995-04-20 (NOTE-36827A) but the hit's listed date of birth is 1987-06-04. Apart from this, ..."
- After: "2 different people in the system of record fit the alert (CUS-326916 and CUS-782367), and the hit is cleared for each of them. For CUS-326916, the customer's date of birth is 1995-04-20 (NOTE-36827A) but the hit's listed date of birth is 1987-06-04. For CUS-782367, the customer's date of birth is 1995-05-21 (NOTE-0C692B) but the hit's listed date of birth is 1987-06-04."

H-50E5CD (LOCATION_MISMATCH)
- Before: "... Apart from this, the customer's name agrees with the hit's name Markus Müller and the hit gives no date of birth to compare; the country difference is enough to clear the hit under the policy."
- After: "The customer is linked only to South Africa but the hit is linked only to Germany. The country difference alone clears the hit under the policy, because the name and date of birth do not both agree: the customer's name agrees with the hit's name Markus Müller and the hit gives no date of birth to compare."

H-7BF47E (TEMPORAL_IMPOSSIBILITY)
- Before: "... at most 14 when the hit's profile reports activity on 2012-05-28. The customer's date of birth is 1998-03-24 (KYC-5A1B4A) but the hit's search results put its birth year at 1959 or 1960. ..."
- After: "... at most 14 when the hit's profile reports activity on 2012-05-28. The customer's date of birth also contradicts the hit's date of birth in search results, 1959 or 1960. ..."

Unchanged on purpose: every SAME_ENTITY and INSUFFICIENT_DATA template, and the first (deciding) sentence of every clearance. These already match the organisers' reference wording word for word.

## Gates

- validate.py practice: 50/50, 0 unsafe, reason code 100%, customer record 100%. Practice evidence still 50/50 exact.
- Counts 464/125/230, unchanged. Decision, code and customer record changed on 0/819 hits. Evidence set changed on 14 hits (all with several people fitting the alert).
- `make test` passes. `tools/check_submission.py output/dev.jsonl dev` PASS.
- `tools/shadow.py`, seeds 7 and 11: 0 unsafe, scores 0.965 and 0.964, decisions and codes identical to baseline.
- Two runs give byte-identical output. Sentence counts over dev: 2: 538, 3: 261, 4: 20. Hedging: 0.

## Left open

- Evidence lists are in discovery order, not sorted. Harmless for scoring.
- When several people fit and all are confirmed or all left for review, the reason still quotes only the first person's facts. That keeps the practice reference wording.
