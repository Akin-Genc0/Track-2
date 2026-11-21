"""Shadow test-set generator: synthetic alerts with NEW customers, fresh free-text phrasings and ground truth labels
derived (by construction) from POLICY.md. Independent of system/ code.

  python3 tools/shadow.py gen  <out_dir> [seed]       -> writes a data room + shadow_labels.jsonl
  python3 tools/shadow.py score <out_dir> <pred.jsonl> -> cost-matrix score + error breakdown by scenario
"""
import json, os, random, re, sys, unicodedata, collections

MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
COUNTRIES = {  # name: (iso2, demonym)
    "Kenya": ("KE", "Kenyan"), "Ghana": ("GH", "Ghanaian"), "Nigeria": ("NG", "Nigerian"), "Germany": ("DE", "German"),
    "France": ("FR", "French"), "Spain": ("ES", "Spanish"), "Italy": ("IT", "Italian"), "Poland": ("PL", "Polish"),
    "Sweden": ("SE", "Swedish"), "Brazil": ("BR", "Brazilian"), "Mexico": ("MX", "Mexican"), "Pakistan": ("PK", "Pakistani"),
    "Bangladesh": ("BD", "Bangladeshi"), "India": ("IN", "Indian"), "Turkey": ("TR", "Turkish"), "Egypt": ("EG", "Egyptian"),
    "United Kingdom": ("GB", "British"), "United States": ("US", "American"), "Canada": ("CA", "Canadian"),
    "Portugal": ("PT", "Portuguese"), "Romania": ("RO", "Romanian"), "Serbia": ("RS", "Serbian"), "Ukraine": ("UA", "Ukrainian"),
    "Philippines": ("PH", "Filipino"), "Indonesia": ("ID", "Indonesian"), "Morocco": ("MA", "Moroccan"), "Peru": ("PE", "Peruvian"),
    "Colombia": ("CO", "Colombian"), "Netherlands": ("NL", "Dutch"), "Ireland": ("IE", "Irish"),
}
CITIES = {"Kenya": "Nairobi", "Ghana": "Accra", "Nigeria": "Lagos", "Germany": "Hamburg", "France": "Lyon", "Spain": "Valencia",
          "Italy": "Turin", "Poland": "Krakow", "Sweden": "Malmo", "Brazil": "Recife", "Mexico": "Puebla", "Pakistan": "Lahore",
          "Bangladesh": "Chittagong", "India": "Pune", "Turkey": "Izmir", "Egypt": "Alexandria", "United Kingdom": "Leeds",
          "United States": "Denver", "Canada": "Calgary", "Portugal": "Porto", "Romania": "Cluj", "Serbia": "Novi Sad",
          "Ukraine": "Lviv", "Philippines": "Cebu", "Indonesia": "Surabaya", "Morocco": "Fes", "Peru": "Arequipa",
          "Colombia": "Medellin", "Netherlands": "Utrecht", "Ireland": "Cork"}
FIRST = ["Amina", "Kwame", "Chiamaka", "Tobias", "Henrike", "Margaux", "Ines", "Rafael", "Agnieszka", "Linnea", "Thiago", "Ximena",
         "Farhan", "Nusrat", "Arjun", "Deniz", "Yasmin", "Callum", "Brooke", "Gabriel", "Ioana", "Dragan", "Oksana", "Jericho",
         "Wulan", "Youssef", "Rosario", "Valentina", "Joris", "Siobhan", "Mohammed", "Robert", "Anthony", "Catherine", "Ibrahim",
         "Hussein", "Yusuf", "Alexander", "Stephen", "Nicholas", "Olumide", "Babatunde", "Abubakar", "Elizabeth", "Matthew", "Francis"]
LAST = ["Wanjiru", "Mensah", "Okonkwo", "Brandt", "Vogel", "Lefevre", "Morales", "Castillo", "Wisniewska", "Sjoberg", "Barbosa",
        "Hernandez", "Rahman", "Chowdhury", "Patel", "Yilmaz", "Haddad", "McAllister", "Fletcher", "Ionescu", "Petrovic", "Kovalenko",
        "Santos", "Wibowo", "El Amrani", "Quispe", "Restrepo", "Van Dijk", "O'Connell", "Abdullahi", "Okafor", "Lindgren"]
ACCENT = {"Ines": "Inès", "Rafael": "Rafaël", "Joris": "Jöris", "Yilmaz": "Yılmaz", "Sjoberg": "Sjöberg", "Lefevre": "Lefèvre",
          "Wisniewska": "Wiśniewska", "Petrovic": "Petrović", "Hernandez": "Hernández", "Malmo": "Malmö"}
VARIANT = {"Mohammed": ["Muhammad", "Mohamed", "Mohd"], "Robert": ["Bob", "Rob"], "Anthony": ["Tony", "Antonio"],
           "Catherine": ["Kate", "Katherine"], "Ibrahim": ["Ebrahim", "Ibraheem"], "Hussein": ["Hussain", "Hossain"],
           "Yusuf": ["Yousef", "Youssef"], "Alexander": ["Alex", "Aleksandr"], "Stephen": ["Steven", "Stefan"],
           "Nicholas": ["Nick", "Nikolai"], "Olumide": ["Mide"], "Babatunde": ["Tunde"], "Abubakar": ["Abubakr"],
           "Elizabeth": ["Liz", "Isabel"], "Matthew": ["Matteo", "Matt"], "Francis": ["Francisco", "Frank"]}
