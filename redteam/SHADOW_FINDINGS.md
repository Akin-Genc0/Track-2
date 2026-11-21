# Shadow test-set findings (Track 2) — Sat 21 Nov 2026, ~12:45 London (GMT)

The system code was not changed. Tools added: `tools/shadow.py` (generator and scorer), `tools/ablate.py` (leave-one-component-out check).
Runs are saved in `shadow_runs/`.

## 1. Shadow set results

`python3 tools/shadow.py gen /tmp/shadowN N` builds 559 hits (452–544 alerts, about 570 new customers). The scenarios are policy-labelled:

- 467 hits come from **"in-distribution" scenarios**: fresh names, transliterations, shifted DOBs, swapped countries, and new KYC, residence, age and snippet templates. These include 13 trap types (rejected checks, wrong-form dated reports, numbers that are not ages, namesake snippets, joint accounts, placeholders, etc.).
- 92 hits come from **12 "hard" out-of-distribution scenarios**: formats never seen in dev.

| seed | slice | hits | cost | all-REVIEW cost | score | unsafe |
|---|---|---|---|---|---|---|
| 7  | in-distribution | 467 | 0 | 862 | **1.000** | 0 |
| 21 | in-distribution | 467 | 0 | 862 | **1.000** | 0 |
| 7  | hard (OOD) | 92 | 1446 | 155 | −8.3 | **23** |
| 21 | hard (OOD) | 92 | 1447 | 157 | −8.2 | **23** |

Output is byte-identical across reruns (deterministic).

The perfect in-distribution score is partly optimistic, because the generator and the system share an author. The OOD slice is where the real risk shows. Every unsafe clear has the same cause: **a country string the gazetteer cannot normalise is silently dropped, and the shrunken country set then "proves" a LOCATION_MISMATCH**.

| hard scenario | n | errors | cost |
|---|---|---|---|
| hard_dual_nationality (customer nationality `British/Kenyan`, `Kenya and Italy`, `Dual Kenyan-British`) | 10 | REVIEW→DIFF ×10 | 600 |
| hard_customer_country_longform (residence `Federal Republic of Germany`, `Republic of Kenya`) | 8 | REVIEW→DIFF ×8 | 480 |
| hard_native_country_name (hit address `Kraków, Polska`, `Sverige`, `Nederland`, `Misr`) | 8 | REVIEW→DIFF ×5 | 300 |
| hard_age_words_* (`aged forty-five`) | 12 | SAME/DIFF→REVIEW ×11 | 30 |
| hard_deceased_in_notes (death date only in profile notes) | 6 | DIFF→REVIEW ×6 | 18 |
| hard_lowercase_verified_mismatch | 6 | DIFF→REVIEW ×6 | 18 (by design) |

These hard scenarios passed with 0 errors: circa/range DOBs (`c. 1969`, `1968 - 1970`, `Approximately`), KYC notes with issue and expiry dates, two approved checks where the newest wins, and no-link resolution with a nickname plus a surname typo.

The dev data shows how likely these situations are on the unseen set:

- All structured country fields in dev (customers, hits, KYC) normalise, with **0 unknown strings**.
- All 22,575 KYC notes parse, with name, DOB and country, and all are approved.
- The 3,067 residence notes (2,986 distinct LLM paraphrases) name countries by their canonical English name.

So the OOD failures are **low-probability but catastrophic** (60 points each). The fixes are cheap and only ever move a hit toward REVIEW.

## 2. Leave-out check on dev and the 50 practice labels (`tools/ablate.py data/dev`)

Each component is disabled in turn, and the table counts which decisions change.

