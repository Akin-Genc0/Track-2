# Reason-quality audit

Baseline: bot/core-system, 819 rebuilt predictions. All 50 practice labels plus 10 deterministic supplements (first missing code, then earliest remaining hits in output order): 60 total, all three decisions and all 11 codes. References are guidance, not proof that every extra citation is wrong. No unseen accuracy claims.

## Findings

All 50 decisions, codes and customer IDs pass the local scorer; evidence sets match exactly (Jaccard 1.00). 45/50 reason texts equal the reference verbatim. The sample below preserves all 50 references for comparison. DOBs and countries are generally already explicit: do not replace these with generic mismatch prose.

* Over-citation: decide_person unions evidence from every contradiction but prints only three. It also reports secondary contradictions after a sufficient primary ground. H-5EEC5A can be explained by company versus individual using CUS-559377 alone; its KYC-30794E location evidence is unnecessary for that chosen ground. Keep resolution evidence where it actually establishes the customer.
* Under-citation risk: match branches omit nsrc. Include the source of the compared customer name, even when it differs from the DOB/country source. H-23805C currently cites only NOTE-4A8FF2: verify whether that note establishes the name before adding a citation; absence of a CUS ID alone is not an error. Hit-native facts need no invented external evidence ID; H-BD709E legitimately has empty evidence for death versus screening date.
* Ambiguity: H-2B5507 names three people and cites their evidence but prints only the first person's DOB. Each candidate needs its own deciding comparison. H-0F3C96 provides candidate codes but no factual basis for their different outcomes. Rendering cannot repair incorrect resolution.
* One-sentence explanations violate the requested two-to-four sentences: H-AC1114 and H-BD709E are concrete examples. Add identification/context, not unsupported claims.
* Generic review: H-8A1D28 says DOB cannot be compared without saying which side is missing. Supply customer DOB and hit DOB availability separately, including conflicting sources where relevant. Do not say nothing contradicts when contradictory records caused review.
* Code risk (source inspection): when names and DOBs agree but known country sets are disjoint, decide.py suppresses LOCATION_MISMATCH then returns SAME_ENTITY/NAME_DOB_MATCH. Policy principle 6 explicitly requires REVIEW. This requires a decision-engine fix, not prettier text. No practice code mismatch was observed. NAME_MISMATCH_VERIFIED must compare all aliases; its current prose names only the primary name. Temporal reasons must distinguish not-yet-born from age zero and retain partial-date uncertainty.

## Before / after

H-AC1114 before: “The customer's date of birth is 1968-08-20 (KYC-9FC168) but the hit's listed date of birth is 1968-01-12.” After: “The customer birth date is 1968-08-20; the hit birth date is 1968-01-12. The dates share a year but disagree on month, establishing different people.” Evidence remains KYC-9FC168.

H-5EEC5A before: type mismatch plus Germany versus Singapore, citing CUS-559377 and KYC-30794E. After: “The customer is a company; the hit is an individual. This type contradiction decides CUS-559377 against this hit.” Evidence: CUS-559377, unless additional records are needed for resolution.

H-BD709E before: one sentence giving death 2022-03 and screening 2026-11-14. After: “The hit died 2022-03; the customer was screened 2026-11-14. The death precedes screening, satisfying the policy's deceased ground.” Evidence stays empty.

## Integration (not applied)

Import `explain` from `explain.py` in decide.py. Immediately before returning each decision, build `facts = {reason_code, customer_record_id: prof.primary, hit_name: hit.name, grounds, resolution_evidence}` and update the result with `explain(facts)`. Each ground has display strings `customer`, `hit`, and its decisive `evidence`. Only the selected code's grounds are rendered and cited; unrelated grounds are ignored. Pass full DOB alternatives, all countries for exclusion, and all names/aliases for verified-name exclusion. For matches, include nsrc in the name ground. Preserve birth-year ranges instead of inventing full dates. Temporal customer text must state birth/incorporation date and derived age or not-yet-born status.

Review uses `missing: {detail, evidence}` with exact missing/conflicting fields; ambiguity uses `ambiguity: {detail, evidence}` with EACH candidate and its facts. screen.py must eventually build this aggregate rather than copying r0. Supply resolution_evidence only where necessary to connect the selected facts to the customer. The function cannot determine minimal provenance from flat IDs: it returns the union of selected claim sources and explicit resolution dependencies, sorted/deduplicated. It does not change decisions or infer facts. Not wired in, so output/dev.jsonl remains the baseline.