COMPANY_WORDS = ["Harbor", "Kestrel", "Meridian", "Lumen", "Sablewood", "Oriel", "Tamarind", "Cobalt", "Juniper", "Halcyon", "Vantage", "Ardent"]
COMPANY_TAIL = ["Logistics", "Holdings", "Trading", "Analytics", "Foods", "Mining", "Textiles", "Shipping"]
FORMS = [("Ltd", "Limited"), ("GmbH", "GmbH"), ("S.A.", "SA"), ("LLC", "L.L.C."), ("Plc", "PLC"), ("S.r.l.", "SRL")]
PHRASE = {"PEP": "a politically exposed person", "Sanctions": "a sanctioned individual", "Enforcement": "the subject of enforcement action",
          "Adverse Media": "named in adverse media", "SOE": "a state-owned enterprise official"}
PROVIDERS = ["Jumio", "IDnow", "Trulioo", "Incode", "Mitek"]
DOCS = ["passport", "national identity card", "driving licence", "residence permit"]


def fold(s):
    s = unicodedata.normalize("NFKD", s.replace("ı", "i").replace("ł", "l"))
    return "".join(c for c in s if not unicodedata.combining(c))


def qkey(name):
    s = re.sub(r"[`'’]", "", fold(name).lower())
    return " ".join(sorted(re.sub(r"[^\w]+", " ", s).split()))


