# Clearsight: the 12 hardest judge questions

Answers are short enough to say in under 30 seconds. Numbers were checked at 60f640f; see the source table in `DEMO_SCRIPT_3MIN.md`.

---

**1. 50 out of 50 on practice: are you just overfitting 50 labels?**
Fifty labels is a sanity check, not proof, and we say so. We wrote the rules from POLICY.md, not from the labels, then tested on data the labels never touched. On 559 synthetic hits with brand-new customers and new phrasing, we got 97.9% right with 0 unsafe clears. All 12 misses were clears we sent to review, which costs 2 or 3 points, never 60. On top of that, 16 rewordings of the real data moved zero decisions toward clearing.

**2. Why no LLM? Isn't that the obvious tool for messy free text?**
The scoring punishes one wrong clear 20 to 30 times harder than anything else, and the hidden set runs five times. A model that's right 99% of the time but varies between runs is a liability there. Our output is byte-identical across runs, takes about 16 seconds for 819 hits, and every reason is built from record IDs we can point to. Free text is read with patterns. When a pattern fails, we lose a fact, and a lost fact can only lead to review.

**3. Where can you still unsafely clear?**
Single-ground clears are the risk: 217 dev clears rest on location alone and 79 on a verified name alone. They follow the policy literally, but some look risky in practice, like a bank branch listed in another country or two names sharing a single part. We list them in the README rather than hide them. In production, they're the first thing we'd route to sampled QA in Fathom.

**4. Your review rate is 28%. Isn't that just pushing the work back onto analysts?**
Review is the cheap error: 2 or 3 points against 60. We still clear 464 of 819 hits (57%) and confirm 125 more, so analysts see 230 instead of 819, which cuts the queue by 72%. Most of the 230 are genuinely missing a fact, usually a date of birth on one side. Even the shadow-set misses all went to review.

**5. How do you find the right customer among 72,265 records?**
We follow the alert's hard link first: account reference (including joint holders), login handle, or email. Without one, we search on the screened name, date of birth, country and city. Records sharing a phone number and full date of birth, or a document number on an approved ID check, are merged into one person. If two different people fit and would get different outcomes, the answer is review with an ambiguous customer. That happens on 16 dev hits, including H-009799. If nobody fits, the answer is review too.

**6. Two customers fit, but they'd get the same outcome. What then?**
We return that outcome, because the answer doesn't depend on which person was screened. We only escalate ambiguity when it changes the decision, so in H-009799 we escalate: one candidate clears and the other needs review. A clear also has to hold for anyone the city spelling alone ruled out (Munich against München). If it doesn't hold for them, the hit goes to review.

**7. In the demo, H-4D76E3 and H-EA68B7 are both SAME_ENTITY for the same sanctioned person, but on different customer records. Isn't that a contradiction?**
No, it's the safe direction. The same person can be onboarded twice. CUS-401918 only has February 1968 on its check, so we can't prove it's the same customer record as CUS-970916, and we don't merge without a hard link. Both get flagged. The real disaster would be clearing one of them, and H-C864DC shows we only clear when a verified 1993 birth date rules him out.

**8. How do you know your evidence citations are right, not just plausible?**
Every customer fact is stored with the record IDs it came from, so the citation comes from the same fact the decision used, not from a search afterwards. A DOB clear cites the DOB source and a location clear cites every source of every customer country. On all 50 practice labels, our cited evidence matches the reference exactly (Jaccard 1.00), and the reason code and customer record are right on all 50.

**9. The hidden set has ~550 unseen hits with new wording. Why should it hold?**
We attacked the parser ourselves with 16 rewordings: surname-first and lower-case names, dates like "3rd March 1970" and "03/03/70", reworded notes and search results. No rewording moved a decision toward clearing. All of them combined changed 4 of 819 decisions, every one to review. A new phrasing we don't understand costs us a review, not a 60-point clear.

**10. What did you get wrong along the way?**
H-009799. An earlier build cleared it on a timeline argument, reading "January 1997" as a dated report. POLICY.md defines a dated report as a full date. Our own cross-check audit flagged it, and commit 60f640f now clears on time only from full dates. It's a policy test now (`month_only_report`), and the hit goes to review as an ambiguous customer. We'd rather show you the bug than pretend there wasn't one.

**11. Is it deterministic, really? Hash seeds, dict order, dates?**
There's no model, no network, no randomness and no clock: the screening date comes from the data. Every input is sorted by ID before we loop over it, merge roots are the smallest record ID, and ties between checks on the same date break on check ID. Two fresh runs come out byte-identical to each other and to the committed `output/dev.jsonl`. Any unexpected error on a hit falls back to review, so every hit always gets one line.

**12. Would a real compliance team use this, and what's the next step?**
The design fits how compliance gets audited: every decision is a reason code, two to four sentences and record IDs a regulator can open. Fathom puts the customer and list entry side by side with conflicts highlighted, so a reviewer can check a call in seconds. The next steps are sampled QA on single-ground clears, then growing the labelled set from analyst decisions made in Fathom and re-scoring against them.

---

### Quick numbers card

- Dev: 819 hits, 440 alerts, 72,265 customers. Decisions: 464 DIFFERENT / 125 SAME / 230 REVIEW (56.7% / 15.3% / 28.1%).
- Official `validate.py` on practice: 50/50, 0 unsafe, decision score 100.0; code and customer 100%; evidence Jaccard 1.00 (local scorer). Practice cost 0 against an all-review baseline of 108.
- Shadow (559 synthetic hits): 97.9% right, 0 unsafe, score 0.965.
- Rewordings: 16 single rewordings, 0 flips toward clearing; all combined, 4 of 819 change, all to REVIEW.
- 102 automated checks (41 policy, 21 age parser, 22 name matcher, 18 unit). About 16 s per full run, byte-identical every time.
- Scoring: an unsafe clear costs 60, any other error 2 or 3. The hidden set is ~550 hits run 5×.
