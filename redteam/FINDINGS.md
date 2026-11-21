# Red team: ways the system clears a hit (DIFFERENT_ENTITY) when the policy says SAME_ENTITY or REVIEW

```
python3 redteam/run_all.py            # 44 synthetic cases; checks each one still behaves as recorded
python3 redteam/run_all.py --strict   # checks each case gives a decision the policy allows (40 fail today)
```
Each case in `redteam/cases.py` builds a tiny data room (one customer, one alert, one hit, plus notes, KYC and search rows
where needed), runs the real `screen.run`, and records the decision. Stdlib only, no pytest. Base: `bot/core-system` @ 6f21c02.
When a fix lands, its cases print **FIXED** and the default run fails on purpose. Update the recorded `now` value, or switch the gate to `--strict`.

**Score:** 36 unsafe clears in 10 groups (F1–F10), one accuracy deviation that costs 2 per hit and affects 12 dev hits (F11),
two judgement calls (F12), and 4 controls that hold. **One unsafe clear is live in dev today: H-46F1CE** (see F2).

Ranking = how likely the pattern is in the unseen set (new customers, free text worded differently) × cost 60. The owner
column says which file the fix belongs in. decide.py and hitfacts.py are being edited by another agent, so this branch
changes no system code.

| # | Risk | Finding | Cases | Fix in |
|---|---|---|---|---|
| F2 | **High** (live in dev) | Numbers in hit notes are read as ages: list numbering, counts, "born X or Y" | 4 | hitfacts.py |
| F5 | **High** | The verified legal name parsed from a KYC note gets cut short, or comes from a family member | 4 | profile.py |
| F6 | **High** | The verified DOB parsed from a note is the wrong date, or the note's approved/rejected status is misread | 4 | profile.py |
| F4 | Medium-high | Countries dropped or misread: customer dual nationality, lower-case codes, "Korea, Republic of", US states | 9 | profile.py, countries.py, hitfacts.py |
| F1 | Medium | Entity-type words outside the system's list count as "individual", so a company is cleared on type | 3 | hitfacts.py, resolve.py |
| F3 | Medium | `dobs` field shapes: "circa 1960-1965", "1960 to 1965", "1960, 1965", "1960/61"; US M/D in notes | 5 | hitfacts.py |
| F8 | Medium-low | A non-Latin verified name, or a hit named only in a non-Latin script, "agrees with no hit name" | 2 | decide.py |
| F7 | Low-medium | Placeholders: doc number "UNKNOWN" merges strangers, DOB 01/01/1900, company name with no real parts | 3 | resolve.py, profile.py, decide.py |
| F10 | Low-medium | In search snippets, "born in Kano; listed 2012" takes 2012 as the birth year | 1 | hitfacts.py |
| F9 | Low | Customer resolution: the city filter drops the real customer and leaves a namesake; account_ref miss skips login/email | 2 | resolve.py |
| F11 | Accuracy (cost 2) | Name and DOB agree with no shared country: the system gives SAME_ENTITY, the policy says REVIEW (12 dev hits) | 1 | decide.py |
| F12 | Judgement | Clears that follow the policy literally but are risky: a support note corrects the record DOB; customer day/month swap | 2 | none (team call) |

---

## F2. Numbers in hit profile notes are read as ages (High, live in dev)
`hitfacts._AGE_PATTERNS` includes `\((\d{1,3})\)`, `, (\d{1,3}),` and `\b(?:was|is|turned|reached|then) (\d{1,3})\b`.
Any number that matches becomes an age, and the nearest date in the sentence turns it into two birth years. If the notes
give no other birth date, that one fake date is "every birth date the hit gives", so the hit is cleared on DOB_MISMATCH.

- **Dev H-46F1CE (Robert James, US) is cleared today on bogus ages.** The notes say "...without the security being
  (1)a federal-covered security, (2)exempt ..., or (3) registered...", which gives ages 1, 2 and 3, so the hit is "born
  1999–2003". The customer was born in 1955, so the hit is cleared. With the numbering neutralised, the same hit is
  `REVIEW / INSUFFICIENT_DATA` (name agrees, United States is shared, no usable DOB). This is a likely 60-point error
  in dev, and more like it will turn up in the unseen enforcement texts.
- `notes_count_read_as_age`: "was 1 of 12 officials" → age 1.
- `notes_list_number_read_as_age`: "counts 1, 3, and 7" → age 3.
- `notes_born_x_or_y_keeps_first_only`: "born 1974 or 1976" keeps only 1974, so a customer born 1977 is cleared.