class Gen:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.n = 0
        self.customers, self.accounts, self.onboarding, self.kyc, self.notes = [], [], [], [], []
        self.alerts, self.hits, self.search, self.labels = [], [], [], []

    def uid(self, p, width=6):
        self.n += 1
        return f"{p}-{(self.n * 7919 + 13) % (16 ** width):0{width}X}"

    # -------------------------------------------------------------- formatting helpers
    def fmt_cust_dob(self, y, m, d):
        return self.r.choice([f"{y}-{m:02d}-{d:02d}", f"{d:02d}/{m:02d}/{y}", f"{d} {MON[m-1]} {y}", f"{MON[m-1]} {d}, {y}"])

    def fmt_note_dob(self, y, m, d):
        sfx = "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
        return self.r.choice([f"{d}{sfx} {MON[m-1]} {y}", f"{MON[m-1][:3]} {d}, {y}", f"{y}-{m:02d}-{d:02d}", f"{d:02d}.{m:02d}.{y}", f"{d} {MON[m-1]} {y}"])

    def country_value(self, c, kind):
        iso, dem = COUNTRIES[c]
        if kind == "res":
            return self.r.choice([c, iso])
        return self.r.choice([c, dem])

    # -------------------------------------------------------------- customer side
    def person(self, first, last, dob, country, email_tag=None, middle=None, phone=None, extra_country=None):
        rid = self.uid("CUS")
        full = f"{first} {middle} {last}" if middle else f"{first} {last}"
        email = f"{fold(first).lower()}.{fold(last).lower().replace(' ', '').replace(chr(39), '')}{self.r.randint(1000, 9999)}@shadow.example"
        c = {"record_id": rid, "entity_type": "Individual", "full_name": full, "preferred_name": None, "login_name": None,
             "dob": self.fmt_cust_dob(*dob) if dob else None,
             "nationality": self.country_value(extra_country or country, "nat"), "residence_country": self.country_value(country, "res"),
             "city": CITIES[country], "address": f"{self.r.randint(1, 200)} Market Street, {CITIES[country]}", "email": email,
             "phone": phone or f"+{self.r.randint(20, 99)} {self.r.randint(10 ** 9, 10 ** 10 - 1)}", "occupation": "Engineer",
             "employer": "Shadow Ltd", "registration_number": None, "onboarded_at": "2022-01-01", "status": "active", "last_kyc_refresh": "2024-01-01"}
        self.customers.append(c)
        return c

    def company(self, name, inc, country):
        rid = self.uid("CUS")
        c = {"record_id": rid, "entity_type": "Company", "full_name": name, "preferred_name": None, "login_name": None,
             "dob": self.fmt_cust_dob(*inc), "nationality": None, "residence_country": self.country_value(country, "res"),
             "city": CITIES[country], "address": f"{self.r.randint(1, 99)} Dock Road, {CITIES[country]}",
             "email": f"info{self.r.randint(10000, 99999)}@{fold(name.split()[0]).lower()}.example",
             "phone": f"+{self.r.randint(20, 99)} {self.r.randint(10 ** 9, 10 ** 10 - 1)}", "occupation": None, "employer": None,
             "registration_number": f"REG{self.r.randint(10 ** 5, 10 ** 6)}", "onboarded_at": "2021-01-01", "status": "active", "last_kyc_refresh": "2024-01-01"}
        self.customers.append(c)
        return c

    def account(self, cust, joint=None):
        aid = self.uid("ACC")
        login = re.sub(r"[^a-z]", "", fold(cust["full_name"]).lower())[:7] + str(self.r.randint(100, 9999))
        self.accounts.append({"account_id": aid, "customer_id": cust["record_id"], "login_handle": login, "phone": cust["phone"],
                              "opened_at": "2022-01-01", "status": "active"})
        if joint:
            self.accounts.append({"account_id": aid, "customer_id": joint["record_id"], "login_handle": login, "phone": joint["phone"],
                                  "opened_at": "2022-01-01", "status": "active"})
        app = self.uid("APP")
        self.onboarding.append({"account_id": aid, "customer_id": cust["record_id"], "kyc_applicant_id": app, "onboarded_at": "2022-01-01"})
        return aid, login, app

    def kyc_check(self, app, name, dob, country, result="approved", date="2024-03-05", docnum=None, company=False):
        kid = self.uid("KYC")
        self.kyc.append({"check_id": kid, "applicant_id": app, "provider": "Companies registry lookup" if company else self.r.choice(PROVIDERS),
                         "verified_name": name, "verified_dob": self.fmt_cust_dob(*dob) if dob else None,
                         "document_type": "registry extract" if company else self.r.choice(DOCS),
                         "document_number": docnum or f"X{self.r.randint(10 ** 7, 10 ** 8)}", "document_country": country,
                         "result": result, "checked_at": date})
        return kid

    def kyc_note(self, email, name, dob, country, approved=True, date="2024-04-10", case="upper"):
        nid = self.uid("NOTE")
        N = name.upper() if case == "upper" else (name.title() if case == "title" else name)
        dem = COUNTRIES[country][1]
        dobs = self.fmt_note_dob(*dob)
        doc, prov = self.r.choice(DOCS), self.r.choice(PROVIDERS)
        if approved:
            t = self.r.choice([
                f"ID check passed ({prov}): {N}, date of birth {dobs}, {dem} {doc}. Completed {date}.",
                f"{prov} returned a clear result for {N} on {date} - {doc} issued in {country}, birth date shown as {dobs}.",
                f"Onboarding: {doc} ({country}) for {N} verified via {prov} on {date}; DOB on document {dobs}.",
                f"Document review complete on {date}. {prov} matched the {dem} {doc} to {N}, born {dobs}.",
            ])
        else:
            t = self.r.choice([
                f"{prov} declined the {doc} uploaded for {N} (DOB {dobs}) on {date} - image unreadable, check rejected.",
                f"Verification failed on {date}: {prov} could not validate the {dem} {doc} presented as {N}, born {dobs}.",
            ])
        self.notes.append({"note_id": nid, "requester_email": email, "created_at": date, "channel": "kyc", "text": t})
        return nid

    def residence_note(self, email, country):
        nid = self.uid("NOTE")
        y1 = self.r.randint(2005, 2015)
        y2 = y1 + self.r.randint(1, 6)
        t = self.r.choice([f"Customer explained the {y1}-{y2} transfers came from their years working in {country}.",
                           f"KYC refresh: customer previously resided in {country} ({y1} to {y2}).",
                           f"Prior address history on file shows {country}, {y1}-{y2}."])
        self.notes.append({"note_id": nid, "requester_email": email, "created_at": "2025-06-01", "channel": "phone", "text": t})
        return nid

    def noise_note(self, email):
        self.notes.append({"note_id": self.uid("NOTE"), "requester_email": email, "created_at": "2025-07-01", "channel": "app",
                           "text": self.r.choice(["Customer asked to raise the card limit; done.", "Statement re-sent at customer request.",
                                                  "Customer disputed a duplicate charge of 25 EUR; refunded."])})

    # -------------------------------------------------------------- hit side
    def hit_name(self, first, last, style=None):
        style = style or self.r.choice(["order", "variant", "accent", "middle", "typo", "upper", "plain"])
        f, l = first, last
        if style == "variant" and first in VARIANT:
            f = self.r.choice(VARIANT[first])
            # a short form (Bob, Tony) still matches via the groups; keep the surname exact
        elif style == "accent":
            f, l = ACCENT.get(first, first), ACCENT.get(last, last)
        elif style == "typo":
            p = l if len(l.replace(" ", "")) >= 6 else f
            if len(p) >= 6:
                i = self.r.randint(1, len(p) - 2)
                q = p[:i] + ("a" if p[i] != "a" else "e") + p[i + 1:]
                if p == l:
                    l = q
                else:
                    f = q
        if style == "middle":
            return f"{l}, {f} {self.r.choice(['Adeyemi', 'Marie', 'Jose', 'Kofi', 'Ali'])}"
        if style == "order":
            return f"{l}, {f}"
        if style == "upper":
            return f"{l.upper()}, {f}"
        return f"{f} {l}"

    def new_hit(self, aid, name, cat=None, et="Individual", dobs=(), countries=(), notes=None, deceased=None, aliases=()):
        hid = self.uid("H")
        cat = cat or self.r.choice(list(PHRASE))
        addrs = []
        for c in countries:
            addrs.append(self.r.choice([f"{CITIES[c]}, {c}", c, f"{c} [Residency]", f"{self.r.randint(1, 99)} Main Rd, {CITIES[c]}, {c} [Business]"]))
        h = {"hit_id": hid, "alert_id": aid, "match_score": 95.0, "entity_type": et, "name": name, "aliases": list(aliases),
             "gender": None, "dobs": list(dobs), "place_of_birth": [], "life_status": "Deceased" if deceased else None,
             "deceased_date": deceased, "nationality": [], "citizenship": [], "countries": [], "addresses": addrs,
             "identifiers": [], "categories": [cat], "primary_category": cat if self.r.random() < 0.6 else None,
             "position_or_allegation": None, "details": None, "relationships": [], "profile_notes": notes, "sources": [], "source_urls": []}
        if countries and self.r.random() < 0.5:
            h["countries"] = list(countries)
        self.hits.append(h)
        return h

    def age_sentence(self, name, age, y, m):
        mon = MON[m - 1]
        return self.r.choice([
            f"In {mon} {y}, prosecutors charged {age}-year-old {name} over the scheme.",
            f"{name} was {age} years old at the time of the {mon} {y} raid.",
            f"Aged {age}, {name} appeared before magistrates in {mon} {y}.",
            f"Then {age}, {name} pleaded guilty in {mon} {y}.",
            f"Reports from {mon} {y} put the age of {name} at {age}.",
            f"{name}, who was {age} at the time, was arrested in {mon} {y}.",
        ])

    def snippet(self, name, age, y, m, phrase, country):
        mon = MON[m - 1]
        return self.r.choice([
            f"Bulletin {mon} {y}: {country} authorities list {name}, age {age}, as {phrase}.",
            f"{mon} {y} coverage in {country} described {name}, then {age}, as {phrase}.",
            f"{name} was {age} when a {mon} {y} report from {country} identified them as {phrase}.",
            f"Aged {age} in {mon} {y}, {name} was recorded as {phrase} in {country}.",
        ])

    def add_sr(self, name, text):
        self.search.append({"result_id": self.uid("SR"), "query": qkey(name), "title": f"{name} - record", "snippet": text,
                            "source": "shadow-news.example"})
        return self.search[-1]["result_id"]

    def namesake_noise(self, name, exclude_countries):
        others = [c for c in COUNTRIES if c not in exclude_countries]
        for _ in range(self.r.randint(1, 3)):
            c = self.r.choice(others)
            y = self.r.randint(1990, 2024)
            self.add_sr(name, self.r.choice([f"{name}, {self.r.randint(20, 70)}, won a cycling race in {c} in {MON[self.r.randint(0, 11)]} {y}.",
                                             f"A {c} bakery owned by {name} ({self.r.randint(20, 70)}) opened in {MON[self.r.randint(0, 11)]} {y}."]))

    def label(self, hit, decision, codes, scenario, cust_ids):
        self.labels.append({"hit_id": hit["hit_id"], "alert_id": hit["alert_id"], "decision": decision, "reason_codes": codes,
                            "customer_record_ids": cust_ids, "scenario": scenario})

    # -------------------------------------------------------------- scenarios
    def pick_names(self):
        f = self.r.choice(FIRST)
        l = self.r.choice(LAST)
        return f, l

    def other_country(self, *exclude):
        return self.r.choice([c for c in COUNTRIES if c not in exclude])

    def base_person(self, verified="kyc", dob=None, country=None, link=None, first=None, last=None, middle=None):
        """Create a resolved customer with an approved verification. Returns dict of facts."""
        first, last = first or self.pick_names()[0], last or self.pick_names()[1]
        country = country or self.r.choice(list(COUNTRIES))
        dob = dob or (self.r.randint(1950, 1998), self.r.randint(1, 12), self.r.randint(1, 28))
        c = self.person(first, last, dob, country, middle=middle)
        aid, login, app = self.account(c)
        src = None
        vname = c["full_name"]
        if verified == "kyc":
            src = self.kyc_check(app, vname.upper() if self.r.random() < 0.5 else vname, dob, country)
        elif verified == "note":
            src = self.kyc_note(c["email"], vname, dob, country, case=self.r.choice(["upper", "upper", "title"]))
        if self.r.random() < 0.5:
            self.noise_note(c["email"])
        link = link or self.r.choice(["account", "account", "login", "email", "none"])
        return {"c": c, "first": first, "last": last, "country": country, "dob": dob, "acc": aid, "login": login, "app": app,
                "link": link, "src": src}

    def make_alert(self, p, et="Individual", screened_name=None, with_dob=True):
        aid = self.uid("A")
        c = p["c"]
        a = {"alert_id": aid, "screened_at": "2026-11-05", "customer_name": screened_name or c["full_name"], "entity_type": et,
             "dob": None, "country": None, "city": None, "account_ref": None, "login_handle": None, "email": None, "hit_count": 1, "hit_ids": []}
        if p["link"] == "account":
            a["account_ref"] = p["acc"]
        elif p["link"] == "login":
            a["login_handle"] = p["login"]
        elif p["link"] == "email":
            a["email"] = c["email"]
        else:
            if with_dob and p.get("dob"):
                y, m, d = p["dob"]
                a["dob"] = f"{y}-{m:02d}-{d:02d}"
            a["country"] = p["country"]
            a["city"] = CITIES[p["country"]] if self.r.random() < 0.5 else None
        self.alerts.append(a)
        return a

    def attach(self, a, h):
        a["hit_ids"].append(h["hit_id"])
        a["hit_count"] = len(a["hit_ids"])

    def dob_on_hit(self, h, by, mode, name, country, exact=None):
        """Give the hit a birth date that implies birth years {by-1, by} (age modes) or exact (field)."""
        if mode == "field":
            if exact:
                y, m, d = exact
                h["dobs"] = [self.r.choice([f"{y}-{m:02d}-{d:02d}", f"{d} {MON[m-1][:3]} {y}", f"{MON[m-1]} {d}, {y}"])]
            else:
                h["dobs"] = [str(by - 1), str(by)]
        elif mode == "notes":
            ry = self.r.randint(min(max(by + 20, 1990), 2025), 2025)
            rm = self.r.randint(1, 12)
            age = ry - by
            h["profile_notes"] = self.age_sentence(name, age, ry, rm) + "\n\nCareer:\nVarious roles."
        elif mode == "search":
            ry = self.r.randint(min(max(by + 20, 1990), 2025), 2025)
            rm = self.r.randint(1, 12)
            cat = h["primary_category"] or h["categories"][0]
            self.add_sr(h["name"], self.snippet(name.replace(",", ""), ry - by, ry, rm, PHRASE[cat], country))
            self.namesake_noise(h["name"], [country])

    def scenario(self, kind):
        r = self.r
        if kind in ("same_field", "same_notes", "same_search", "same_verified_beats_declared"):
            p = self.base_person(verified=r.choice(["kyc", "note"]))
            if kind == "same_verified_beats_declared":
                # record dob wrong; newest approved check correct; older approved check also wrong
                y, m, d = p["dob"]
                p["c"]["dob"] = self.fmt_cust_dob(y + 4, m, d)
                self.kyc_check(p["app"], p["c"]["full_name"], (y + 4, m, d), p["country"], date="2019-01-01")
                if p["src"] is None or p["src"].startswith("NOTE"):
                    self.kyc_check(p["app"], p["c"]["full_name"], p["dob"], p["country"], date="2025-01-01")
            a = self.make_alert(p, with_dob=kind != "same_verified_beats_declared")
            hn = self.hit_name(p["first"], p["last"])
            h = self.new_hit(a["alert_id"], hn, countries=[p["country"]])
            mode = {"same_field": r.choice(["field", "field_exact"]), "same_notes": "notes", "same_search": "search",
                    "same_verified_beats_declared": "field"}[kind]
            if mode == "field_exact":
                self.dob_on_hit(h, None, "field", hn, p["country"], exact=p["dob"])
            else:
                by = p["dob"][0] + r.choice([0, 1])
                self.dob_on_hit(h, by, mode, f"{p['first']} {p['last']}", p["country"])
            self.attach(a, h)
            self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "same_company":
            word = f"{r.choice(COMPANY_WORDS)} {r.choice(COMPANY_TAIL)}"
            f1, f2 = r.choice(FORMS)
            country = r.choice(list(COUNTRIES))
            c = self.company(f"{word} {f1}", (r.randint(1990, 2015), r.randint(1, 12), r.randint(1, 28)), country)
            aid, login, app = self.account(c)
            self.kyc_check(app, c["full_name"], None, country, company=True)
            p = {"c": c, "link": r.choice(["account", "login", "email", "none"]), "acc": aid, "login": login, "country": country, "dob": None}
            a = self.make_alert(p, et="Company", with_dob=False)
            h = self.new_hit(a["alert_id"], f"{word.upper() if r.random() < 0.3 else word} {f2}", et="Company", countries=[country], cat=r.choice(["Enforcement", "Sanctions"]))
            self.attach(a, h)
            self.label(h, "SAME_ENTITY", ["NAME_LOCATION_MATCH"], kind, [c["record_id"]])
            return a, p
        if kind == "company_location":
            word = f"{r.choice(COMPANY_WORDS)} {r.choice(COMPANY_TAIL)}"
            f1, f2 = r.choice(FORMS)
            country = r.choice(list(COUNTRIES))
            c = self.company(f"{word} {f1}", (r.randint(1990, 2015), 5, 5), country)
            aid, login, app = self.account(c)
            self.kyc_check(app, c["full_name"], None, country, company=True)
            p = {"c": c, "link": "account", "acc": aid, "login": login, "country": country, "dob": None}
            a = self.make_alert(p, et="Company", with_dob=False)
            h = self.new_hit(a["alert_id"], f"{word} {f2}", et="Company", countries=[self.other_country(country)], cat="Enforcement")
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["LOCATION_MISMATCH"], kind, [c["record_id"]])
            return a, p
        if kind in ("dob_field", "dob_notes", "dob_search"):
            p = self.base_person(verified=r.choice(["kyc", "note"]))
            a = self.make_alert(p)
            hn = self.hit_name(p["first"], p["last"])
            h = self.new_hit(a["alert_id"], hn, countries=[p["country"]])
            by = p["dob"][0] + r.choice([-3, -2, 3, 4, 8, -12]) + (1 if r.random() < 0.5 else 0)
            # implied years {by-1, by}; contradiction needs customer year outside [by-2, by+1]
            if not (p["dob"][0] < by - 2 or p["dob"][0] > by + 1):
                by = p["dob"][0] + 6
            self.dob_on_hit(h, by, kind.split("_")[1], f"{p['first']} {p['last']}", p["country"])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["DOB_MISMATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "dob_same_year_month":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            y, m, d = p["dob"]
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], dobs=[f"{MON[(m % 12)]} {y}"])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["DOB_MISMATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "temporal":
            p = self.base_person(verified=r.choice(["kyc", "note"]), dob=(r.randint(2004, 2008), r.randint(1, 12), r.randint(1, 28)))
            a = self.make_alert(p)
            hn = self.hit_name(p["first"], p["last"])
            ry = p["dob"][0] + r.randint(4, 12)
            date = r.choice([f"{MON[3]} {r.randint(1, 28):02d}, {ry}", f"{ry}-03-{r.randint(10, 28)}", f"{r.randint(1, 28)} {MON[8]} {ry}"])
            notes = f"According to {r.choice(['The Daily Ledger', 'Regional Court Registry', 'Securities Board'])}; {date}: {p['first']} {p['last']} was named in a fraud complaint."
            h = self.new_hit(a["alert_id"], hn, countries=[p["country"]], notes=notes)
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["TEMPORAL_IMPOSSIBILITY"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_report_wrong_form":
            p = self.base_person(verified="kyc", dob=(r.randint(2004, 2008), 5, 5))
            a = self.make_alert(p)
            ry = p["dob"][0] + 6
            notes = f"On March 3, {ry}, {p['first']} {p['last']} was named in a fraud complaint filed by regulators."
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], notes=notes)
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_numbers_not_ages":
            p = self.base_person(verified="kyc", dob=(r.randint(1950, 1975), 5, 5))
            a = self.make_alert(p)
            notes = (f"According to {r.choice(['High Court', 'Fraud Office'])}; June 2, 2019: {p['first']} {p['last']} was sentenced to 25 years "
                     f"and fined 40,000 euros; 3 co-defendants (aged between 19 and 22) were also charged, and case no. 14 of 2019 remains open.")
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], notes=notes)
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "location":
            p = self.base_person(verified=r.choice(["kyc", "note", None]))
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[self.other_country(p["country"])])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["LOCATION_MISMATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_residence_note_shared":
            p = self.base_person(verified="kyc")
            other = self.other_country(p["country"])
            self.residence_note(p["c"]["email"], other)
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[other])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_linked_record_country":
            p = self.base_person(verified="kyc", link="account")
            other = self.other_country(p["country"])
            # second record of the same person: same phone + same full DOB, different country
            c2 = self.person(p["first"], p["last"], p["dob"], other, phone=p["c"]["phone"])
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[other])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"], c2["record_id"]])
            return a, p
        if kind == "name_verified":
            p = self.base_person(verified=None, last=self.r.choice([x for x in LAST if " " not in x]))
            vf = r.choice([f for f in FIRST if f not in VARIANT and f != p["first"] and abs(len(f) - len(p["first"])) > 2] or ["Zebulon"])
            if r.random() < 0.5:
                src = self.kyc_check(p["app"], f"{vf} {p['last']}".upper(), p["dob"], p["country"])
            else:
                src = self.kyc_note(p["c"]["email"], f"{vf} {p['last']}", p["dob"], p["country"], case=r.choice(["upper", "title"]))
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], f"{p['last']}, {p['first']}", countries=[p["country"]])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["NAME_MISMATCH_VERIFIED"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_rejected_check":
            p = self.base_person(verified=None)
            vf = r.choice([f for f in FIRST if f not in VARIANT and f != p["first"]])
            if r.random() < 0.5:
                self.kyc_check(p["app"], f"{vf} {p['last']}", (p["dob"][0] - 20, 1, 1), self.other_country(p["country"]), result=r.choice(["rejected", "expired"]))
            else:
                self.kyc_note(p["c"]["email"], f"{vf} {p['last']}", (p["dob"][0] - 20, 1, 1), self.other_country(p["country"]), approved=False)
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "deceased":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            dd = r.choice(["2019-04-02", "2021-11", "March 3, 2022", "2015"])
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], deceased=dd)
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["DECEASED"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "type_mismatch":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], f"{p['last']} {r.choice(COMPANY_TAIL)} {r.choice(FORMS)[0]}", et="Company", countries=[p["country"]])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["ENTITY_TYPE_MISMATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind in ("review_no_dob", "review_international"):
            p = self.base_person(verified=r.choice(["kyc", "note", None]))
            a = self.make_alert(p)
            countries = [p["country"]] if kind == "review_no_dob" and r.random() < 0.7 else []
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=countries)
            if kind == "review_international":
                h["addresses"] = ["International", "Europe"]
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "review_name_dob_agree_loc_differs":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[self.other_country(p["country"])])
            self.dob_on_hit(h, p["dob"][0], "field", h["name"], p["country"])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "review_dob_one_off":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], dobs=[str(p["dob"][0] + r.choice([-1, 1]))])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_namesake_search":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"], "plain"), countries=[p["country"]], cat="PEP")
            nm = f"{p['first']} {p['last']}"
            # right phrase, wrong country; wrong phrase, right country -> both must be ignored
            self.add_sr(h["name"], self.snippet(nm, 30, p["dob"][0] + 50, 6, PHRASE["PEP"], self.other_country(p["country"])))
            self.add_sr(h["name"], self.snippet(nm, 30, p["dob"][0] + 50, 6, PHRASE["Sanctions"], p["country"]))
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_placeholder_name":
            p = self.base_person(verified=None, first="Unknown", last=self.r.choice(LAST))
            p["c"]["full_name"] = f"{p['last']} 0000"
            a = self.make_alert(p, screened_name=f"{p['last']} N/A")
            h = self.new_hit(a["alert_id"], p["last"], countries=[p["country"]], dobs=[str(p["dob"][0])])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "trap_joint_account":
            p = self.base_person(verified="kyc", link="account")
            other = self.person(self.r.choice(FIRST), p["last"], (p["dob"][0] - 30, 2, 2), self.other_country(p["country"]))
            # rewire the account to be joint
            self.accounts.append({"account_id": p["acc"], "customer_id": other["record_id"], "login_handle": p["login"], "phone": other["phone"], "opened_at": "2022-01-01", "status": "active"})
            a = self.make_alert(p)
            y, m, d = p["dob"]
            a["dob"] = f"{y}-{m:02d}-{d:02d}"
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], dobs=[str(y)])
            self.attach(a, h)
            self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "ambiguous":
            f, l = self.pick_names()
            country = r.choice(list(COUNTRIES))
            c1 = self.person(f, l, (1962, 3, 3), country)
            c2 = self.person(f, l, (1991, 7, 7), country)
            for c in (c1, c2):
                self.account(c)
            p = {"c": c1, "link": "none", "country": country, "dob": None}
            a = self.make_alert(p, with_dob=False)
            h = self.new_hit(a["alert_id"], f"{l}, {f}", countries=[country], dobs=["1962", "1963"])
            self.attach(a, h)
            self.label(h, "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], kind, ["AMBIGUOUS"])
            return a, p
        if kind == "hard_dual_nationality":
            p = self.base_person(verified=None)
            other = self.other_country(p["country"])
            p["c"]["nationality"] = self.r.choice([f"{COUNTRIES[p['country']][1]}/{COUNTRIES[other][1]}", f"{p['country']} and {other}",
                                                   f"Dual {COUNTRIES[p['country']][1]}-{COUNTRIES[other][1]}"])
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[other])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_native_country_name":
            native = {"Poland": "Polska", "Germany": "Deutschland", "Spain": "Espana", "Italy": "Italia", "Sweden": "Sverige",
                      "Netherlands": "Nederland", "Egypt": "Misr", "Morocco": "Al-Maghrib", "Romania": "Romania", "Ukraine": "Ukraina"}
            c0 = self.r.choice(list(native))
            p = self.base_person(verified="kyc", country=c0)
            a = self.make_alert(p)
            third = self.other_country(c0)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[third])
            h["addresses"] = [f"{CITIES[c0]}, {native[c0]}", third]
            h["countries"] = []
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_customer_country_longform":
            longf = {"Germany": "Federal Republic of Germany", "Spain": "Kingdom of Spain", "Poland": "Republic of Poland",
                     "Kenya": "Republic of Kenya", "Nigeria": "Federal Republic of Nigeria", "Egypt": "Arab Republic of Egypt",
                     "Netherlands": "Kingdom of the Netherlands", "Brazil": "Federative Republic of Brazil"}
            c0 = self.r.choice(list(longf))
            nat = self.other_country(c0)
            p = self.base_person(verified=None, country=c0)
            p["c"]["residence_country"] = longf[c0]
            p["c"]["nationality"] = COUNTRIES[nat][1]
            a = self.make_alert(p, with_dob=False)
            if a["country"]:
                a["country"] = None
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[c0])
            self.attach(a, h)
            self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind in ("hard_age_words_agree", "hard_age_words_mismatch"):
            words = {31: "thirty-one", 38: "thirty-eight", 42: "forty-two", 45: "forty-five", 50: "fifty", 53: "fifty-three", 57: "fifty-seven", 60: "sixty"}
            age = self.r.choice(list(words))
            p = self.base_person(verified="kyc")
            ry = p["dob"][0] + age + (0 if kind.endswith("agree") else self.r.choice([5, -6]))
            if ry > 2025:
                ry = 2025
            a = self.make_alert(p)
            nm = f"{p['first']} {p['last']}"
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]],
                             notes=f"{nm}, aged {words[age]}, was questioned by police in {MON[5]} {ry}.")
            by = ry - age
            truth_same = p["dob"][0] in (by - 1, by)
            self.attach(a, h)
            if truth_same:
                self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            elif p["dob"][0] < by - 2 or p["dob"][0] > by + 1:
                self.label(h, "DIFFERENT_ENTITY", ["DOB_MISMATCH"], kind, [p["c"]["record_id"]])
            else:
                self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_dob_circa_range":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            y = p["dob"][0]
            form, years = self.r.choice([(f"c. {y + 7}", [y + 7]), (f"circa {y - 9}", [y - 9]), (f"{y + 5} - {y + 8}", list(range(y + 5, y + 9))),
                                         (f"Approximately {y}", [y]), (f"{y - 1}-{y + 1}", [y - 1, y, y + 1])])
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], dobs=[form])
            self.attach(a, h)
            if y in years:
                self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            elif y < min(years) - 1 or y > max(years) + 1:
                self.label(h, "DIFFERENT_ENTITY", ["DOB_MISMATCH"], kind, [p["c"]["record_id"]])
            else:
                self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_kyc_note_expiry":
            p = self.base_person(verified=None)
            y, m, d = p["dob"]
            nid = self.uid("NOTE")
            exp = f"{self.r.randint(1, 28)} {MON[self.r.randint(0, 11)]} {self.r.randint(2028, 2034)}"
            iss = f"{self.r.randint(1, 28)} {MON[self.r.randint(0, 11)]} {self.r.randint(2015, 2022)}"
            self.notes.append({"note_id": nid, "requester_email": p["c"]["email"], "created_at": "2024-02-02", "channel": "kyc",
                               "text": f"Passport issued {iss} and valid until {exp} checked by Jumio on 2024-02-02 for {p['c']['full_name'].upper()}; holder born {self.fmt_note_dob(y, m, d)}, nationality {COUNTRIES[p['country']][1]}."})
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]], dobs=[str(y)])
            self.attach(a, h)
            self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            return a, p
        if kind in ("hard_two_checks_newest_differs", "hard_two_checks_newest_agrees"):
            p = self.base_person(verified=None, last=self.r.choice([x for x in LAST if " " not in x]))
            vf = self.r.choice([f for f in FIRST if f not in VARIANT and f != p["first"] and abs(len(f) - len(p["first"])) > 2] or ["Zebulon"])
            good, bad = f"{p['first']} {p['last']}".upper(), f"{vf} {p['last']}".upper()
            newest_bad = kind.endswith("differs")
            self.kyc_check(p["app"], bad if not newest_bad else good, p["dob"], p["country"], date="2020-05-05")
            self.kyc_check(p["app"], bad if newest_bad else good, p["dob"], p["country"], date="2025-05-05")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], f"{p['last']}, {p['first']}", countries=[p["country"]])
            self.attach(a, h)
            if newest_bad:
                self.label(h, "DIFFERENT_ENTITY", ["NAME_MISMATCH_VERIFIED"], kind, [p["c"]["record_id"]])
            else:
                self.label(h, "REVIEW", ["INSUFFICIENT_DATA"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_deceased_in_notes":
            p = self.base_person(verified="kyc")
            a = self.make_alert(p)
            nm = f"{p['first']} {p['last']}"
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[p["country"]],
                             notes=self.r.choice([f"{nm} died on 3 May 2019.", f"Date of death: 2021-08-14. {nm} was a regional official.", f"{nm} passed away in March 2020."]))
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["DECEASED"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_lowercase_verified_mismatch":
            p = self.base_person(verified=None, last=self.r.choice([x for x in LAST if " " not in x]))
            vf = self.r.choice([f for f in FIRST if f not in VARIANT and f != p["first"] and abs(len(f) - len(p["first"])) > 2] or ["Zebulon"])
            self.kyc_note(p["c"]["email"], f"{vf} {p['last']}".lower(), p["dob"], p["country"], case="as_is")
            a = self.make_alert(p)
            h = self.new_hit(a["alert_id"], f"{p['last']}, {p['first']}", countries=[p["country"]])
            self.attach(a, h)
            self.label(h, "DIFFERENT_ENTITY", ["NAME_MISMATCH_VERIFIED"], kind, [p["c"]["record_id"]])
            return a, p
        if kind == "hard_nolink_screened_typo":
            p = self.base_person(verified="kyc", link="none", first=self.r.choice(list(VARIANT)))
            nick = self.r.choice(VARIANT[p["first"]])
            last = p["last"]
            typo = last[:-2] + last[-1] + last[-2] if len(last) >= 7 and " " not in last else last
            a = self.make_alert(p, screened_name=f"{nick} {typo}")
            h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"], "order"), countries=[p["country"]], dobs=[str(p["dob"][0])])
            self.attach(a, h)
            self.label(h, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], kind, [p["c"]["record_id"]])
            return a, p
        raise ValueError(kind)

    def extra_location_hit(self, a, p):
        if p.get("first") is None:
            return
        h = self.new_hit(a["alert_id"], self.hit_name(p["first"], p["last"]), countries=[self.other_country(p["country"])])
        self.attach(a, h)
        self.label(h, "DIFFERENT_ENTITY", ["LOCATION_MISMATCH"], "extra_location", [p["c"]["record_id"]])


MIX = [("same_field", 30), ("same_notes", 20), ("same_search", 16), ("same_verified_beats_declared", 8), ("same_company", 22),
       ("company_location", 18), ("dob_field", 22), ("dob_notes", 20), ("dob_search", 16), ("dob_same_year_month", 8),
       ("temporal", 20), ("location", 50), ("name_verified", 35), ("deceased", 8), ("type_mismatch", 6),
       ("review_no_dob", 40), ("review_international", 6), ("review_name_dob_agree_loc_differs", 10), ("review_dob_one_off", 10),
       ("trap_report_wrong_form", 8), ("trap_numbers_not_ages", 10), ("trap_residence_note_shared", 12),
       ("trap_linked_record_country", 10), ("trap_rejected_check", 12), ("trap_namesake_search", 12),
       ("trap_placeholder_name", 5), ("trap_joint_account", 8), ("ambiguous", 10),
       ("hard_dual_nationality", 10), ("hard_native_country_name", 8), ("hard_customer_country_longform", 8),
       ("hard_age_words_agree", 6), ("hard_age_words_mismatch", 6), ("hard_dob_circa_range", 12), ("hard_kyc_note_expiry", 8),
       ("hard_two_checks_newest_differs", 8), ("hard_two_checks_newest_agrees", 6), ("hard_deceased_in_notes", 6),
       ("hard_lowercase_verified_mismatch", 6), ("hard_nolink_screened_typo", 8)]


def generate(out, seed):
    g = Gen(seed)
    for kind, n in MIX:
        for _ in range(n):
            a, p = g.scenario(kind)
            if kind in ("review_no_dob", "same_field", "location") and g.r.random() < 0.15 and p.get("first") and p["link"] != "none":
                g.extra_location_hit(a, p)
    os.makedirs(out, exist_ok=True)
    order = list(range(len(g.alerts)))
    g.r.shuffle(order)
    def w(n, rows):
        with open(os.path.join(out, n + ".jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    w("alerts", [g.alerts[i] for i in order]); w("hits", g.hits); w("customers", g.customers); w("accounts", g.accounts)
    w("onboarding", g.onboarding); w("kyc_checks", g.kyc); w("notes", g.notes); w("search_results", g.search)
    w("shadow_labels", g.labels)
    root = os.path.join(os.path.dirname(__file__), "..")
    candidates = [os.path.join(os.environ["TRACK2_DEV"], "name_variants.json")] if os.environ.get("TRACK2_DEV") else []
    candidates += [os.path.join(root, rel) for rel in ("dev/name_variants.json", "data/dev/name_variants.json")]
    nv_src = next((path for path in candidates if os.path.exists(path)), None)
    if not nv_src:
        raise SystemExit("name_variants.json not found under $TRACK2_DEV, dev/ or data/dev/; place the official dev folder at ./dev")
    with open(nv_src) as f, open(os.path.join(out, "name_variants.json"), "w") as g2:
        g2.write(f.read())
    print(f"alerts={len(g.alerts)} hits={len(g.hits)} customers={len(g.customers)} labels={collections.Counter(l['decision'] for l in g.labels)}")


COST = {("DIFFERENT_ENTITY", "SAME_ENTITY"): 3, ("DIFFERENT_ENTITY", "REVIEW"): 3, ("SAME_ENTITY", "DIFFERENT_ENTITY"): 60,
        ("SAME_ENTITY", "REVIEW"): 2, ("REVIEW", "DIFFERENT_ENTITY"): 60, ("REVIEW", "SAME_ENTITY"): 2}


def score(out, pred_path, verbose=True):
    labs = [json.loads(l) for l in open(os.path.join(out, "shadow_labels.jsonl"))]
    pred = {json.loads(l)["hit_id"]: json.loads(l) for l in open(pred_path)}
    cost = base = unsafe = right = code_ok = 0
    by = collections.defaultdict(lambda: collections.Counter())
    errs = collections.defaultdict(list)
    for L in labs:
        p = pred.get(L["hit_id"], {"decision": "REVIEW", "reason_code": "MISSING", "reason": "missing"})
        t, d = L["decision"], p["decision"]
        c = COST.get((t, d), 0)
        cost += c; base += COST.get((t, "REVIEW"), 0)
        by[L["scenario"]]["n"] += 1
        by[L["scenario"]]["cost"] += c
        if c == 60:
            unsafe += 1
        if t == d:
            right += 1
            if p["reason_code"] in L["reason_codes"]:
                code_ok += 1
            else:
                by[L["scenario"]]["code_wrong"] += 1
        else:
            by[L["scenario"]][f"{t[:4]}->{d[:4]}"] += 1
            errs[L["scenario"]].append((L["hit_id"], t, d, p.get("reason_code"), p.get("reason", "")[:220]))
    s = max(0.0, 1 - cost / base) if base else 0
    print(f"hits={len(labs)} correct={right} ({right / len(labs):.1%}) unsafe={unsafe} cost={cost} all-review={base} SCORE={s:.3f} code_ok_on_correct={code_ok}/{right}")
    print(f"{'scenario':38s} {'n':>4s} {'cost':>5s}  errors")
    for k in sorted(by, key=lambda k: -by[k]["cost"]):
        v = by[k]
        print(f"{k:38s} {v['n']:4d} {v['cost']:5d}  " + ", ".join(f"{a}={b}" for a, b in v.items() if a not in ("n", "cost")))
    if verbose:
        for k in sorted(errs, key=lambda k: -by[k]["cost"]):
            for e in errs[k][:4]:
                print(f"  [{k}] {e[0]} truth={e[1]} pred={e[2]} {e[3]} :: {e[4]}")
    return s


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        generate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 7)
    else:
        score(sys.argv[2], sys.argv[3], "-q" not in sys.argv)
