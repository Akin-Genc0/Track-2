# Track 2: Same person or not? A deterministic, rule-based screening resolver

```
system/run <data folder> <output file>       # e.g.  system/run dev output/dev.jsonl
```
One JSON line per watchlist hit: a decision, policy reason code, resolved customer ID, explanation and evidence IDs. The resolver uses Python's standard library; there is no model, prompt, API key or network dependency. The 819-hit dev run takes about 16 seconds on one laptop core (Apple Silicon, Python 3.11) with no API cost.

## Architecture

![Clearsight pipeline: resolve, verified facts, listed-person facts, decide, one cited line per hit](../deck/assets/architecture.svg)

```mermaid
flowchart TD
    A["alerts.jsonl + hits.jsonl<br/>one work item per hit"] --> R["resolve.py<br/>which customer was screened?<br/>account / login / email link, else name + DOB + country + city"]
    R -->|"no record"| U["REVIEW, customer null"]
    R -->|"one or more candidates"| P["profile.py<br/>verified customer facts<br/>approved KYC beats declared; each fact keeps its record IDs"]
    P --> H["hitfacts.py<br/>listed-person facts<br/>names, aliases, type, DOB or dated ages, countries, death date"]
    H --> D["decide.py (POLICY.md)<br/>contradiction: DIFFERENT_ENTITY<br/>agreement, no contradiction: SAME_ENTITY<br/>otherwise or candidates disagree: REVIEW"]
    D --> E["explain.py<br/>2-4 sentence reason + deciding evidence IDs"]
    U --> O
    E --> O["output line<br/>hit_id, alert_id, decision, reason_code,<br/>customer_record_id, reason, evidence"]
```

**Model and prompts: none.** Every decision comes from deterministic Python rules; there is no LLM, no prompt, no API key and no network call.

**Time and cost:** about 16 s for all 819 dev hits on one laptop core, $0 per run (no model calls), well under the 30-minute limit.

| Analyst question | How the resolver answers it |
|---|---|
| Which customer was screened? (`resolve.py`) | Follow the account, login or email link first. Screened details distinguish joint holders. Without a link, compare name, DOB, country and city. Group records only on phone **and** full DOB, or a shared document number on approved checks. Keep distinct plausible people separate. |
| What do we know about each candidate? (`profile.py`) | Follow accounts through onboarding to the KYC applicant, and email to support notes. The latest approved identity check supplies legal name, DOB and document country. Reject expired or failed checks; retain the source IDs behind each fact, including former residence. |
| Which facts belong to the listed entity? (`hitfacts.py`) | Read the hit's name and aliases, entity type, countries, reports and death date. For DOB, try structured dates, then profile text. A dated age yields two possible birth years. Only use a fallback search result when the query, listing context and country tie it to this hit. |
| Does the evidence settle identity? (`decide.py`) | Clear on a policy contradiction; confirm a person on name and DOB, or a company on name and country, with no contradiction. Matching name and DOB with disjoint countries goes to review. If plausible customers lead to different decisions, return `REVIEW / AMBIGUOUS_CUSTOMER_RECORD`. |
`screen.py` is the entry point. `textutil.py` handles dates (ISO, day-first D/M/Y, "17 June 1976", "June 17, 1976", month-year, year) and names. `countries.py` is an embedded gazetteer: names, ISO2 and ISO3 codes, demonyms ("Nigerian" → Nigeria) and aliases. Territories count as their own country.