## Reviewed sample

### H-13E1CF — DIFFERENT_ENTITY / TEMPORAL_IMPOSSIBILITY

Customer: `CUS-364225`. Evidence: KYC-358C76, CUS-364225, CUS-851234.

The customer was born on 2007-08-21 (KYC-358C76), so they were at most 12 when the hit's profile reports activity on 2020-01-08. The customer is linked only to Singapore, United States but the hit is linked only to Pakistan.

Reference: The customer was born in 2007 (KYC-358C76), so they were at most 13 when the hit's profile reports activity on 2020-01-08. The customer is linked only to Singapore, United States but the hit is linked only to Pakistan.

### H-9FD80D — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-375608`. Evidence: CUS-375608, KYC-A932A4.

The customer is linked only to Germany but the hit is linked only to Switzerland.

Reference: The customer is linked only to Germany but the hit is linked only to Switzerland.

### H-582410 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-377745`. Evidence: NOTE-14E25A, CUS-377745.

The customer's date of birth 1968-03-05 (NOTE-14E25A) agrees with the hit's 1967 or 1968. Both the customer and the hit are linked to Spain. The customer's name agrees with the hit's name Elvira Velasco Morillo.

Reference: The customer's date of birth 1968-03-05 (NOTE-14E25A) agrees with the hit's 1967 or 1968. Both the customer and the hit are linked to Spain. The customer's name agrees with the hit's name Elvira Velasco Morillo.

### H-FF3096 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-459031`. Evidence: NOTE-10AEAB.

Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Abdul Rahman Yasin. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Abdul Rahman Yasin. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-58A39C — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-604925`. Evidence: KYC-232AE0.

The customer's date of birth is 1965-03-28 (KYC-232AE0) but the hit's listed date of birth is 1962-09-10.

Reference: The customer's date of birth is 1965-03-28 (KYC-232AE0) but the hit's listed date of birth is 1962-09-10.

### H-18E6BA — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-065730`. Evidence: CUS-065730, KYC-3925C4.

The customer is linked only to South Africa but the hit is linked only to United States.

Reference: The customer is linked only to South Africa but the hit is linked only to United States.

### H-CF5228 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-028455`. Evidence: KYC-66A040.

The customer's date of birth is 1951-09-17 (KYC-66A040) but the hit's listed date of birth is 1980-11-11.

Reference: The customer's date of birth is 1951-09-17 (KYC-66A040) but the hit's listed date of birth is 1980-11-11.

### H-F2AEA4 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-028455`. Evidence: CUS-028455, CUS-674197, KYC-66A040.

The customer is linked only to Netherlands, United States but the hit is linked only to Ireland.

Reference: The customer is linked only to Netherlands, United States but the hit is linked only to Ireland.

### H-42CF02 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-500524`. Evidence: CUS-500524, KYC-D1DFCD.

The customer is linked only to Australia but the hit is linked only to United States.

Reference: The customer is linked only to Australia but the hit is linked only to United States.

### H-A69C00 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-500524`. Evidence: CUS-500524, KYC-D1DFCD.

The customer is linked only to Australia but the hit is linked only to United States.

Reference: The customer is linked only to Australia but the hit is linked only to United States.

### H-FC22E2 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-271392`. Evidence: KYC-04520F, SR-65C752.

The customer's date of birth is 2002-05-13 (KYC-04520F) but the hit's search results put its birth year at 1972 or 1973. The customer's verified name is Joseph gallardo (KYC-04520F), which does not match the hit's name Gallardo, Bartolo Diego.

Reference: The customer's date of birth is 2002-05-13 (KYC-04520F) but the hit's search results put its birth year at 1972 or 1973. The customer's verified name is Joseph gallardo (KYC-04520F), which does not match the hit's name Gallardo, Bartolo Diego.

### H-A22C42 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-007742`. Evidence: NOTE-F302A4.

Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Yahaya, AbdulBasit Abdullahi. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Yahaya, AbdulBasit Abdullahi. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-A72A50 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-186144`. Evidence: KYC-6075EB, CUS-186144, CUS-977888.

The customer's date of birth 1962-10-23 (KYC-6075EB) agrees with the hit's 1962, 1961. Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Bowman, David.

Reference: The customer's date of birth 1962-10-23 (KYC-6075EB) agrees with the hit's 1962, 1961. Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Bowman, David.

### H-5E39F0 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-227265`. Evidence: NOTE-302C97.

