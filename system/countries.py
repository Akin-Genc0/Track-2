"""Country gazetteer (stdlib only). Canonical name | ISO2 | ISO3 | aliases and demonyms (comma separated).
Territories are their own country (policy principle 6)."""
import re, unicodedata

_RAW = """
Afghanistan|AF|AFG|Afghan
Albania|AL|ALB|Albanian
Algeria|DZ|DZA|Algerian
American Samoa|AS|ASM|American Samoan
Andorra|AD|AND|Andorran
Angola|AO|AGO|Angolan
Anguilla|AI|AIA|Anguillan
Antigua and Barbuda|AG|ATG|Antiguan
Argentina|AR|ARG|Argentine,Argentinian
Armenia|AM|ARM|Armenian
Aruba|AW|ABW|Aruban
Australia|AU|AUS|Australian
Austria|AT|AUT|Austrian,Österreich,Oesterreich
Azerbaijan|AZ|AZE|Azerbaijani,Azeri
Bahamas|BS|BHS|Bahamian,The Bahamas
Bahrain|BH|BHR|Bahraini
Bangladesh|BD|BGD|Bangladeshi
Barbados|BB|BRB|Barbadian
Belarus|BY|BLR|Belarusian
Belgium|BE|BEL|Belgian
Belize|BZ|BLZ|Belizean
Benin|BJ|BEN|Beninese
Bermuda|BM|BMU|Bermudian
Bhutan|BT|BTN|Bhutanese
Bolivia|BO|BOL|Bolivian,Plurinational State of Bolivia
Bosnia and Herzegovina|BA|BIH|Bosnian,Bosnia,Bosnia-Herzegovina
Botswana|BW|BWA|Botswanan,Motswana
Brazil|BR|BRA|Brazilian,Brasil
British Virgin Islands|VG|VGB|Virgin Islands British,BVI
Brunei|BN|BRN|Bruneian,Brunei Darussalam
Bulgaria|BG|BGR|Bulgarian
Burkina Faso|BF|BFA|Burkinabe
Burundi|BI|BDI|Burundian
Cambodia|KH|KHM|Cambodian
Cameroon|CM|CMR|Cameroonian
Canada|CA|CAN|Canadian
Cape Verde|CV|CPV|Cabo Verde,Cape Verdean
Cayman Islands|KY|CYM|Caymanian
Central African Republic|CF|CAF|Central African
Chad|TD|TCD|Chadian
Chile|CL|CHL|Chilean
China|CN|CHN|Chinese,People's Republic of China,PRC
Colombia|CO|COL|Colombian
Comoros|KM|COM|Comoran
Congo|CG|COG|Republic of the Congo,Congolese,Congo-Brazzaville
Democratic Republic of the Congo|CD|COD|DR Congo,DRC,Congo-Kinshasa,Congo Democratic Republic
Cook Islands|CK|COK|Cook Islander
Costa Rica|CR|CRI|Costa Rican
Cote d'Ivoire|CI|CIV|Ivory Coast,Ivorian,Côte d'Ivoire,Cote D'Ivoire
Croatia|HR|HRV|Croatian,Croat,Hrvatska
Cuba|CU|CUB|Cuban
Curacao|CW|CUW|Curaçao,Curacaoan
Cyprus|CY|CYP|Cypriot
Czech Republic|CZ|CZE|Czech,Czechia,Czechoslovakia,Czechoslovak,Česko,Česká republika
Denmark|DK|DNK|Danish,Dane,Danmark
Djibouti|DJ|DJI|Djiboutian
Dominica|DM|DMA|Dominican (Dominica)
Dominican Republic|DO|DOM|Dominican
Ecuador|EC|ECU|Ecuadorian,Ecuadorean
Egypt|EG|EGY|Egyptian,Misr
El Salvador|SV|SLV|Salvadoran,Salvadorean
Equatorial Guinea|GQ|GNQ|Equatoguinean
Eritrea|ER|ERI|Eritrean
Estonia|EE|EST|Estonian
Eswatini|SZ|SWZ|Swaziland,Swazi
Ethiopia|ET|ETH|Ethiopian
Falkland Islands|FK|FLK|Falkland Islander
Faroe Islands|FO|FRO|Faroese
Fiji|FJ|FJI|Fijian
Finland|FI|FIN|Finnish,Finn,Suomi
France|FR|FRA|French
French Guiana|GF|GUF|French Guianese
French Polynesia|PF|PYF|French Polynesian
Gabon|GA|GAB|Gabonese
Gambia|GM|GMB|Gambian,The Gambia
Georgia|GE|GEO|Georgian
Germany|DE|DEU|German,Deutschland
Ghana|GH|GHA|Ghanaian
Gibraltar|GI|GIB|Gibraltarian
Greece|GR|GRC|Greek,Hellenic,Hellas,Ellada
Greenland|GL|GRL|Greenlandic
Grenada|GD|GRD|Grenadian
Guadeloupe|GP|GLP|Guadeloupean
Guam|GU|GUM|Guamanian
Guatemala|GT|GTM|Guatemalan
Guernsey|GG|GGY|
Guinea|GN|GIN|Guinean
Guinea-Bissau|GW|GNB|Bissau-Guinean
Guyana|GY|GUY|Guyanese
Haiti|HT|HTI|Haitian
Honduras|HN|HND|Honduran
Hong Kong|HK|HKG|Hong Konger,Hong Kong SAR,Hong Kong Special Administrative Region of China
Hungary|HU|HUN|Hungarian,Magyarország
Iceland|IS|ISL|Icelandic,Icelander
India|IN|IND|Indian,Bharat
Indonesia|ID|IDN|Indonesian
Iran|IR|IRN|Iranian,Islamic Republic of Iran,Persia
Iraq|IQ|IRQ|Iraqi
Ireland|IE|IRL|Irish,Republic of Ireland,Eire
Isle of Man|IM|IMN|Manx
Israel|IL|ISR|Israeli
Italy|IT|ITA|Italian,Italia
Jamaica|JM|JAM|Jamaican
Japan|JP|JPN|Japanese,Nippon,Nihon
Jersey|JE|JEY|
Jordan|JO|JOR|Jordanian
Kazakhstan|KZ|KAZ|Kazakh,Kazakhstani
Kenya|KE|KEN|Kenyan
Kiribati|KI|KIR|I-Kiribati
Kosovo|XK|XKX|Kosovar,Kosovan
Kuwait|KW|KWT|Kuwaiti
Kyrgyzstan|KG|KGZ|Kyrgyz,Kyrgyz Republic
Laos|LA|LAO|Lao,Laotian,Lao People's Democratic Republic,Lao PDR
Latvia|LV|LVA|Latvian
Lebanon|LB|LBN|Lebanese
Lesotho|LS|LSO|Basotho,Mosotho
Liberia|LR|LBR|Liberian
Libya|LY|LBY|Libyan
Liechtenstein|LI|LIE|Liechtensteiner
Lithuania|LT|LTU|Lithuanian
Luxembourg|LU|LUX|Luxembourgish,Luxembourger
Macao|MO|MAC|Macau,Macanese,Macao SAR,Macao Special Administrative Region of China
Madagascar|MG|MDG|Malagasy
Malawi|MW|MWI|Malawian
Malaysia|MY|MYS|Malaysian
Maldives|MV|MDV|Maldivian
Mali|ML|MLI|Malian
Malta|MT|MLT|Maltese
Marshall Islands|MH|MHL|Marshallese
Martinique|MQ|MTQ|Martinican
Mauritania|MR|MRT|Mauritanian
Mauritius|MU|MUS|Mauritian
Mayotte|YT|MYT|
Mexico|MX|MEX|Mexican
Micronesia|FM|FSM|Micronesian,Federated States of Micronesia
Moldova|MD|MDA|Moldovan,Republic of Moldova
Monaco|MC|MCO|Monegasque,Monacan
Mongolia|MN|MNG|Mongolian
Montenegro|ME|MNE|Montenegrin
Montserrat|MS|MSR|Montserratian
Morocco|MA|MAR|Moroccan,Al-Maghrib,Maroc
Mozambique|MZ|MOZ|Mozambican
Myanmar|MM|MMR|Burma,Burmese,Myanmar (Burma)
Namibia|NA|NAM|Namibian
Nauru|NR|NRU|Nauruan
Nepal|NP|NPL|Nepalese,Nepali
Netherlands|NL|NLD|Dutch,Holland,The Netherlands,Netherlander,Nederland
New Caledonia|NC|NCL|New Caledonian
New Zealand|NZ|NZL|New Zealander,Kiwi
Nicaragua|NI|NIC|Nicaraguan
Niger|NE|NER|Nigerien
Nigeria|NG|NGA|Nigerian
North Korea|KP|PRK|North Korean,Democratic People's Republic of Korea,DPRK,Korea North,Korea Democratic People's Republic of
North Macedonia|MK|MKD|Macedonia,Macedonian,North Macedonian
Northern Mariana Islands|MP|MNP|Northern Marianan
Norway|NO|NOR|Norwegian,Norge,Noreg
Oman|OM|OMN|Omani
Pakistan|PK|PAK|Pakistani
Palau|PW|PLW|Palauan
Palestine|PS|PSE|Palestinian,Palestina,State of Palestine,Palestinian Territories,West Bank,Gaza
Panama|PA|PAN|Panamanian
Papua New Guinea|PG|PNG|Papua New Guinean
Paraguay|PY|PRY|Paraguayan
Peru|PE|PER|Peruvian
Philippines|PH|PHL|Filipino,Philippine,The Philippines
Poland|PL|POL|Polish,Pole,Polska
Portugal|PT|PRT|Portuguese
Puerto Rico|PR|PRI|Puerto Rican
Qatar|QA|QAT|Qatari
Reunion|RE|REU|Réunion
Romania|RO|ROU|Romanian
Russia|RU|RUS|Russian,Russian Federation,USSR,U.S.S.R.,Soviet Union,Rossiya,Rossiia
Rwanda|RW|RWA|Rwandan
Saint Kitts and Nevis|KN|KNA|Kittitian,St Kitts and Nevis
Saint Lucia|LC|LCA|Saint Lucian,St Lucia
Saint Vincent and the Grenadines|VC|VCT|Vincentian,St Vincent and the Grenadines
Samoa|WS|WSM|Samoan
San Marino|SM|SMR|Sammarinese
Sao Tome and Principe|ST|STP|Sao Tomean,São Tomé and Príncipe
Saudi Arabia|SA|SAU|Saudi,Saudi Arabian,KSA,Kingdom of Saudi Arabia
Senegal|SN|SEN|Senegalese
Serbia|RS|SRB|Serbian,Serb,Yugoslavia,Yugoslav,Serbia and Montenegro
Seychelles|SC|SYC|Seychellois
Sierra Leone|SL|SLE|Sierra Leonean
Singapore|SG|SGP|Singaporean
Sint Maarten|SX|SXM|
Slovakia|SK|SVK|Slovak,Slovakian,Slovak Republic
Slovenia|SI|SVN|Slovenian,Slovene
Solomon Islands|SB|SLB|Solomon Islander
Somalia|SO|SOM|Somali
South Africa|ZA|ZAF|South African
South Korea|KR|KOR|South Korean,Republic of Korea,Korea South,Korea,Korea Republic of
South Sudan|SS|SSD|South Sudanese
Spain|ES|ESP|Spanish,Spaniard,España
Sri Lanka|LK|LKA|Sri Lankan
Sudan|SD|SDN|Sudanese
Suriname|SR|SUR|Surinamese
Sweden|SE|SWE|Swedish,Swede,Sverige
Switzerland|CH|CHE|Swiss,Schweiz,Suisse,Svizzera,Confoederatio Helvetica
Syria|SY|SYR|Syrian,Syrian Arab Republic
Taiwan|TW|TWN|Taiwanese
Tajikistan|TJ|TJK|Tajik,Tajikistani
Tanzania|TZ|TZA|Tanzanian,United Republic of Tanzania
Thailand|TH|THA|Thai
Timor-Leste|TL|TLS|East Timor,Timorese
Togo|TG|TGO|Togolese
Tonga|TO|TON|Tongan
Trinidad and Tobago|TT|TTO|Trinidadian,Tobagonian
Tunisia|TN|TUN|Tunisian
Turkey|TR|TUR|Turkish,Türkiye,Turkiye
Turkmenistan|TM|TKM|Turkmen
Turks and Caicos Islands|TC|TCA|
Tuvalu|TV|TUV|Tuvaluan
Uganda|UG|UGA|Ugandan
Ukraine|UA|UKR|Ukrainian,Crimea,Ukraina
United Arab Emirates|AE|ARE|Emirati,UAE,U.A.E.,the Emirates,Emirates
United Kingdom|GB|GBR|UK,U.K.,British,Great Britain,Britain,England,Scotland,Wales,Northern Ireland,English,Scottish,Welsh,United Kingdom of Great Britain and Northern Ireland
United States|US|USA|U.S.,U.S.A.,United States of America,America,American,the United States,the US,the USA
US Virgin Islands|VI|VIR|Virgin Islands U.S.,U.S. Virgin Islands
Uruguay|UY|URY|Uruguayan
Uzbekistan|UZ|UZB|Uzbek,Uzbekistani
Vanuatu|VU|VUT|Ni-Vanuatu
Vatican City|VA|VAT|Holy See,Vatican
Venezuela|VE|VEN|Venezuelan,Bolivarian Republic of Venezuela
Vietnam|VN|VNM|Vietnamese,Viet Nam
Western Sahara|EH|ESH|Sahrawi
Yemen|YE|YEM|Yemeni
Zambia|ZM|ZMB|Zambian
Zimbabwe|ZW|ZWE|Zimbabwean
"""

