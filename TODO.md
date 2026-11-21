# Sanctions Screening Task Outline

This branch contains planning only. No dataset processing or screening logic has been implemented.

## Workstreams

### Person 1: Data Discovery and Customer Resolution

- [ ] Inspect the data-room files, `POLICY.md`, and `name_variants.json`.
- [ ] Map alert-to-customer resolution paths and enforce customer-record linking rules.
- [ ] Define how to detect ambiguous customer records.

### Person 2: Customer Profile Assembly

- [ ] Build normalized customer profiles from customer, account, onboarding, KYC, and note records.
- [ ] Apply KYC reliability rules, including approved and most-recent identity checks.
- [ ] Expose source record IDs for every resolved customer fact.

### Person 3: Hit Fact Extraction

- [ ] Gather and normalize hit facts, including aliases, dates, locations, entity type, notes, and search results.
- [ ] Implement name normalization, name variants, placeholder removal, and minor-edit matching.
- [ ] Expose source record IDs for every extracted hit fact.

### Person 4: Decisioning and Validation

- [ ] Implement the policy decision rules and required reason codes for each hit.
- [ ] Produce the required per-hit submission output with cited source record IDs.
- [ ] Use the 50 practice labels to validate record resolution and decision behavior.
- [ ] Add automated checks for policy edge cases and output schema validation.
