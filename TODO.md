# Sanctions Screening Task Outline

This branch contains planning only. No dataset processing or screening logic has been implemented.

## Next Steps

- [ ] Inspect the data-room files, `POLICY.md`, and `name_variants.json`.
- [ ] Map alert-to-customer resolution paths and enforce customer-record linking rules.
- [ ] Build normalized customer profiles from customer, account, onboarding, KYC, and note records.
- [ ] Gather and normalize hit facts, including aliases, dates, locations, entity type, notes, and search results.
- [ ] Implement the policy decision rules and required reason codes for each hit.
- [ ] Use the 50 practice labels to validate record resolution and decision behavior.
- [ ] Produce the required per-hit submission output with cited source record IDs.
- [ ] Add automated checks for policy edge cases and output schema validation.
