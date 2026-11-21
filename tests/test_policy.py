"""Synthetic rare-situation tests for the policy rules. Run: python3 tests/test_policy.py"""
import json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "..", "system", "run")
NV = {"given_names": [["muhammad", "mohammed"], ["robert", "bob"]], "company_legal_forms": ["ltd", "gmbh", "sa", "llc"]}


def cust(rid, name, dob, nat="United Kingdom", res="GB", email=None, phone=None, et="Individual"):
    return {"record_id": rid, "entity_type": et, "full_name": name, "preferred_name": None, "login_name": None, "dob": dob,
            "nationality": nat, "residence_country": res, "city": "London", "address": "1 High St, London",
            "email": email or rid.lower() + "@x.example", "phone": phone or "+44 " + rid[-6:] + "0000"}


CASES = []   # (name, customers, accounts, onboarding, kyc, notes, alert, hit, search, expected decision, expected code)


def case(name, customers, alert, hit, exp, code=None, accounts=(), onboarding=(), kyc=(), notes=(), search=(), says=()):
    CASES.append(dict(name=name, customers=customers, alert=alert, hit=hit, exp=exp, code=code, says=list(says), accounts=list(accounts),
                      onboarding=list(onboarding), kyc=list(kyc), notes=list(notes), search=list(search)))


def alert(aid, name, acc=None, et="Individual", dob=None, country=None):
    return {"alert_id": aid, "screened_at": "2026-11-06", "customer_name": name, "entity_type": et, "dob": dob, "country": country,
            "city": None, "account_ref": acc, "login_handle": None, "email": None, "hit_ids": ["H-" + aid[2:]]}


def hit(aid, name, et="Individual", dobs=(), countries=(), notes=None, deceased=None, cat="PEP", aliases=()):
    return {"hit_id": "H-" + aid[2:], "alert_id": aid, "entity_type": et, "name": name, "aliases": list(aliases), "dobs": list(dobs),
            "countries": list(countries), "addresses": [], "nationality": [], "citizenship": [], "place_of_birth": [],
            "categories": [cat], "primary_category": cat, "profile_notes": notes, "deceased_date": deceased}


acc = lambda a, c: {"account_id": a, "customer_id": c, "login_handle": None, "phone": None}
onb = lambda a, c, app: {"account_id": a, "customer_id": c, "kyc_applicant_id": app}
chk = lambda cid, app, name, dob, ctry, res, date, num="P123456": {"check_id": cid, "applicant_id": app, "verified_name": name,
        "verified_dob": dob, "document_type": "passport", "document_number": num, "document_country": ctry, "result": res, "checked_at": date}

# 1 name+DOB agree, location differs -> REVIEW (location may not clear)
case("name_dob_agree_location_differs", [cust("CUS-000001", "John Smith", "1970-05-05")], alert("A-000001", "John Smith", "ACC-1"),
     hit("A-000001", "Smith, John", dobs=["1970"], countries=["Peru"]), "REVIEW", accounts=[acc("ACC-1", "CUS-000001")])
# 2 deceased after screening -> not DECEASED
case("deceased_after_screening", [cust("CUS-000002", "Jane Doe", "1970-05-05")], alert("A-000002", "Jane Doe", "ACC-2"),
     hit("A-000002", "Jane Doe", countries=["United Kingdom"], deceased="2027-01-01"), "REVIEW", accounts=[acc("ACC-2", "CUS-000002")])
# 3 deceased before screening -> DECEASED
case("deceased_before", [cust("CUS-000003", "Jane Roe", "1970-05-05")], alert("A-000003", "Jane Roe", "ACC-3"),
     hit("A-000003", "Jane Roe", countries=["United Kingdom"], deceased="2020-03"), "DIFFERENT_ENTITY", "DECEASED", accounts=[acc("ACC-3", "CUS-000003")])
# 4 company incorporated after earliest dated report -> TEMPORAL
case("company_temporal", [cust("CUS-000004", "Acme Widgets Ltd", "2015-01-01", et="Company")], alert("A-000004", "Acme Widgets Ltd", "ACC-4", et="Company"),
     hit("A-000004", "Acme Widgets Limited", et="Company", countries=["United Kingdom"],
         notes="According to Example Times; March 3, 2010: Acme Widgets was fined."), "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", accounts=[acc("ACC-4", "CUS-000004")])
