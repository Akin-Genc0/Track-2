# Track 2 data + output format (for helpers)

Dataset: `/workspace/track2/data/dev/` (rebuilt from the organisers' browsing workbook, Google Sheet
1wbfVyDrnnasxenUTr9jwlti1zWGrBWx6Hl505W47iLM; list fields split from "; " back into JSON arrays).
NOTE: the official dev/ JSONL files were not obtainable publicly; field names are the organisers', but
array-vs-string typing is our reconstruction. Loaders must accept either a list or a "; "-joined string.

Files (JSON Lines unless noted):
- alerts.jsonl: alert_id, screened_at, customer_name, entity_type (Individual|Company), dob, country, city,
  account_ref, login_handle, email, hit_count, hit_ids[]
- hits.jsonl: hit_id, alert_id, match_score, entity_type, name, aliases[], gender, dobs[], place_of_birth[],
  life_status, deceased_date, nationality[], citizenship[], countries[], addresses[], identifiers[],
  categories[], primary_category, position_or_allegation, details, relationships[], profile_notes, sources[], source_urls[]
- customers.jsonl: record_id (CUS-xxxxxx), entity_type, full_name, preferred_name, login_name, dob (mixed formats,
  DD/MM/YYYY is day-first), nationality, residence_country (names or ISO2), city, address, email, phone, occupation,
  employer, registration_number, onboarded_at, status, last_kyc_refresh
- accounts.jsonl: account_id, customer_id, login_handle, phone, opened_at, status (52 joint accounts = 2 rows)
- onboarding.jsonl: account_id, customer_id, kyc_applicant_id, onboarded_at
- kyc_checks.jsonl: check_id, applicant_id, provider, verified_name, verified_dob, document_type, document_number,
  document_country, result (approved|rejected|expired), checked_at
- notes.jsonl: note_id, requester_email, created_at, channel (kyc|phone|app|email), text (free text: KYC write-ups, residence history)
- search_results.jsonl: result_id, query (lowercase name words sorted alphabetically), title, snippet, source
- practice_labels.jsonl: hit_id, alert_id, decision, reason_codes[], customer_record_ids[], evidence[], reference_reason, path
- name_variants.json: {"given_names": [[...],...], "company_legal_forms": [...]}
- POLICY.md: the identity SOP (decisions, principles, reason codes)

Output: `/workspace/track2/output/dev.jsonl`, one line per hit (819):
{"hit_id","alert_id","decision": DIFFERENT_ENTITY|SAME_ENTITY|REVIEW,
 "reason_code": TEMPORAL_IMPOSSIBILITY|DOB_MISMATCH|LOCATION_MISMATCH|NAME_MISMATCH_VERIFIED|ENTITY_TYPE_MISMATCH|DECEASED
              |NAME_DOB_LOCATION_MATCH|NAME_DOB_MATCH|NAME_LOCATION_MATCH|INSUFFICIENT_DATA|AMBIGUOUS_CUSTOMER_RECORD,
 "customer_record_id": "CUS-..." | "AMBIGUOUS" | null,
 "reason": "2-4 sentences", "evidence": ["CUS-...","KYC-...","NOTE-...","SR-..."]}
Run: `system/run <data folder> <output file>`
