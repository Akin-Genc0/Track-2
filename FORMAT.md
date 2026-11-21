# Track 2 data + output format (for helpers)

Official input is the organisers' `dev/` folder (gitignored; never commit it). The optional
workbook reconstruction under `data/dev/` is accepted by the same loader.

Files (JSON Lines unless noted):
- alerts.jsonl: alert_id, screened_at, customer: {name, entity_type (Individual|Company), dob, country, city},
  account_ref, login_handle, email, hit_ids[]. (The workbook form is flat: customer_name, entity_type, dob, country, city.)
- hits.jsonl: hit_id, alert_id, match_score (int), entity_type, name, first_name, middle_name, last_name,
  best_matching_name, aliases[], gender, dobs[], place_of_birth (null or a place), life_status, deceased_date,
  nationality[], citizenship[], countries[], addresses[], identifiers[], categories[], primary_category,
  subcategories[], position_or_allegation, details (dict, e.g. {"pep": "..."}, or a string in the workbook form),
  relationships[], profile_notes, sources[], source_urls[]
- customers.jsonl: record_id (CUS-xxxxxx), entity_type, full_name, preferred_name, login_name, dob (mixed formats,
  DD/MM/YYYY is day-first), nationality, residence_country (names or ISO2), city, address, email, phone, occupation,
  employer, registration_number, onboarded_at, status, last_kyc_refresh
- accounts.jsonl: account_id, customer_id, login_handle, phone, opened_at, status (52 joint accounts = 2 rows)
- onboarding.jsonl: account_id, customer_id, kyc_applicant_id, onboarded_at
- kyc_checks.jsonl: check_id, applicant_id, provider, verified_name, verified_dob, document_type, document_number,
  document_country, result (approved|rejected|expired), checked_at
- notes.jsonl: note_id, requester_email, created_at, channel (kyc|phone|app|email), text (free text: KYC write-ups, residence history)
- search_results.jsonl: result_id, query (lowercase name words sorted alphabetically), title, snippet, source
- practice_labels.jsonl: hit_id, alert_id, decision, reason_codes[], customer_record_ids[], evidence[], reference_reason,
  path (a list of steps; the workbook form may be a single string)
- name_variants.json: {"description": "...", "groups": [[...],...], "company_legal_forms": [...]}
  (the workbook form uses "given_names" in place of "groups")
- POLICY.md: the identity SOP, with markdown `#` / `##` headers and the reason-code table

Output: `output/dev.jsonl`, one line per hit (819):
{"hit_id","alert_id","decision": DIFFERENT_ENTITY|SAME_ENTITY|REVIEW,
 "reason_code": TEMPORAL_IMPOSSIBILITY|DOB_MISMATCH|LOCATION_MISMATCH|NAME_MISMATCH_VERIFIED|ENTITY_TYPE_MISMATCH|DECEASED
              |NAME_DOB_LOCATION_MATCH|NAME_DOB_MATCH|NAME_LOCATION_MATCH|INSUFFICIENT_DATA|AMBIGUOUS_CUSTOMER_RECORD,
 "customer_record_id": "CUS-..." | "AMBIGUOUS" | null,
 "reason": "2-4 sentences", "evidence": ["CUS-...","KYC-...","NOTE-...","SR-..."]}
Run: `system/run dev output/dev.jsonl`
