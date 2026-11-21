"""Load the data room folder. Tolerant of list fields arriving as JSON arrays, '; '-joined strings, or dicts."""
import json, os


def decode_value(value):
    if isinstance(value, str) and value.strip().startswith(("[", "{")):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
    return value


IDS = {"hits": "hit_id", "alerts": "alert_id", "customers": "record_id",
       "accounts": "account_id", "kyc_checks": "check_id", "notes": "note_id",
       "search_results": "result_id"}
ALIASES = {
    "hits": {"hit_id": ["id"], "name": ["full_name", "names"], "aliases": ["alternate_names"],
             "dobs": ["dob", "date_of_birth", "dates_of_birth"], "countries": ["country"],
             "profile_notes": ["biography", "description"]},
    "customers": {"record_id": ["id", "customer_id"], "full_name": ["name", "names"],
                  "dob": ["date_of_birth", "dobs"], "residence_country": ["country", "countries"]},
    "alerts": {"alert_id": ["id"], "customer_name": ["name", "full_name"],
               "dob": ["date_of_birth"], "hit_ids": ["hits"]},
}


def normalize(row, kind):
    # Only unwrap known record envelopes; arbitrary nested IDs must not become identity links.
    row = {k: decode_value(v) for k, v in row.items()}
    wrappers = (kind.rstrip("s"), "record", "data", "profile") + (("customer", "screened", "screened_customer") if kind == "alerts" else ())
    for wrapper in wrappers:
        nested = row.get(wrapper)
        if isinstance(nested, dict):
            row = dict(nested, **{k: v for k, v in row.items() if k != wrapper})
    aliases = dict(ALIASES.get(kind, {}))
    if kind in IDS:
        aliases.setdefault(IDS[kind], ["id"])
    for key, alternatives in aliases.items():
        if row.get(key) in (None, "", []):
            for alt in alternatives:
                if row.get(alt) not in (None, "", []):
                    row[key] = row[alt]
                    break
    for key in list(row):
        if key.endswith("_id") or key in ("id", "account_ref"):
            row[key] = as_text(row[key])
    return row


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            out.append(value)
                    except json.JSONDecodeError:
                        pass
    except (OSError, UnicodeError):
        pass  # The runner separately marks this source unavailable for clearing.
    return out


def as_text(v):
    v = decode_value(v)
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "; ".join(as_text(x) for x in v if as_text(x))
    if isinstance(v, dict):
        return ", ".join(as_text(x) for x in v.values() if as_text(x))
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def as_list(v):
    """Normalise to a list of strings."""
    v = decode_value(v)
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out.extend(as_list(x) if isinstance(x, (list, tuple)) else ([as_text(x)] if as_text(x) else []))
        return out
    if isinstance(v, dict):
        t = as_text(v)
        return [t] if t else []
    s = as_text(v)
    if not s:
        return []
    return [p.strip() for p in s.split(";") if p.strip()]


def as_dict_list(v):
    """List of raw items (dicts kept) - used for addresses that may be structured."""
    v = decode_value(v)
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return [v]
    return as_list(v)


DEFAULT_GROUPS_NOTE = "embedded fallback used only if name_variants.json is missing"


def load_name_variants(folder):
    path = os.path.join(folder, "name_variants.json")
    groups, forms = [], []
    if os.path.exists(path):
        try:
            nv = json.load(open(path, encoding="utf-8-sig"))
        except Exception:
            nv = None

        def walk(x, key=""):
            if isinstance(x, dict):
                for k, v in x.items():
                    walk(v, k)
            elif isinstance(x, list):
                if all(isinstance(e, str) for e in x):
                    if "legal" in key.lower() or "form" in key.lower() or "compan" in key.lower():
                        forms.extend(x)
                    else:
                        groups.append(list(x))
                else:
                    for e in x:
                        walk(e, key)
            elif isinstance(x, str) and ("legal" in key.lower() or "form" in key.lower()):
                forms.extend([p.strip() for p in x.split(",") if p.strip()])
        if nv is not None:
            if isinstance(nv, dict):
                # dict of canonical -> variants
                for k, v in nv.items():
                    if isinstance(v, list) and all(isinstance(e, str) for e in v) and not (
                            "legal" in k.lower() or "form" in k.lower() or "compan" in k.lower() or "given" in k.lower() or "group" in k.lower() or "name" in k.lower()):
                        groups.append([k] + list(v))
                    else:
                        walk(v, k)
            else:
                walk(nv)
    if not forms:
        forms = "ab ag as asa bv co company corp corporation gmbh inc kg limited llc llp lp ltd na nv oy oyj plc sa sarl sas se sf sl spa srl".split()
    return groups, forms


class DataRoom:
    def __init__(self, folder):
        self.folder = folder
        j = lambda n: [normalize(r, n) for r in read_jsonl(os.path.join(folder, n + ".jsonl"))]
        self.alerts = j("alerts")
        self.hits = j("hits")
        self.customers = {c["record_id"]: c for c in j("customers") if c.get("record_id")}
        self.accounts = j("accounts")
        self.onboarding = j("onboarding")
        self.kyc = j("kyc_checks")
        self.notes = j("notes")
        self.search = j("search_results")
        self.groups, self.legal_forms = load_name_variants(folder)