NOT_COUNTRIES = {"international", "europe", "global", "worldwide", "unknown", "none", "africa", "asia",
                 "middle east", "latin america", "south america", "north america", "european union", "eu"}


def _key(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    return s


LOOKUP = {}     # normalised alias -> canonical
CODES = {}      # upper-case ISO code -> canonical
CANON = []
for line in _RAW.strip().splitlines():
    name, iso2, iso3, extra = (line.split("|") + [""])[:4]
    CANON.append(name)
    CODES[iso2] = name
    CODES[iso3] = name
    for a in [name] + [x for x in extra.split(",") if x.strip()]:
        a = re.sub(r"\(.*?\)", "", a)
        k = _key(a)
        if k and k not in LOOKUP:
            LOOKUP[k] = name
# US states and Canadian provinces: an address ending in one is in that country ("Newark, New Jersey" is not Jersey).
# Georgia is both a state and a country, so it stays ambiguous (see SUBNATIONAL_AMBIG).
US_STATES = """Alabama,Alaska,Arizona,Arkansas,California,Colorado,Connecticut,Delaware,Florida,Hawaii,Idaho,Illinois,Indiana,Iowa,
Kansas,Kentucky,Louisiana,Maine,Maryland,Massachusetts,Michigan,Minnesota,Mississippi,Missouri,Montana,Nebraska,Nevada,New Hampshire,
New Jersey,New Mexico,New York,North Carolina,North Dakota,Ohio,Oklahoma,Oregon,Pennsylvania,Rhode Island,South Carolina,South Dakota,
Tennessee,Texas,Utah,Vermont,Virginia,Washington,West Virginia,Wisconsin,Wyoming,District of Columbia,Washington DC,Washington D.C."""
CA_PROVINCES = """Ontario,Quebec,British Columbia,Alberta,Manitoba,Saskatchewan,Nova Scotia,New Brunswick,Newfoundland and Labrador,
Prince Edward Island,Yukon,Northwest Territories,Nunavut"""
SUBNATIONAL = {}
for _st in US_STATES.replace("\n", "").split(","):
    SUBNATIONAL[_key(_st)] = "United States"
for _st in CA_PROVINCES.replace("\n", "").split(","):
    SUBNATIONAL[_key(_st)] = "Canada"
SUBNATIONAL_AMBIG = {"georgia": ("Georgia", "United States")}
LOOKUP["states"] = "United States"           # 'the States' as a whole value only (not in free text: "member states")
LOOKUP.pop("dominican", None)
LOOKUP["dominican"] = "Dominican Republic"


def norm_country(value, codes_any_case=False):
    """Map a single country value (name, ISO code, nationality/demonym, or 'City, Country')
    to a canonical country name, or None."""
    if value is None:
        return None
    v = re.sub(r"\[.*?\]", "", str(value)).strip()
    v = re.sub(r"\s*\((?:islamic |federal |democratic |people'?s |plurinational |bolivarian |the )?(?:republic|state|kingdom)[^)]*\)", "", v).strip()
    if not v:
        return None
    if v.isupper() and v.strip() in CODES and len(v.strip()) in (2, 3):
        return CODES[v.strip()]
    if codes_any_case and len(v) in (2, 3) and v.isalpha() and v.upper() in CODES:
        return CODES[v.upper()]
    k = _key(v)
    if not k or k in NOT_COUNTRIES:
        return None
    if k in LOOKUP:
        return LOOKUP[k]
    if v.strip() in CODES and len(v.strip()) in (2, 3) and v.strip().isupper():
        return CODES[v.strip()]
    # 'City, Region, Country' -> last part
    if "," in v:
        return norm_country(v.split(",")[-1])
    return None


# regex for finding country mentions in free text (longest aliases first)
_text_aliases = sorted((a for a in LOOKUP if (len(a) >= 4 or a in ("uk", "usa", "uae", "us", "ksa", "u s", "u k")) and a not in ("states", "emirates")),
                       key=len, reverse=True)
_TEXT_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in _text_aliases) + r")\b")
_AMBIG_TEXT = {"us", "georgia", "jersey", "chad", "guinea", "niger", "jordan", "america", "korea"}


