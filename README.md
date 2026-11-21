# Track 2: Is my customer sanctioned?

A deterministic screening-alert reviewer. For every watchlist hit it decides **SAME_ENTITY**, **DIFFERENT_ENTITY** or **REVIEW**, gives a policy reason code and the resolved customer record, and cites the records it relied on. It implements the identity SOP rule by rule. There's no LLM in the decision path, so the same input gives the same answer every time, and every decision can be audited.

**Practice labels: 50/50 correct on decision, reason code and customer record.**

## Run it

```bash
pip install openpyxl   # only needed for the xlsx converter
python xlsx_to_jsonl.py "Screening Dev Set - browse.xlsx" dev   # skip if you have the data room's dev/ folder
python screen.py --data dev --out predictions.jsonl --eval
```

To run on the unseen set, point `--data` at its folder (same JSONL layout).

## How it works

1. **Find the customer.** Follow the alert's link (account → holders, login → account, email → record). Joint accounts are narrowed down by the screened name, DOB, country and city. Alerts with no link run a fuzzy search over the system of record.
2. **One person, one picture.** Records that share a phone number and full DOB, or a document number on an approved KYC check, are merged with union-find.
3. **Verified beats declared.** The latest *approved* identity check, from the KYC provider or parsed from an onboarding note, supplies the legal name, DOB and document country.
4. **Gather the hit's facts.** These come from the `dobs` field, ages in the profile notes ("aged 30 in November 1998" → 1967/1968), dated "According to …" reports, and web search results that only count when they show the same listing type in a country tied to the hit.
5. **Decide.** Contradictions clear a hit (type, death, age at earliest report, DOB, location, verified name). Agreement confirms it (name + DOB for people, name + country for companies). Everything else goes to a human (`REVIEW`). A country difference never clears a hit whose name and DOB agree, and ambiguous customers are decided per person.

The name matching follows principle 8: accents and brackets are ignored, initials dropped, a variant table is used, joined/split forms match (Abdulsalam = Abdul Salam), edit distance is allowed by part length, and placeholders and company legal forms are ignored.

## Output (`predictions.jsonl`)

`hit_id, alert_id, decision, reason_code, customer_record_id (or "AMBIGUOUS" / null), customer_record_ids, evidence[], explanation, resolution_path`

## Test one case by hand

```bash
python3 screen.py --case A-A79F99     # full reasoning for one alert (or a hit id, H-...)
python3 screen.py --try               # type in your own customer + watchlist hit
python3 screen.py --demo              # 11 built-in examples (or: --demo 1 5 11)
```

## Browse results in the terminal

```bash
python3 screen.py --list REVIEW 20          # first 20 "needs a human" cases
python3 screen.py --list SAME random 10     # 10 random confirmed matches
python3 screen.py --list LOCATION_MISMATCH  # filter by reason code
python3 screen.py --case H-227FDA H-2D8E94  # full evidence for several hits
```

## Web terminal (demo UI)

```bash
python3 app.py          # then open http://localhost:8000
```
An analyst workstation on top of the same engine: a command console, case files with a field-by-field evidence check, and live totals. Commands: `scan`, `list review 20`, `case H-227FDA`, `check` (a form to screen a person by hand), `demo 1`, `stats`, `about`, `help`. Click any `H-…` id to open its dossier. Standard library only, nothing to install.