# 5 rejected check is not evidence: rejected check name mismatch must not clear
case("rejected_check_ignored", [cust("CUS-000005", "Robert Brown", "1980-01-01")], alert("A-000005", "Robert Brown", "ACC-5"),
     hit("A-000005", "Brown, Bob", countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-5", "CUS-000005")],
     onboarding=[onb("ACC-5", "CUS-000005", "APP-5")], kyc=[chk("KYC-5", "APP-5", "Susan Green", "1980-01-01", "United Kingdom", "rejected", "2024-01-01")])
# 6 expired check ignored too
case("expired_check_ignored", [cust("CUS-000006", "Robert Black", "1980-01-01")], alert("A-000006", "Robert Black", "ACC-6"),
     hit("A-000006", "Black, Robert", countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-6", "CUS-000006")],
     onboarding=[onb("ACC-6", "CUS-000006", "APP-6")], kyc=[chk("KYC-6", "APP-6", "Peter White", "1990-01-01", "France", "expired", "2024-01-01")])
# 7 placeholder name: cannot confirm on name
case("placeholder_name_no_confirm", [cust("CUS-000007", "Sani 0000 0000", "1970-05-05")], alert("A-000007", "Sani 0000", "ACC-7"),
     hit("A-000007", "Sani", dobs=["1970-05-05"], countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-7", "CUS-000007")])
# 8 ambiguous: two people, different decisions -> REVIEW AMBIGUOUS
case("ambiguous_people", [cust("CUS-000008", "Omar Khan", "1970-05-05"), cust("CUS-000009", "Omar Khan", "1990-02-02")],
     alert("A-000008", "Omar Khan"), hit("A-000008", "Omar Khan", dobs=["1970"], countries=["United Kingdom"]), "REVIEW", "AMBIGUOUS_CUSTOMER_RECORD")
# 9 no customer found -> REVIEW, null
case("unresolved", [cust("CUS-000010", "Zed Zulu", "1970-05-05")], alert("A-000010", "Quentin Tarantula"),
     hit("A-000010", "Quentin Tarantula", dobs=["1950"], countries=["Peru"]), "REVIEW", "INSUFFICIENT_DATA")
# 10 type mismatch
case("type_mismatch", [cust("CUS-000011", "Delta Trading Ltd", None, et="Company")], alert("A-000011", "Delta Trading Ltd", "ACC-11", et="Company"),
     hit("A-000011", "Delta Trading", et="Individual"), "DIFFERENT_ENTITY", "ENTITY_TYPE_MISMATCH", accounts=[acc("ACC-11", "CUS-000011")])
# 11 territory counts as own country: Puerto Rico vs United States -> location mismatch
case("territory_own_country", [cust("CUS-000012", "Maria Lopez Ruiz", "1980-01-01", nat="United States", res="US")], alert("A-000012", "Maria Lopez Ruiz", "ACC-12"),
     hit("A-000012", "Lopez Ruiz, Maria", countries=["Puerto Rico"]), "DIFFERENT_ENTITY", "LOCATION_MISMATCH", accounts=[acc("ACC-12", "CUS-000012")])
# 12 'International' is not a country -> no location clear
case("international_not_country", [cust("CUS-000013", "Ali Hassan", "1980-01-01")], alert("A-000013", "Ali Hassan", "ACC-13"),
     hit("A-000013", "Hassan, Ali", countries=["International", "Europe"]), "REVIEW", accounts=[acc("ACC-13", "CUS-000013")])
# 13 year only DOB on customer agrees with full date on hit -> SAME
case("year_vs_full_date", [cust("CUS-000014", "Peter Novak", "1975")], alert("A-000014", "Peter Novak", "ACC-14"),
     hit("A-000014", "Novak, Peter", dobs=["1975-06-01"], countries=["United Kingdom"]), "SAME_ENTITY", accounts=[acc("ACC-14", "CUS-000014")])
# 14 DOB one year off -> not contradicted (REVIEW), two years off -> DOB_MISMATCH
case("dob_one_year_off", [cust("CUS-000015", "Karl Weiss", "1976-01-01")], alert("A-000015", "Karl Weiss", "ACC-15"),
     hit("A-000015", "Weiss, Karl", dobs=["1975"], countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-15", "CUS-000015")])
case("dob_two_years_off", [cust("CUS-000016", "Karl Weisz", "1977-01-01")], alert("A-000016", "Karl Weisz", "ACC-16"),
     hit("A-000016", "Weisz, Karl", dobs=["1975"], countries=["United Kingdom"]), "DIFFERENT_ENTITY", "DOB_MISMATCH", accounts=[acc("ACC-16", "CUS-000016")])
# 15 same year, different month -> DOB_MISMATCH
case("same_year_month_differs", [cust("CUS-000017", "Lena Berg", "1980-03-10")], alert("A-000017", "Lena Berg", "ACC-17"),
     hit("A-000017", "Berg, Lena", dobs=["1980-07"], countries=["United Kingdom"]), "DIFFERENT_ENTITY", "DOB_MISMATCH", accounts=[acc("ACC-17", "CUS-000017")])
# 16 ambiguous D/M on hit (04/05/1980) must not clear on month
case("ambiguous_dm_hit", [cust("CUS-000018", "Lena Borg", "1980-04-05")], alert("A-000018", "Lena Borg", "ACC-18"),
     hit("A-000018", "Borg, Lena", dobs=["05/04/1980"], countries=["United Kingdom"]), "SAME_ENTITY", accounts=[acc("ACC-18", "CUS-000018")])
# 17 verified name from note in Title Case: mismatch clears
case("note_verified_name_titlecase", [cust("CUS-000019", "Jake Miller", "1980-01-01", email="jm@x.example")], alert("A-000019", "Jake Miller", "ACC-19"),
     hit("A-000019", "Miller, Jacob Henry", countries=["United Kingdom"]), "DIFFERENT_ENTITY", "NAME_MISMATCH_VERIFIED", accounts=[acc("ACC-19", "CUS-000019")],
     notes=[{"note_id": "NOTE-19", "requester_email": "jm@x.example", "created_at": "2024-01-01", "channel": "kyc",
             "text": "Veriff verified the passport of Sarah Miller (born 1 January 1980) from the United Kingdom on 2024-01-01."}])
# 18 lower-case verified name in note: never clears on name
case("note_verified_name_lowercase", [cust("CUS-000020", "Jake Mills", "1980-01-01", email="jk@x.example")], alert("A-000020", "Jake Mills", "ACC-20"),
     hit("A-000020", "Mills, Jacob Henry", countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-20", "CUS-000020")],
     notes=[{"note_id": "NOTE-20", "requester_email": "jk@x.example", "created_at": "2024-01-01", "channel": "kyc",
             "text": "veriff verified the passport of sarah mills (born 1 january 1980) from the united kingdom on 2024-01-01."}])
# 19 rejected KYC note is not evidence
case("rejected_note", [cust("CUS-000021", "Tom Okafor", "1980-01-01", email="to@x.example")], alert("A-000021", "Tom Okafor", "ACC-21"),
     hit("A-000021", "Okafor, Thomas", countries=["United Kingdom"]), "REVIEW", accounts=[acc("ACC-21", "CUS-000021")],
     notes=[{"note_id": "NOTE-21", "requester_email": "to@x.example", "created_at": "2024-01-01", "channel": "kyc",
             "text": "Onfido rejected the passport for GRACE OKAFOR (DOB 2001-01-01) from Nigeria on 2024-01-01: document expired."}])
# 20 too young at earliest dated report
case("too_young", [cust("CUS-000022", "Tom Okoro", "2004-01-01")], alert("A-000022", "Tom Okoro", "ACC-22"),
     hit("A-000022", "Thomas Okoro", countries=["United Kingdom"], notes="According to Daily Example; June 1, 2011: Thomas Okoro was charged with fraud."),
     "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", accounts=[acc("ACC-22", "CUS-000022")])
# 21 dated report in a non-qualifying wording does not count
case("non_qualifying_report", [cust("CUS-000023", "Tom Okeke", "2004-01-01")], alert("A-000023", "Tom Okeke", "ACC-23"),
     hit("A-000023", "Thomas Okeke", countries=["United Kingdom"], notes="On June 1, 2011, Thomas Okeke was charged with fraud."),
     "REVIEW", accounts=[acc("ACC-23", "CUS-000023")])
# 22 numbered list items in notes are not ages
case("list_numbers_not_ages", [cust("CUS-000024", "Rob James", "1955-01-01")], alert("A-000024", "Rob James", "ACC-24"),
     hit("A-000024", "Robert James", countries=["United Kingdom"], notes="According to Regulator X; September 15, 2005: order issued as the security was not (1) covered, (2) exempt or (3) registered."),
     "REVIEW", accounts=[acc("ACC-24", "CUS-000024")])
# 23 a month-only dated report ("According to ...; January 1997:") is not the policy's full-date form and never clears
case("month_only_report", [cust("CUS-000025", "Jim Okafor", "1993-03-11")], alert("A-000025", "Jim Okafor", "ACC-25"),
     hit("A-000025", "James Okafor", countries=["United Kingdom"], notes="According to Regulator X; January 1997: James Okafor was fined."),
     "REVIEW", accounts=[acc("ACC-25", "CUS-000025")])
# 24 two people fit and both are cleared: the reason names each one's own countries
case("ambiguous_cleared_names_each_country", [cust("CUS-000026", "Ada Eze", "1980-01-01", nat="France", res="FR"),
                                             cust("CUS-000027", "Ada Eze", "1985-02-02", nat="Chile", res="CL")],
     alert("A-000026", "Ada Eze"), hit("A-000026", "Ada Eze", countries=["Japan"]), "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
     says=["CUS-000026, linked to France", "CUS-000027, linked to Chile"])
# 25 an explanation says which side is missing: no hit DOB -> REVIEW says so; no hit country -> NAME_DOB_MATCH says so
case("review_says_hit_dob_missing", [cust("CUS-000028", "Ada Obi", "1980-01-01")], alert("A-000028", "Ada Obi"),
     hit("A-000028", "Ada Obi", countries=["United Kingdom"]), "REVIEW", "INSUFFICIENT_DATA",
     says=["the hit gives no date of birth to compare"])
case("name_dob_match_says_country_missing", [cust("CUS-000029", "Ada Nwosu", "1980-01-01")], alert("A-000029", "Ada Nwosu"),
     hit("A-000029", "Ada Nwosu", dobs=["1980-01-01"]), "SAME_ENTITY", "NAME_DOB_MATCH",
     says=["because the hit lists no country"])

fails = 0
for c in CASES:
    d = tempfile.mkdtemp()
    w = lambda n, rows: open(os.path.join(d, n + ".jsonl"), "w").write("".join(json.dumps(r) + "\n" for r in rows))
    w("customers", c["customers"]); w("alerts", [c["alert"]]); w("hits", [c["hit"]]); w("accounts", c["accounts"])
    w("onboarding", c["onboarding"]); w("kyc_checks", c["kyc"]); w("notes", c["notes"]); w("search_results", c["search"])
    json.dump(NV, open(os.path.join(d, "name_variants.json"), "w"))
    out = os.path.join(d, "out.jsonl")
    subprocess.run([RUN, d, out], check=True, stderr=subprocess.DEVNULL)
    r = json.loads(open(out).readline())
    ok = r["decision"] == c["exp"] and (c["code"] is None or r["reason_code"] == c["code"]) and all(x in r["reason"] for x in c["says"])
    fails += not ok
    print(("PASS " if ok else "FAIL ") + c["name"], "->", r["decision"], r["reason_code"], "" if ok else "| " + r["reason"])
    shutil.rmtree(d)
print(f"{len(CASES) - fails}/{len(CASES)} passed")
sys.exit(1 if fails else 0)