The customer's date of birth is 1988-10-03 (NOTE-302C97) but the hit's listed date of birth is 1963-12-16. The customer's verified name is SAMUEL DIAZ (NOTE-302C97), which does not match the hit's name Ramirez Diaz, Jesus Amable.

Reference: The customer's date of birth is 1988-10-03 (NOTE-302C97) but the hit's listed date of birth is 1963-12-16. The customer's verified name is SAMUEL DIAZ (NOTE-302C97), which does not match the hit's name Ramirez Diaz, Jesus Amable.

### H-8E4EC8 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-976714`. Evidence: CUS-976714, KYC-A62617.

The customer is linked only to Netherlands but the hit is linked only to United States.

Reference: The customer is linked only to Netherlands but the hit is linked only to United States.

### H-DC05D5 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-293016`. Evidence: CUS-293016, KYC-16E55D.

Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Abdullahi, Tijjani. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Abdullahi, Tijjani. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-CF0978 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-221663`. Evidence: KYC-89E659, CUS-221663.

The customer's date of birth 1998-12-18 (KYC-89E659) agrees with the hit's 1998, 1999. Both the customer and the hit are linked to Bangladesh. The customer's name agrees with the hit's name Amin, Md Al.

Reference: The customer's date of birth 1998-12-18 (KYC-89E659) agrees with the hit's 1998, 1999. Both the customer and the hit are linked to Bangladesh. The customer's name agrees with the hit's name Amin, Md Al.

### H-A7A9F9 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-674104`. Evidence: CUS-674104, NOTE-F106B8.

The customer is linked only to United States but the hit is linked only to Austria, Russia, Switzerland.

Reference: The customer is linked only to United States but the hit is linked only to Austria, Russia, Switzerland.

### H-D1520C — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-453893`. Evidence: CUS-453893, KYC-F04C4D.

The customer is linked only to Singapore but the hit is linked only to Canada.

Reference: The customer is linked only to Singapore but the hit is linked only to Canada.

### H-6C7985 — REVIEW / INSUFFICIENT_DATA

Customer: `AMBIGUOUS`. Evidence: CUS-618916, KYC-8DE62A, CUS-885413, NOTE-BC6437.

2 different people in the system of record fit the alert (CUS-618916, CUS-885413); each leads to REVIEW. Both the customer and the hit are linked to Pakistan. The customer's name agrees with the hit's name Mohammad Nadeem. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Pakistan. The customer's name agrees with the hit's name Mohammad Nadeem. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-D861DA — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-804632`. Evidence: NOTE-8548C1.

The customer's date of birth is 1979-11-08 (NOTE-8548C1) but the hit's profile notes put its birth year at 1976 or 1977.

Reference: The customer's date of birth is 1979-11-08 (NOTE-8548C1) but the hit's profile notes put its birth year at 1976 or 1977.

### H-D8119F — SAME_ENTITY / NAME_LOCATION_MATCH

Customer: `CUS-779191`. Evidence: CUS-779191, KYC-97C367.

Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name PULLMAN GLOBAL SOLUTIONS LLC.

Reference: Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name PULLMAN GLOBAL SOLUTIONS LLC.

### H-CF173B — DIFFERENT_ENTITY / NAME_MISMATCH_VERIFIED

Customer: `CUS-921880`. Evidence: KYC-F112AA, CUS-277574, CUS-921880.

The customer's verified name is Jonathan Reyes Whitfield (KYC-F112AA), which does not match the hit's name John Whitfield. The customer is linked only to Peru, United States but the hit is linked only to United Kingdom.

Reference: The customer is linked only to Peru, United States but the hit is linked only to United Kingdom. The customer's verified name is Jonathan Reyes Whitfield (KYC-F112AA), which does not match the hit's name John Whitfield.

### H-FA9F83 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-783545`. Evidence: CUS-783545, KYC-80B445.

Both the customer and the hit are linked to Moldova. The customer's name agrees with the hit's name Diana Cristian. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Moldova. The customer's name agrees with the hit's name Diana Cristian. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-58CFBE — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-812010`. Evidence: CUS-812010, NOTE-C3E53D.

The customer is linked only to United States but the hit is linked only to China.

Reference: The customer is linked only to United States but the hit is linked only to China.

### H-91AC66 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-962814`. Evidence: KYC-038F14, CUS-962814.

The customer's date of birth 1994-11-01 (KYC-038F14) agrees with the hit's 1994, 1995. Both the customer and the hit are linked to Bangladesh. The customer's name agrees with the hit's name Emran Ali.