**Fix (hitfacts.py):** (a) Drop any derived age under 16 or over 100. No adult watchlist profile gives an age like that,
and dropping it only removes a clearing fact. (b) Accept `(N)` only when a space or the end of the clause follows it and
a name comes right before it (`Ivan Petrov (45)`). Accept `, N,` only right after a name. (c) Reject
`was/is N` when one of `of|out of|times|counts?|people|defendants|others|million|bn|%` follows. (d) After "born", collect
every date up to the end of the clause ("1974 or 1976" → {1974, 1976}).

## F5. Verified legal name parsed from a KYC note (High)
The policy says the verified name outranks everything, and the only clear on name is NAME_MISMATCH_VERIFIED. So a wrong
parse of the note's name turns straight into a clear. The unseen set has "differently worded free text".

- `note_name_split_by_lowercase_particle`: "ANA MARIA da SILVA SANTOS". The parser keeps the longest *first* caps run,
  "ANA MARIA", which does not agree with the hit "Silva Santos, Ana", so the hit is cleared. The full legal name agrees.
- `note_titlecase_name_split_by_particle`: title case "Mohammed bin Salman Al Saud". The title-case runs are "Mohammed"
  and "Salman Al Saud", and the second one does not agree with the hit "Mohammed bin Salman", so the hit is cleared.
- `note_about_family_member_on_shared_email`: notes are linked by requester email, and families share emails. A note
  on "MARY SMITH (spouse of the account holder)" passes the plausibility guard (it shares "Smith"), and her DOB becomes the
  customer's verified DOB, so the hit is cleared on DOB_MISMATCH. The dev set is full of verified names that share only a
  surname with the record, so the guard cannot be tightened to fix this.
- `note_title_counts_as_name_part`: verified name "MR AHMED". "mr" counts as a second part, so a name with one real
  part is used to clear.

**Fix (profile.py):** join caps or title-case runs that only a lower-case particle separates
(`da|de|del|della|di|do|dos|das|du|van|von|der|den|ter|bin|ibn|bint|al|el|la|le|y|e`). Where one run is ambiguous,
prefer the run that covers the most record name parts. Ignore a note as identity evidence when it names a relation
(`spouse|wife|husband|son|daughter|mother|father|partner|child|joint holder|on behalf of|minor`). Strip titles
(`mr|mrs|ms|miss|dr|prof|sir|sheikh|haji|hajji|alhaji|chief|eng`) before counting real parts. In decide.py, NAME_MISMATCH
from a **note**-parsed name could also require that the record names disagree too. The policy does not demand that, but
the case where a record name agrees and only a parsed note name disagrees is exactly where parser errors live. Log it to
REVIEW rather than clearing.

## F6. Verified DOB and approval status parsed from a note (High)
- `note_dob_tie_picks_issue_date`: "passport issued 2019-02-03, DOB: March 1968". Both dates are 2 characters from
  "DOB" and the tie goes to the earlier one, so the verified DOB is 2019-02-03 and the hit is cleared on
  TEMPORAL_IMPOSSIBILITY.
- `note_two_digit_year_dob_falls_back_to_other_date`: "DOB 10.08.68" cannot be parsed, so the account-opening date
  2023-01-05 becomes the DOB (full dates have no distance limit).
- `note_onfido_consider_treated_as_approved`: "result: consider ... Manual review required" has no negative keyword, so
  the check counts as approved and its DOB clears the hit.
- `note_rejected_word_kills_approved_reverification`: "After an earlier rejected attempt, Onfido re-verified and
  approved ..." makes the whole note count as rejected, so the record's typo DOB clears the hit. The approved DOB would
  agree.

**Fix (profile.py):** prefer dates *after* the birth keyword, and break ties toward the later position. Exclude a date
when one of `issued|issue|expir|valid|opened|account|onboard|checked|on` comes within ~15 characters before it. Never let
a full date that is not next to a birth keyword be the DOB. Treat a DOB that makes the person younger than 16 on the
check date as unreadable. Add `consider|caution|refer|flagged|manual review|resubmi|on hold|review required|not clear`
to the negatives. When a note has both a positive outcome word and a negative word, treat it as *ambiguous*. Then it
must not supply clearing facts, and if its DOB or name would *prevent* a clear, the hit goes to REVIEW.

## F4. Countries dropped or misread (Medium-high)
Customer fields go through `norm_country` only (one value, exact match). The hit side falls back to
`countries_in_text`, which finds sub-strings.
- `customer_dual_nationality_comma`: "Russia, Cyprus" keeps only the last part (Cyprus).
- `customer_dual_nationality_slash`: "Russian/Cypriot" is not read at all.
- `customer_lowercase_iso_code`: "ru" is dropped (codes are accepted only in upper case).
- `customer_iso_style_long_name`: "Korea, Republic of" is dropped on the customer side, though the hit side reads it.
- `approved_note_second_country_dropped`: an approved ID note keeps only its *first* country. "previously lived in
  Russia" is lost, although the policy says places the notes say they lived count.
