#!/usr/bin/env python3
"""
Track 2 - "Is my customer sanctioned?"
Deterministic screening-alert reviewer that implements the identity SOP (POLICY.md).

Usage:
    python screen.py --data dev --out predictions.jsonl
    python screen.py --data dev --eval          # score against practice_labels.jsonl
"""
import argparse, json, os, re, sys, unicodedata
from collections import defaultdict
from datetime import date

# Built-in ISO country table (so the script needs no extra packages)
_ISO = json.loads(r'''{"names":{"Aruba":"AW","Afghanistan":"AF","Islamic Republic of Afghanistan":"AF","Angola":"AO","Republic of Angola":"AO","Anguilla":"AI","Åland Islands":"AX","Albania":"AL","Republic of Albania":"AL","Andorra":"AD","Principality of Andorra":"AD","United Arab Emirates":"AE","Argentina":"AR","Argentine Republic":"AR","Armenia":"AM","Republic of Armenia":"AM","American Samoa":"AS","Antarctica":"AQ","French Southern Territories":"TF","Antigua and Barbuda":"AG","Australia":"AU","Austria":"AT","Republic of Austria":"AT","Azerbaijan":"AZ","Republic of Azerbaijan":"AZ","Burundi":"BI","Republic of Burundi":"BI","Belgium":"BE","Kingdom of Belgium":"BE","Benin":"BJ","Republic of Benin":"BJ","Bonaire, Sint Eustatius and Saba":"BQ","Burkina Faso":"BF","Bangladesh":"BD","People's Republic of Bangladesh":"BD","Bulgaria":"BG","Republic of Bulgaria":"BG","Bahrain":"BH","Kingdom of Bahrain":"BH","Bahamas":"BS","Commonwealth of the Bahamas":"BS","Bosnia and Herzegovina":"BA","Republic of Bosnia and Herzegovina":"BA","Saint Barthélemy":"BL","Belarus":"BY","Republic of Belarus":"BY","Belize":"BZ","Bermuda":"BM","Bolivia, Plurinational State of":"BO","Bolivia":"BO","Plurinational State of Bolivia":"BO","Brazil":"BR","Federative Republic of Brazil":"BR","Barbados":"BB","Brunei Darussalam":"BN","Bhutan":"BT","Kingdom of Bhutan":"BT","Bouvet Island":"BV","Botswana":"BW","Republic of Botswana":"BW","Central African Republic":"CF","Canada":"CA","Cocos (Keeling) Islands":"CC","Switzerland":"CH","Swiss Confederation":"CH","Chile":"CL","Republic of Chile":"CL","China":"CN","People's Republic of China":"CN","Côte d'Ivoire":"CI","Republic of Côte d'Ivoire":"CI","Cameroon":"CM","Republic of Cameroon":"CM","Congo, The Democratic Republic of the":"CD","Congo":"CG","Republic of the Congo":"CG","Cook Islands":"CK","Colombia":"CO","Republic of Colombia":"CO","Comoros":"KM","Union of the Comoros":"KM","Cabo Verde":"CV","Republic of Cabo Verde":"CV","Costa Rica":"CR","Republic of Costa Rica":"CR","Cuba":"CU","Republic of Cuba":"CU","Curaçao":"CW","Christmas Island":"CX","Cayman Islands":"KY","Cyprus":"CY","Republic of Cyprus":"CY","Czechia":"CZ","Czech Republic":"CZ","Germany":"DE","Federal Republic of Germany":"DE","Djibouti":"DJ","Republic of Djibouti":"DJ","Dominica":"DM","Commonwealth of Dominica":"DM","Denmark":"DK","Kingdom of Denmark":"DK","Dominican Republic":"DO","Algeria":"DZ","People's Democratic Republic of Algeria":"DZ","Ecuador":"EC","Republic of Ecuador":"EC","Egypt":"EG","Arab Republic of Egypt":"EG","Eritrea":"ER","the State of Eritrea":"ER","Western Sahara":"EH","Spain":"ES","Kingdom of Spain":"ES","Estonia":"EE","Republic of Estonia":"EE","Ethiopia":"ET","Federal Democratic Republic of Ethiopia":"ET","Finland":"FI","Republic of Finland":"FI","Fiji":"FJ","Republic of Fiji":"FJ","Falkland Islands (Malvinas)":"FK","France":"FR","French Republic":"FR","Faroe Islands":"FO","Micronesia, Federated States of":"FM","Federated States of Micronesia":"FM","Gabon":"GA","Gabonese Republic":"GA","United Kingdom":"GB","United Kingdom of Great Britain and Northern Ireland":"GB","Georgia":"GE","Guernsey":"GG","Ghana":"GH","Republic of Ghana":"GH","Gibraltar":"GI","Guinea":"GN","Republic of Guinea":"GN","Guadeloupe":"GP","Gambia":"GM","Republic of the Gambia":"GM","Guinea-Bissau":"GW","Republic of Guinea-Bissau":"GW","Equatorial Guinea":"GQ","Republic of Equatorial Guinea":"GQ","Greece":"GR","Hellenic Republic":"GR","Grenada":"GD","Greenland":"GL","Guatemala":"GT","Republic of Guatemala":"GT","French Guiana":"GF","Guam":"GU","Guyana":"GY","Republic of Guyana":"GY","Hong Kong":"HK","Hong Kong Special Administrative Region of China":"HK","Heard Island and McDonald Islands":"HM","Honduras":"HN","Republic of Honduras":"HN","Croatia":"HR","Republic of Croatia":"HR","Haiti":"HT","Republic of Haiti":"HT","Hungary":"HU","Indonesia":"ID","Republic of Indonesia":"ID","Isle of Man":"IM","India":"IN","Republic of India":"IN","British Indian Ocean Territory":"IO","Ireland":"IE","Iran, Islamic Republic of":"IR","Iran":"IR","Islamic Republic of Iran":"IR","Iraq":"IQ","Republic of Iraq":"IQ","Iceland":"IS","Republic of Iceland":"IS","Israel":"IL","State of Israel":"IL","Italy":"IT","Italian Republic":"IT","Jamaica":"JM","Jersey":"JE","Jordan":"JO","Hashemite Kingdom of Jordan":"JO","Japan":"JP","Kazakhstan":"KZ","Republic of Kazakhstan":"KZ","Kenya":"KE","Republic of Kenya":"KE","Kyrgyzstan":"KG","Kyrgyz Republic":"KG","Cambodia":"KH","Kingdom of Cambodia":"KH","Kiribati":"KI","Republic of Kiribati":"KI","Saint Kitts and Nevis":"KN","Korea, Republic of":"KR","South Korea":"KR","Kuwait":"KW","State of Kuwait":"KW","Lao People's Democratic Republic":"LA","Laos":"LA","Lebanon":"LB","Lebanese Republic":"LB","Liberia":"LR","Republic of Liberia":"LR","Libya":"LY","Saint Lucia":"LC","Liechtenstein":"LI","Principality of Liechtenstein":"LI","Sri Lanka":"LK","Democratic Socialist Republic of Sri Lanka":"LK","Lesotho":"LS","Kingdom of Lesotho":"LS","Lithuania":"LT","Republic of Lithuania":"LT","Luxembourg":"LU","Grand Duchy of Luxembourg":"LU","Latvia":"LV","Republic of Latvia":"LV","Macao":"MO","Macao Special Administrative Region of China":"MO","Saint Martin (French part)":"MF","Morocco":"MA","Kingdom of Morocco":"MA","Monaco":"MC","Principality of Monaco":"MC","Moldova, Republic of":"MD","Moldova":"MD","Republic of Moldova":"MD","Madagascar":"MG","Republic of Madagascar":"MG","Maldives":"MV","Republic of Maldives":"MV","Mexico":"MX","United Mexican States":"MX","Marshall Islands":"MH","Republic of the Marshall Islands":"MH","North Macedonia":"MK","Republic of North Macedonia":"MK","Mali":"ML","Republic of Mali":"ML","Malta":"MT","Republic of Malta":"MT","Myanmar":"MM","Republic of Myanmar":"MM","Montenegro":"ME","Mongolia":"MN","Northern Mariana Islands":"MP","Commonwealth of the Northern Mariana Islands":"MP","Mozambique":"MZ","Republic of Mozambique":"MZ","Mauritania":"MR","Islamic Republic of Mauritania":"MR","Montserrat":"MS","Martinique":"MQ","Mauritius":"MU","Republic of Mauritius":"MU","Malawi":"MW","Republic of Malawi":"MW","Malaysia":"MY","Mayotte":"YT","Namibia":"NA","Republic of Namibia":"NA","New Caledonia":"NC","Niger":"NE","Republic of the Niger":"NE","Norfolk Island":"NF","Nigeria":"NG","Federal Republic of Nigeria":"NG","Nicaragua":"NI","Republic of Nicaragua":"NI","Niue":"NU","Netherlands":"NL","Kingdom of the Netherlands":"NL","Norway":"NO","Kingdom of Norway":"NO","Nepal":"NP","Federal Democratic Republic of Nepal":"NP","Nauru":"NR","Republic of Nauru":"NR","New Zealand":"NZ","Oman":"OM","Sultanate of Oman":"OM","Pakistan":"PK","Islamic Republic of Pakistan":"PK","Panama":"PA","Republic of Panama":"PA","Pitcairn":"PN","Peru":"PE","Republic of Peru":"PE","Philippines":"PH","Republic of the Philippines":"PH","Palau":"PW","Republic of Palau":"PW","Papua New Guinea":"PG","Independent State of Papua New Guinea":"PG","Poland":"PL","Republic of Poland":"PL","Puerto Rico":"PR","Korea, Democratic People's Republic of":"KP","North Korea":"KP","Democratic People's Republic of Korea":"KP","Portugal":"PT","Portuguese Republic":"PT","Paraguay":"PY","Republic of Paraguay":"PY","Palestine, State of":"PS","the State of Palestine":"PS","French Polynesia":"PF","Qatar":"QA","State of Qatar":"QA","Réunion":"RE","Romania":"RO","Russian Federation":"RU","Rwanda":"RW","Rwandese Republic":"RW","Saudi Arabia":"SA","Kingdom of Saudi Arabia":"SA","Sudan":"SD","Republic of the Sudan":"SD","Senegal":"SN","Republic of Senegal":"SN","Singapore":"SG","Republic of Singapore":"SG","South Georgia and the South Sandwich Islands":"GS","Saint Helena, Ascension and Tristan da Cunha":"SH","Svalbard and Jan Mayen":"SJ","Solomon Islands":"SB","Sierra Leone":"SL","Republic of Sierra Leone":"SL","El Salvador":"SV","Republic of El Salvador":"SV","San Marino":"SM","Republic of San Marino":"SM","Somalia":"SO","Federal Republic of Somalia":"SO","Saint Pierre and Miquelon":"PM","Serbia":"RS","Republic of Serbia":"RS","South Sudan":"SS","Republic of South Sudan":"SS","Sao Tome and Principe":"ST","Democratic Republic of Sao Tome and Principe":"ST","Suriname":"SR","Republic of Suriname":"SR","Slovakia":"SK","Slovak Republic":"SK","Slovenia":"SI","Republic of Slovenia":"SI","Sweden":"SE","Kingdom of Sweden":"SE","Eswatini":"SZ","Kingdom of Eswatini":"SZ","Sint Maarten (Dutch part)":"SX","Seychelles":"SC","Republic of Seychelles":"SC","Syrian Arab Republic":"SY","Syria":"SY","Turks and Caicos Islands":"TC","Chad":"TD","Republic of Chad":"TD","Togo":"TG","Togolese Republic":"TG","Thailand":"TH","Kingdom of Thailand":"TH","Tajikistan":"TJ","Republic of Tajikistan":"TJ","Tokelau":"TK","Turkmenistan":"TM","Timor-Leste":"TL","Democratic Republic of Timor-Leste":"TL","Tonga":"TO","Kingdom of Tonga":"TO","Trinidad and Tobago":"TT","Republic of Trinidad and Tobago":"TT","Tunisia":"TN","Republic of Tunisia":"TN","Türkiye":"TR","Republic of Türkiye":"TR","Tuvalu":"TV","Taiwan, Province of China":"TW","Taiwan":"TW","Tanzania, United Republic of":"TZ","Tanzania":"TZ","United Republic of Tanzania":"TZ","Uganda":"UG","Republic of Uganda":"UG","Ukraine":"UA","United States Minor Outlying Islands":"UM","Uruguay":"UY","Eastern Republic of Uruguay":"UY","United States":"US","United States of America":"US","Uzbekistan":"UZ","Republic of Uzbekistan":"UZ","Holy See (Vatican City State)":"VA","Saint Vincent and the Grenadines":"VC","Venezuela, Bolivarian Republic of":"VE","Venezuela":"VE","Bolivarian Republic of Venezuela":"VE","Virgin Islands, British":"VG","British Virgin Islands":"VG","Virgin Islands, U.S.":"VI","Virgin Islands of the United States":"VI","Viet Nam":"VN","Vietnam":"VN","Socialist Republic of Viet Nam":"VN","Vanuatu":"VU","Republic of Vanuatu":"VU","Wallis and Futuna":"WF","Samoa":"WS","Independent State of Samoa":"WS","Yemen":"YE","Republic of Yemen":"YE","South Africa":"ZA","Republic of South Africa":"ZA","Zambia":"ZM","Republic of Zambia":"ZM","Zimbabwe":"ZW","Republic of Zimbabwe":"ZW"},"a3":{"ABW":"AW","AFG":"AF","AGO":"AO","AIA":"AI","ALA":"AX","ALB":"AL","AND":"AD","ARE":"AE","ARG":"AR","ARM":"AM","ASM":"AS","ATA":"AQ","ATF":"TF","ATG":"AG","AUS":"AU","AUT":"AT","AZE":"AZ","BDI":"BI","BEL":"BE","BEN":"BJ","BES":"BQ","BFA":"BF","BGD":"BD","BGR":"BG","BHR":"BH","BHS":"BS","BIH":"BA","BLM":"BL","BLR":"BY","BLZ":"BZ","BMU":"BM","BOL":"BO","BRA":"BR","BRB":"BB","BRN":"BN","BTN":"BT","BVT":"BV","BWA":"BW","CAF":"CF","CAN":"CA","CCK":"CC","CHE":"CH","CHL":"CL","CHN":"CN","CIV":"CI","CMR":"CM","COD":"CD","COG":"CG","COK":"CK","COL":"CO","COM":"KM","CPV":"CV","CRI":"CR","CUB":"CU","CUW":"CW","CXR":"CX","CYM":"KY","CYP":"CY","CZE":"CZ","DEU":"DE","DJI":"DJ","DMA":"DM","DNK":"DK","DOM":"DO","DZA":"DZ","ECU":"EC","EGY":"EG","ERI":"ER","ESH":"EH","ESP":"ES","EST":"EE","ETH":"ET","FIN":"FI","FJI":"FJ","FLK":"FK","FRA":"FR","FRO":"FO","FSM":"FM","GAB":"GA","GBR":"GB","GEO":"GE","GGY":"GG","GHA":"GH","GIB":"GI","GIN":"GN","GLP":"GP","GMB":"GM","GNB":"GW","GNQ":"GQ","GRC":"GR","GRD":"GD","GRL":"GL","GTM":"GT","GUF":"GF","GUM":"GU","GUY":"GY","HKG":"HK","HMD":"HM","HND":"HN","HRV":"HR","HTI":"HT","HUN":"HU","IDN":"ID","IMN":"IM","IND":"IN","IOT":"IO","IRL":"IE","IRN":"IR","IRQ":"IQ","ISL":"IS","ISR":"IL","ITA":"IT","JAM":"JM","JEY":"JE","JOR":"JO","JPN":"JP","KAZ":"KZ","KEN":"KE","KGZ":"KG","KHM":"KH","KIR":"KI","KNA":"KN","KOR":"KR","KWT":"KW","LAO":"LA","LBN":"LB","LBR":"LR","LBY":"LY","LCA":"LC","LIE":"LI","LKA":"LK","LSO":"LS","LTU":"LT","LUX":"LU","LVA":"LV","MAC":"MO","MAF":"MF","MAR":"MA","MCO":"MC","MDA":"MD","MDG":"MG","MDV":"MV","MEX":"MX","MHL":"MH","MKD":"MK","MLI":"ML","MLT":"MT","MMR":"MM","MNE":"ME","MNG":"MN","MNP":"MP","MOZ":"MZ","MRT":"MR","MSR":"MS","MTQ":"MQ","MUS":"MU","MWI":"MW","MYS":"MY","MYT":"YT","NAM":"NA","NCL":"NC","NER":"NE","NFK":"NF","NGA":"NG","NIC":"NI","NIU":"NU","NLD":"NL","NOR":"NO","NPL":"NP","NRU":"NR","NZL":"NZ","OMN":"OM","PAK":"PK","PAN":"PA","PCN":"PN","PER":"PE","PHL":"PH","PLW":"PW","PNG":"PG","POL":"PL","PRI":"PR","PRK":"KP","PRT":"PT","PRY":"PY","PSE":"PS","PYF":"PF","QAT":"QA","REU":"RE","ROU":"RO","RUS":"RU","RWA":"RW","SAU":"SA","SDN":"SD","SEN":"SN","SGP":"SG","SGS":"GS","SHN":"SH","SJM":"SJ","SLB":"SB","SLE":"SL","SLV":"SV","SMR":"SM","SOM":"SO","SPM":"PM","SRB":"RS","SSD":"SS","STP":"ST","SUR":"SR","SVK":"SK","SVN":"SI","SWE":"SE","SWZ":"SZ","SXM":"SX","SYC":"SC","SYR":"SY","TCA":"TC","TCD":"TD","TGO":"TG","THA":"TH","TJK":"TJ","TKL":"TK","TKM":"TM","TLS":"TL","TON":"TO","TTO":"TT","TUN":"TN","TUR":"TR","TUV":"TV","TWN":"TW","TZA":"TZ","UGA":"UG","UKR":"UA","UMI":"UM","URY":"UY","USA":"US","UZB":"UZ","VAT":"VA","VCT":"VC","VEN":"VE","VGB":"VG","VIR":"VI","VNM":"VN","VUT":"VU","WLF":"WF","WSM":"WS","YEM":"YE","ZAF":"ZA","ZMB":"ZM","ZWE":"ZW"},"disp":{"AW":"Aruba","AF":"Afghanistan","AO":"Angola","AI":"Anguilla","AX":"Åland Islands","AL":"Albania","AD":"Andorra","AE":"United Arab Emirates","AR":"Argentina","AM":"Armenia","AS":"American Samoa","AQ":"Antarctica","TF":"French Southern Territories","AG":"Antigua and Barbuda","AU":"Australia","AT":"Austria","AZ":"Azerbaijan","BI":"Burundi","BE":"Belgium","BJ":"Benin","BQ":"Bonaire, Sint Eustatius and Saba","BF":"Burkina Faso","BD":"Bangladesh","BG":"Bulgaria","BH":"Bahrain","BS":"Bahamas","BA":"Bosnia and Herzegovina","BL":"Saint Barthélemy","BY":"Belarus","BZ":"Belize","BM":"Bermuda","BO":"Bolivia","BR":"Brazil","BB":"Barbados","BN":"Brunei Darussalam","BT":"Bhutan","BV":"Bouvet Island","BW":"Botswana","CF":"Central African Republic","CA":"Canada","CC":"Cocos (Keeling) Islands","CH":"Switzerland","CL":"Chile","CN":"China","CI":"Côte d'Ivoire","CM":"Cameroon","CD":"Congo, The Democratic Republic of the","CG":"Congo","CK":"Cook Islands","CO":"Colombia","KM":"Comoros","CV":"Cabo Verde","CR":"Costa Rica","CU":"Cuba","CW":"Curaçao","CX":"Christmas Island","KY":"Cayman Islands","CY":"Cyprus","CZ":"Czechia","DE":"Germany","DJ":"Djibouti","DM":"Dominica","DK":"Denmark","DO":"Dominican Republic","DZ":"Algeria","EC":"Ecuador","EG":"Egypt","ER":"Eritrea","EH":"Western Sahara","ES":"Spain","EE":"Estonia","ET":"Ethiopia","FI":"Finland","FJ":"Fiji","FK":"Falkland Islands (Malvinas)","FR":"France","FO":"Faroe Islands","FM":"Micronesia, Federated States of","GA":"Gabon","GB":"United Kingdom","GE":"Georgia","GG":"Guernsey","GH":"Ghana","GI":"Gibraltar","GN":"Guinea","GP":"Guadeloupe","GM":"Gambia","GW":"Guinea-Bissau","GQ":"Equatorial Guinea","GR":"Greece","GD":"Grenada","GL":"Greenland","GT":"Guatemala","GF":"French Guiana","GU":"Guam","GY":"Guyana","HK":"Hong Kong","HM":"Heard Island and McDonald Islands","HN":"Honduras","HR":"Croatia","HT":"Haiti","HU":"Hungary","ID":"Indonesia","IM":"Isle of Man","IN":"India","IO":"British Indian Ocean Territory","IE":"Ireland","IR":"Iran","IQ":"Iraq","IS":"Iceland","IL":"Israel","IT":"Italy","JM":"Jamaica","JE":"Jersey","JO":"Jordan","JP":"Japan","KZ":"Kazakhstan","KE":"Kenya","KG":"Kyrgyzstan","KH":"Cambodia","KI":"Kiribati","KN":"Saint Kitts and Nevis","KR":"South Korea","KW":"Kuwait","LA":"Laos","LB":"Lebanon","LR":"Liberia","LY":"Libya","LC":"Saint Lucia","LI":"Liechtenstein","LK":"Sri Lanka","LS":"Lesotho","LT":"Lithuania","LU":"Luxembourg","LV":"Latvia","MO":"Macao","MF":"Saint Martin (French part)","MA":"Morocco","MC":"Monaco","MD":"Moldova","MG":"Madagascar","MV":"Maldives","MX":"Mexico","MH":"Marshall Islands","MK":"North Macedonia","ML":"Mali","MT":"Malta","MM":"Myanmar","ME":"Montenegro","MN":"Mongolia","MP":"Northern Mariana Islands","MZ":"Mozambique","MR":"Mauritania","MS":"Montserrat","MQ":"Martinique","MU":"Mauritius","MW":"Malawi","MY":"Malaysia","YT":"Mayotte","NA":"Namibia","NC":"New Caledonia","NE":"Niger","NF":"Norfolk Island","NG":"Nigeria","NI":"Nicaragua","NU":"Niue","NL":"Netherlands","NO":"Norway","NP":"Nepal","NR":"Nauru","NZ":"New Zealand","OM":"Oman","PK":"Pakistan","PA":"Panama","PN":"Pitcairn","PE":"Peru","PH":"Philippines","PW":"Palau","PG":"Papua New Guinea","PL":"Poland","PR":"Puerto Rico","KP":"North Korea","PT":"Portugal","PY":"Paraguay","PS":"Palestine, State of","PF":"French Polynesia","QA":"Qatar","RE":"Réunion","RO":"Romania","RU":"Russian Federation","RW":"Rwanda","SA":"Saudi Arabia","SD":"Sudan","SN":"Senegal","SG":"Singapore","GS":"South Georgia and the South Sandwich Islands","SH":"Saint Helena, Ascension and Tristan da Cunha","SJ":"Svalbard and Jan Mayen","SB":"Solomon Islands","SL":"Sierra Leone","SV":"El Salvador","SM":"San Marino","SO":"Somalia","PM":"Saint Pierre and Miquelon","RS":"Serbia","SS":"South Sudan","ST":"Sao Tome and Principe","SR":"Suriname","SK":"Slovakia","SI":"Slovenia","SE":"Sweden","SZ":"Eswatini","SX":"Sint Maarten (Dutch part)","SC":"Seychelles","SY":"Syria","TC":"Turks and Caicos Islands","TD":"Chad","TG":"Togo","TH":"Thailand","TJ":"Tajikistan","TK":"Tokelau","TM":"Turkmenistan","TL":"Timor-Leste","TO":"Tonga","TT":"Trinidad and Tobago","TN":"Tunisia","TR":"Türkiye","TV":"Tuvalu","TW":"Taiwan","TZ":"Tanzania","UG":"Uganda","UA":"Ukraine","UM":"United States Minor Outlying Islands","UY":"Uruguay","US":"United States","UZ":"Uzbekistan","VA":"Holy See (Vatican City State)","VC":"Saint Vincent and the Grenadines","VE":"Venezuela","VG":"Virgin Islands, British","VI":"Virgin Islands, U.S.","VN":"Vietnam","VU":"Vanuatu","WF":"Wallis and Futuna","WS":"Samoa","YE":"Yemen","ZA":"South Africa","ZM":"Zambia","ZW":"Zimbabwe"}}''')

# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
FILES = ["alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks",
         "notes", "search_results"]


def load_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def find_file(data_dir, stem):
    for cand in (stem, stem.replace("_", "-"), stem.replace("_", "")):
        for ext in (".jsonl", ".json"):
            p = os.path.join(data_dir, cand + ext)
            if os.path.exists(p):
                return p
    return os.path.join(data_dir, stem + ".jsonl")


def s(v):
    """Normalise a raw cell to a clean string or None."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    v = str(v).strip()
    return v or None


def split_list(v, sep=";"):
    v = s(v)
    if not v:
        return []
    if isinstance(v, list):
        return v
    return [p.strip() for p in v.split(sep) if p.strip()]


# ----------------------------------------------------------------------------
# Name variants (policy name_variants.json); loaded from file if present
# ----------------------------------------------------------------------------
DEFAULT_VARIANTS = """muhammad, mohammed, mohammad, mohamed, muhammed, mohamad, mohd, muhamad
ahmed, ahmad, ahmet
abdul, abdel, abd
abdullah, abdallah, abdulla
abubakar, abubakr, aboubakar, bubakar
ibrahim, ebrahim, ibraheem, brahim
yusuf, yousef, youssef, yousuf, josef, joseph, joe
umar, omar, omer
usman, uthman, othman, osman
hussein, hussain, husain, hossain, hosein
hassan, hasan
ali, aly
faruk, farouk, faruq, farooq, faroq
sulaiman, suleiman, sulayman, suleman, solomon
aminu, amin, ameen
anthony, antony, tony, antonio
robert, rob, robbie, bob, bobby, roberto
william, will, bill, billy, liam, guillermo
richard, rick, ricky, dick, ricardo
james, jim, jimmy, jamie, jaime
john, johnny, jon, jack, juan, jean, johann, johannes
michael, mike, mick, mikey, miguel, michel, michele
daniel, dan, danny, dani
david, dave, davey, davit
christopher, chris, kristopher, cristobal
matthew, matt, mateo, matteo, mathieu
andrew, andy, drew, andres, andrea, andreas
thomas, tom, tommy, tomas, tomasz
joshua, josh
nicholas, nick, nicolas, nicola, nikola, nikolai
alexander, alex, alejandro, alessandro, aleksandr, sasha
peter, pete, pedro, pietro, pierre
paul, pablo, paolo
stephen, steven, steve, stefan, esteban, stefano
joseph, joe, jose, giuseppe, jozef
francis, frank, francisco, francesco, franco, francois
charles, charlie, chuck, carlos, carlo, karl, karol
edward, ed, eddie, ted, eduardo, edoardo
henry, harry, enrique, enrico, henrik, heinrich
mark, marc, marco
markus, marcus, marcos
catherine, katherine, kathryn, kate, katie, cathy, catalina, katarzyna
elizabeth, liz, beth, betty, elisabeth, isabel
margaret, maggie, meg, peggy, margarita
jennifer, jen, jenny
rebecca, becky
susan, sue, susanna, susana
maria, mary, marie, mariya
olumide, mide
oluwaseun, seun
babatunde, tunde
oluwatobiloba, tobi
chukwuemeka, emeka
ifeanyichukwu, ifeanyi
nnamdi, namdi"""
DEFAULT_LEGAL_FORMS = ("ab ag as asa bv co company corp corporation gmbh inc kg limited llc llp lp "
                       "ltd na nv oy oyj plc sa sarl sas se sf sl spa srl").split()

VARIANT_PAIRS = set()
LEGAL_FORMS = set(DEFAULT_LEGAL_FORMS)


def load_variants(data_dir):
    groups = [[w.strip() for w in line.split(",") if w.strip()]
              for line in DEFAULT_VARIANTS.splitlines()]
    legal = list(DEFAULT_LEGAL_FORMS)
    for p in (os.path.join(data_dir, "name_variants.json"),
              os.path.join(data_dir, "..", "name_variants.json")):
        if os.path.exists(p):
            try:
                j = json.load(open(p, encoding="utf-8"))
                g = j.get("given_name_groups") or j.get("groups") or j.get("variants")
                if isinstance(j, list):
                    g = j
                if g:
                    groups = [[norm_text(x) for x in grp] for grp in g]
                lf = j.get("company_legal_forms") or j.get("legal_forms") if isinstance(j, dict) else None
                if lf:
                    legal = [norm_text(x) for x in lf]
            except Exception as e:
                print("warn: could not parse name_variants.json:", e, file=sys.stderr)
            break
    VARIANT_PAIRS.clear()
    for grp in groups:
        for a in grp:
            for b in grp:
                if a != b:
                    VARIANT_PAIRS.add((a, b))
    LEGAL_FORMS.clear()
    LEGAL_FORMS.update(legal)


# ----------------------------------------------------------------------------
# Name matching (principle 8)
# ----------------------------------------------------------------------------
PLACEHOLDERS = {"na", "test", "unknown", "xxx", "xx", "none", "null", "nil", "tbd", "tba",
                "dummy", "sample", "noname", "unk", "nn", "xxxx"}


def strip_accents(t):
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def norm_text(t):
    t = strip_accents(t or "").lower()
    t = t.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("ł", "l").replace("đ", "d")
    return t


def name_parts(name, company=False):
    if not name:
        return []
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}", " ", name)
    t = norm_text(t)
    t = re.sub(r"['’`´]", "", t)
    t = re.sub(r"[^\w]+", " ", t)
    parts, seen = [], set()
    for p in t.split():
        if len(p) < 2:                       # single letters are initials
            continue
        if p in PLACEHOLDERS or any(ch.isdigit() for ch in p) or p == "_" * len(p):
            continue
        if company and p in LEGAL_FORMS:
            continue
        if p not in seen:
            seen.add(p)
            parts.append(p)
    return parts


def lev(a, b, cap):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        best = cur[0]
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            best = min(best, cur[j])
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def part_match(a, b):
    if a == b or (a, b) in VARIANT_PAIRS:
        return True
    n = min(len(a), len(b))
    if n < 4:
        return False
    cap = 1 if n <= 6 else 2
    return lev(a, b, cap) <= cap


def names_agree(pa, pb):
    """pa, pb: lists of name parts. True if names agree under principle 8."""
    if not pa or not pb:
        return False
    # Build candidate units: single parts, plus joined adjacent pairs ("abdul salam" ~ "abdulsalam")
    def units(p):
        u = [((i,), x) for i, x in enumerate(p)]
        u += [((i, i + 1), p[i] + p[i + 1]) for i in range(len(p) - 1)]
        return u
    ua, ub = units(pa), units(pb)
    edges = []
    for ia, xa in ua:
        for ib, xb in ub:
            if len(ia) == 2 and len(ib) == 2:
                continue
            if part_match(xa, xb):
                edges.append((ia, ib))
    # Greedy maximum matching, prefer edges covering more parts
    edges.sort(key=lambda e: -(len(e[0]) + len(e[1])))
    used_a, used_b, matched_units, cov_a, cov_b = set(), set(), 0, set(), set()
    for ia, ib in edges:
        if used_a & set(ia) or used_b & set(ib):
            continue
        used_a |= set(ia); used_b |= set(ib)
        matched_units += 1
    cov_a, cov_b = used_a, used_b
    if matched_units >= 2:
        return True
    # every part of the shorter name matches
    if len(pa) <= len(pb) and len(cov_a) == len(pa):
        return True
    if len(pb) <= len(pa) and len(cov_b) == len(pb):
        return True
    return False


def any_names_agree(names_a, names_b, comp_a=False, comp_b=False):
    for na in names_a:
        pa = name_parts(na, comp_a)
        for nb in names_b:
            if names_agree(pa, name_parts(nb, comp_b)):
                return nb
    return None


# ----------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MON_RE = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"


def parse_date(v):
    """Return (y, m, d) tuple with m/d possibly None, or None."""
    v = s(v)
    if not v:
        return None
    v = v.strip().rstrip(".")
    m = re.fullmatch(r"(\d{4})(?:[-/.](\d{1,2})(?:[-/.](\d{1,2}))?)?(?:[T ].*)?", v)
    if m:
        return (int(m[1]), int(m[2]) if m[2] else None, int(m[3]) if m[3] else None)
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", v)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12:
            return (y, b, a)
        if b > 12:
            return (y, a, b)
        return (y, b, a)  # day-first (UK)
    m = re.fullmatch(MON_RE + r"\s+(\d{1,2}),?\s+(\d{4})", v, re.I)
    if m:
        return (int(m[3]), MONTHS[m[1].lower()[:3]], int(m[2]))
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + MON_RE + r",?\s+(\d{4})", v, re.I)
    if m:
        return (int(m[3]), MONTHS[m[2].lower()[:3]], int(m[1]))
    m = re.fullmatch(MON_RE + r",?\s+(\d{4})", v, re.I)
    if m:
        return (int(m[2]), MONTHS[m[1].lower()[:3]], None)
    m = re.fullmatch(r"(\d{4})", v)
    if m:
        return (int(m[1]), None, None)
    return None


DATE_IN_TEXT = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|"
    r"\b" + MON_RE + r"\s+\d{1,2},?\s+\d{4}\b|\b\d{1,2}\s+" + MON_RE + r",?\s+\d{4}\b", re.I)


def dates_in_text(t):
    out = []
    for m in DATE_IN_TEXT.finditer(t or ""):
        d = parse_date(m.group(0).replace(",", ", ").replace("  ", " "))
        if d is None:
            d = parse_date(m.group(0))
        if d:
            out.append((m.start(), d))
    return out


def fmt_date(d):
    if not d:
        return "?"
    y, m, dd = d
    return f"{y}" + (f"-{m:02d}" if m else "") + (f"-{dd:02d}" if dd else "")


def to_date(d, end=False):
    """Concrete date for comparisons; partial dates go to the start (or end) of period."""
    y, m, dd = d
    if m is None:
        return date(y, 12, 31) if end else date(y, 1, 1)
    if dd is None:
        if end:
            nm = date(y + (m == 12), m % 12 + 1, 1)
            return date.fromordinal(nm.toordinal() - 1)
        return date(y, m, 1)
    try:
        return date(y, m, dd)
    except ValueError:
        return date(y, m, 28)


# ----------------------------------------------------------------------------
# Countries
# ----------------------------------------------------------------------------
DEMONYMS = {
    "american": "US", "british": "GB", "english": "GB", "scottish": "GB", "welsh": "GB",
    "nigerian": "NG", "german": "DE", "spanish": "ES", "french": "FR", "bangladeshi": "BD",
    "italian": "IT", "irish": "IE", "polish": "PL", "indian": "IN", "canadian": "CA",
    "dutch": "NL", "australian": "AU", "kenyan": "KE", "austrian": "AT", "pakistani": "PK",
    "south african": "ZA", "singaporean": "SG", "swedish": "SE", "serbian": "RS",
    "danish": "DK", "portuguese": "PT", "norwegian": "NO", "ghanaian": "GH",
    "brazilian": "BR", "mexican": "MX", "indonesian": "ID", "swiss": "CH", "russian": "RU",
    "chinese": "CN", "japanese": "JP", "ecuadorian": "EC", "thai": "TH", "vietnamese": "VN",
    "panamanian": "PA", "haitian": "HT", "syrian": "SY", "algerian": "DZ", "czech": "CZ",
    "peruvian": "PE", "armenian": "AM", "moroccan": "MA", "hungarian": "HU",
    "romanian": "RO", "lebanese": "LB", "moldovan": "MD", "emirati": "AE",
    "dominican": "DO", "argentine": "AR", "argentinian": "AR", "jamaican": "JM",
    "israeli": "IL", "slovenian": "SI", "colombian": "CO", "finnish": "FI", "greek": "GR",
    "turkish": "TR", "iranian": "IR", "iraqi": "IQ", "afghan": "AF", "ukrainian": "UA",
    "new zealander": "NZ", "montenegrin": "ME", "north korean": "KP", "south korean": "KR",
    "ivorian": "CI", "filipino": "PH", "malaysian": "MY", "egyptian": "EG",
}
ALIASES = {
    "uk": "GB", "great britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "usa": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US",
    "america": "US", "russia": "RU", "iran": "IR", "syria": "SY", "north korea": "KP",
    "south korea": "KR", "korea": "KR", "vietnam": "VN", "palestina": "PS", "palestine": "PS",
    "macao special administrative region of china": "MO", "macao": "MO", "macau": "MO",
    "hong kong": "HK", "czech republic": "CZ", "czechia": "CZ", "cote d'ivoire": "CI",
    "ivory coast": "CI", "moldova": "MD", "kosovo": "XK", "turkey": "TR", "turkiye": "TR",
    "bolivia": "BO", "venezuela": "VE", "tanzania": "TZ", "laos": "LA", "taiwan": "TW",
    "brunei": "BN", "cape verde": "CV", "the netherlands": "NL", "holland": "NL",
    "uae": "AE", "the gambia": "GM", "gambia": "GM", "congo": "CG", "dr congo": "CD",
    "democratic republic of the congo": "CD", "burma": "MM", "myanmar": "MM",
    "british virgin islands": "VG", "us virgin islands": "VI", "swaziland": "SZ",
    "macedonia": "MK", "north macedonia": "MK", "micronesia": "FM", "vatican": "VA",
}
NOT_COUNTRIES = {"international", "europe", "global", "worldwide", "unknown", "n/a", "na", "none"}
_COUNTRY_NAMES = {}  # lowercase name -> code


def _init_countries():
    if _COUNTRY_NAMES:
        return
    for n, code in _ISO["names"].items():
        _COUNTRY_NAMES[norm_text(n)] = code
    for k, v in ALIASES.items():
        _COUNTRY_NAMES[norm_text(k)] = v


def country_code(v):
    _init_countries()
    v = s(v)
    if not v:
        return None
    v = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", v).strip()
    if "," in v:
        v = v.split(",")[-1].strip()
    t = norm_text(v).strip(" .")
    if not t or t in NOT_COUNTRIES:
        return None
    if t in DEMONYMS:
        return DEMONYMS[t]
    if t in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[t]
    if len(t) == 2 and t.isalpha():
        if t == "uk":
            return "GB"
        return t.upper()
    if len(t) == 3 and t.isalpha() and t.upper() in _ISO["a3"]:
        return _ISO["a3"][t.upper()]
    if t.startswith("the "):
        return country_code(t[4:])
    return "?" + t  # unknown but keep as a distinct token


def country_name(code):
    if not code:
        return "?"
    if code.startswith("?"):
        return code[1:].title()
    return _ISO["disp"].get(code, code)


_COUNTRY_TEXT_RE = None


def countries_in_text(t):
    """Find country mentions (names or demonyms) in free text."""
    global _COUNTRY_TEXT_RE
    _init_countries()
    if _COUNTRY_TEXT_RE is None:
        keys = set(k for k in _COUNTRY_NAMES if len(k) > 3) | set(DEMONYMS)
        keys |= {"uk", "usa", "uae"}
        keys = sorted(keys, key=len, reverse=True)
        _COUNTRY_TEXT_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b")
    out = []
    for m in _COUNTRY_TEXT_RE.finditer(norm_text(t or "")):
        c = country_code(m.group(1))
        if c and not c.startswith("?"):
            out.append(c)
    return out


# ----------------------------------------------------------------------------
# The engine
# ----------------------------------------------------------------------------
LISTING_PHRASES = {
    "sanctions": "a sanctioned individual",
    "pep": "a politically exposed person",
    "enforcement": "the subject of enforcement action",
    "adverse media": "named in adverse media",
    "soe": "a state-owned enterprise official",
}
DEFAULT_PHRASE = "named on a watchlist"
REPORT_RE = re.compile(r"^According to [^;\n]+; " + MON_RE + r" (\d{1,2}), (\d{4}):", re.M)


def norm_phone(p):
    p = s(p)
    if not p:
        return None
    d = re.sub(r"\D", "", p)
    return d or None


def norm_email(e):
    e = s(e)
    return e.lower() if e else None


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


class Engine:
    def __init__(self, data_dir):
        load_variants(data_dir)
        D = {k: load_jsonl(find_file(data_dir, k)) for k in FILES}
        self.alerts = D["alerts"]
        self.hits = {h["hit_id"]: h for h in D["hits"]}
        self.cust = {c["record_id"]: c for c in D["customers"]}
        # accounts
        self.acc_by_id = defaultdict(list)
        self.acc_by_login = defaultdict(list)
        self.acc_by_cust = defaultdict(list)
        for a in D["accounts"]:
            self.acc_by_id[a["account_id"]].append(a)
            if s(a.get("login_handle")):
                self.acc_by_login[s(a["login_handle"]).lower()].append(a)
            self.acc_by_cust[a["customer_id"]].append(a)
        self.cust_by_email = defaultdict(list)
        for c in self.cust.values():
            e = norm_email(c.get("email"))
            if e:
                self.cust_by_email[e].append(c["record_id"])
        # onboarding -> applicants per customer
        self.apps_by_cust = defaultdict(list)
        for o in D["onboarding"]:
            self.apps_by_cust[o["customer_id"]].append((o["account_id"], o["kyc_applicant_id"]))
        self.kyc_by_app = defaultdict(list)
        for k in D["kyc_checks"]:
            self.kyc_by_app[k["applicant_id"]].append(k)
        self.notes_by_email = defaultdict(list)
        for n in D["notes"]:
            e = norm_email(n.get("requester_email"))
            if e:
                self.notes_by_email[e].append(n)
        self.search_by_query = defaultdict(list)
        for r in D["search_results"]:
            self.search_by_query[" ".join(sorted(norm_text(s(r.get("query")) or "").split()))].append(r)
        self._build_persons()
        self._build_name_index()

    # ---------------- person merging (principle 3) ----------------
    def kyc_checks_for(self, cid):
        out = []
        for acc, app in self.apps_by_cust.get(cid, []):
            for k in self.kyc_by_app.get(app, []):
                out.append((acc, app, k))
        return out

    def _build_persons(self):
        uf = UF()
        by_phone_dob = defaultdict(list)
        by_doc = defaultdict(list)
        for cid, c in self.cust.items():
            uf.find(cid)
            ph = norm_phone(c.get("phone"))
            d = parse_date(c.get("dob"))
            if ph and d and d[1] and d[2]:
                by_phone_dob[(ph, d)].append(cid)
            for _, _, k in self.kyc_checks_for(cid):
                if (s(k.get("result")) or "").lower() == "approved" and s(k.get("document_number")):
                    by_doc[(s(k["document_number"]).upper())].append(cid)
        for grp in list(by_phone_dob.values()) + list(by_doc.values()):
            for x in grp[1:]:
                uf.union(grp[0], x)
        self.person_of = {cid: uf.find(cid) for cid in self.cust}
        self.members = defaultdict(list)
        for cid, p in self.person_of.items():
            self.members[p].append(cid)

    def _build_name_index(self):
        self.tok_index = defaultdict(set)
        for cid, c in self.cust.items():
            comp = (s(c.get("entity_type")) or "").lower() == "company"
            for f in ("full_name", "preferred_name", "login_name"):
                for p in name_parts(s(c.get(f)), comp):
                    self.tok_index[p[:3]].add(cid)

    # ---------------- KYC notes parsing ----------------
    CAPS_STOP = {"DOB", "ID", "KYC", "UK", "US", "USA", "UAE", "EU"}

    @classmethod
    def caps_name(cls, t):
        """Longest run of ALL-CAPS words (accents allowed) - the name on the document."""
        best, run = [], []
        for m in re.finditer(r"\S+", t):
            raw = m.group(0)
            core = raw.strip(",.;:()\"'")
            core_poss = re.sub(r"['’][sS]$", "", core)
            letters = re.sub(r"[^\w]", "", core_poss)
            is_caps = (core_poss.upper() == core_poss and any(ch.isalpha() for ch in core_poss)
                       and (len(letters) >= 2 or core_poss in ("N/A",)) and core_poss not in cls.CAPS_STOP)
            if is_caps:
                run.append(core_poss)
                if raw[-1] in ",.;:)" or core != core_poss:
                    if len(run) > len(best):
                        best = run
                    run = []
            else:
                if len(run) > len(best):
                    best = run
                run = []
        if len(run) > len(best):
            best = run
        return " ".join(best) or None

    def parse_kyc_note(self, n):
        t = s(n.get("text")) or ""
        if (s(n.get("channel")) or "").lower() != "kyc":
            return None
        if re.search(r"\b(reject|fail|declin|expired|unsuccessful|could not|unable|not (?:been )?(?:verified|approved))", t, re.I):
            return None
        checked = parse_date(s(n.get("created_at")))
        found = dates_in_text(t)
        others = [(pos, d) for pos, d in found if d != checked]
        if checked is None and found:
            checked = max((d for _, d in found), key=to_date)
            others = [(pos, d) for pos, d in found if d != checked]
        dob = None
        if others:
            dob = min((d for _, d in others), key=to_date)
        else:
            m = re.search(r"(?:born|DOB|birth)\D{0,25}?(\d{4})\b", t, re.I)
            if m:
                dob = (int(m.group(1)), None, None)
            elif len(found) >= 2:   # DOB happens to equal the check date - impossible, so ignore
                dob = None
        cs = countries_in_text(t)
        return {"id": n["note_id"], "name": self.caps_name(t), "dob": dob, "checked": checked,
                "doc_country": cs[0] if cs else None}

    # ---------------- person picture (principles 3 & 4) ----------------
    def picture(self, pid):
        recs = sorted(self.members[pid])
        P = {"pid": pid, "records": recs, "countries": {}, "names": [], "dob": None,
             "dob_src": None, "verified_name": None, "verified_src": None, "type": None,
             "doc_country_src": None}
        checks = []
        for cid in recs:
            c = self.cust[cid]
            P["type"] = P["type"] or s(c.get("entity_type"))
            if s(c.get("full_name")):
                P["names"].append(s(c["full_name"]))
            for f in ("nationality", "residence_country"):
                cc = country_code(c.get(f))
                if cc:
                    P["countries"].setdefault(cc, cid)
            for acc, app, k in self.kyc_checks_for(cid):
                if (s(k.get("result")) or "").lower() == "approved":
                    checks.append({"id": k["check_id"], "name": s(k.get("verified_name")),
                                   "dob": parse_date(k.get("verified_dob")),
                                   "checked": parse_date(k.get("checked_at")),
                                   "doc_country": country_code(k.get("document_country"))})
            e = norm_email(c.get("email"))
            for n in self.notes_by_email.get(e, []) if e else []:
                kn = self.parse_kyc_note(n)
                if kn:
                    checks.append(kn)
                elif (s(n.get("channel")) or "").lower() != "kyc":
                    t = s(n.get("text")) or ""
                    if re.search(r"\b(liv|resid|based|home|reside|working|employ)", t, re.I):
                        for cc in countries_in_text(t):
                            P["countries"].setdefault(cc, n["note_id"])
        for k in checks:
            if k.get("doc_country"):
                P["countries"].setdefault(k["doc_country"], k["id"])
        checks = [k for k in checks if k.get("checked")]
        if checks:
            latest = max(checks, key=lambda k: (to_date(k["checked"]), k["id"]))
            P["latest_check"] = latest
            if latest.get("name"):
                P["verified_name"], P["verified_src"] = latest["name"], latest["id"]
            if latest.get("dob"):
                P["dob"], P["dob_src"] = latest["dob"], latest["id"]
            if latest.get("doc_country"):
                P["doc_country_src"] = latest["id"]
        if not P["dob"]:
            for cid in recs:
                d = parse_date(self.cust[cid].get("dob"))
                if d:
                    P["dob"], P["dob_src"] = d, cid
                    break
        return P

    def screened_picture(self, al):
        P = {"pid": None, "records": [], "countries": {}, "names": [s(al.get("customer_name"))],
             "dob": parse_date(al.get("dob")), "dob_src": "screened details" if al.get("dob") else None,
             "verified_name": None, "verified_src": None, "type": s(al.get("entity_type")), "doc_country_src": None}
        cc = country_code(al.get("country"))
        if cc:
            P["countries"][cc] = None
        return P

    # ---------------- customer resolution (principle 2) ----------------
    def fits(self, cid, al):
        c = self.cust[cid]
        comp = (s(al.get("entity_type")) or "").lower() == "company"
        sname = s(al.get("customer_name"))
        if sname:
            sp = name_parts(sname, comp)
            ok = False
            for f in ("full_name", "preferred_name", "login_name"):
                v = s(c.get(f))
                if v and names_agree(sp, name_parts(v, comp)):
                    ok = True
                    break
            if not ok:
                return False
        sd = parse_date(al.get("dob"))
        if sd:
            cd = parse_date(c.get("dob"))
            if not cd:
                return False
            for a, b in zip(sd, cd):
                if a is not None and b is not None and a != b:
                    return False
        sc = country_code(al.get("country"))
        if sc:
            if sc not in {country_code(c.get("nationality")), country_code(c.get("residence_country"))}:
                return False
        city = s(al.get("city"))
        if city:
            ct = norm_text(city)
            if ct not in norm_text(s(c.get("city")) or "") and ct not in norm_text(s(c.get("address")) or ""):
                return False
        return True

    def resolve(self, al):
        """Return (list_of_person_ids, path_text)."""
        cands, path = None, ""
        if s(al.get("account_ref")):
            cands = [a["customer_id"] for a in self.acc_by_id.get(s(al["account_ref"]), [])]
            path = f"account_ref {al['account_ref']}"
        elif s(al.get("login_handle")):
            cands = [a["customer_id"] for a in self.acc_by_login.get(s(al["login_handle"]).lower(), [])]
            path = f"login_handle {al['login_handle']}"
        elif s(al.get("email")):
            cands = list(self.cust_by_email.get(norm_email(al["email"]), []))
            path = f"email {al['email']}"
        if cands is not None:
            cands = [c for c in dict.fromkeys(cands) if c in self.cust]
            persons = list(dict.fromkeys(self.person_of[c] for c in cands))
            if len(persons) > 1:
                fit = [c for c in cands if self.fits(c, al)]
                fp = list(dict.fromkeys(self.person_of[c] for c in fit))
                if fp:
                    persons = fp
                path += " -> several holders; screened details pick"
            return persons, path
        # no link: search
        comp = (s(al.get("entity_type")) or "").lower() == "company"
        sp = name_parts(s(al.get("customer_name")), comp)
        pool = set()
        for p in sp:
            pool |= self.tok_index.get(p[:3], set())
            # tolerate a typo in the first letters
            for k, v in self.tok_index.items():
                if len(p) >= 4 and k[0] == p[0] and k != p[:3] and lev(k, p[:3], 1) <= 1:
                    pool |= v
        if not sp:
            pool = set(self.cust)
        fit = [c for c in pool if self.fits(c, al)]
        persons = list(dict.fromkeys(self.person_of[c] for c in sorted(fit)))
        return persons, "search by name, date of birth, country and city"

    # ---------------- hit facts (principle 5) ----------------
    def hit_names(self, h):
        names = [s(h.get("name"))] if s(h.get("name")) else []
        names += split_list(h.get("aliases"))
        return names

    def hit_countries(self, h):
        out = {}
        for f in ("countries", "nationality", "citizenship"):
            for p in split_list(h.get(f)):
                c = country_code(p)
                if c:
                    out.setdefault(c, f)
        for f in ("addresses", "place_of_birth"):
            for p in split_list(h.get(f)):
                c = country_code(p.split(",")[-1])
                if c:
                    out.setdefault(c, f)
        return out

    def hit_dobs(self, h):
        """Return (list of (y,m,d) candidate dates, source label, evidence ids)."""
        out = []
        for p in split_list(h.get("dobs")):
            d = parse_date(p)
            if d:
                out.append(d)
        src = "listed date of birth" if out else None
        notes = s(h.get("profile_notes")) or ""
        first = re.split(r"\n\s*\n", notes.strip(), maxsplit=1)[0] if notes else ""
        pn = self.dobs_from_text(first, profile=True)
        if pn and not out:
            out, src = pn, "profile notes"
        elif pn:
            out += [d for d in pn if d not in out]
        if out:
            return out, src, []
        # search results
        if (s(h.get("entity_type")) or "").lower() == "company":
            return [], None, []
        cat = (s(h.get("primary_category")) or (split_list(h.get("categories")) or [""])[0]).lower()
        phrase = LISTING_PHRASES.get(cat, DEFAULT_PHRASE)
        hc = set(self.hit_countries(h))
        q = " ".join(sorted(name_parts(s(h.get("name")))))
        res, ev = [], []
        for r in self.search_by_query.get(q, []):
            sn = s(r.get("snippet")) or ""
            if phrase not in sn.lower():
                continue
            if not (set(countries_in_text(sn)) & hc):
                continue
            ys = self.dobs_from_text(sn, profile=False)
            if ys:
                res += [d for d in ys if d not in res]
                ev.append(r["result_id"])
        if res:
            return res, "search results", ev
        return [], None, []

    AGE_PATS = [r"\baged (\d{1,3})\b", r"\bage of (\d{1,3})\b", r"\bat age (\d{1,3})\b",
                r"\b(\d{1,3}) years? of age\b", r"\b(\d{1,3}) years? old\b", r"\bAge: ?(\d{1,3})\b",
                r"\b(\d{1,3})-year-old\b", r"\bage of [^.,;]{1,60}? was (\d{1,3})\b",
                r"\bwas (\d{1,3}) when\b", r"\b(?:he|she|they|who) (?:was|were) (\d{1,3})\b",
                r"\breached (\d{1,3})\b", r"\bwas (\d{1,3})\b(?![,.]?\d)"]
    SNIPPET_AGE_PATS = [r"(?<![\d,.])\b(\d{1,3})[,.](?!\d)", r"\((\d{1,3})\)", r"\bage (\d{1,3})\b",
                        r"\bthen (\d{1,3})\b", r"\bat (\d{1,3})\b(?![,.]?\d)", r"\bwas (\d{1,3})\b",
                        r"(?<![\d$£€])\b(\d{1,3})\b(?![,.]?\d)"]

    def dobs_from_text(self, t, profile):
        if not t:
            return []
        m = re.search(r"\bborn (?:on |in )?([^.;\n]*?\d{4})", t)
        if m:
            d = parse_date(m.group(1).strip())
            if d:
                return [d]
        age = None
        for pat in self.AGE_PATS + ([] if profile else self.SNIPPET_AGE_PATS):
            mm = re.search(pat, t, re.I)
            if mm:
                age = int(mm.group(1))
                break
        if age is None or age < 1 or age > 120:
            return []
        yr = None
        mm = re.search(r"\bas of " + MON_RE + r" \d{1,2},? (\d{4})", t)
        if mm:
            yr = int(mm.group(2))
        if yr is None:
            mm = re.search(MON_RE + r"(?: \d{1,2},?)? (\d{4})\b", t)
            if mm:
                yr = int(mm.group(2))
        if yr is None:
            mm = re.search(r"\b(1[89]\d{2}|20\d{2})\b", t)
            if mm:
                yr = int(mm.group(1))
        if yr is None:
            return []
        return [(yr - age - 1, None, None), (yr - age, None, None)]

    def earliest_report(self, h):
        notes = s(h.get("profile_notes")) or ""
        ds = []
        for m in REPORT_RE.finditer(notes):
            try:
                ds.append(date(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2))))
            except ValueError:
                pass
        return min(ds) if ds else None

    # ---------------- comparisons ----------------
    @staticmethod
    def dob_agree(c, hds):
        if not c:
            return None
        for h in hds:
            if c[0] != h[0]:
                continue
            if h[1] is not None and c[1] is not None and h[1] != c[1]:
                continue
            if h[2] is not None and c[2] is not None and h[2] != c[2]:
                continue
            return h
        return None

    @staticmethod
    def dob_contradicted(c, hds):
        if not c or not hds:
            return False
        for h in hds:
            contra = False
            if abs(c[0] - h[0]) > 1:
                contra = True
            elif c[0] == h[0]:
                if c[1] and h[1] and c[1] != h[1]:
                    contra = True
                elif c[1] and h[1] and c[2] and h[2] and c[2] != h[2]:
                    contra = True
            if not contra:
                return False
        return True

    # ---------------- decision for one person vs one hit ----------------
    def decide_one(self, P, h, al):
        R = lambda dec, code, ev, why: {"decision": dec, "reason_code": code, "evidence": ev, "why": why}
        recs = P["records"]
        ctype = (P.get("type") or s(al.get("entity_type")) or "").lower()
        htype = (s(h.get("entity_type")) or "").lower()
        is_comp = ctype == "company"
        screened_at = parse_date(al.get("screened_at"))
        if ctype and htype and ctype != htype:
            return R("DIFFERENT_ENTITY", "ENTITY_TYPE_MISMATCH", recs[:1],
                     f"The customer is a {ctype} but the hit is a {htype}.")
        dd = parse_date(h.get("deceased_date"))
        if dd and screened_at and to_date(dd, end=True) < to_date(screened_at):
            return R("DIFFERENT_ENTITY", "DECEASED", recs[:1],
                     f"The hit's profile gives a date of death {fmt_date(dd)}, before the customer was screened on {fmt_date(screened_at)}.")
        cdob, dsrc = P["dob"], P["dob_src"]
        er = self.earliest_report(h)
        if er and cdob:
            if is_comp:
                if to_date(cdob) > er:
                    return R("DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", [x for x in [dsrc] if x],
                             f"The company was incorporated {fmt_date(cdob)}, after the hit's earliest report on {er}.")
            else:
                birth_earliest = to_date(cdob)
                max_age = er.year - birth_earliest.year - ((er.month, er.day) < (birth_earliest.month, birth_earliest.day))
                if cdob[1] is None:
                    max_age = er.year - cdob[0]
                if max_age < 16:
                    return R("DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", sorted(set(recs) | {dsrc} - {None}),
                             f"The customer was born {fmt_date(cdob)} ({dsrc}), so they were at most {max_age} when the hit's profile reports activity on {er}.")
        hnames = self.hit_names(h)
        comp_names = is_comp
        cust_names = [P["verified_name"]] if P["verified_name"] else [n for n in P["names"] if n]
        cust_parts_ok = any(len(name_parts(n, comp_names)) >= 2 for n in cust_names) or is_comp
        name_hit = any_names_agree(cust_names, hnames, comp_names, htype == "company")
        if not is_comp and not cust_parts_ok:
            # can be neither confirmed nor cleared on name - but a hit single-part alias may still agree
            name_hit = None
        name_contra = bool(P["verified_name"]) and (len(name_parts(P["verified_name"], comp_names)) >= 2 or is_comp) \
            and not any_names_agree([P["verified_name"]], hnames, comp_names, htype == "company")
        hds, hsrc, sr_ev = self.hit_dobs(h)
        if is_comp:
            hds = [parse_date(p) for p in split_list(h.get("dobs"))]
            hds = [d for d in hds if d]
            hsrc, sr_ev = "listed incorporation date", []
        dob_ok = self.dob_agree(cdob, hds) if hds else None
        dob_contra = self.dob_contradicted(cdob, hds)
        hc = self.hit_countries(h)
        cc = P["countries"]
        overlap = sorted(set(cc) & set(hc))
        loc_contra = bool(cc) and bool(hc) and not overlap
        cnames = ", ".join(sorted(country_name(x) for x in cc))
        hcn = ", ".join(sorted(country_name(x) for x in hc))
        loc_ev = sorted(set(recs) | {v for v in cc.values() if v and not v.startswith("CUS")} | ({P["doc_country_src"]} if P["doc_country_src"] else set()))

        # confirm on full agreement (individuals)
        if not is_comp and name_hit and dob_ok:
            if loc_contra:
                return R("REVIEW", "INSUFFICIENT_DATA", sorted(set(recs) | {dsrc} - {None}) + sr_ev,
                         f"Name and date of birth agree (customer born {fmt_date(cdob)}, hit {name_hit} born {', '.join(fmt_date(d) for d in hds)}), but the customer is linked only to {cnames} while the hit is linked to {hcn}. A country difference alone cannot clear this.")
            code = "NAME_DOB_LOCATION_MATCH" if overlap else "NAME_DOB_MATCH"
            why = f"The customer's date of birth {fmt_date(cdob)} ({dsrc}) agrees with the hit's {', '.join(fmt_date(d) for d in hds)}."
            if overlap:
                why += f" Both are linked to {', '.join(country_name(x) for x in overlap)}."
            why += f" The customer's name agrees with the hit's name {name_hit}."
            return R("SAME_ENTITY", code, sorted(set(recs) | {dsrc} - {None}) + sr_ev, why)
        # contradictions
        if dob_contra:
            return R("DIFFERENT_ENTITY", "DOB_MISMATCH", sorted({dsrc} - {None}) + sr_ev,
                     f"The customer's date of birth is {fmt_date(cdob)} ({dsrc}) but the hit's {hsrc} put it at {', '.join(fmt_date(d) for d in hds)}.")
        if loc_contra:
            return R("DIFFERENT_ENTITY", "LOCATION_MISMATCH", loc_ev,
                     f"The customer is linked only to {cnames} but the hit is linked only to {hcn}.")
        if name_contra:
            return R("DIFFERENT_ENTITY", "NAME_MISMATCH_VERIFIED", [P["verified_src"]],
                     f"The customer's verified name is {P['verified_name']} ({P['verified_src']}), which does not match the hit's name {s(h.get('name'))}.")
        # companies confirm on name + country
        if is_comp and name_hit and overlap:
            return R("SAME_ENTITY", "NAME_LOCATION_MATCH", sorted(set(recs) | ({P["doc_country_src"]} if P["doc_country_src"] else set())),
                     f"Both the customer and the hit are linked to {', '.join(country_name(x) for x in overlap)}. The customer's name agrees with the hit's name {name_hit}.")
        bits = []
        if overlap:
            bits.append(f"Both are linked to {', '.join(country_name(x) for x in overlap)}.")
        if name_hit:
            bits.append(f"The customer's name agrees with the hit's name {name_hit}.")
        if not hds:
            bits.append("The hit gives no date of birth to compare.")
        elif not cdob:
            bits.append("The customer has no date of birth on file.")
        else:
            bits.append(f"The dates of birth neither agree nor contradict ({fmt_date(cdob)} vs {', '.join(fmt_date(d) for d in hds)}).")
        if name_hit is None or (not name_hit):
            bits.append("The names cannot confirm it.")
        ev = sorted(set(recs) | ({dsrc} if dsrc else set()) | ({P["verified_src"]} if P["verified_src"] else set()))
        return R("REVIEW", "INSUFFICIENT_DATA", ev, " ".join(bits) + " Nothing settles it, so a person should look.")

    # ---------------- per alert ----------------
    def run(self):
        out = []
        for al in self.alerts:
            out += self.run_alert(al)
        return out

    def run_alert(self, al):
        out = []
        if True:
            persons, path = self.resolve(al)
            pics = [self.picture(p) for p in persons]
            for hid in split_list(al.get("hit_ids")):
                h = self.hits.get(hid)
                if not h:
                    continue
                if not pics:
                    r = self.decide_one(self.screened_picture(al), h, al)
                    crid = None
                elif len(pics) == 1:
                    r = self.decide_one(pics[0], h, al)
                    crid = pics[0]["records"]
                else:
                    rs = [self.decide_one(P, h, al) for P in pics]
                    crid = "AMBIGUOUS"
                    if len({x["decision"] for x in rs}) == 1:
                        r = dict(rs[0])
                        r["evidence"] = sorted({e for x in rs for e in x["evidence"]})
                        r["why"] = f"{len(pics)} different people fit the alert; all lead to the same decision. " + rs[0]["why"]
                    else:
                        r = {"decision": "REVIEW", "reason_code": "AMBIGUOUS_CUSTOMER_RECORD",
                             "evidence": sorted({rec for P in pics for rec in P["records"]}),
                             "why": f"{len(pics)} different people fit the alert and they lead to different decisions: " +
                                    "; ".join(f"{P['records'][0]} -> {x['decision']}" for P, x in zip(pics, rs))}
                r["evidence"] = [e for e in r["evidence"] if e and e != "screened details"]
                out.append({
                    "hit_id": hid, "alert_id": al["alert_id"], "decision": r["decision"],
                    "reason_code": r["reason_code"],
                    "customer_record_id": crid if isinstance(crid, str) or crid is None else crid[0],
                    "customer_record_ids": crid if isinstance(crid, list) else ([] if crid is None else [crid]),
                    "evidence": [e for e in dict.fromkeys(r["evidence"]) if e],
                    "explanation": r["why"], "resolution_path": path,
                })
        return out


# ----------------------------------------------------------------------------
# Evaluation against practice labels
# ----------------------------------------------------------------------------
def evaluate(preds, labels_path, verbose=True):
    labels = load_jsonl(labels_path)
    P = {p["hit_id"]: p for p in preds}
    ok_dec = ok_code = ok_cust = 0
    rows = []
    for l in labels:
        p = P.get(l["hit_id"])
        if not p:
            continue
        codes = [c.strip() for c in (l.get("reason_codes") or "").split(";") if c.strip()]
        lc = [c.strip() for c in (l.get("customer_record_ids") or "").split(";") if c.strip()]
        d_ok = p["decision"] == l["decision"]
        c_ok = p["reason_code"] in codes
        if lc == ["AMBIGUOUS"]:
            r_ok = p["customer_record_id"] == "AMBIGUOUS"
        elif not lc:
            r_ok = p["customer_record_id"] is None
        else:
            r_ok = p["customer_record_id"] in lc
        ok_dec += d_ok; ok_code += d_ok and c_ok; ok_cust += r_ok
        if not (d_ok and c_ok and r_ok):
            rows.append((l, p, d_ok, c_ok, r_ok))
    n = len(labels)
    print(f"decision {ok_dec}/{n}   decision+reason {ok_code}/{n}   customer {ok_cust}/{n}")
    if verbose:
        for l, p, d_ok, c_ok, r_ok in rows:
            print("-" * 100)
            print(f"{l['hit_id']} {l['alert_id']}  GOLD {l['decision']} [{l['reason_codes']}] cust={l['customer_record_ids']}")
            print(f"            PRED {p['decision']} [{p['reason_code']}] cust={p['customer_record_ids']}  ({'' if d_ok else 'DEC '}{'' if c_ok else 'CODE '}{'' if r_ok else 'CUST'})")
            print("   gold:", l.get("reference_reason", "")[:400])
            print("   pred:", p["explanation"][:400])
    return ok_dec, n


# ----------------------------------------------------------------------------
# Testing one case by hand
# ----------------------------------------------------------------------------
ICON = {"SAME_ENTITY": "🚨 SAME PERSON", "DIFFERENT_ENTITY": "✅ DIFFERENT PERSON", "REVIEW": "🤔 NEEDS A HUMAN"}


def show_case(eng, key):
    """Pretty-print the full reasoning for one alert (A-...) or hit (H-...)."""
    al = None
    if key.startswith("H-"):
        al = next((a for a in eng.alerts if key in split_list(a.get("hit_ids"))), None)
        hit_ids = [key]
    else:
        al = next((a for a in eng.alerts if a["alert_id"] == key), None)
        hit_ids = split_list(al.get("hit_ids")) if al else []
    if not al:
        print("No alert or hit found with id", key)
        return
    print("=" * 78)
    print(f"ALERT {al['alert_id']}  screened {al.get('screened_at')}")
    print(f"  Screened as: {al.get('customer_name')} | {al.get('entity_type')} | dob {al.get('dob') or '-'} | "
          f"{al.get('country') or '-'} {al.get('city') or ''}")
    persons, path = eng.resolve(al)
    print(f"  Found via:   {path}")
    pics = [eng.picture(p) for p in persons]
    if not pics:
        print("  Customer:    no matching customer record - using the screened details only")
    for P in pics:
        print(f"  Customer:    records {', '.join(P['records'])}")
        print(f"     names on file: {', '.join(P['names'])}")
        if P["verified_name"]:
            print(f"     verified name: {P['verified_name']}  ({P['verified_src']})")
        print(f"     date of birth: {fmt_date(P['dob'])}  ({P['dob_src']})")
        print(f"     countries:     {', '.join(country_name(c) + ' (' + str(v) + ')' for c, v in P['countries'].items()) or '-'}")
    preds = {p["hit_id"]: p for p in eng.run_alert(al)}
    for hid in hit_ids:
        h = eng.hits[hid]
        hds, hsrc, sr = eng.hit_dobs(h)
        print("-" * 78)
        print(f"HIT {hid}  ({h.get('primary_category') or h.get('categories')}, match score {h.get('match_score')})")
        print(f"  Name:        {h.get('name')}" + (f"  aka {h.get('aliases')}" if h.get('aliases') else ""))
        print(f"  Born:        {', '.join(fmt_date(d) for d in hds) or 'unknown'}" + (f"  (from {hsrc})" if hsrc else ""))
        print(f"  Countries:   {', '.join(country_name(c) for c in eng.hit_countries(h)) or '-'}")
        r = preds[hid]
        print(f"\n  >>> {ICON[r['decision']]}   [{r['reason_code']}]")
        print(f"      {r['explanation']}")
        print(f"      evidence: {', '.join(r['evidence'])}")
    print("=" * 78)


def list_cases(eng, args):
    import random as _r
    n, filt, rand = 25, [], False
    for x in args:
        if x.isdigit():
            n = int(x)
        elif x.lower() in ("random", "shuffle"):
            rand = True
        else:
            filt.append(x.upper())
    alias = {"SAME": "SAME_ENTITY", "DIFFERENT": "DIFFERENT_ENTITY", "CLEARED": "DIFFERENT_ENTITY",
             "HUMAN": "REVIEW"}
    filt = [alias.get(f, f) for f in filt]
    preds = eng.run()
    rows = [p for p in preds if all(f in (p["decision"], p["reason_code"]) for f in filt)]
    if rand:
        _r.shuffle(rows)
    short = {"SAME_ENTITY": "🚨 SAME ", "DIFFERENT_ENTITY": "✅ DIFF ", "REVIEW": "🤔 HUMAN"}
    print(f"{len(rows)} matching hits" + (f" (showing {min(n, len(rows))})" if len(rows) > n else ""))
    print(f"{'hit':<9} {'verdict':<8} {'reason':<25} {'customer screened as':<26} {'flagged as':<28}")
    print("-" * 100)
    for p in rows[:n]:
        al = next(a for a in eng.alerts if a["alert_id"] == p["alert_id"])
        h = eng.hits[p["hit_id"]]
        print(f"{p['hit_id']:<9} {short[p['decision']]:<8} {p['reason_code']:<25} "
              f"{(s(al.get('customer_name')) or '')[:25]:<26} {(s(h.get('name')) or '')[:28]:<28}")
        print(f"{'':<9} {p['explanation'][:150]}")
    print("-" * 100)
    print("Full evidence for any of these:  python3 screen.py --case <hit id>")


def ask(prompt, default=None):
    v = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return v or default


def try_mode(eng):
    """Type in a customer and a watchlist hit by hand and see the decision."""
    print("Type a customer and a watchlist hit. Leave anything blank if unknown. Ctrl+C to quit.")
    while True:
        print("\nCUSTOMER")
        cname = ask("name", "Jerome Kerviel")
        ctype = ask("Individual or Company", "Individual")
        cdob = ask("date of birth (e.g. 1977-01-11)")
        ccountry = ask("country")
        print("WATCHLIST HIT")
        hname = ask("name", "Kerviel, Jérôme")
        haka = ask("aliases (separate with ;)")
        hdob = ask("date(s) of birth (e.g. 1977 or 1976; 1977)")
        hcountry = ask("country/countries (separate with ;)")
        hnotes = ask("profile text (optional, e.g. 'Charged in May 2010, aged 33.')")
        hdead = ask("date of death (optional)")
        al = {"alert_id": "A-TEST", "screened_at": date.today().isoformat(), "customer_name": cname,
              "entity_type": ctype, "dob": cdob, "country": ccountry}
        h = {"hit_id": "H-TEST", "entity_type": ctype if not hname else ask("hit is Individual or Company", ctype),
             "name": hname, "aliases": haka, "dobs": hdob, "countries": hcountry, "profile_notes": hnotes,
             "deceased_date": hdead, "primary_category": "Sanctions"}
        r = None
        P = eng.screened_picture(al)
        r = eng.decide_one(P, h, al)
        print(f"\n  >>> {ICON[r['decision']]}   [{r['reason_code']}]")
        print(f"      {r['why']}")


DEMOS = [
    # (title, customer {name,type,dob,country}, hit {name,type,aliases,dobs,countries,profile_notes,deceased_date})
    ("Same person - birthday worked out from 'aged 30 in November 1998'",
     ("Elvira Velasco Morillo", "Individual", "1968-03-05", "Spain"),
     ("Velasco Morillo, Elvira", "Individual", "", "", "Spain",
      "Formal charges were brought against Elvira Velasco Morillo, aged 30, in November 1998.", "")),
    ("Same person - spelling variants (Mohammed = Muhammad, Abubakar = Abubakr)",
     ("Mohammed Abubakar", "Individual", "1975-06-01", "Nigeria"),
     ("Muhammad Abubakr", "Individual", "", "1975", "Nigeria", "", "")),
    ("Same person - typo (Kervel vs Kerviel) and accents",
     ("Jerome Kervel", "Individual", "1977-01-11", "France"),
     ("Kerviel, Jérôme", "Individual", "", "1977", "France", "", "")),
    ("Same company - legal form 'SA' ignored",
     ("Pescanova SA", "Company", "", "Spain"),
     ("Pescanova, Sociedad Anónima", "Company", "", "", "Spain", "", "")),
    ("Different person - same as #1 but born 1985",
     ("Elvira Velasco Morillo", "Individual", "1985-03-05", "Spain"),
     ("Velasco Morillo, Elvira", "Individual", "", "", "Spain",
      "Formal charges were brought against Elvira Velasco Morillo, aged 30, in November 1998.", "")),
    ("Different person - same name, different country",
     ("Muhammad Nadeem", "Individual", "1980-02-10", "United Kingdom"),
     ("Muhammad Nadeem", "Individual", "", "", "Pakistan", "", "")),
    ("Different person - customer was 8 when the hit was reported",
     ("Samuel Bernard", "Individual", "2010-04-02", "United Kingdom"),
     ("Bernard, Samuel", "Individual", "", "", "United Kingdom",
      "According to bbc.co.uk; March 10, 2019: Samuel Bernard was charged with fraud.", "")),
    ("Different person - the hit died before screening",
     ("Samuel Bernard", "Individual", "1960-04-02", "United Kingdom"),
     ("Bernard, Samuel", "Individual", "", "", "United Kingdom", "", "2021-08-02")),
    ("Different entity - company vs person",
     ("Starling Ltd", "Company", "", "United Kingdom"),
     ("Starling, John", "Individual", "", "", "United Kingdom", "", "")),
    ("Needs a human - name and country match, no birthday to compare",
     ("Rajesh Kumar", "Individual", "1982-07-19", "India"),
     ("Rajesh Kumar", "Individual", "", "", "India", "", "")),
    ("Needs a human - name + birthday match but country differs (never auto-cleared)",
     ("Rajesh Kumar", "Individual", "1982-07-19", "United Kingdom"),
     ("Rajesh Kumar", "Individual", "", "1982", "India", "", "")),
]


def run_demo(eng, which=None):
    for i, (title, c, hh) in enumerate(DEMOS, 1):
        if which and i not in which:
            continue
        al = {"alert_id": "A-DEMO", "screened_at": date.today().isoformat(), "customer_name": c[0],
              "entity_type": c[1], "dob": c[2], "country": c[3]}
        h = {"hit_id": "H-DEMO", "name": hh[0], "entity_type": hh[1], "aliases": hh[2], "dobs": hh[3],
             "countries": hh[4], "profile_notes": hh[5], "deceased_date": hh[6], "primary_category": "Sanctions"}
        r = eng.decide_one(eng.screened_picture(al), h, al)
        print("=" * 78)
        print(f"#{i}  {title}")
        print(f"  CUSTOMER  {c[0]} ({c[1]})  born {c[2] or '-'}  {c[3] or '-'}")
        print(f"  HIT       {hh[0]} ({hh[1]})  born {hh[3] or '-'}  {hh[4] or '-'}"
              + (f"  died {hh[6]}" if hh[6] else ""))
        if hh[5]:
            print(f"            profile: \"{hh[5]}\"")
        print(f"\n  >>> {ICON[r['decision']]}   [{r['reason_code']}]")
        print(f"      {r['why']}")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dev")
    ap.add_argument("--out", default="predictions.jsonl")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--case", nargs="+", help="show full reasoning for alert ids (A-...) or hit ids (H-...)")
    ap.add_argument("--list", nargs="*", metavar="FILTER",
                    help="list decisions in the terminal, e.g. --list REVIEW 20, --list SAME, --list LOCATION_MISMATCH")
    ap.add_argument("--try", dest="try_", action="store_true", help="type in your own customer + hit")
    ap.add_argument("--demo", nargs="*", type=int, help="run built-in examples (all, or e.g. --demo 1 5 11)")
    a = ap.parse_args()
    if a.demo is not None:
        load_variants(a.data)
        eng = Engine.__new__(Engine)
        eng.search_by_query = {}
        run_demo(eng, set(a.demo) if a.demo else None)
        return
    if a.try_:
        load_variants(a.data)
        eng = Engine.__new__(Engine)
        eng.search_by_query = {}
        try:
            try_mode(eng)
        except (KeyboardInterrupt, EOFError):
            print()
        return
    eng = Engine(a.data)
    if a.case:
        for k in a.case:
            show_case(eng, k)
        return
    if a.list is not None:
        list_cases(eng, a.list)
        return
    preds = eng.run()
    with open(a.out, "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"wrote {len(preds)} decisions to {a.out}:", dict(Counter(p["decision"] for p in preds)))
    lp = find_file(a.data, "practice_labels")
    if a.eval and os.path.exists(lp):
        evaluate(preds, lp, verbose=not a.quiet)


if __name__ == "__main__":
    main()
