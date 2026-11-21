"""Leave-one-component-out check: disable one parsing component at a time (monkeypatch, no system edits),
rerun on a data folder, report which practice-labelled and which other decisions change.
usage: python3 tools/ablate.py <data folder> [labels.jsonl]"""
import sys, os, json, re, importlib, io, contextlib
SYS = os.path.join(os.path.dirname(__file__), "..", "system")
sys.path.insert(0, SYS)
os.environ.setdefault("PYTHONHASHSEED", "0")

def fresh():
    for m in ["screen", "decide", "hitfacts", "profile", "resolve", "textutil", "countries", "data"]:
        sys.modules.pop(m, None)
    import textutil, countries, data, resolve, profile, hitfacts, decide, screen
    return dict(textutil=textutil, countries=countries, profile=profile, hitfacts=hitfacts, decide=decide, screen=screen, resolve=resolve)

def run(folder, patch):
    M = fresh()
    if patch:
        patch(M)
    out = "/tmp/_abl.jsonl"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        M["screen"].run(folder, out)
    return {json.loads(l)["hit_id"]: json.loads(l) for l in open(out)}

def p_no_age_notes(M):
    hf = M["hitfacts"]; orig = hf.years_from_age
    hf.years_from_age = lambda text, weak=False: orig(text, weak) if weak else []
def p_no_search(M):
    M["screen"].build_search_index = lambda rows: {}
def p_no_reports(M):
    M["hitfacts"]._REPORT_RE = re.compile(r"(?!x)x")
def p_no_born_notes(M):
    hf = M["hitfacts"]; hf._BORN_RE_orig = hf._BORN_RE
    # only affects first-paragraph + search 'born' reads
    hf._BORN_RE = re.compile(r"(?!x)x")
def p_no_kyc_notes(M):
    pr = M["profile"]; orig = pr.parse_id_note; cit = pr.countries_in_text
    idtexts = set()
    def f(n):
        if orig(n) is not None:
            idtexts.add(pr.as_text(n.get("text")))
        return None
    pr.parse_id_note = f
    pr.countries_in_text = lambda t: [] if t in idtexts else cit(t)
def p_no_residence_notes(M):
    pr = M["profile"]; orig = pr.countries_in_text
    pr.countries_in_text = lambda t: []
def p_no_title_runs(M):
    pr = M["profile"]; orig = pr.parse_id_note
    def f(n):
        r = orig(n)
        if r is not None:
            r["title_runs"] = []
        return r
    pr.parse_id_note = f
def p_no_variants(M):
    T = M["textutil"].NameMatcher; init = T.__init__
    T.__init__ = lambda self, g, lf: init(self, [], lf)
def p_no_fuzzy(M):
    M["textutil"].lev = lambda a, b, cap=3: 0 if a == b else 9
def p_no_hit_text_country(M):
    M["hitfacts"].countries_in_text = lambda t: []
def p_no_demonyms(M):
    c = M["countries"]
    for name in ("LOOKUP",):
        if hasattr(c, name):
            d = getattr(c, name)
            for k in [k for k in d if k.endswith(("ian", "ish", "ese", "an", "i"))]:
                pass

ABL = [("age-sentence DOBs in first paragraph (strong cues)", p_no_age_notes),
       ("search-result DOBs", p_no_search),
       ("dated-report regex 'According to …; <date>:'", p_no_reports),
       ("'born …' cue regex (notes + snippets)", p_no_born_notes),
       ("free-text KYC note parsing", p_no_kyc_notes),
       ("country mentions in customer notes", p_no_residence_notes),
       ("title-case/lower-case name fallback in KYC notes", p_no_title_runs),
       ("given-name variant groups", p_no_variants),
       ("edit-distance name matching", p_no_fuzzy),
       ("country names inside hit free-text fields", p_no_hit_text_country)]

if __name__ == "__main__":
    folder = sys.argv[1]
    labels = {}
    lp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(folder, "practice_labels.jsonl")
    if os.path.exists(lp):
        for l in open(lp):
            r = json.loads(l); labels[r["hit_id"]] = r
    base = run(folder, None)
    for name, p in ABL:
        try:
            alt = run(folder, p)
        except Exception as e:
            print(f"## {name}: patch failed {e!r}", flush=True); continue
        ch = [h for h in base if alt[h]["decision"] != base[h]["decision"]]
        lab = [h for h in ch if h in labels]
        toward = {}
        for h in ch:
            k = f"{base[h]['decision'][:4]}->{alt[h]['decision'][:4]}"
            toward[k] = toward.get(k, 0) + 1
        print(flush=True, *[f"## {name}: {len(ch)} decisions change {toward}; practice labels affected {len(lab)}: " +
              ", ".join(f"{h}({labels[h]['decision'][:4]}:{labels[h]['reason_codes'][0]}->{alt[h]['decision'][:4]})" for h in lab)])