| component disabled | dev decisions changed (of 819) | practice labels that depend on it |
|---|---|---|
| free-text KYC-note parsing (verified beats declared) | 60 (15 SAME→DIFF, 10 DIFF→SAME, 34 DIFF→REVIEW) | **5**: H-4D76E3, H-80B4B5 (become **unsafe** DIFF without it), H-5E39F0, H-622EDD, H-EDBB79 |
| edit-distance name matching | 42 (28 REVIEW→DIFF, 5 SAME→DIFF) | **5**: H-DC05D5, H-FA9F83, H-404FB7, H-59908A, H-F9DBF9 (all become **unsafe** DIFF) |
| country mentions in customer notes (residence notes) | 40 (all REVIEW→DIFF) | **3**: H-FF3096, H-A22C42, H-7F2A6C (become **unsafe**) |
| search-result DOBs and the snippet country filter | 46 (25 SAME→REVIEW, 21 DIFF→REVIEW) | **4**: H-0181BD, H-F9DBF9, H-80B4B5, H-622EDD |
| age-sentence DOBs in the first paragraph (strong cues) | 22 (9 SAME→REVIEW, 12 DIFF→REVIEW, 1 REVIEW→DIFF) | **3**: H-582410, H-D861DA, H-4AA437 |
| `born …` cue regex | 16 (→REVIEW) | 0 |
| given-name variant groups | 13 | 0 |
| dated-report regex `According to …; <date>:` | 4 (3 DIFF→SAME) | 0 |
| title-case/lower-case name fallback | 0 | 0 |

About 33 of the 50 practice labels rest only on structured fields: dobs, countries, KYC table, customer fields.

The regex-sensitive groups are:

- **Age sentences.** Hits whose DOB comes from an LLM-paraphrased age sentence. I listed all 37 such sentences in dev: every one is detected, and none of the 15 number-plus-date distractors (sentences, fines, counts) is misread.
- **KYC notes.** A parse failure falls back to declared data, which can be unsafe.
- **Residence notes.** A missed country leads to an unsafe location clear.

I probed the age cues with 29 hand-written sentences. All distractors were rejected, but these common forms are **missed**:

- `John Smith, 45, was arrested…`
- `John Smith (45)`
- `now 45`
- `a man of 45`
- `aged forty-five`
- `Age at the time …: 45`

A miss goes to REVIEW (cost 2–3), so it is never unsafe.

## 3. Findings, ranked by expected cost on the unseen set

### F1. An unrecognised country string is dropped silently, so LOCATION_MISMATCH fires on a partial country set

- **Cost if hit:** 60 per hit. The shadow OOD run had 23 unsafe clears.
- **Likelihood:** low, since dev has 0 unknown strings. The fix has no downside.

**Files:** `system/profile.py` (Profile.__init__ `add(norm_country(...))`) and `system/hitfacts.py` (the country loop).

**Fix:**
1. **Customer side.** If `norm_country(v)` is None, fall back to `countries_in_text(v)` and add *all* of the countries it finds. This covers dual nationality (`British/Kenyan`) and long forms (`Republic of Kenya`).
2. **Hit side.** Add *all* `countries_in_text` matches, not just `cs[-1]`.
3. **Unknown values.** If a non-empty country, nationality or address value still yields nothing, set `profile.unknown_country = True` (or `hit.unknown_country = True`). In `system/decide.py`, block the LOCATION_MISMATCH clear when either flag is set, which gives REVIEW.
4. **Aliases.** Add to `system/countries.py`: `Polska`, `Sverige`, `Nederland`, `Misr`, `Al-Maghrib`, `Ukraina`, `Rossiya`, `Bharat`, `Nippon`, `Suomi`, `Norge`, `Danmark`, `Österreich`, `Schweiz`/`Suisse`/`Svizzera`, `Hellas`, `Magyarország`, `Česko`, `KSA`, `the Emirates`, `the States`, `U.S.`, `U.K.`, `Lao PDR`, and strip `(…)` qualifiers such as `Iran (Islamic Republic of)`.

On dev this should change nothing (0 unknown strings); rerun `tools/score.py` to confirm.

### F2. The KYC-note negation regex treats "expires/expiry" as a failed check, so verified data is ignored and the system falls back to declared data

- **Cost if hit:** 60, when declared data contradicts the hit but verified data agrees. The ablation shows 15 dev hits where the note is the only thing stopping a SAME→DIFF.
- **Likelihood:** low to medium. Dev notes never mention expiry, but there are 21,555 distinct paraphrases, so unseen wording can vary.

**File:** `system/profile.py` `_NEG_RE`.