- `hit_us_state_read_as_country` / `hit_new_jersey_read_as_jersey` / `hit_new_mexico_read_as_mexico`: an address that
  ends in a US state becomes Georgia / Jersey / Mexico, so a US customer is cleared on location.
- `hit_historic_country_dropped`: "Belgrade, Yugoslavia" (also USSR, Soviet Union, Czechoslovakia, Crimea) is dropped.
  An unknown country makes a location clear easier.

Each lost or wrong country can turn "shares a country" into LOCATION_MISMATCH, the most common clear (214 of 466 dev clears).

**Fix:** profile.py `add()` for residence/nationality: if `norm_country` fails or the value contains `,`, `/`, `;`, `&`
or ` and `, split it and also add `countries_in_text(value)`. Accept 2–3 letter codes in any case *in these code
fields*. Approved ID notes: add every country the text mentions, not just the first. countries.py: add US state and
Canadian province names (→ United States / Canada) and block the "New " prefix in `countries_in_text`. Add aliases USSR /
Soviet Union → Russia, Yugoslavia → Serbia, Czechoslovakia → Czech Republic, Crimea → Ukraine, Lao PDR, Kyrgyz Republic,
Slovak Republic. Safety rule for hitfacts.py: if any address or country value is present but not recognised, do not clear
on location (unrecognised ≠ different).

## F1. Entity-type words outside the list (Medium)
Hit side: company only for `compan*|organisation|organization|entity|vessel|business`. Customer side:
`compan*|organisation|organization|entity|business|legal entity`. Anything else, **including blank**, counts as an
individual, so a company is cleared on ENTITY_TYPE_MISMATCH, which outranks every other code.
Cases: hit "Legal Entity", hit "", customer "Corporate". Dev only has Individual/Company, so this matters only if the
unseen schema varies, but the fix is two lines and the failure is the highest-priority clear.

**Fix:** use three states (company / individual / unknown). Company if the value matches `compan|corp|organi[sz]|entity|
business|firm|vessel|bank|trust|partnership|fund|foundation|agency|government|llc|ltd|inc`. Individual if it matches
`individual|person|natural|human`. Otherwise unknown. Only `company ≠ individual` with both known is a contradiction.

## F3. `dobs` field shapes and US-format dates (Medium)
`dobs` items are split on `;`, `or` and `/YYYY`. A range counts only as a bare `YYYY-YYYY`. Otherwise `parse_date` keeps
the first date, so one item that means a span becomes its earliest year.
Cases: "circa 1960-1965", "1960 to 1965", "1960, 1965", "1960/61" → 1960 only. `notes_month_first_us_format`: notes say
"born on 05/12/1980" from a US provider (= 12 May) and the date is read day-first as 5 Dec, so customer 1980-05-12 is
cleared (same year, months differ). The policy warns that hit dates are "written as the provider wrote them".
Dev `dobs` are clean (YYYY / YYYY-MM-DD / YYYY-MM), so the risk is moderate.

**Fix (hitfacts.py):** if one dobs item or one "born ..." clause holds more than one 4-digit year (or `YYYY/YY`), use the
whole span min..max with no month or day. In hit notes and dobs, when a D/M/Y date has both numbers ≤ 12, keep the year
only. The month and day then stop contradicting, but the year still counts.

## F8. Non-Latin scripts (Medium-low)
`verified_name_in_cyrillic`: a KYC provider returns "ИВАН ПЕТРОВ". Its parts are Cyrillic and can never match
"Petrov, Ivan", so the hit is cleared on NAME_MISMATCH_VERIFIED. `hit_name_only_in_arabic`: a hit whose only name is
"عمر علي حسين", against the verified "Omar Ali Hussain", is also cleared. In dev, every hit has a Latin primary name and
non-Latin aliases sit in brackets or have a Latin twin (a control holds), but "non-Latin scripts" is on the unseen-set list.

**Fix (decide.py, for the owner):** before NAME_MISMATCH_VERIFIED, check whether the verified name and at least one
hit name share a script. Compare Latin letters after `fold()`. If no pair is comparable, there is no name clear.

## F7. Placeholders (Low-medium)
- `placeholder_document_number_merges_strangers`: two approved checks with document number "UNKNOWN" merge a Russian
  and a Chinese customer into one person. The stranger's newer verified DOB and name are then used, so the hit is
  cleared. `norm_doc` accepts any 4 or more alphanumerics, so PENDING, NONE00 and 000000 would merge people too.