Reference: The customer's date of birth 1994-11-01 (KYC-038F14) agrees with the hit's 1994, 1995. Both the customer and the hit are linked to Bangladesh. The customer's name agrees with the hit's name Emran Ali.

### H-4D76E3 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-970916`. Evidence: NOTE-4E8A14, CUS-906311, CUS-970916.

The customer's date of birth 1968-02-17 (NOTE-4E8A14) agrees with the hit's 1968-02. Both the customer and the hit are linked to Pakistan, United Kingdom. The customer's name agrees with the hit's name Mohammad Nadeem Ghani.

Reference: The customer's date of birth 1968-02-17 (NOTE-4E8A14) agrees with the hit's 1968-02. Both the customer and the hit are linked to Pakistan, United Kingdom. The customer's name agrees with the hit's name Mohammad Nadeem Ghani.

### H-0181BD — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-775419`. Evidence: NOTE-CB2CB8, SR-590704, CUS-138588, CUS-775419.

The customer's date of birth 1985-09-12 (NOTE-CB2CB8) agrees with the hit's 1985 or 1986. Both the customer and the hit are linked to Brazil. The customer's name agrees with the hit's name COSTA, MARCOS ROBERTO.

Reference: The customer's date of birth 1985-09-12 (NOTE-CB2CB8) agrees with the hit's 1985 or 1986. Both the customer and the hit are linked to Brazil. The customer's name agrees with the hit's name COSTA, MARCOS ROBERTO.

### H-AE0262 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-905593`. Evidence: CUS-905593, KYC-197B8B.

The customer is linked only to Spain but the hit is linked only to Brazil.

Reference: The customer is linked only to Spain but the hit is linked only to Brazil.

### H-404FB7 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-558991`. Evidence: CUS-558991, KYC-E7150E.

Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Umar, Suleiman. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Umar, Suleiman. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-427D39 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-762804`. Evidence: CUS-510447, NOTE-7F183D.

Both the customer and the hit are linked to India. The customer's name agrees with the hit's name Rajesh Kumar. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to India. The customer's name agrees with the hit's name Rajesh Kumar. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-F9DBF9 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-558035`. Evidence: KYC-685B2C, SR-AE2CE1, CUS-529109, CUS-558035.

The customer's date of birth 1959-09-12 (KYC-685B2C) agrees with the hit's 1959 or 1960. Both the customer and the hit are linked to Italy. The customer's name agrees with the hit's name Giampiero Fiorani.

Reference: The customer's date of birth 1959-09-12 (KYC-685B2C) agrees with the hit's 1959 or 1960. Both the customer and the hit are linked to Italy. The customer's name agrees with the hit's name Giampiero Fiorani.

### H-CDEC83 — REVIEW / INSUFFICIENT_DATA

Customer: `AMBIGUOUS`. Evidence: CUS-037213, NOTE-6D8352, CUS-565167, CUS-892985, KYC-3B906A.

2 different people in the system of record fit the alert (CUS-037213, CUS-565167); each leads to REVIEW. Both the customer and the hit are linked to Panama. The customer's name agrees with the hit's name Juan González. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Panama. The customer's name agrees with the hit's name Juan González. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-539324 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-048448`. Evidence: CUS-048448, CUS-139694, NOTE-76C514.

The customer is linked only to Bangladesh, United Kingdom but the hit is linked only to United States.

Reference: The customer is linked only to Bangladesh, United Kingdom but the hit is linked only to United States.

### H-710D2C — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-048448`. Evidence: CUS-048448, CUS-139694, NOTE-76C514.

The customer is linked only to Bangladesh, United Kingdom but the hit is linked only to United States.

Reference: The customer is linked only to Bangladesh, United Kingdom but the hit is linked only to United States.

### H-80B4B5 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-626609`. Evidence: NOTE-23FC8E, SR-01BFC3, CUS-626609.

The customer's date of birth 1977-01-11 (NOTE-23FC8E) agrees with the hit's 1976 or 1977. Both the customer and the hit are linked to France. The customer's name agrees with the hit's name Jérôme Kerviel.

Reference: The customer's date of birth 1977-01-11 (NOTE-23FC8E) agrees with the hit's 1976 or 1977. Both the customer and the hit are linked to France. The customer's name agrees with the hit's name Jérôme Kerviel.

### H-24D490 — SAME_ENTITY / NAME_LOCATION_MATCH

Customer: `CUS-245548`. Evidence: CUS-245548, KYC-247853.