**Fix:**
- Replace the bare `expir` with `\b(?:has|had|was|is)\s+expired\b|\bexpired\b(?!\s+on\s+\d{4}-\d\d-\d\d\s*\)?$)`. Better still, require `expired` (past tense) and ignore `expires|expiry|expiring|valid until`.
- As a safety net: if a note matches the ID-check pattern but its name or DOB cannot be read, or it was flagged negative only by a weak word, do not let declared DOB or name produce DOB_MISMATCH or NAME_MISMATCH_VERIFIED for that person. Send it to REVIEW (`decide.py`).

Verified: `"Veriff verified passport (expires 2031-05-12) for JOHN SMITH, born 1980-02-03…"` is currently parsed as `approved=False`.

### F3. Age-sentence coverage misses common news forms (never unsafe; cost 2–3 per miss)

- **Exposure:** about 2.7% of dev decisions (22/819) depend on age sentences. The unseen set will contain new paraphrases, so expect about 3–8 misses on roughly 550 hits, costing about 10–20 points.
- **File:** `system/hitfacts.py` `_STRONG_RE`.

**Fix:** add strong cues for:
- `<Capitalised name>, (NN), <lower-case word>` — an appositive. NN must be 16–99 and not followed by `,000`, `%`, `months` or `years in`.
- `<Name> \((?:age )?(NN)\)`
- `\b(?:now|then) (?:aged )?(NN)\b`
- `a (?:man|woman) of (NN)`
- number words 20–99 after `aged|age of|was|, ` (for example `forty-five`)

Keep the existing date-adjacency exclusions. Add the 29 probe sentences from this file to `tests/test_policy.py`.

### F4. Name matching depends on edit distance for 5 practice labels; transliteration pairs beyond 1–2 edits clear as NAME_MISMATCH_VERIFIED

- **Note:** this follows the policy literally, so the labels should agree. The risk lies only in our edit thresholds or folding drifting from the policy.
- **File:** `system/textutil.py`.

**Fix:** no logic change. Add unit tests that pin the policy exactly:
- 4–6 letters: 1 edit
- 7 or more letters: 2 edits
- accent and case folding (`Paweł`→`pawel`, `Thuận`→`thuan`)
- written together or apart, exact only

A one-character threshold mistake would flip about 33 dev decisions toward DIFF.

### F5. A death date that appears only in the profile notes is ignored (cost 3 per miss, not unsafe)

- **Likelihood:** low. Dev has 4 `deceased_date` values and 0 note-only deaths.
- **File:** `system/hitfacts.py`.

**Fix:** only use `life_status == Deceased` together with a parsed date in the first paragraph (`died on <date>`, `date of death: <date>`, `passed away in <date>`). Otherwise leave it as is: missing is safe.

### F6. A residence-note country is the only thing preventing 40 unsafe dev clears

- **Status:** robust today. Countries are named canonically in all 2,986 paraphrases.
- **Files:** `system/profile.py` and `system/countries.py`.

**Fix:** shares F1's fix. Also, if a note has a residence or work verb (`lived|resid|based|employ|work|relocat|moved`) but `countries_in_text` returns nothing, set `profile.unknown_country = True` so the location clear is blocked. Expected dev impact is 0: all non-ID notes without a country are the 6 boilerplate templates (lost card, statement, etc.), which contain none of these verbs except "address on file". Exclude that phrase.

### F7. The dated-report regex is exact by design

Only 4 dev decisions depend on it. If the form is not exact, the TEMPORAL clear is lost and the hit goes to REVIEW (cost 3). No change is recommended: the policy requires the exact form.

## 4. Suggested order for the fix agent

1. F1 + F6: country unknown → block LOCATION, plus aliases. Touches `profile.py`, `hitfacts.py`, `decide.py`, `countries.py`.
2. F2: `_NEG_RE` expiry. Touches `profile.py`.
3. F3: age cues. Touches `hitfacts.py`.
4. F4: tests only.

After each step:
- run `python3 tools/score.py output/dev.jsonl data/dev/practice_labels.jsonl`, which must stay 50/50 with 0 unsafe
- run `python3 tools/shadow.py gen /tmp/s7 7 && system/run /tmp/s7 /tmp/p7 && python3 tools/shadow.py score /tmp/s7 /tmp/p7`
- run `python3 tools/ablate.py data/dev`