def countries_in_text(text):
    """Return canonical countries mentioned in free text (normalised matching)."""
    out = []
    if not text:
        return out
    k = " " + _key(text) + " "
    raw = str(text)
    for m in _TEXT_RE.finditer(k):
        a = m.group(1)
        if k[max(0, m.start(1) - 4):m.start(1)] == "new ":
            continue        # New Jersey / New Mexico / New Guinea are not Jersey / Mexico / Guinea
        if a == "us":
            # only accept 'US' written in capitals as a country code
            if not re.search(r"\bU\.?S\.?\b", raw):
                continue
        c = LOOKUP[a]
        if c not in out:
            out.append(c)
    return out


def countries_in_value(value, address=False):
    """Every country one customer or hit field value names: 'Russia, Cyprus', 'Russian/Cypriot', 'ru', 'Korea, Republic of',
    'Atlanta, Georgia' (state or country: both). Returns (countries, recognised); recognised is False when the value
    names a place we cannot place at all, which must never count as a different country."""
    v = re.sub(r"\[.*?\]", "", str(value or "")).strip()
    if not v:
        return [], True
    if _key(v) in NOT_COUNTRIES:
        return [], True
    out = []
    last = _key(v.split(",")[-1])
    if address and last in SUBNATIONAL_AMBIG:
        return list(SUBNATIONAL_AMBIG[last]), True
    if address and last in SUBNATIONAL:
        return [SUBNATIONAL[last]], True
    whole = norm_country(v, codes_any_case=True)
    if whole and not re.search(r"[,/;&]| and ", v):
        return [whole], True
    pieces = [x for x in re.split(r"\s*(?:[,/;&]|\band\b)\s*", v) if x.strip()]
    for piece in pieces:
        c = norm_country(piece, codes_any_case=True) if len(piece) <= 3 or not address else norm_country(piece)
        if c and c not in out:
            out.append(c)
    if whole and whole not in out and not out:
        out.append(whole)
    for c in countries_in_text(v):
        if c not in out:
            out.append(c)
    if not address and whole and whole not in out:
        out.append(whole)
    return out, bool(out)