Both the customer and the hit are linked to Germany. The customer's name agrees with the hit's name N26 Bank SE.

Reference: Both the customer and the hit are linked to Germany. The customer's name agrees with the hit's name N26 Bank SE.

### H-59908A — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-839781`. Evidence: CUS-839781, NOTE-2A1C15.

Both the customer and the hit are linked to Slovenia. The customer's name agrees with the hit's name Stefanović, Milan. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Slovenia. The customer's name agrees with the hit's name Stefanović, Milan. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-622EDD — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-270502`. Evidence: NOTE-CA9BBC, SR-A88751.

The customer's date of birth is 1979-04-17 (NOTE-CA9BBC) but the hit's search results put its birth year at 1972 or 1973.

Reference: The customer's date of birth is 1979-04-17 (NOTE-CA9BBC) but the hit's search results put its birth year at 1972 or 1973.

### H-4AA437 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-648181`. Evidence: KYC-DE8245.

The customer's date of birth is 1995-12-17 (KYC-DE8245) but the hit's profile notes put its birth year at 1986 or 1987.

Reference: The customer's date of birth is 1995-12-17 (KYC-DE8245) but the hit's profile notes put its birth year at 1986 or 1987.

### H-D9BBCC — DIFFERENT_ENTITY / NAME_MISMATCH_VERIFIED

Customer: `CUS-323991`. Evidence: NOTE-ADDA81, CUS-323991.

The customer's verified name is MARKUS GERHARD MUELLER (NOTE-ADDA81), which does not match the hit's name Mark Mueller. The customer is linked only to Germany but the hit is linked only to United States.

Reference: The customer is linked only to Germany but the hit is linked only to United States. The customer's verified name is MARKUS GERHARD MUELLER (NOTE-ADDA81), which does not match the hit's name Mark Mueller.

### H-2017F1 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-401918`. Evidence: CUS-401918, KYC-60A0F7.

The customer is linked only to United Kingdom but the hit is linked only to Pakistan.

Reference: The customer is linked only to United Kingdom but the hit is linked only to Pakistan.

### H-D6EDC1 — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-401918`. Evidence: CUS-401918, KYC-60A0F7.

The customer is linked only to United Kingdom but the hit is linked only to Pakistan.

Reference: The customer is linked only to United Kingdom but the hit is linked only to Pakistan.

### H-02115F — SAME_ENTITY / NAME_LOCATION_MATCH

Customer: `CUS-470646`. Evidence: CUS-470646, KYC-997803.

Both the customer and the hit are linked to Spain. The customer's name agrees with the hit's name Pescanova, Sociedad Anónima.

Reference: Both the customer and the hit are linked to Spain. The customer's name agrees with the hit's name Pescanova, Sociedad Anónima.

### H-2808BE — DIFFERENT_ENTITY / NAME_MISMATCH_VERIFIED

Customer: `CUS-149132`. Evidence: KYC-20EE17.

The customer's verified name is CHINEDU AZEEZ (KYC-20EE17), which does not match the hit's name Ridwan, Azeez.

Reference: The customer's verified name is CHINEDU AZEEZ (KYC-20EE17), which does not match the hit's name Ridwan, Azeez.

### H-32E48C — DIFFERENT_ENTITY / LOCATION_MISMATCH

Customer: `CUS-562751`. Evidence: CUS-562751, KYC-63356F, NOTE-2EF1F0.

The customer is linked only to Ghana, Netherlands but the hit is linked only to United States.

Reference: The customer is linked only to Ghana, Netherlands but the hit is linked only to United States.

### H-380854 — DIFFERENT_ENTITY / NAME_MISMATCH_VERIFIED

Customer: `CUS-485845`. Evidence: KYC-2EA887.

The customer's verified name is SARAH JOHNSON (KYC-2EA887), which does not match the hit's name Johnson, James Jacob.

Reference: The customer's verified name is SARAH JOHNSON (KYC-2EA887), which does not match the hit's name Johnson, James Jacob.

### H-7F2A6C — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-629156`. Evidence: NOTE-F1D4BE.

Both the customer and the hit are linked to Denmark. The customer's name agrees with the hit's name Carl E. Andersen. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

Reference: Both the customer and the hit are linked to Denmark. The customer's name agrees with the hit's name Carl E. Andersen. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-84548F — SAME_ENTITY / NAME_LOCATION_MATCH

Customer: `CUS-278765`. Evidence: CUS-278765, KYC-1EBF52.

Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Metropolitan Transportation Authority, Inc. (MTA).

