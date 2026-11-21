"""Official dev-format fixtures: nested alert.customer, details dict, name_variants.groups,
POLICY.md # headers, practice path as a list, place_of_birth null, int match_score."""
import json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system"))
sys.path.insert(0, str(ROOT / "tools"))

from data import DataRoom, flatten_details, load_name_variants, normalize, as_list
from hitfacts import HitFacts, build_search_index
from textutil import NameMatcher
import check_submission


POLICY = """# Screening alert review: identity SOP

## Reason codes

| Decision | Reason code | Use it when |
|---|---|---|
| `DIFFERENT_ENTITY` | `DOB_MISMATCH` | dates contradict |
| `DIFFERENT_ENTITY` | `LOCATION_MISMATCH` | countries differ |
| `SAME_ENTITY` | `NAME_DOB_LOCATION_MATCH` | name, date and country agree |
| `REVIEW` | `INSUFFICIENT_DATA` | nothing settles it |
"""

NAME_VARIANTS = {
    "description": "Groups of given-name forms and company legal forms.",
    "groups": [
        ["muhammad", "mohammed", "mohammad", "mohamed"],
        ["abdul", "abdel", "abd"],
    ],
    "company_legal_forms": ["ltd", "gmbh", "sa", "llc"],
}

DETAILS_PEP = {
    "pep": "Deputy for Zamora | Spain | National | PEP | (2004-4-2–2008-1-15) | Inactive | Legislature"
}


def _room(folder, **files):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "POLICY.md").write_text(files.pop("POLICY.md", POLICY))
    (folder / "name_variants.json").write_text(json.dumps(files.pop("name_variants.json", NAME_VARIANTS)))
    for name, rows in files.items():
        with open(folder / name, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")


class OfficialFormatTests(unittest.TestCase):
    def test_nested_alert_customer(self):
        row = normalize({
            "alert_id": "A-1",
            "customer": {"name": "Ada Lovelace", "entity_type": "Individual",
                         "dob": "1815-12-10", "country": "United Kingdom", "city": "London"},
            "hit_ids": ["H-1"],
        }, "alerts")
        self.assertEqual(row["customer_name"], "Ada Lovelace")
        self.assertEqual(row["dob"], "1815-12-10")
        self.assertEqual(row["country"], "United Kingdom")
        self.assertEqual(row["entity_type"], "Individual")
        self.assertEqual(row["city"], "London")

    def test_name_variants_groups_and_description_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "name_variants.json").write_text(json.dumps(NAME_VARIANTS))
            groups, forms = load_name_variants(d)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][0], "muhammad")
        self.assertEqual(len(forms), 4)
        self.assertTrue(all("Groups of given-name" not in " ".join(g) for g in groups))

    def test_details_flattened_but_not_read_as_dob_country_or_deceased(self):
        raw = {
            "hit_id": "H-1", "alert_id": "A-1", "name": "Elvira Velasco Morillo",
            "entity_type": "Individual", "dobs": ["1967", "1968"],
            "countries": ["Spain"], "place_of_birth": None, "deceased_date": None,
            "details": DETAILS_PEP, "profile_notes": "She was a 30-year-old deputy in November 1998.\n\nCareer follows.",
            "match_score": 100, "first_name": "Elvira", "middle_name": None,
            "last_name": "Velasco Morillo", "best_matching_name": "Velasco Morillo, Elvira",
            "subcategories": ["PEP"], "categories": ["PEP"],
        }
        hit = normalize(dict(raw), "hits")
        self.assertIsInstance(hit["details"], str)
        self.assertIn("Spain", hit["details"])
        self.assertIn("2004", hit["details"])
        matcher = NameMatcher([], [])
        base = HitFacts(hit, matcher, {})
        # Same facts as a hit with details removed (parsers must not harvest PEP text).
        stripped = dict(hit, details="")
        other = HitFacts(stripped, matcher, {})
        self.assertEqual(base.countries, other.countries)
        self.assertEqual(base.countries, ["Spain"])
        self.assertEqual({tuple(sorted(d["years"])) for d in base.dobs},
                         {tuple(sorted(d["years"])) for d in other.dobs})
        self.assertTrue(any(1967 in d["years"] and 1968 in d["years"] for d in base.dobs))
        self.assertIsNone(base.deceased)
        self.assertIsNone(other.deceased)
        self.assertIn(hit["best_matching_name"], base.names)

        # If details were prepended to profile notes, dated-report lines can disappear;
        # they must not invent a birth date, death date, or extra country.
        poisoned = dict(hit, profile_notes=flatten_details(DETAILS_PEP) + ". " + hit["profile_notes"])
        bad = HitFacts(poisoned, matcher, {})
        self.assertEqual(bad.countries, ["Spain"])
        self.assertIsNone(bad.deceased)
        # Tenure years such as 2004-4-2 must not become a date of birth.
        self.assertFalse(any(2004 in d["years"] or 2008 in d["years"] for d in bad.dobs))

    def test_place_of_birth_null_and_int_match_score(self):
        hit = normalize({
            "hit_id": "H-2", "name": "Test Person", "place_of_birth": None,
            "match_score": 100, "details": {}, "dobs": ["1990"],
        }, "hits")
        self.assertIsNone(hit["place_of_birth"])
        self.assertEqual(hit["match_score"], 100)
        hf = HitFacts(hit, NameMatcher([], []), {})
        self.assertEqual(hf.countries, [])

    def test_practice_path_as_list(self):
        path = [
            "account_ref ACC-1 -> accounts -> customer CUS-1",
            "SAME_ENTITY ['NAME_DOB_MATCH']: agrees.",
        ]
        self.assertEqual(as_list(path), path)

    def test_check_submission_parses_hash_header_policy(self):
        with tempfile.TemporaryDirectory() as d:
            _room(d,
                  **{"alerts.jsonl": [{"alert_id": "A-1", "customer": {"name": "Ann"}, "hit_ids": ["H-1"]}],
                     "hits.jsonl": [{"hit_id": "H-1", "alert_id": "A-1", "name": "Ann", "details": DETAILS_PEP}],
                     "customers.jsonl": [{"record_id": "CUS-000001", "full_name": "Ann"}],
                     "accounts.jsonl": [], "onboarding.jsonl": [], "kyc_checks.jsonl": [],
                     "notes.jsonl": [], "search_results.jsonl": [],
                     "practice_labels.jsonl": [{"hit_id": "H-1", "path": ["step one", "step two"]}]})
            out = Path(d) / "out.jsonl"
            out.write_text(json.dumps({
                "hit_id": "H-1", "alert_id": "A-1", "decision": "REVIEW",
                "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                "reason": "No customer record settles this hit. A person must review it.",
                "evidence": [],
            }) + "\n")
            errors = check_submission.validate(str(out), d)
            self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
