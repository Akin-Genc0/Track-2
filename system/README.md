# Track 2: Same person or not? A deterministic, rule-based screening resolver

```
system/run <data folder> <output file>       # e.g.  system/run dev output/dev.jsonl
```
One JSON line per watchlist hit: a decision, policy reason code, resolved customer ID, explanation and evidence IDs. The resolver uses Python's standard library; there is no model, prompt, API key or network dependency. The 819-hit dev run takes about six seconds on one core with no API cost.

## Architecture

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
- **Confirms and reviews:** the sources of the agreeing facts (the DOB source and the sources of the shared countries).

When several contradictions apply, the evidence is the union and the reason lists up to three of them. Reasons are generated from templates filled with this hit's own values: dates, countries, names and record IDs.

## Determinism
There is no randomness, no model, no network and no clock. Every input is sorted by ID before iteration. Union-find roots are the smallest record ID. Ties between checks on the same date break on check ID. `run` sets `PYTHONHASHSEED=0`, and runs with other seeds give byte-identical output (checked). Any unexpected exception on a hit falls back to `REVIEW` instead of crashing, so a run always writes one line per hit.

## Results on the development set
- 50 practice labels: 50/50 decisions correct, 0 unsafe clearances, local decision score 1.000. Reason code fits 50/50, customer record right 50/50, evidence identical to the reference on all 50.
- All 819 dev hits: 465 DIFFERENT_ENTITY (56.8%), 125 SAME_ENTITY, 229 REVIEW (28.0% review rate). The same run with any `PYTHONHASHSEED` gives byte-identical output.
- [Spot check of 20 clears and 10 reviews](../REVIEW_NOTES.md): three clears warrant checking the link between the screened holder and the approved identity check. The practice score does not measure this risk across the unlabelled set.

## Hardening for the unseen set
**Policy coverage.** `tests/test_policy.py` has 23 synthetic data rooms, one per rare situation, and all pass:
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

**Effect on dev:** none. `output/dev.jsonl` is byte-identical before and after all of these fixes: the 819 dev hits never hit
these patterns, so the fixes protect the unseen set at no dev cost. Practice is still 50/50, 0 unsafe, codes, customers and
evidence 50/50; the 23 policy tests pass; no perturbation moves any decision towards DIFFERENT_ENTITY.

**Reason renderer not wired.** `system/explain.py` (from the reasons audit, `audit/REASONS.md`) cites only the evidence for
the chosen reason code. On the practice labels that alone lowers evidence agreement from 1.00 to 0.96 (H-13E1CF, H-CF173B,
H-D9BBCC, whose references cite every contradiction), so we kept the current templates and left the renderer unintegrated.

## Three cases
1. **Clear mismatch: H-D861DA → DIFFERENT_ENTITY / DOB_MISMATCH.** The alert's account ACC-A82365 is a joint account (CUS-804632 and CUS-902175), and the screened name and DOB pick CUS-804632. That customer's latest approved identity check is an onboarding note, NOTE-8548C1, giving a DOB of 1979-11-08. The hit has no `dobs` field, but its profile notes give an age at a date, so it was born in 1976 or 1977. 1979 is more than one year outside both years, so the hit is cleared, citing NOTE-8548C1.
2. **Match: H-582410 → SAME_ENTITY / NAME_DOB_LOCATION_MATCH.** The same joint-account resolution gives CUS-377745. Verified DOB 1968-03-05 (NOTE-14E25A) is one of the hit's possible years (1967 or 1968, from "a 30-year-old … November 1998"). Spain is shared through the customer record, and the name agrees with "Elvira Velasco Morillo". Evidence: NOTE-14E25A, CUS-377745.
3. **Left for review: H-CDEC83 → REVIEW / INSUFFICIENT_DATA, customer AMBIGUOUS.** The alert has no link. Name, DOB, country and city fit two different people (CUS-037213 and CUS-565167; CUS-892985 is the same person as one of them). Each shares Panama with the hit and agrees on the name "Juan González", but the hit gives no birth date to compare. Both people lead to REVIEW, so the decision is REVIEW and `customer_record_id` is `AMBIGUOUS`.

## Honest limitations
- **Free text is parsed with patterns, not a model.** Onboarding identity notes are read like this. The name is the longest upper-case token run; if there is none, it is a run of Capitalised words that shares a name part with the person's own records. The DOB is the date nearest a birth keyword (not the note's own date). The document country is a country or demonym outside the name. A note naming a rejected, failed or expired check is not evidence. A name read from a note is used only if it shares at least one part with the person's own records, which guards against parser garbage. Stress test: we rewrote every dev KYC note with Title-Case names. One decision moved (SAME → REVIEW) and none moved towards clearing.
- **Age statements** are recognised by cue patterns. Profile notes use strong cues only (an age word, or "was / turned N" that ends the clause or is followed by an age word); search snippets also use weak ones. Ages outside 16–100 are dropped. A new phrasing for an age means no DOB from that sentence, which leads to REVIEW, not a clearance. The reverse risk is a number wrongly read as an age, which can clear a hit. That is why weak cues are limited to search snippets that already passed the listing-phrase and country checks.
- **DD/MM/YYYY is assumed day-first.** An impossible month falls back to the year only.
- **The dev JSONL files were rebuilt from the organisers' browsing workbook.** The original dev/ files were not publicly downloadable. The loader accepts list fields either as JSON arrays or as "; "-joined strings, and structured address dicts with a `country` key. Profile notes over 32,000 characters were cut in the workbook.
- **Unresolved alerts** (no record fits) go to REVIEW with `customer_record_id = null`. We never clear on unverified screened data alone. This did not happen in dev.
- **The policy's rules are applied literally.** For example, a location clear only needs every customer country to differ from every hit country. If the bank's systems are missing a country the customer is linked to, that clear can be wrong. That risk comes from the policy, not from the code.
- **Clears that rest on the policy alone (risky in the real world).** Most dev clears come from LOCATION_MISMATCH (214 location-only) and NAME_MISMATCH_VERIFIED (79 name-only). They follow the SOP to the letter, but they deserve a look:
  - Branch listings, such as "N26 Bank AG - Branch" (UK or Austria) against N26 Bank AG (Germany), are cleared on location (H-19C3BF, H-E2B46A).
  - Verified names that share one part with the hit, such as "Amelia Owusu" against "Owusu-Ansah, Emmanuel Mainoo", or "IFEANYI ADELEYE" against "Adeleke, Ayodele", are cleared because one matched part is not enough under principle 8.
  - Company names that differ only by a legal form, such as "STILE ITALIANO S.R.L. GmbH" (Austria) against "STILE ITALIANO S.R.L." (Italy), are cleared on location.

## Tests and tools
- `python3 tests/test_policy.py`: 23 synthetic rare-situation policy tests.
- `python3 tools/perturb.py <data folder> [variant…]`: the rewording test above.
- `python3 redteam/run_all.py --strict`: 48 adversarial synthetic cases (2 open, both F12).
- `python3 tools/score.py output/dev.jsonl <data folder>/practice_labels.jsonl -v`: local cost score and reason checks.