Reference: Both the customer and the hit are linked to United States. The customer's name agrees with the hit's name Metropolitan Transportation Authority, Inc. (MTA).

### H-EDBB79 — DIFFERENT_ENTITY / NAME_MISMATCH_VERIFIED

Customer: `CUS-171566`. Evidence: NOTE-CB3D0D.

The customer's verified name is TASLIMA RAHIM ISLAM (NOTE-CB3D0D), which does not match the hit's name Islam, Md Saidul.

Reference: The customer's verified name is TASLIMA RAHIM ISLAM (NOTE-CB3D0D), which does not match the hit's name Islam, Md Saidul.

### H-0F3C96 — REVIEW / AMBIGUOUS_CUSTOMER_RECORD

Customer: `AMBIGUOUS`. Evidence: KYC-FB41DD, CUS-390024, NOTE-4A1210, CUS-623367, CUS-965373, KYC-92880F.

3 different people in the system of record fit the alert (CUS-205759, CUS-390024, CUS-623367) and they lead to different decisions: CUS-205759: DIFFERENT_ENTITY (NAME_MISMATCH_VERIFIED); CUS-390024: REVIEW (INSUFFICIENT_DATA); CUS-623367: REVIEW (INSUFFICIENT_DATA). A person must decide which customer was screened.

### H-BD709E — DIFFERENT_ENTITY / DECEASED

Customer: `CUS-343316`. Evidence: (none).

The hit's profile gives a date of death of 2022-03, before the customer was screened on 2026-11-14.

### H-5EEC5A — DIFFERENT_ENTITY / ENTITY_TYPE_MISMATCH

Customer: `CUS-559377`. Evidence: CUS-559377, KYC-30794E.

The customer is a company but the hit is an individual. The customer is linked only to Germany but the hit is linked only to Singapore.

### H-23805C — SAME_ENTITY / NAME_DOB_MATCH

Customer: `CUS-898557`. Evidence: NOTE-4A8FF2.

The customer's date of birth 1994-08-24 (NOTE-4A8FF2) agrees with the hit's 1994, 1993. The customer's name agrees with the hit's name Usman, Muhammad.

### H-2B5507 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `AMBIGUOUS`. Evidence: KYC-36C899, CUS-284928, KYC-9CD4AA, CUS-385461, KYC-62E924, CUS-885257.

3 different people in the system of record fit the alert (CUS-284928, CUS-385461, CUS-885257); each leads to DIFFERENT_ENTITY. The customer's date of birth is 1994-12-22 (KYC-36C899) but the hit's profile notes put its birth year at 1973. The customer is linked only to Austria but the hit is linked only to Denmark, Iran, Singapore, United Arab Emirates.

### H-D48032 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-562288`. Evidence: KYC-299F4C, CUS-562288.

The customer's date of birth 1992-01-12 (KYC-299F4C) agrees with the hit's 1992, 1991. Both the customer and the hit are linked to Bangladesh. The customer's name agrees with the hit's name Mia, Badsha.

### H-08110E — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-725235`. Evidence: KYC-535606, CUS-725235.

The customer's date of birth 1999-02-11 (KYC-535606) agrees with the hit's 1999, 1998. Both the customer and the hit are linked to United Kingdom. The customer's name agrees with the hit's name Rahman, Abdul.

### H-AC1114 — DIFFERENT_ENTITY / DOB_MISMATCH

Customer: `CUS-717853`. Evidence: KYC-9FC168.

The customer's date of birth is 1968-08-20 (KYC-9FC168) but the hit's listed date of birth is 1968-01-12.

### H-8A1D28 — REVIEW / INSUFFICIENT_DATA

Customer: `CUS-623529`. Evidence: NOTE-C1E05D.

Both the customer and the hit are linked to Nigeria. The customer's name agrees with the hit's name Oluwaseun, Emmanuel. Nothing in the customer's records contradicts the hit, and the date of birth cannot be compared with it, so the hit can be neither cleared nor confirmed.

### H-A9AA55 — SAME_ENTITY / NAME_DOB_LOCATION_MATCH

Customer: `CUS-558035`. Evidence: KYC-685B2C, SR-AE2CE1, CUS-529109, CUS-558035.

The customer's date of birth 1959-09-12 (KYC-685B2C) agrees with the hit's 1959 or 1960. Both the customer and the hit are linked to Italy. The customer's name agrees with the hit's name Giampiero Fiorani.