- `placeholder_customer_dob_1900`: record DOB 01/01/1900 contradicts every real hit DOB.
- `company_name_all_digits`: the verified company "3M Company" has no real parts ("3m" has a digit, "company" is a
  legal form), so it "agrees with none", and the hit "3M Co" is cleared on name.

**Fix:** resolve.py `norm_doc`: require at least one digit, at least 5 characters, not all the same character, and skip
values in a placeholder list. profile.py: treat customer DOBs in {1900-01-01, 1901-01-01, 1800s, after the screening
date} as missing. decide.py: a verified name with zero real parts is unusable for a name clear (companies included).

## F10. Search snippets: "born" has no distance limit (Low-medium)
`search_born_place_then_listing_year`: "Musa Bello, a sanctioned individual from Nigeria, born in Kano; listed 2012."
The first date within 30 characters of "born in" is 2012, so a customer born in 1975 is cleared. 71 dev hits take their
DOB from search results. Hit notes already require the date within 3 characters of "born"; search snippets do not.
**Fix (hitfacts.py):** apply the same ≤3-character rule (after the optional "on/in") to snippets.

## F9. Customer resolution (Low)
- `unlinked_search_misses_true_customer_city_spelling`: no link. The screened city is "Munich"; the real customer's
  record says "München" (exact name and DOB). The city filter drops them, and a namesake in "Munich, North Dakota"
  (Austria) is the only fit and is cleared on location. The filter follows the policy literally, but an exonym or
  transliteration should not decide who the customer is.
- `account_ref_missing_but_login_present`: if account_ref is not found, the system stops (REVIEW). It does not try the
  login handle or email the alert also carries. That costs 2, it is not unsafe.

**Fix (resolve.py):** if a record matches the screened name *and* full DOB but fails only on city/country, keep it as a
candidate. Several people then lead to AMBIGUOUS / REVIEW when their decisions differ. On a missed account_ref, fall
through to login_handle, then email.

## F11. Name and DOB agree, no shared country, system confirms (accuracy, 12 dev hits)
Policy 6: "A country difference does not clear a hit whose name and date of birth agree: **that hit is REVIEW**."
decide.py skips the location clear correctly, but then confirms SAME_ENTITY / NAME_DOB_MATCH. In dev, 12 hits are
SAME_ENTITY / NAME_DOB_MATCH even though the hit lists countries the customer does not share: H-23805C, H-ADF453,
H-6833AE, H-E2408C, H-D05706, H-A501C4, H-2C12E1, H-F93F3C, H-665870, H-227FDA, H-241B53, H-68561C (cost 2 each if the
labels follow the policy text).
**Fix (decide.py):** if `cust_c and hit_c and not shared` and name and DOB agree, return REVIEW / INSUFFICIENT_DATA with
a reason saying the countries differ.

## F12. Judgement calls: the policy clears literally, but the clear is risky
- `support_note_corrects_record_dob`: a phone note says "the date of birth on file (1990) is a typo, correct date of
  birth is 01/05/1970". It is not an identity check, so the record's 1990 DOB clears a 1970-born hit.
- `customer_day_month_swap`: record 05/12/1980 (day-first, 5 Dec) against hit 1980-05-12. Months differ, so the hit is
  cleared. This is the classic data-entry swap.

The labels probably follow the policy text, so changing these could cost points. Suggested middle ground: give REVIEW
only when *every* other fact agrees (name agrees and a country is shared) and the only contradiction is a swap or a
note-corrected DOB.

## Probed and holding (controls)
Bracketed script tags on aliases ("Иван Петров (None, Cyrillic)") are ignored and the Latin name still confirms. A
year-only customer DOB agrees with a full hit DOB. A minor is not cleared on TEMPORAL when the report line does not use
the "According to …;" form. A rejected KYC check's different name does not clear. Also checked by reading the code:
DECEASED needs a parsed date before screening; several candidate people with different outcomes → AMBIGUOUS /
REVIEW; any exception → REVIEW; an unresolved alert → REVIEW with null.

## A cheap safety net worth adding (screen.py, not in the files others own)
Most of F2/F3/F5/F6/F10 come down to a clear that rests on **one fact parsed from free text** (a notes or search-derived
hit DOB, or a note-derived verified name or DOB). screen.py could re-run the decision with those parsed facts removed.
If the result is no longer DIFFERENT_ENTITY *and* the parsed fact was the only contradiction, downgrade to REVIEW. On
dev this costs at most the clears that rest on a single parsed fact. Measure before adopting, because the practice
labels include note-DOB clears (e.g. H-D861DA).
