# Clearsight: spot check of the hardened dev output

**Result:** Prioritise the three verified-name clears below for a customer-to-KYC linkage check. Six country-only clears and one search-derived DOB clear merit secondary QA. These are plausible risks, not ten known wrong answers. None of the ten sampled reviews had enough evidence to decide safely.

**Sample:** `output/dev.jsonl` at `45ddc8c` (465 clears, 229 reviews). Within each decision, rank hits by SHA-256 of UTF-8 `edge-audit-2026-11-21-v1|<decision>|<hit_id>`, ascending; take the first 20 clears and first 10 reviews. Reusing the seed after hardening lets us compare versions without choosing cases by outcome. Compared output with the workbook-derived dev records. IDs below refer to those files. This sample is not an estimate of unseen accuracy.

## Clearances to check first

| Hit | Deciding source | Why an analyst should look again |
|---|---|---|
| H-006E36 | KYC-CAB2E3 | The screened and linked names agree with the hit; birth year and US location also fit. Only the approved check gives a different given name. Verify the applicant belongs to the screened holder. |
| H-FE1415 | KYC-13A69E | Linked customer records fit the hit's name, possible birth year and UK connection; the verified given name differs. Check the record grouping and applicant link. |
| H-E954EE | KYC-096881 | The hit contains the screened given name and surname, but the approved check supplies another given name. No hit DOB settles which identity was screened. |

Verified beats declared under the SOP. A disagreement alone does not invalidate the check; the follow-up is to verify **whose check it is**.

| Other single-signal clears | Evidence checked | Residual risk |
|---|---|---|
| H-B28CF3, H-58CFBE | NOTE-3E9982, NOTE-C3E53D respectively | US documents; hits in Bangladesh and China respectively. Name parts overlap and neither hit supplies a DOB. |
| H-E3A326, H-D71960 | KYC-A932A4, KYC-68E6D6 respectively | Similar name forms; German versus Brazilian ties, or UK/Danish versus Pakistani ties. No hit DOB. |
| H-AE0262, H-4D89A9 | CUS-905593, KYC-197B8B | Same Spanish customer, two distinct hits (Brazil and Colombia). Both share name parts; neither has a comparable DOB. |
| H-953146 | KYC-72276C, SR-AE2CE1 | Name and country agree. The 1962 vs 1959/60 contradiction depends on attributing one age-bearing search result to this hit. Verify the result's subject. |

The six location decisions follow the disjoint-country rule on the available facts. A missing residence history could change that comparison; it is not evidence that the countries actually overlap.

## Other ten sampled clears

| Hit(s) | Cross-check |
|---|---|
| H-640BA3, H-007074 | Austrian registration (KYC-0853F2); first hit has distinct Russian registration details, second describes a clone. |
| H-8DAC34, H-75D62E | Incorporation in 2014 (KYC-2D2D44) follows the respective 2013 and 2009 reports. |
| H-15E86F, H-100E0E | Verified given names differ (KYC-73F0E9, KYC-A932A4); countries also disjoint. |
| H-CD2704 | All five candidate customers have 1984 birth years versus 1992/93 for the hit; choosing among them would not change the decision. |
| H-7A7ADF | KYC-DE8245 gives 1995; dated age in profile implies 1973/74. |
| H-30CCE6 | KYC-48E3DE gives 1977; SR-A96BC2 implies 1968/69. Search attribution matters here too. |
| H-02F3CB | Given name on KYC-DA4324 differs; the surname alone is insufficient. The one-year birth tolerance is not an independent clear. |

## Ten reviews: what is still missing?

| Hit(s) | Why retain REVIEW |
|---|---|
| H-92BC26 | Six plausible people yield different decisions. Need a reliable customer link, not another name comparison. |
| H-665870, H-6833AE | Names and birth years agree (NOTE-4A8FF2 and NOTE-EAF1AD respectively), but countries differ. The SOP explicitly sends that combination to review. |
| H-9FBBCA, H-EC5FED | NOTE-204014 and NOTE-3CA967 establish shared residence respectively, but there is no attributable hit DOB. |
| H-26E53C, H-E4DDC7, H-03C536, H-FBAD2B, H-B5160F | Country and name overlap; the customer DOB is available but a corresponding hit DOB is not. Name and country cannot confirm a person. |
