# Track 2: Same person or not? A deterministic, rule-based screening resolver

```
system/run <data folder> <output file>       # e.g.  system/run dev output/dev.jsonl
```
Python 3 standard library only. No network, no language model, no API key. A full dev run (819 hits, 72k customer records) takes about 6 s on one core and costs nothing.

## Architecture

```
alerts.jsonl ─┐
              ▼
 (1) resolve.py   CUSTOMER RESOLUTION
     follow the alert link: account_ref → accounts (joint holders) | login_handle → accounts | email → customers
     no link → search customers by screened name (name-part index + variants), DOB, country, city
     several linked records → the screened details choose between them
     group records into PEOPLE with union-find: same phone + same full DOB, or same document number on approved KYC checks
              │  1..n people
              ▼
 (2) profile.py   CUSTOMER PROFILE (one per person; every fact keeps its source record IDs)
     record names, declared DOBs, residence and nationality (CUS-…)
     KYC provider checks via accounts → onboarding → applicant (KYC-…); onboarding-team write-ups parsed from notes (NOTE-…)
     verified beats declared: the most recent APPROVED check gives legal name, DOB and document country; rejected or expired checks are ignored
     other notes add places the customer lived (NOTE-…)
              │
 hits.jsonl ──┤
              ▼
 (3) hitfacts.py  HIT FACTS
     names and aliases, entity type, countries (countries, nationality, citizenship, last part of each address, place of birth;
     "International"/"Europe" dropped), possible birth dates: dobs field → first paragraph of profile notes ("born …",
     "aged 45 in March 2019" → 1973/1974) → only if neither gives one, search results whose query is the hit's name AND that use
     the hit's listing phrase AND name a hit country (SR-…). Earliest "According to …; <date>:" report, date of death.
              ▼
 (4) decide.py    POLICY RULES  →  decision, reason_code, customer_record_id, reason, evidence
     clear only on a contradiction: ENTITY_TYPE > DECEASED > TEMPORAL (<16 at earliest report) > DOB (every hit date contradicted,
     ±1 year tolerance) > NAME_MISMATCH_VERIFIED (verified legal name only) > LOCATION (no shared country, and not when name+DOB agree)
     confirm only on agreement: person = name + DOB agree; company = name + country agree
     otherwise REVIEW / INSUFFICIENT_DATA; several people fit and disagree → REVIEW / AMBIGUOUS_CUSTOMER_RECORD
```
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
- All 819 dev hits: 466 DIFFERENT_ENTITY (57%), 136 SAME_ENTITY, 217 REVIEW (26.5% review rate).

## Three cases
1. **Clear mismatch: H-D861DA → DIFFERENT_ENTITY / DOB_MISMATCH.** The alert's account ACC-A82365 is a joint account (CUS-804632 and CUS-902175), and the screened name and DOB pick CUS-804632. That customer's latest approved identity check is an onboarding note, NOTE-8548C1, giving a DOB of 1979-11-08. The hit has no `dobs` field, but its profile notes give an age at a date, so it was born in 1976 or 1977. 1979 is more than one year outside both years, so the hit is cleared, citing NOTE-8548C1.
2. **Match: H-582410 → SAME_ENTITY / NAME_DOB_LOCATION_MATCH.** The same joint-account resolution gives CUS-377745. Verified DOB 1968-03-05 (NOTE-14E25A) is one of the hit's possible years (1967 or 1968, from "a 30-year-old … November 1998"). Spain is shared through the customer record, and the name agrees with "Elvira Velasco Morillo". Evidence: NOTE-14E25A, CUS-377745.
3. **Left for review: H-CDEC83 → REVIEW / INSUFFICIENT_DATA, customer AMBIGUOUS.** The alert has no link. Name, DOB, country and city fit two different people (CUS-037213 and CUS-565167; CUS-892985 is the same person as one of them). Each shares Panama with the hit and agrees on the name "Juan González", but the hit gives no birth date to compare. Both people lead to REVIEW, so the decision is REVIEW and `customer_record_id` is `AMBIGUOUS`.

## Honest limitations
- **Free text is parsed with patterns, not a model.** Onboarding identity notes are read like this. The name is the longest upper-case token run; if there is none, it is a run of Capitalised words that shares a name part with the person's own records. The DOB is the date nearest a birth keyword (not the note's own date). The document country is a country or demonym outside the name. A note naming a rejected, failed or expired check is not evidence. A name read from a note is used only if it shares at least one part with the person's own records, which guards against parser garbage. Stress test: we rewrote every dev KYC note with Title-Case names. One decision moved (SAME → REVIEW) and none moved towards clearing.
- **Age statements** in hit notes and search snippets are recognised by a set of cue patterns ("aged 45", "45-year-old", "(45)", ", 45,", "at the age of", "was 45", "Age: 45"). A new phrasing for an age means no DOB from that sentence. That leads to REVIEW, never a wrong clearance.
- **DD/MM/YYYY is assumed day-first.** An impossible month falls back to the year only.
- **The dev JSONL files were rebuilt from the organisers' browsing workbook.** The original dev/ files were not publicly downloadable. The loader accepts list fields either as JSON arrays or as "; "-joined strings, and structured address dicts with a `country` key. Profile notes over 32,000 characters were cut in the workbook.
- **Unresolved alerts** (no record fits) go to REVIEW with `customer_record_id = null`. We never clear on unverified screened data alone. This did not happen in dev.
- **The policy's rules are applied literally.** For example, a location clear only needs every customer country to differ from every hit country. If the bank's systems are missing a country the customer is linked to, that clear can be wrong. That risk comes from the policy, not from the code.
