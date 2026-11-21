"""Red-team cases. Each case builds a tiny synthetic data room where POLICY.md demands SAME_ENTITY or REVIEW
(never DIFFERENT_ENTITY) and records what the system does today.

    python3 redteam/run_all.py            # table of every case; asserts the CURRENT behaviour (documents the bug)
    python3 redteam/run_all.py --strict   # asserts the POLICY behaviour (use as a regression gate after a fix)

Each case function returns (row, safe, now, why):
  row   the system's output row for the hit
  safe  decisions the policy allows for this situation
  now   the decision the system gave when this case was written (so a change shows up as FIXED / CHANGED)
  why   one line: the policy rule the case exercises"""
from harness import one

SAFE = {"SAME_ENTITY", "REVIEW"}
REVIEW = {"REVIEW"}
CASES = []


def case(rank, finding):
    def deco(fn):
        fn.rank, fn.finding = rank, finding
        CASES.append(fn)
        return fn
    return deco


# ============================================================================ F1 entity type
@case(1, "F1")
def hit_entity_type_legal_entity():
    """Hit typed 'Legal Entity' is read as an individual, so a company customer is cleared on type."""
    def b(w):
        c = w.customer("Northwind Trading Ltd", dob="2010-04-01", nationality="United Kingdom", residence_country="GB",
                       entity_type="Company")
        return w.hit(c, entity_type="Legal Entity", name="Northwind Trading Limited", countries=["United Kingdom"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Type contradiction needs one person and one company (6. Type)"


@case(1, "F1")
def hit_entity_type_blank():
    """Hit with no entity_type is assumed to be an individual; a company customer is cleared on type."""
    def b(w):
        c = w.customer("Northwind Trading Ltd", dob="2010-04-01", nationality="United Kingdom", residence_country="GB",
                       entity_type="Company")
        return w.hit(c, entity_type="", name="Northwind Trading Limited", countries=["United Kingdom"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Unknown type is not a contradiction (6. Type)"


@case(1, "F1")
def customer_entity_type_corporate():
    """Customer typed 'Corporate' is read as an individual; a company hit is cleared on type."""
    def b(w):
        c = w.customer("Northwind Trading Ltd", dob="2010-04-01", nationality="United Kingdom", residence_country="GB",
                       entity_type="Corporate")
        return w.hit(c, entity_type="Company", name="Northwind Trading Limited", countries=["United Kingdom"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Type contradiction needs one person and one company (6. Type)"


# ============================================================================ F2 hit age statements
@case(2, "F2")
def notes_enumerated_list_read_as_age_dev_H46F1CE():
    """Replica of dev hit H-46F1CE (cleared today): '(1)a federal-covered security, (2)exempt ..., or (3) registered'
    gives ages 1, 2, 3 at 2004/2003 -> 'born 1999-2003' -> DOB_MISMATCH. Without those ages the dev hit is REVIEW."""
    def b(w):
        c = w.customer("Robert James", dob="1955-11-19", nationality="United States", residence_country="US")
        return w.hit(c, name="Robert James", countries=["United States"], profile_notes=(
            "According to the U.S. Missouri Secretary of State Securities Division; September 15, 2005: Final order to cease "
            "and desist was issued against Robert James. Respondents violated § 409.3-301, RSMo Supp. 2004, when they offered "
            "a security without the security being (1)a federal-covered security, (2)exempt from registration under §§ "
            "409.2-201 or 409.2-202, or (3) registered under the Missouri Securities Act of 2003."))
    return one(b), SAFE, "DIFFERENT_ENTITY", "An age at a date gives birth years (5); list numbering is not an age"


@case(2, "F2")
def notes_count_read_as_age():
    """'was 1 of 12 officials' in the first paragraph is read as age 1 -> born 2018 -> DOB_MISMATCH."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"],
                     profile_notes="In March 2019, Ivan Petrov was 1 of 12 officials named in the indictment.")
    return one(b), SAFE, "DIFFERENT_ENTITY", "An age at a date gives birth years (5); a count is not an age"


@case(2, "F2")
def notes_list_number_read_as_age():
    """', 3,' in a list of counts is read as age 3 by the ', NN,' pattern."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"],
                     profile_notes="In 2015 Ivan Petrov was charged on counts 1, 3, and 7 of the indictment.")
    return one(b), SAFE, "DIFFERENT_ENTITY", "An age at a date gives birth years (5); a count is not an age"


@case(2, "F2")
def notes_born_x_or_y_keeps_first_only():
    """'born 1974 or 1976': only 1974 is kept, so a customer born 1977 (within 1 year of 1976) is cleared."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1977-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"],
                     profile_notes="Ivan Petrov was born 1974 or 1976 in Moscow.")
    return one(b), SAFE, "DIFFERENT_ENTITY", "One agreeing hit date prevents a DOB clear (6. Date of birth)"


# ============================================================================ F3 dobs field shapes
@case(3, "F3")
def dobs_circa_range():
    """'circa 1960-1965' is not recognised as a range: parsed as 1960 only, customer born 1964 cleared."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1964-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], dobs=["circa 1960-1965"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every birth date the hit gives must be contradicted (6)"


@case(3, "F3")
def dobs_to_range():
    """'1960 to 1965' is parsed as 1960 only."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1964-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], dobs=["1960 to 1965"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every birth date the hit gives must be contradicted (6)"


@case(3, "F3")
def dobs_comma_list_in_one_item():
    """'1960, 1965' in one list item: only 1960 is kept."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1965-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], dobs=["1960, 1965"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every birth date the hit gives must be contradicted (6)"


@case(3, "F3")
def dobs_short_year_slash():
    """'1960/61' keeps 1960 only; a customer born 1962 (within 1 of 1961) is cleared."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1962-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], dobs=["1960/61"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every birth date the hit gives must be contradicted (6)"


@case(3, "F3")
def notes_month_first_us_format():
    """Notes say 'born on 05/12/1980' (US provider, = May 12); read day-first as 1980-12-05, customer 1980-05-12 cleared.
    (The same string in the dobs field happens to be safe: the field splitter cuts it at '/1980' and keeps the year.)"""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1980-05-12", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], profile_notes="Ivan Petrov was born on 05/12/1980 in Omsk.")
    return one(b), SAFE, "DIFFERENT_ENTITY", "Hit dates are 'written as the provider wrote them' (5); D/M is ambiguous"


# ============================================================================ F4 customer countries
@case(4, "F4")
def customer_dual_nationality_comma():
    """Nationality 'Russia, Cyprus' keeps only the last part (Cyprus); hit in Russia cleared on location."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="", nationality="Russia, Cyprus", residence_country="Cyprus")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every country tied to the customer must differ (6. Location)"


@case(4, "F4")
def customer_dual_nationality_slash():
    """Nationality 'Russian/Cypriot' is not recognised at all."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="", nationality="Russian/Cypriot", residence_country="Cyprus")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every country tied to the customer must differ (6. Location)"


@case(4, "F4")
def customer_lowercase_iso_code():
    """residence_country 'ru' (lower-case ISO2) is dropped; only the other country is left."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="", nationality="Cyprus", residence_country="ru")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Codes are countries (6. Location)"


@case(4, "F4")
def customer_iso_style_long_name():
    """Nationality 'Korea, Republic of' is dropped on the customer side (the hit side would read it)."""
    def b(w):
        c = w.customer("Kim Min-jun", dob="", nationality="Korea, Republic of", residence_country="Japan")
        return w.hit(c, name="Kim, Min Jun", countries=["South Korea"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Every country tied to the customer must differ (6. Location)"


@case(4, "F4")
def approved_note_second_country_dropped():
    """An approved KYC note keeps only its first country; 'previously lived in Russia' is lost."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="", nationality="Cyprus", residence_country="Cyprus")
        w.note(c, "Onfido verified the Cypriot passport of IVAN PETROV on 2024-01-01. Customer previously lived in Russia "
                  "for ten years.")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Places the notes say they lived are customer countries (6. Location)"


@case(4, "F4")
def hit_us_state_read_as_country():
    """Hit address 'Atlanta, Georgia' (US state, no country) becomes the country Georgia; US customer cleared."""
    def b(w):
        c = w.customer("John Carter", dob="", nationality="United States", residence_country="US")
        return w.hit(c, name="Carter, John", addresses=["1200 Peachtree St, Atlanta, Georgia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Country of an address = its last part (5); a US state is not Georgia"


@case(4, "F4")
def hit_new_jersey_read_as_jersey():
    """'Newark, New Jersey' becomes the Crown dependency Jersey."""
    def b(w):
        c = w.customer("John Carter", dob="", nationality="United States", residence_country="US")
        return w.hit(c, name="Carter, John", addresses=["Newark, New Jersey"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Country of an address = its last part (5)"


@case(4, "F4")
def hit_new_mexico_read_as_mexico():
    """'Albuquerque, New Mexico' becomes Mexico."""
    def b(w):
        c = w.customer("John Carter", dob="", nationality="United States", residence_country="US")
        return w.hit(c, name="Carter, John", addresses=["Albuquerque, New Mexico"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Country of an address = its last part (5)"


@case(4, "F4")
def hit_historic_country_dropped():
    """Hit place_of_birth 'Belgrade, Yugoslavia' is dropped; with nationality Montenegro only, a Serbian customer is cleared."""
    def b(w):
        c = w.customer("Dejan Jovanovic", dob="", nationality="Serbia", residence_country="RS")
        return w.hit(c, name="Jovanović, Dejan", nationality=["Montenegro"], place_of_birth=["Belgrade, Yugoslavia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Place of birth is a hit country (5); unknown country != different country"


# ============================================================================ F5 verified name parsed from notes
@case(5, "F5")
def note_name_split_by_lowercase_particle():
    """'ANA MARIA da SILVA SANTOS': only the first caps run 'ANA MARIA' becomes the verified name -> NAME_MISMATCH."""
    def b(w):
        c = w.customer("Ana Maria da Silva Santos", dob="1980-01-01", nationality="Brazil", residence_country="BR")
        w.note(c, "Onfido approved the Brazilian passport of ANA MARIA da SILVA SANTOS, born 1980-01-01, on 2024-01-01.")
        return w.hit(c, name="Silva Santos, Ana", countries=["Brazil"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Verified legal name vs hit names (4, 6. Name): the legal name agrees"


@case(5, "F5")
def note_titlecase_name_split_by_particle():
    """Title-case note: 'Mohammed bin Salman Al Saud' -> run 'Salman Al Saud' only -> NAME_MISMATCH vs 'Mohammed bin Salman'."""
    def b(w):
        c = w.customer("Mohammed bin Salman Al Saud", dob="1985-08-31", nationality="Saudi Arabia", residence_country="SA")
        w.note(c, "Veriff verified the passport of Mohammed bin Salman Al Saud, born 1985-08-31, issued in Saudi Arabia.")
        return w.hit(c, name="Mohammed bin Salman", countries=["Saudi Arabia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Verified legal name vs hit names (4, 6. Name): the legal name agrees"


@case(5, "F5")
def note_about_family_member_on_shared_email():
    """A spouse's approved check is filed under the shared email; her name/DOB become the customer's 'verified' facts."""
    def b(w):
        c = w.customer("John Smith", dob="1970-03-03", nationality="United Kingdom", residence_country="GB")
        w.note(c, "Onfido approved the passport of MARY SMITH (spouse of the account holder), born 1975-06-06, issued in "
                  "the United Kingdom.", created_at="2025-01-01")
        return w.hit(c, name="Smith, John", dobs=["1970"], countries=["United Kingdom"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Never use another customer's records (2); identity check of the person (4)"


@case(5, "F5")
def note_title_counts_as_name_part():
    """Verified name 'MR AHMED' has one real part; the title makes it two, so it is used to clear on name."""
    def b(w):
        c = w.customer("Ahmed Karimi", dob="1980-01-01", nationality="Iran", residence_country="IR")
        w.kyc_check(c, verified_name="MR AHMED", verified_dob="1980-01-01", document_country="Iran")
        return w.hit(c, name="Karimi, Ahmed", countries=["Iran"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Fewer than two real name parts: neither confirmed nor cleared on name (8)"


# ============================================================================ F6 verified DOB parsed from notes
@case(6, "F6")
def note_dob_tie_picks_issue_date():
    """Issue date and 'DOB: March 1968' are equally close to 'DOB'; the earlier (issue date) wins -> born 2019."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1968-03-10", nationality="Russia", residence_country="RU")
        w.note(c, "Onfido approved IVAN PETROV, passport issued 2019-02-03, DOB: March 1968, Russia.", created_at="2024-05-05")
        return w.hit(c, name="Petrov, Ivan", dobs=["1968"], countries=["Russia"],
                     profile_notes="According to Reuters; March 3, 2020: Ivan Petrov was sanctioned.")
    return one(b), SAFE, "DIFFERENT_ENTITY", "Verified DOB = the person's birth date, not the document issue date (4)"


@case(6, "F6")
def note_two_digit_year_dob_falls_back_to_other_date():
    """DOB '10.08.68' is unparseable; the account-opening date is taken as the verified DOB."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1968-08-10", nationality="Russia", residence_country="RU")
        w.note(c, "Veriff approved IVAN PETROV on 2024-04-26 (account opened 2023-01-05). DOB 10.08.68. Russian passport.",
               created_at="2024-04-26")
        return w.hit(c, name="Petrov, Ivan", dobs=["1968"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Verified DOB = the person's birth date (4)"


@case(6, "F6")
def note_onfido_consider_treated_as_approved():
    """Onfido 'consider' (= not passed, needs review) has no negative keyword, so the check's DOB is used as verified."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        w.note(c, "Onfido result for IVAN PETROV: consider - document shows DOB 1990-02-02, Russian passport. Manual review "
                  "required.", created_at="2025-01-01")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Only approved checks are evidence (4)"


@case(6, "F6")
def note_rejected_word_kills_approved_reverification():
    """'re-verified and approved after an earlier rejected attempt' is treated as rejected; record DOB (typo) clears."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1990-05-01", nationality="Russia", residence_country="RU")
        w.note(c, "After an earlier rejected attempt, Onfido re-verified and approved the Russian passport of IVAN PETROV, "
                  "born 1970-05-01.", created_at="2025-01-01")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Verified beats declared (4): the approved check's DOB agrees"


# ============================================================================ F7 placeholders
@case(7, "F7")
def placeholder_document_number_merges_strangers():
    """Two strangers whose approved checks carry doc number 'UNKNOWN' are merged; the stranger's newer DOB is used."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        w.kyc_check(c, verified_name="Ivan Petrov", verified_dob="1970-05-01", document_country="Russia",
                    document_number="UNKNOWN", checked_at="2023-01-01")
        s = w.customer("Wei Zhang", dob="1995-09-09", nationality="China", residence_country="CN")
        w.kyc_check(s, verified_name="Wei Zhang", verified_dob="1995-09-09", document_country="China",
                    document_number="UNKNOWN", checked_at="2024-06-01")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Same document number = same person (3); a placeholder is not a number"


@case(7, "F7")
def placeholder_customer_dob_1900():
    """Record DOB 01/01/1900 (system default) contradicts every real hit DOB -> DOB_MISMATCH."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="01/01/1900", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "A placeholder is not a date of birth (8 by analogy: placeholders are not data)"


@case(7, "F7")
def company_name_all_digits():
    """Company verified name '3M Company' has no parts (digit token + legal form), so it 'agrees with no hit name'."""
    def b(w):
        c = w.customer("3M Company", dob="1999-01-01", nationality="United States", residence_country="US", entity_type="Company")
        w.kyc_check(c, verified_name="3M Company", verified_dob="1999-01-01", document_country="United States")
        return w.hit(c, entity_type="Company", name="3M Co", countries=["United States"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "A name with no real parts can be neither confirmed nor cleared on name (8)"


# ============================================================================ F8 non-Latin scripts
@case(8, "F8")
def verified_name_in_cyrillic():
    """KYC provider returns the passport name in Cyrillic; it 'agrees with none' of the Latin hit names."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        w.kyc_check(c, verified_name="ИВАН ПЕТРОВ", verified_dob="1970-05-01", document_country="Russia")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Name clear only when the legal name agrees with no hit name (6); scripts can't be compared"


@case(8, "F8")
def hit_name_only_in_arabic():
    """Hit gives its name only in Arabic script; a verified Latin legal name cannot match it -> NAME_MISMATCH."""
    def b(w):
        c = w.customer("Omar Ali Hussain", dob="1975-01-01", nationality="Iraq", residence_country="IQ")
        w.kyc_check(c, verified_name="Omar Ali Hussain", verified_dob="1975-01-01", document_country="Iraq")
        return w.hit(c, name="عمر علي حسين", countries=["Iraq"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Name clear only when the legal name agrees with no hit name (6); scripts can't be compared"


# ============================================================================ F9 resolution
@case(9, "F9")
def unlinked_search_misses_true_customer_city_spelling():
    """No link; screened city 'Munich' vs the customer's 'München' excludes them, the only other fit is a namesake who is cleared."""
    def b(w):
        w.customer("Markus Weber", dob="1975-02-02", nationality="Germany", residence_country="DE", city="München",
                   address="Leopoldstr. 1, München")
        n = w.customer("Markus Weber", dob="", nationality="Austria", residence_country="AT", city="Munich, North Dakota",
                       address="1 Main St, Munich, North Dakota")
        return w.hit(n, link=None, alert={"customer_name": "Markus Weber", "city": "Munich"},
                     name="Weber, Markus", dobs=["1975-02-02"], countries=["Germany"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Know who the customer is before comparing (2); a missed record is not a contradiction"


@case(9, "F9")
def account_ref_missing_but_login_present():
    """account_ref not found -> unresolved REVIEW even though login_handle resolves (cost, not unsafe)."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, link=None, alert={"account_ref": "ACC-DOESNOTEXIST", "login_handle": c["record_id"].lower().replace("-", "")},
                     name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), {"SAME_ENTITY"}, "REVIEW", "Follow whatever link the alert carries (2) - accuracy, not safety"


# ============================================================================ F10 search results
@case(10, "F10")
def search_born_place_then_listing_year():
    """'born in Kano; listed 2012' -> the listing year is taken as the birth year (no distance check in search snippets)."""
    def b(w):
        c = w.customer("Musa Bello", dob="1975-01-01", nationality="Nigeria", residence_country="NG")
        w.search_result("musa bello", "Musa Bello, a sanctioned individual from Nigeria, born in Kano; listed 2012.")
        return w.hit(c, name="Bello, Musa", countries=["Nigeria"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Only a birth date the result gives counts (5)"


# ============================================================================ F11 accuracy (not unsafe, cost 2)
@case(11, "F11")
def name_dob_agree_location_differs_confirms():
    """Name and DOB agree but no country is shared: policy says REVIEW, the system says SAME_ENTITY / NAME_DOB_MATCH."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Cyprus", residence_country="CY")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970"], countries=["Russia"])
    return one(b), REVIEW, "SAME_ENTITY", "'A country difference does not clear a hit whose name and DOB agree: that hit is REVIEW' (6)"


# ============================================================================ F12 judgement calls (policy-literal clears)
@case(12, "F12")
def support_note_corrects_record_dob():
    """A phone note says the record DOB is a typo; it is not an identity check, so the wrong record DOB clears."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1990-05-01", nationality="Russia", residence_country="RU")
        w.note(c, "Customer called: the date of birth on file (1990) is a typo, correct date of birth is 01/05/1970. Updated "
                  "ticket raised.", channel="phone")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Judgement: literal policy uses the declared DOB; a sensible analyst would REVIEW"


@case(12, "F12")
def customer_day_month_swap():
    """Record '05/12/1980' (day-first = 5 Dec) vs hit 1980-05-12: same year, months differ -> DOB_MISMATCH."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="05/12/1980", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", dobs=["1980-05-12"], countries=["Russia"])
    return one(b), SAFE, "DIFFERENT_ENTITY", "Judgement: literal policy clears (months differ); a swap is the classic data-entry error"


# ============================================================================ controls: probed, system holds
@case(99, "control")
def control_cyrillic_alias_in_brackets():
    """Bracketed script tags on aliases are ignored and the Latin name still agrees."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", aliases=["Иван Петров (None, Cyrillic)"], dobs=["1970-05-01"], countries=["Russia"])
    return one(b), {"SAME_ENTITY"}, "SAME_ENTITY", "control"


@case(99, "control")
def control_year_only_customer_dob_vs_full_hit_dob():
    """Year-only customer DOB vs full hit DOB in the same year agrees."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), {"SAME_ENTITY"}, "SAME_ENTITY", "control (7)"


@case(99, "control")
def control_minor_temporal_only_with_report_line():
    """A 12-year-old customer is not cleared on TEMPORAL when the report is not in the 'According to …;' form."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="2014-05-01", nationality="Russia", residence_country="RU")
        return w.hit(c, name="Petrov, Ivan", countries=["Russia"], profile_notes="Reuters reported on 2020-01-08 that he was sanctioned.")
    return one(b), REVIEW, "REVIEW", "control (5: other wordings do not count)"


@case(99, "control")
def control_rejected_kyc_name_ignored():
    """A rejected check's different name does not clear on NAME_MISMATCH_VERIFIED."""
    def b(w):
        c = w.customer("Ivan Petrov", dob="1970-05-01", nationality="Russia", residence_country="RU")
        w.kyc_check(c, verified_name="Pavel Sidorov", verified_dob="1970-05-01", result="rejected", document_country="Russia")
        return w.hit(c, name="Petrov, Ivan", dobs=["1970-05-01"], countries=["Russia"])
    return one(b), {"SAME_ENTITY"}, "SAME_ENTITY", "control (4)"