**Name matching (principle 8).** Text is case-folded and accent-folded (ł, ø, ß included). Anything in brackets and all punctuation are dropped. Single letters (initials), placeholders (NA, N/A, TEST, UNKNOWN, XXX, NONE, any token with digits) and, for companies, legal forms are removed, and each part counts once. Two parts match when they are identical, sit in the same `name_variants.json` group, are written together or apart (Abdulsalam = Abdul Salam, counted as one match covering both), or are close in spelling: 1 edit for parts of 4–6 letters, 2 edits for longer parts (Levenshtein on the shorter part's length). Parts under 4 letters must be identical. Names agree when the best disjoint matching has 2 or more matches, or covers every part of the shorter name. An individual whose names have fewer than 2 real parts can be neither confirmed nor cleared on name.

## How evidence is represented
Each customer fact is stored with the set of record IDs it came from. For example, `countries = {"Spain": {"CUS-377745"}, "Nigeria": {"KYC-…", "NOTE-…"}}`, `verified_dob = ((1968,3,5), "NOTE-14E25A")`. The citations depend on the decision:
- **DOB or temporal clears:** the source of the customer's date of birth, plus any SR-… result that gave the hit its date.
- **Location clears:** every source of every customer country.
- **Name clears:** the check that gave the verified name.
- **Deceased clears:** the screened customer record (the death date is the hit's own fact).
- **Confirms and reviews:** the sources of the agreeing facts (the DOB source and the sources of the shared countries).

When several contradictions apply, the evidence is the union and the reason lists up to three of them. Reasons are generated from templates filled with this hit's own values: dates, countries, names and record IDs. `explain.py` renders every reason and enforces the brief's two to four sentences: the deciding facts first, then, if only one deciding fact applies, a sentence on what else was compared or is missing (name, date of birth, countries). For example, H-9FD80D: "The customer is linked only to Germany but the hit is linked only to Switzerland. The country difference alone clears the hit under the policy, because the name and date of birth do not both agree: the customer's name agrees with the hit's name Markus A. Müller-Kägi and the hit gives no date of birth to compare."

## Determinism
There is no randomness, no model, no network and no clock. Every input is sorted by ID before iteration. Union-find roots are the smallest record ID. Ties between checks on the same date break on check ID. `run` sets `PYTHONHASHSEED=0`, and runs with other seeds give byte-identical output (checked). A fresh-clone check of 5 runs with `PYTHONHASHSEED` 1 to 5 gave byte-identical output that matches `output/dev.jsonl` (verified 14:47 on f91f316), and the final tree's output is identical under `PYTHONHASHSEED` 0 to 3 (re-checked after the reason-wording fix). Any unexpected exception on a hit falls back to `REVIEW` instead of crashing, so a run always writes one line per hit.

Tested on Python 3.11 and 3.13.5. To verify determinism, run twice and compare hashes (`shasum -a 256` on macOS). We don't publish a fixed hash because the output changes as fixes land:

```sh
system/run dev /tmp/run1.jsonl && system/run dev /tmp/run2.jsonl
sha256sum /tmp/run1.jsonl /tmp/run2.jsonl output/dev.jsonl   # all three must match
```

**Robustness under perturbation (external test).** Across 8 perturbed copies of dev, stripping accents, swapping name order, upper-casing
hit, customer and KYC names, and rewriting ISO DOBs as "24 August 1994" changed 0 of 819 decisions. Deleting one letter in long name
parts moved 19 decisions, 18 of them towards `REVIEW`; the one move to a clear is being fixed.

## Results on the development set
- 50 practice labels: 50/50 decisions correct, 0 unsafe clearances, local decision score 1.000. Reason code fits 50/50, customer record right 50/50, evidence identical to the reference on all 50.
- All 819 dev hits: 464 DIFFERENT_ENTITY (56.7%), 125 SAME_ENTITY (15.3%), 230 REVIEW (28.1% review rate); see `audit/CROSSCHECK_JOHN.md` for the cross-check that moved one clear to REVIEW. The same run with any `PYTHONHASHSEED` gives byte-identical output.
- Final integrated tree (after merging the loader hardening and repo polish): `tools/check_submission.py` passes on `output/dev.jsonl` (every row valid, every reason 2–4 sentences, every conclusive decision cites evidence); `tests/test_policy.py` 27/27, `tests/test_ages.py` 21/21, `tests/test_textutil.py` 7/7, `tests/test_loader.py` and `tests/test_runner_boundary.py` pass; `redteam/run_all.py --strict` fails only the 2 F12 team-call cases; shadow seeds 7 and 21 score 0.965 with 0 unsafe; `tools/unseen_sim.py` shows 0 crashes, 0 missing rows and 0 moves to clear across 7 schema mutations; no `tools/perturb.py` rewrite moves a decision towards DIFFERENT_ENTITY.
- [Spot check of 20 clears and 10 reviews](../REVIEW_NOTES.md) (historical, taken at 45ddc8c): three clears warrant checking the link between the screened holder and the approved identity check; all three are still clears today (see "Shared-account KYC checks" below). The practice score does not measure this risk across the unlabelled set.

## How we score on the judges' metrics
Measured with `tools/metrics.py`, which reads our predictions and a label file and computes exactly the figures the brief's judging
reports. Definitions: an **unsafe clearance** is a `DIFFERENT_ENTITY` on a hit labelled `SAME_ENTITY` or `REVIEW` (the 60-point error);
**false positives cleared** is the share of hits labelled `DIFFERENT_ENTITY` that we clear; **clearance precision** is the share of our
clears labelled `DIFFERENT_ENTITY`; **same-entity recall** is the share of hits labelled `SAME_ENTITY` that we confirm; **review rate** is
the share we send to `REVIEW`; **decision score** is 1 − cost / cost of reviewing everything, with the brief's costs (60 / 3 / 2).

| Set | Hits | Unsafe clearances | False positives cleared | Clearance precision | Same-entity recall | Review rate | Decision score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Official practice labels | 50 | **0** | 100.0% (28 of 28) | 100.0% (28 clears) | 100.0% (12 of 12) | 20.0% | 1.000 |
| Shadow set, seed 7 | 559 | **0** | 95.3% (243 of 255) | 100.0% (243 clears) | 100.0% (126 of 126) | 34.0% | 0.965 |
| Shadow set, seed 21 | 559 | **0** | 95.3% (243 of 255) | 100.0% (243 clears) | 100.0% (127 of 127) | 33.8% | 0.965 |
| Baseline: review every practice hit | 50 | 0 | 0.0% | n/a (no clears) | 0.0% | 100.0% | 0.000 |

On all 819 dev hits (no labels) the review rate is 28.1% (230 of 819). Every shadow miss is a `REVIEW` on a hit labelled
`DIFFERENT_ENTITY` (cost 3, never unsafe); see "Shadow test set" below. The shadow generator shares authors with the system, so treat
it as a check on unseen wording, not an independent benchmark. To reproduce:

```sh
system/run dev output/dev.jsonl
for N in 7 21; do TRACK2_DEV=dev python3 tools/shadow.py gen /tmp/sh$N $N && system/run /tmp/sh$N /tmp/sh$N.out; done
python3 tools/metrics.py output/dev.jsonl dev/practice_labels.jsonl \
    /tmp/sh7.out /tmp/sh7/shadow_labels.jsonl /tmp/sh21.out /tmp/sh21/shadow_labels.jsonl --md
```

## Hardening for the unseen set
**Policy coverage.** `tests/test_policy.py` has 27 synthetic data rooms, one per rare situation, and all pass:
- name + DOB agree but the countries differ → REVIEW, not SAME (the policy says so explicitly);
- date of death after screening (no clear) and before it (DECEASED);
- company incorporated after the earliest dated report;
- rejected or expired KYC checks, and rejected KYC notes, ignored;
- placeholder-only names (neither confirmed nor cleared on name);
- two people fit and lead to different decisions → AMBIGUOUS_CUSTOMER_RECORD;
- no customer found → REVIEW with null;
- person vs company;
- territory as its own country (Puerto Rico ≠ United States);
- "International"/"Europe" not counted as countries;
- a year-only DOB agrees with a full date;
- DOB tolerance: one year off is no contradiction, two years off is;
- same year with a different month;
- a hit date written ambiguously as D/M or M/D (05/04/1980) keeps only the year;
- verified names in Title Case and lower case;
- 16 or older vs younger at the earliest dated report;
- dated reports that don't use the exact form are ignored;
- "(1) (2) (3)" list items are not ages.
- two people fit and both are cleared: the reason names each one's own countries.
- a review says which side's date of birth is missing, and a name + DOB confirm says which side has no country.

**Perturbation test.** `tools/perturb.py` rewrites a copy of the data room and counts decisions that change. It covers:
- KYC notes: names in Title Case, lower case, or surname-first; other date formats ("3rd March 1970", "03/03/70", "03-Mar-1970", "03.03.1970"); synonyms; added noise;
- hit profile notes: other age wordings, date formats and verbs;
- the hit `dobs` field in other formats; hit countries as ISO codes and demonyms;
- search snippets: ages, dates, sentence order;
- residence notes reworded;
- customer and KYC DOBs in other formats.

At first, surname-first KYC names changed 8.4% of decisions (29 of them towards clearing), and new date formats changed up to 5.6% (10 towards clearing). After the fixes, no rewording moves any decision towards DIFFERENT_ENTITY, and the combined rewrite changes at most about 0.5% (towards REVIEW). Lower-case names in KYC notes change 3.4%, all towards REVIEW: on purpose, those names are never used to clear on name.

**Fixes from this pass.**
1. Names written in capitals may now run across a comma ("KUMAR, RAJESH").
2. New date formats: ordinals, two-digit years (fixed pivot at 26, no clock), dd-Mon-yy, yyyy.mm.dd.
3. Numbers that belong to a date are never read as ages. This fixed a real bug: on "On 24/02/23, the …" the old code read "23" as an age.
4. Age cues are split into strong ones (an age word, or "was/then/at N" with unit exclusions), used everywhere, and weak ones ("Name, 48, …"), used only in search snippets. This removed an unsafe-looking dev clear: H-46F1CE had "(1) … (2) … (3)" read as ages.
5. A verified name in a note that is not capitalised can confirm or keep a hit for review but never clears on name.
6. Tokens such as "N26" are kept as name parts, so "N26 Bank AG" no longer agrees with "Danske Bank A/S"; digit-only tokens are still placeholders, and login handles lose their digit suffix.
7. An individual customer name with fewer than 2 real parts can no longer agree through a one-part hit alias.
8. Name + DOB agree with no shared country → REVIEW (12 dev hits moved from SAME_ENTITY).
9. Birth-date phrases widened ("birth date of", "born during").

## Red team (adversarial synthetic cases)
A second agent tried to make the system clear hits it should not. `redteam/cases.py` has 48 tiny synthetic data rooms (one
customer, one alert, one hit, plus notes, KYC checks and search rows where needed). Each runs the real `screen.run` and checks
that the decision is one the policy allows; `redteam/FINDINGS.md` groups them into findings F1–F12 with a risk ranking.
`python3 redteam/run_all.py --strict` is the gate.

**Before:** 36 of 48 cases failed (33 unsafe clears, 1 REVIEW that should be SAME, 2 judgement calls).
**After this pass:** 2 fail, both F12 (left as a team call, see below). The fixes are general rules, not patches for the
synthetic wording, and the safe default when unsure is REVIEW:
- **F2b / F2 ages:** "was / is / turned N" is an age only when the clause ends there or an age word follows ("was 45.",
  "was 45 when", "turned 45 in 2019"); "at N" only as "at 24," or "at 24 years old"; "were / are N" is never an age. Derived
  ages outside 16–100 are dropped. "born 1974 or 1976" keeps both years.
- **F3 dobs shapes:** an item or born-clause naming two or more years ("circa 1960-1965", "1960 to 1965", "1960, 1965",
  "1960/61") becomes the whole span, year only.
- **F5 note names:** capitals runs join across lower-case particles ("ANA MARIA da SILVA SANTOS"); titles (MR, DR, SHEIKH…) are
  not name parts; a note that names a relative (spouse, son, on behalf of…) is not identity evidence for this customer.
- **F6 note DOB / status:** dates after the birth keyword win; issue, expiry, opening and check dates are skipped; a DOB under
  16 at the check date is unreadable. "consider", "refer", "manual review", "on hold"… count as negative. A note that both
  approves and rejects is ambiguous: it never supplies clearing facts, and if counting it as approved would stop a clear,
  the hit goes to REVIEW.
- **F4 countries:** customer values with several countries ("Russia, Cyprus", "Russian/Cypriot"), lower-case codes and
  ISO-style names are all read; every country an approved note names counts; US states and Canadian provinces map to their
  country ("Newark, New Jersey" is not Jersey; "Atlanta, Georgia" counts as both Georgia and the US); historic names (USSR,
  Yugoslavia, Czechoslovakia) map to successors. A place value we cannot place blocks a location clear.
- **F1 entity type:** company / individual / unknown. Only a known company against a known individual is a contradiction.
- **F8 scripts:** no NAME_MISMATCH_VERIFIED between names that share no script (Cyrillic verified name vs Latin hit).
- **F7 placeholders:** document numbers like UNKNOWN / 000000 never merge people; 1900-01-01-style DOBs are missing.
- **F10 snippets:** a search-snippet birth date must follow "born" directly ("born in Kano; listed 2012" is not 2012).
- **F9 resolution:** a missed account_ref falls through to login_handle, then email. On an unlinked search, a clear must also
  hold for anyone excluded only by the city spelling ("Munich" vs "München"); otherwise AMBIGUOUS / REVIEW.

**Open, team call (F12):** the policy clears literally, but two patterns are risky: a support note saying the record DOB is a
typo (not an identity check, so the record DOB still clears), and a customer day/month swap (05/12 vs 12/05). Changing them
could cost practice points, so they are unchanged.

**Effect on dev:** none. Decisions, codes, customers and evidence in `output/dev.jsonl` are identical before and after all of
these fixes (the file was byte-identical until the reason wording below): the 819 dev hits never hit these patterns, so the
fixes protect the unseen set at no dev cost. Practice is still 50/50, 0 unsafe, codes, customers and
evidence 50/50; the 27 policy tests pass; no perturbation moves any decision towards DIFFERENT_ENTITY.

**Shadow test set (formats dev never shows).** `tools/shadow.py gen <dir> <seed>` builds a 559-hit policy-labelled data room
from a separate generator (findings in `redteam/SHADOW_FINDINGS.md`); `tools/shadow.py score <dir> <predictions>` scores it.
Its 92 "hard" hits use formats that never occur in dev. Before our fixes they gave 23 unsafe clears per seed, all from one
cause: a country string the gazetteer could not read was dropped, and LOCATION_MISMATCH fired on the countries left. The F4
country work above already removed all 23. This pass added: native and short country names (Polska, Sverige, Nederland, Misr,
KSA, the Emirates, the States, U.S., U.K.…); qualifiers like "(Islamic Republic of)"; every country an address names when its
last part is not a country; a residence note that says where someone lived or worked but names no known country blocks a location clear;
only "expired" (not "expires 2031-05-12") rejects a KYC note; and more age forms ("Smith, 45, was", "(45)", "now 45",
"a man of 45", "aged forty-two", "put the age of X at 39."; probes in `tests/test_ages.py`).

| shadow seed | before (hard slice) | after: whole set | unsafe |
|---|---|---|---|
| 7 | 23 unsafe, score −8.3 | 547/559 correct, score 0.965 | 0 |
| 21 | 23 unsafe, score −8.2 | 547/559 correct, score 0.965 | 0 |

The 12 remaining misses per seed are all REVIEW where the label is DIFFERENT (cost 3 each, never unsafe): death dates written
only in profile notes (we do not clear on a death date parsed from free text) and lower-case verified names (by design: a lower-case name in a note never clears on name,
item 5 under "Fixes from this pass"). The generator and the system share authors, so the in-distribution part is optimistic; dev output is unchanged.

**Reason renderer.** `system/explain.py` came from the reasons audit (`audit/REASONS.md`). Its first design cited only the
evidence for the chosen reason code; on the practice labels that alone lowered evidence agreement from 1.00 to 0.96 (H-13E1CF,
H-CF173B, H-D9BBCC, whose references cite every contradiction). It is now wired in with decide.py choosing the evidence as
before, and it guarantees two to four sentences. Before, 358 of 819 dev reasons were a single sentence; now none are.

**Shared-account KYC checks (policy reading, switch off).** Akin's spot check (`REVIEW_NOTES.md`) flagged H-006E36, H-FE1415 and
H-E954EE: the customer's own record name agrees with the hit, but the approved check gives another given name with the same
surname (record Joseph Ferrante, check MARIA MEGAN FERRANTE), which looks like a relative's check. `DOUBTFUL_LINK_REVIEW` in
decide.py sends that pattern to REVIEW instead of clearing on the verified name. It is **off**: the practice labels clear exactly
this pattern (H-2808BE record Ridwan Azeez / check CHINEDU AZEEZ, H-EDBB79, H-380854, all with one account holder and the check
on the customer's own applicant, like Akin's three). It stays off because policy principle 4 says the verified legal name
outranks the record name; the practice labels apply the policy the same way. Turned on, it moves 60 dev clears to REVIEW (practice
46/50, score 0.889). It is a one-line switch for a bank that wants to be stricter. See "Judge Q&A".

## Three cases
1. **Clear mismatch: H-D861DA → DIFFERENT_ENTITY / DOB_MISMATCH.** The alert's account ACC-A82365 is a joint account (CUS-804632 and CUS-902175), and the screened name and DOB pick CUS-804632. That customer's latest approved identity check is an onboarding note, NOTE-8548C1, giving a DOB of 1979-11-08. The hit has no `dobs` field, but its profile notes give an age at a date, so it was born in 1976 or 1977. 1979 is more than one year outside both years, so the hit is cleared, citing NOTE-8548C1.
2. **Match: H-582410 → SAME_ENTITY / NAME_DOB_LOCATION_MATCH.** The same joint-account resolution gives CUS-377745. Verified DOB 1968-03-05 (NOTE-14E25A) is one of the hit's possible years (1967 or 1968, from "a 30-year-old … November 1998"). Spain is shared through the customer record, and the name agrees with "Elvira Velasco Morillo". Evidence: NOTE-14E25A, CUS-377745.
3. **Left for review: H-CDEC83 → REVIEW / INSUFFICIENT_DATA, customer AMBIGUOUS.** The alert has no link. Name, DOB, country and city fit two different people (CUS-037213 and CUS-565167; CUS-892985 is the same person as one of them). Each shares Panama with the hit and agrees on the name "Juan González", but the hit gives no birth date to compare. Both people lead to REVIEW, so the decision is REVIEW and `customer_record_id` is `AMBIGUOUS`.

## Judge Q&A

**How do you find the customer, and the listed person?** *Customer side:* `resolve.py`, `CustomerIndex.resolve`. Follow the alert's
`account_ref`, then `login_handle`, then `email`. On a joint account, the screened name and DOB pick the holder. With no link, match on
name, DOB, country and city (`CustomerIndex.fits`). Records are grouped into one person only on phone plus full DOB, or a shared
document number on approved checks (`UnionFind`). If more than one person fits and they lead to different decisions, the hit goes to
`REVIEW / AMBIGUOUS_CUSTOMER_RECORD` (`screen.run`). `CustomerIndex.near` also checks anyone excluded only by the city's spelling.
`profile.py`, `Profile`, then follows accounts to onboarding and the KYC checks, and email to the support notes. *Listed-person side:*
`hitfacts.py`, `HitFacts`, reads the hit's names and aliases, entity type, structured DOBs, countries and death date. It also reads
dated ages in the profile text (`years_from_age`). Search results count only when tied to this listing (`build_search_index`). Names
on both sides are compared by `textutil.NameMatcher.agree_parts` (principle 8).

**Do you resolve people on the watchlist side too?** No, and on purpose. The watchlist side is per-hit fact extraction:
`hitfacts.py`, `HitFacts`, builds one fact sheet from one hit record and the search results tied to that listing. It never merges
two hits into one listed person. That is safe for three reasons. The brief asks a per-hit question: is *this* hit the screened
customer? A clear may rest only on facts that belong to that listing. If we merged hits that share a name, a date of birth or
country from one listing could be carried into another, creating a contradiction that does not exist, which is exactly how an unsafe
clearance happens. And when two hits really are the same listed person, deciding each one against the same resolved customer
gives the same answer, so nothing is lost. Cross-record resolution happens only on the customer side (`resolve.py`), where
the bank's own identifiers (accounts, logins, emails, phone plus DOB, document numbers) make the grouping verifiable.

**How is evidence represented?** Every customer fact in `profile.Profile` is stored with the set of record IDs it came from, for
example `countries = {"Spain": {"CUS-377745"}}`. `decide.Decider.decide_person` cites only the sources of the facts that decided the
hit. See "How evidence is represented" above. Practice evidence agrees with the references on all 50 (Jaccard 1.00).

**How do you keep runs the same?** There is no model, network, clock or randomness. Customer records are iterated in ID order
(`resolve.CustomerIndex`), and hits in alert and hit ID order (`screen.run`). Union-find roots are the smallest ID (`resolve.UnionFind`). Ties break on check ID. `system/run` pins
`PYTHONHASHSEED=0`, and the output is byte-identical across seeds (see "Determinism"). Any exception on one hit falls back to
`REVIEW` (`screen.fallback`), so every hit still gets a line.

**Do the explanations say what is missing?** Yes. `explain.explain` enforces two to four sentences, with the deciding facts first.
`decide.Decider.decide_person` adds what was compared or is missing: whose date of birth is absent ("the hit gives no date of birth
to compare with the customer's"), why no country was compared, or that the names cannot be confirmed to agree. The 40-line audit is
in [audit/REASON_HONESTY.md](../audit/REASON_HONESTY.md). One known gap is open: on 13 ambiguous reviews, a candidate left for
review is summarised as "nothing settles it".

**Why rule-based, not an LLM?** The policy is a short list of explicit grounds, and an unsafe clearance costs 20 to 30 times a
review. Rules give the same answer every run, cite exact records, cost $0, need no key, and can be tested line by line against the
policy (`tests/test_policy.py`, `redteam/`). An LLM would add variance and cost exactly where the brief punishes mistakes most.
The price is that free text is read with patterns. That is why every unparsed phrasing falls to `REVIEW`, never to a clear.

**What about wording you have never seen?** The shadow sets use formats and phrasings that never occur in dev. On seeds 7 and 21
they score 0.965 with 0 unsafe; every miss is a `REVIEW` that could have been a clear (cost 3). `tools/perturb.py` rewrites dev
names, dates, ages and countries in 18 ways; no rewrite moves any decision towards `DIFFERENT_ENTITY`. `tools/unseen_sim.py`
mutates the schema; there are no crashes and no moves to clear.

**Why is `DOUBTFUL_LINK_REVIEW` off? (the 58 clears where the record name agrees but the verified name does not)** In 58 dev
clears (`NAME_MISMATCH_VERIFIED`), the customer's own record name agrees with the hit, but the approved identity check gives a
different name. Often the surname is the same and the given name differs, which can look like a family member's check on a shared
account. We follow the policy as written. Principle 4 says "verified beats declared": the most recent approved identity check
outranks the name on the customer record. The name ground for a clear applies "even if the name on their record does" agree. The
practice labels read the policy the same way and clear this exact pattern (H-2808BE, H-EDBB79, H-380854). They confirm the reading;
they are not why we chose it. A stricter bank can change this with one line: setting `DOUBTFUL_LINK_REVIEW = True` at the top of
`decide.py` makes `Decider.doubtful_link` send these hits to `REVIEW` instead of clearing on the verified name. Measured on dev, that
moves about 60 clears (60 exactly) to `REVIEW` and never adds a clear, so it can only make the system more cautious. We left it
off because the brief's policy is the spec; in production we would offer it as a bank setting, or sample these clears for QA.

**Known failure modes.**
- **Policy-literal clears that look risky:** 217 clears rest on location alone (for example, bank branch listings abroad) and 79 on a
  verified name alone. See "Honest limitations".
- **Missing countries:** if the bank's records lack a country the customer is linked to, a location clear can be wrong. This risk
  comes from the policy.
- **New phrasings:** an age or birth date written in a new way gives no date, so the hit goes to `REVIEW`. The reverse risk, a
  number misread as an age, is limited by restricting weak age cues to search snippets.
- **Team calls (red-team F12):** a support note saying the record DOB is a typo, and a day/month swap, are still cleared literally.
- **Small labelled set:** 50 practice labels cannot estimate unseen accuracy.

## Honest limitations
- **Free text is parsed with patterns, not a model.** Onboarding identity notes are read like this. The name is the longest upper-case token run; if there is none, it is a run of Capitalised words that shares a name part with the person's own records. The DOB is the date nearest a birth keyword (not the note's own date). The document country is a country or demonym outside the name. A note naming a rejected, failed or expired check is not evidence. A name read from a note is used only if it shares at least one part with the person's own records, which guards against parser garbage. Stress test: we rewrote every dev KYC note with Title-Case names. One decision moved (SAME → REVIEW) and none moved towards clearing.
- **Age statements** are recognised by cue patterns. Profile notes use strong cues only (an age word, or "was / turned N" that ends the clause or is followed by an age word); search snippets also use weak ones. Ages outside 16–100 are dropped. A new phrasing for an age means no DOB from that sentence, which leads to REVIEW, not a clearance. The reverse risk is a number wrongly read as an age, which can clear a hit. That is why weak cues are limited to search snippets that already passed the listing-phrase and country checks.
- **DD/MM/YYYY is assumed day-first.** An impossible month falls back to the year only.
- **The official input is the organisers' `dev/` folder.** Alerts nest the screened person under `customer`; hits may include a `details` dict (flattened to text, never read as a date of birth, death date, or country), `first`/`middle`/`last_name`, `best_matching_name`, `subcategories`, a null `place_of_birth`, and an integer `match_score`. `name_variants.json` uses `description` and `groups`. The loader also accepts the optional workbook reconstruction under `data/dev/` (list fields as JSON arrays or "; "-joined strings; structured address dicts with a `country` key). Profile notes over 32,000 characters were cut in the workbook form.
- **Unresolved alerts** (no record fits) go to REVIEW with `customer_record_id = null`. We never clear on unverified screened data alone. This did not happen in dev.
- **The policy's rules are applied literally.** For example, a location clear only needs every customer country to differ from every hit country. If the bank's systems are missing a country the customer is linked to, that clear can be wrong. That risk comes from the policy, not from the code.
- **Clears that rest on the policy alone (risky in the real world).** Most dev clears come from LOCATION_MISMATCH (217 clears on location alone) and NAME_MISMATCH_VERIFIED (79 on a verified name alone). They follow the SOP to the letter, but they deserve a look:
  - Branch listings, such as "N26 Bank AG - Branch" (UK or Austria) against N26 Bank AG (Germany), are cleared on location (H-19C3BF, H-E2B46A).
  - Verified names that share one part with the hit, such as "Amelia Owusu" against "Owusu-Ansah, Emmanuel Mainoo", or "IFEANYI ADELEYE" against "Adeleke, Ayodele", are cleared because one matched part is not enough under principle 8.
  - Company names that differ only by a legal form, such as "STILE ITALIANO S.R.L. GmbH" (Austria) against "STILE ITALIANO S.R.L." (Italy), are cleared on location.

## Tests and tools
- `python3 tests/test_policy.py`: 27 synthetic rare-situation policy tests.
- `python3 tests/test_textutil.py`: name-matcher edge cases.
- `python3 tools/perturb.py <data folder> [variant…]`: the rewording test above.
- `python3 redteam/run_all.py --strict`: 48 adversarial synthetic cases (2 open, both F12).
- `python3 tests/test_ages.py`: age-cue probes (real ages read, counts and money not).
- `python3 tests/test_loader.py`, `python3 tests/test_runner_boundary.py`, `python3 tests/test_real_format.py`: loader tolerance, official-format fixtures, and per-hit fail-safes.
- `python3 tests/test_packaging.py`: `system/run` is executable and runs from any directory with spaces in paths; a missing data folder, a missing `hits.jsonl` or one with no readable hit records exits with code 2 and writes nothing; no data, workbook, `.env` or API key is tracked.
- `python3 tools/check_submission.py output/dev.jsonl dev`: submission format, provenance and 2–4 sentence check.
- `python3 tools/unseen_sim.py dev`: schema mutations (renamed, stringified, nested, missing, corrupt…); no crash, no move to clear.
- `TRACK2_DEV=<dev folder> python3 tools/shadow.py gen <dir> 7 && system/run <dir> <out> && python3 tools/shadow.py score <dir> <out>`: shadow test set.
- `python3 tools/ablate.py dev`: which dev and practice decisions depend on each component.
- `python3 tools/score.py output/dev.jsonl <data folder>/practice_labels.jsonl -v`: local cost score and reason checks.
- `python3 tools/metrics.py <predictions> <labels> [...] [--md]`: the judges' metrics (unsafe clearances, false positives cleared, clearance precision, same-entity recall, review rate, decision score).

