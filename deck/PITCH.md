# Track 2 · Sanctions screening — 3-minute pitch

Deck: `index.html` (open in any browser, works offline). Keys: ← → to move, `n` speaker notes, `f` fullscreen.
Target pace: about 140 words a minute. Timings are cumulative.

---

## Slide 1 — Title (0:00–0:12)
Hi, we're Clearsight. Track 2: "Is my customer sanctioned?" Our resolver clears the noise, never clears a match, and shows its working.

## Slide 2 — The problem (0:12–0:35)
Every screening hit lands in an analyst's queue, and most are false positives. But the errors are not equal. Wrongly clearing a real match costs 60 points; any other mistake costs two or three. A wrong clearance is twenty to thirty times worse than a review. So the goal isn't to decide everything. It's to clear only what you can prove.

## Slide 3 — Our approach (0:35–1:12)
That's our rule, built into the code: clear only on a contradiction, confirm only when the facts agree, otherwise review. Four stages. Resolve finds the customer through an account, login or email link, or by searching name, date of birth, country and city, and merges duplicate records. Profile builds the customer's facts; the latest approved ID check wins. Hit facts reads names, aliases in any script, countries, birth dates and date of death. Decide applies the policy. Plain Python, no model, no network: six seconds for all 819 dev hits.

## Slide 4 — Evidence you can audit (1:12–1:32)
Every fact we hold carries the record ID it came from. When we say this customer was born on 5 March 1968, we cite NOTE-14E25A, the passport check, and that ID goes straight into the evidence list. The reason uses this hit's own dates, countries and names.

## Slide 5 — Fathom (1:32–1:55)
This is Fathom, our analyst view. All 819 hits, customer and list entry side by side, agreements and conflicts highlighted, with decision, reason and evidence. Here, Mohammad Nadeem Ghani: name, date of birth and country all agree, so it's a true match.

## Slide 6 — Results (1:55–2:12)
On the 50 practice labels: 50 out of 50 decisions correct and zero unsafe clearances. Reason code, customer record and evidence match the reference on all 50. Across the dev set we clear 57 percent of hits and send 28 percent to review.

## Slide 7 — Robustness (2:12–2:37)
The unseen set rewords the free text, so we attacked ourselves. A harness rewords our data 17 ways: surname-first names, dates like "third March 1970", lower-case names. Before hardening, one rewording flipped up to 29 decisions toward clearing. After: zero, on every rewording. All combined, only 2 to 4 of 819 change, all toward review. And output is byte-identical across runs.

## Slide 8 — Honest limits (2:37–3:00)
What's missing: 50 labels is a small sample. 214 clears rest on location alone and 79 on a verified name alone. Some, like bank branches abroad, follow the policy literally but look risky; we flag them in the README. Next: route those to sampled QA in Fathom. Safe by design, auditable by default. Thank you.

---

## Likely judge questions

**1. How do you resolve people on both sides: the customer and the list entry?**
Customer side: we follow the alert's link first (account reference, including joint holders, login handle, or email). With no link, we search customers on the screened name, DOB, country and city. Records that share a phone and a full DOB, or a document number on an approved ID check, are merged into one person. If two different people fit and lead to different decisions, the answer is REVIEW with the customer marked ambiguous. If nobody fits, it's REVIEW with no customer; we never clear on unverified screened data alone. List side: we gather names and aliases (including non-Latin scripts), entity type, countries, birth dates from the DOB field, the profile notes or matching search results, the earliest dated report and any date of death.

**2. How is evidence represented?**
Every customer fact is stored with the set of record IDs it came from, for example Spain from CUS-377745, a verified DOB from NOTE-14E25A. The citation follows the decision: a DOB clear cites the DOB source, a location clear cites every source of every customer country, a name clear cites the check that gave the verified name. The latest approved ID check wins; rejected or expired checks are ignored. On all 50 practice labels our cited evidence is identical to the reference.

**3. How does it stay deterministic?**
No model, no network, no randomness, no clock. Every input is sorted by ID before we loop over it, merge roots are the smallest record ID, and ties between checks on the same date break on check ID. Output is byte-identical across runs and across different Python hash seeds, and our eval harness has a 5-run reproducibility check. Any unexpected error on a hit falls back to REVIEW, so a run always writes one line per hit.

**4. The unseen set has new customers and different wording. Why trust it?**
We built a harness that rewords the data 17 ways. Before hardening, one rewording flipped up to 29 decisions toward clearing. After, no rewording moves any decision toward clearing, and all 17 combined change only 2 to 4 of 819 decisions, every one toward REVIEW. When the parser doesn't understand a new phrasing, it loses a fact, and a missing fact leads to REVIEW, not a clearance. We also have 23 tests for rare policy situations, such as a date of death after screening or a DOB one year off.

**5. What's missing? Where would this go wrong?**
Fifty labels is a small sample, so a perfect practice score is a sanity check, not proof. 214 dev clears rest on location alone and 79 on a verified name alone. Some follow the policy literally but look risky in practice: bank branch listings in other countries, or names sharing a single part. We list examples in the README rather than hide them. Free text is read with patterns, not a model, so a new way of writing an age gives no date and goes to review. Next we'd send those single-signal clears to sampled QA and grow the labelled set from analyst decisions in Fathom.
