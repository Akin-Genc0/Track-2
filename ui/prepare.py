#!/usr/bin/env python3
"""Build a compact analyst-review bundle from /workspace/track2.

Does not modify anything inside track2/. Safe to re-run; overwrites
track2_ui/data/bundle.json and track2_ui/data/meta.json only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TRACK2 = Path("/workspace/track2")
OUT_DIR = HERE / "data"

REASON_CODES = {
    "TEMPORAL_IMPOSSIBILITY": {
        "decision": "DIFFERENT_ENTITY",
        "when": "The customer could not have done what the hit's profile reports: too young, or not yet incorporated, at the earliest dated report",
    },
    "DOB_MISMATCH": {
        "decision": "DIFFERENT_ENTITY",
        "when": "The customer's date of birth (or a company's incorporation date) contradicts every birth date the hit gives",
    },
    "LOCATION_MISMATCH": {
        "decision": "DIFFERENT_ENTITY",
        "when": "Every country tied to the customer differs from every country tied to the hit",
    },
    "NAME_MISMATCH_VERIFIED": {
        "decision": "DIFFERENT_ENTITY",
        "when": "The customer's verified legal name does not agree with any of the hit's names",
    },
    "ENTITY_TYPE_MISMATCH": {
        "decision": "DIFFERENT_ENTITY",
        "when": "One is a person and the other a company",
    },
    "DECEASED": {
        "decision": "DIFFERENT_ENTITY",
        "when": "The hit's profile gives a date of death before the customer was screened",
    },
    "NAME_DOB_LOCATION_MATCH": {
        "decision": "SAME_ENTITY",
        "when": "Name, date of birth and country all agree and nothing contradicts them",
    },
    "NAME_DOB_MATCH": {
        "decision": "SAME_ENTITY",
        "when": "Name and date of birth agree and nothing contradicts them",
    },
    "NAME_LOCATION_MATCH": {
        "decision": "SAME_ENTITY",
        "when": "Companies only: name and country agree and nothing contradicts them",
    },
    "INSUFFICIENT_DATA": {
        "decision": "REVIEW",
        "when": "Nothing settles it: no contradiction, and not enough agreement to confirm",
    },
    "AMBIGUOUS_CUSTOMER_RECORD": {
        "decision": "REVIEW",
        "when": "More than one person in the system of record fits the alert and they lead to different decisions",
    },
}

COST = {
    "DIFFERENT_ENTITY": {"DIFFERENT_ENTITY": 0, "SAME_ENTITY": 3, "REVIEW": 3},
    "SAME_ENTITY": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 0, "REVIEW": 2},
    "REVIEW": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 2, "REVIEW": 0},
}


def load_jsonl(path: Path) -> list:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_jsonl_map(path: Path, key: str) -> dict:
    return {row[key]: row for row in load_jsonl(path)}


def fold(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.casefold().strip()


def name_tokens(s: str) -> list[str]:
    s = fold(s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return [t for t in s.split() if t and t not in {"aka", "n", "a"}]


def tokens_overlap(a: str, b: str, variants: dict[str, str] | None = None) -> int:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0
    def canon(t: str) -> str:
        return variants.get(t, t) if variants else t
    sb = set(canon(t) for t in tb)
    return sum(1 for t in ta if canon(t) in sb)


def parse_date_parts(value) -> dict | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return {"y": int(m.group(1)), "m": int(m.group(2)), "d": int(m.group(3)), "raw": s}
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        return {"y": int(m.group(1)), "m": int(m.group(2)), "d": None, "raw": s}
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return {"y": int(m.group(1)), "m": None, "d": None, "raw": s}
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return {"y": int(m.group(3)), "m": int(m.group(2)), "d": int(m.group(1)), "raw": s}
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return {"y": int(m.group(3)), "m": int(m.group(2)), "d": int(m.group(1)), "raw": s}
    return {"y": None, "m": None, "d": None, "raw": s}


def dob_agrees(cust, hit) -> bool:
    if not cust or not hit or cust.get("y") is None or hit.get("y") is None:
        return False
    if cust["y"] not in {hit["y"] - 1, hit["y"], hit["y"] + 1} and cust["y"] != hit["y"]:
        # policy confirm: customer's year is one of the hit's possible years
        # "possible years" for a stated year Y includes only Y for field dates
        # (age-at-date in notes can be Y or Y-1; we are not parsing notes here)
        if cust["y"] != hit["y"]:
            return False
    if cust["y"] != hit["y"]:
        return False
    if cust.get("m") and hit.get("m") and cust["m"] != hit["m"]:
        return False
    if cust.get("d") and hit.get("d") and cust["d"] != hit["d"]:
        return False
    return True


def country_bundle(track2: Path) -> dict:
    sys.path.insert(0, str(track2 / "system"))
    try:
        from countries import LOOKUP, CODES, NOT_COUNTRIES  # type: ignore
        lookup = dict(LOOKUP)
        codes = {k.lower(): v for k, v in CODES.items()}
        return {
            "lookup": {**{k.lower(): v for k, v in lookup.items()}, **codes},
            "not_countries": sorted(NOT_COUNTRIES),
        }
    except Exception:
        return {"lookup": {"gb": "United Kingdom", "uk": "United Kingdom", "us": "United States", "usa": "United States"}, "not_countries": ["international", "europe"]}


def variant_index(name_variants: dict) -> dict[str, str]:
    idx = {}
    for group in name_variants.get("given_names") or []:
        if not group:
            continue
        canon = fold(group[0])
        for n in group:
            idx[fold(n)] = canon
    return idx


def load_predictions(path: Path) -> tuple[list, bool]:
    if not path.exists() or path.stat().st_size == 0:
        return [], False
    rows = load_jsonl(path)
    return rows, True


def sample_from_labels(labels: list[dict]) -> list[dict]:
    out = []
    for lab in labels:
        codes = lab.get("reason_codes") or []
        ids = lab.get("customer_record_ids") or []
        if "AMBIGUOUS_CUSTOMER_RECORD" in codes:
            cust = "AMBIGUOUS"
        elif not ids:
            cust = None
        else:
            cust = ids[0]
        out.append({
            "hit_id": lab["hit_id"],
            "alert_id": lab["alert_id"],
            "decision": lab["decision"],
            "reason_code": codes[0] if codes else "INSUFFICIENT_DATA",
            "customer_record_id": cust,
            "reason": lab.get("reference_reason") or "",
            "evidence": list(lab.get("evidence") or []),
            "_sample": True,
            "_sample_source": "practice_labels",
        })
    return out


def score_predictions(preds: list[dict], labels_by_hit: dict) -> dict:
    scored = 0
    cost = 0
    baseline = 0
    unsafe = 0
    by = {"DIFFERENT_ENTITY": 0, "SAME_ENTITY": 0, "REVIEW": 0}
    conf = defaultdict(int)
    for p in preds:
        lab = labels_by_hit.get(p["hit_id"])
        if not lab:
            continue
        gold = lab["decision"]
        pred = p.get("decision")
        if pred not in COST or gold not in COST:
            continue
        scored += 1
        cost += COST[gold][pred]
        baseline += COST[gold]["REVIEW"]
        by[pred] = by.get(pred, 0) + 0
        conf[f"{gold}>{pred}"] += 1
        if pred == "DIFFERENT_ENTITY" and gold in {"SAME_ENTITY", "REVIEW"}:
            unsafe += 1
    if baseline <= 0:
        decision_score = None
    else:
        decision_score = max(0.0, 1.0 - (cost / baseline))
    return {
        "labeled": scored,
        "cost": cost,
        "baseline_review_cost": baseline,
        "decision_score": decision_score,
        "unsafe_clearances": unsafe,
        "confusion": dict(conf),
    }


def build(track2: Path, out_dir: Path, predictions_only: bool = False) -> Path:
    dev = track2 / "dev" if (track2 / "dev").exists() else track2 / "data" / "dev"
    output_path = track2 / "output" / "dev.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / "bundle.json"

    if predictions_only and bundle_path.exists():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        preds, live = load_predictions(output_path)
        if live:
            bundle["predictions"] = {p["hit_id"]: p for p in preds if "hit_id" in p}
            bundle["meta"]["sample_predictions"] = False
            bundle["meta"]["prediction_source"] = str(output_path)
            bundle["meta"]["n_predictions"] = len(bundle["predictions"])
        bundle["meta"]["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if output_path.exists():
            bundle["meta"]["output_mtime"] = output_path.stat().st_mtime
        labels = list(bundle.get("labels", {}).values())
        bundle["meta"]["practice_score"] = score_predictions(list(bundle["predictions"].values()), bundle.get("labels", {}))
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (out_dir / "meta.json").write_text(json.dumps(bundle["meta"], indent=2), encoding="utf-8")
        return bundle_path

    print("Loading dev files…", flush=True)
    hits = load_jsonl(dev / "hits.jsonl")
    alerts = load_jsonl(dev / "alerts.jsonl")
    customers = load_jsonl(dev / "customers.jsonl")
    accounts = load_jsonl(dev / "accounts.jsonl")
    onboarding = load_jsonl(dev / "onboarding.jsonl")
    kyc_checks = load_jsonl(dev / "kyc_checks.jsonl")
    notes = load_jsonl(dev / "notes.jsonl")
    search_results = load_jsonl(dev / "search_results.jsonl")
    labels = load_jsonl(dev / "practice_labels.jsonl")
    name_variants = json.loads((dev / "name_variants.json").read_text(encoding="utf-8"))
    vidx = variant_index(name_variants)

    hits_by = {h["hit_id"]: h for h in hits}
    alerts_by = {a["alert_id"]: a for a in alerts}
    cust_by = {c["record_id"]: c for c in customers}
    acct_by = {a["account_id"]: a for a in accounts}
    kyc_by = {k["check_id"]: k for k in kyc_checks}
    notes_by = {n["note_id"]: n for n in notes}
    search_by = {s["result_id"]: s for s in search_results}
    labels_by = {l["hit_id"]: l for l in labels}

    accounts_by_login = defaultdict(list)
    accounts_by_customer = defaultdict(list)
    accounts_by_phone = defaultdict(list)
    for a in accounts:
        if a.get("login_handle"):
            accounts_by_login[fold(a["login_handle"])].append(a["account_id"])
        if a.get("customer_id"):
            accounts_by_customer[a["customer_id"]].append(a["account_id"])
        if a.get("phone"):
            accounts_by_phone[re.sub(r"\s+", "", a["phone"])].append(a["account_id"])

    cust_by_email = defaultdict(list)
    cust_by_name = defaultdict(list)
    for c in customers:
        if c.get("email"):
            cust_by_email[fold(c["email"])].append(c["record_id"])
        key = " ".join(sorted(name_tokens(c.get("full_name") or "")))
        if key:
            cust_by_name[key].append(c["record_id"])
        pref = " ".join(sorted(name_tokens(c.get("preferred_name") or "")))
        if pref:
            cust_by_name[pref].append(c["record_id"])
        login = " ".join(sorted(name_tokens(c.get("login_name") or "")))
        if login:
            cust_by_name[login].append(c["record_id"])

    onb_by_account = defaultdict(list)
    onb_by_customer = defaultdict(list)
    onb_by_applicant = defaultdict(list)
    for o in onboarding:
        onb_by_account[o.get("account_id")].append(o)
        onb_by_customer[o.get("customer_id")].append(o)
        onb_by_applicant[o.get("kyc_applicant_id")].append(o)

    notes_by_email = defaultdict(list)
    for n in notes:
        em = fold(n.get("requester_email") or "")
        if em:
            notes_by_email[em].append(n["note_id"])

    kyc_by_applicant = defaultdict(list)
    approved_doc_to_applicants = defaultdict(set)
    for k in kyc_checks:
        kyc_by_applicant[k.get("applicant_id")].append(k)
        if (k.get("result") or "").lower() == "approved" and k.get("document_number"):
            approved_doc_to_applicants[fold(k["document_number"])].add(k.get("applicant_id"))

    # person clustering: phone + full DOB, and approved document numbers
    def full_dob_key(c):
        p = parse_date_parts(c.get("dob"))
        if p and p.get("y") and p.get("m") and p.get("d"):
            return f"{p['y']:04d}-{p['m']:02d}-{p['d']:02d}"
        return None

    phone_dob_index = defaultdict(set)  # (phone, dob) -> customer ids
    for a in accounts:
        cid = a.get("customer_id")
        c = cust_by.get(cid)
        if not c:
            continue
        dk = full_dob_key(c)
        phone = re.sub(r"\s+", "", a.get("phone") or "") or re.sub(r"\s+", "", c.get("phone") or "")
        if phone and dk:
            phone_dob_index[(phone, dk)].add(cid)
    for c in customers:
        dk = full_dob_key(c)
        phone = re.sub(r"\s+", "", c.get("phone") or "")
        if phone and dk:
            phone_dob_index[(phone, dk)].add(c["record_id"])

    applicant_to_customers = defaultdict(set)
    for o in onboarding:
        if o.get("kyc_applicant_id") and o.get("customer_id"):
            applicant_to_customers[o["kyc_applicant_id"]].add(o["customer_id"])

    def expand_person(seed_ids: set[str]) -> set[str]:
        group = set(seed_ids)
        changed = True
        while changed:
            changed = False
            extra = set()
            for cid in group:
                c = cust_by.get(cid)
                if not c:
                    continue
                dk = full_dob_key(c)
                phones = set()
                if c.get("phone"):
                    phones.add(re.sub(r"\s+", "", c["phone"]))
                for aid in accounts_by_customer.get(cid, []):
                    ph = acct_by[aid].get("phone")
                    if ph:
                        phones.add(re.sub(r"\s+", "", ph))
                if dk:
                    for ph in phones:
                        extra |= phone_dob_index.get((ph, dk), set())
                # approved document numbers
                for o in onb_by_customer.get(cid, []):
                    app = o.get("kyc_applicant_id")
                    for k in kyc_by_applicant.get(app, []):
                        if (k.get("result") or "").lower() == "approved" and k.get("document_number"):
                            for other_app in approved_doc_to_applicants.get(fold(k["document_number"]), set()):
                                extra |= applicant_to_customers.get(other_app, set())
            if extra - group:
                group |= extra
                changed = True
        return group

    def screened_fits(c: dict, alert: dict) -> bool:
        """Loose gate: name overlap, and DOB if both present."""
        names = [c.get("full_name"), c.get("preferred_name"), c.get("login_name")]
        overlap = max((tokens_overlap(alert.get("customer_name") or "", n or "", vidx) for n in names), default=0)
        screened_parts = name_tokens(alert.get("customer_name") or "")
        if len(screened_parts) >= 2 and overlap < 1:
            return False
        if alert.get("dob") and c.get("dob"):
            a = parse_date_parts(alert["dob"])
            b = parse_date_parts(c["dob"])
            if a and b and a.get("y") and b.get("y") and not dob_agrees(b, a) and not dob_agrees(a, b):
                # allow year±1? policy says screened DOB must be equal in every part both give
                if a.get("y") != b.get("y"):
                    return False
                if a.get("m") and b.get("m") and a["m"] != b["m"]:
                    return False
                if a.get("d") and b.get("d") and a["d"] != b["d"]:
                    return False
        return True

    print("Resolving candidate customers for each alert…", flush=True)
    needed_customers: set[str] = set()
    needed_accounts: set[str] = set()
    needed_kyc: set[str] = set()
    needed_notes: set[str] = set()
    needed_search: set[str] = set()
    needed_onboarding: list[dict] = []
    seen_onb = set()

    cases = []

    def add_onb_for(cids: set[str], aids: set[str]):
        for cid in cids:
            for o in onb_by_customer.get(cid, []):
                key = (o.get("account_id"), o.get("customer_id"), o.get("kyc_applicant_id"))
                if key not in seen_onb:
                    seen_onb.add(key)
                    needed_onboarding.append(o)
                if o.get("account_id"):
                    aids.add(o["account_id"])
        for aid in list(aids):
            for o in onb_by_account.get(aid, []):
                key = (o.get("account_id"), o.get("customer_id"), o.get("kyc_applicant_id"))
                if key not in seen_onb:
                    seen_onb.add(key)
                    needed_onboarding.append(o)

    # Always include label / prediction cited IDs later
    for alert in alerts:
        seeds = set()
        aids = set()
        if alert.get("account_ref") and alert["account_ref"] in acct_by:
            aids.add(alert["account_ref"])
            cid = acct_by[alert["account_ref"]].get("customer_id")
            if cid:
                seeds.add(cid)
            # joint holders of the same account_id? schema is 1 customer per account row;
            # multiple rows can share account_id? Unlikely given unique map. Check same account.
        if alert.get("login_handle"):
            for aid in accounts_by_login.get(fold(alert["login_handle"]), []):
                aids.add(aid)
                cid = acct_by[aid].get("customer_id")
                if cid:
                    seeds.add(cid)
        if alert.get("email"):
            for cid in cust_by_email.get(fold(alert["email"]), []):
                seeds.add(cid)
        unlinked_search = False
        if not seeds:
            unlinked_search = True
            key = " ".join(sorted(name_tokens(alert.get("customer_name") or "")))
            cands = list(dict.fromkeys(cust_by_name.get(key, [])))
            # also try unsorted original order key variants already handled via sorted tokens
            fitted = [cid for cid in cands if screened_fits(cust_by[cid], alert)]
            if len(fitted) > 12:
                fitted = fitted[:12]
            seeds.update(fitted)

        # If a link produced multiple people, filter by screened details when possible
        if seeds and (alert.get("account_ref") or alert.get("login_handle") or alert.get("email")):
            fitted = [cid for cid in seeds if screened_fits(cust_by.get(cid, {}), alert)]
            if fitted:
                # keep both? policy: screened details pick between them. Keep all seeds but mark fitted.
                pass

        people = []
        remaining = set(seeds)
        while remaining:
            cid = next(iter(remaining))
            group = expand_person({cid})
            people.append(sorted(group))
            remaining -= group

        candidate_ids = sorted({cid for g in people for cid in g})
        for cid in candidate_ids:
            needed_customers.add(cid)
            for aid in accounts_by_customer.get(cid, []):
                aids.add(aid)
        if alert.get("account_ref"):
            aids.add(alert["account_ref"])
        needed_accounts |= aids
        add_onb_for(set(candidate_ids), aids)

        kyc_ids = []
        for o in needed_onboarding:
            if o.get("customer_id") in set(candidate_ids) or o.get("account_id") in aids:
                for k in kyc_by_applicant.get(o.get("kyc_applicant_id"), []):
                    kyc_ids.append(k["check_id"])
                    needed_kyc.add(k["check_id"])
        kyc_ids = sorted(set(kyc_ids))

        note_ids = []
        emails = set()
        if alert.get("email"):
            emails.add(fold(alert["email"]))
        for cid in candidate_ids:
            em = (cust_by.get(cid) or {}).get("email")
            if em:
                emails.add(fold(em))
        for em in emails:
            for nid in notes_by_email.get(em, []):
                note_ids.append(nid)
                needed_notes.add(nid)
        note_ids = sorted(set(note_ids))

        cases.append({
            "alert_id": alert["alert_id"],
            "candidate_customer_ids": candidate_ids,
            "person_groups": people,
            "account_ids": sorted(aids),
            "kyc_ids": kyc_ids,
            "note_ids": note_ids,
            "search_ids": [],
            "unlinked_name_search": unlinked_search,
        })

    cases_by_alert = {c["alert_id"]: c for c in cases}

    # Cited IDs from labels (and later predictions)
    def ingest_cited(ids):
        for i in ids or []:
            if not i:
                continue
            if i in cust_by:
                needed_customers.add(i)
            elif i in acct_by:
                needed_accounts.add(i)
            elif i in kyc_by:
                needed_kyc.add(i)
            elif i in notes_by:
                needed_notes.add(i)
            elif i in search_by:
                needed_search.add(i)

    for lab in labels:
        ingest_cited(lab.get("evidence"))
        ingest_cited(lab.get("customer_record_ids"))
        # ensure those customers sit on the case
        case = cases_by_alert.get(lab.get("alert_id"))
        if case:
            for cid in lab.get("customer_record_ids") or []:
                if cid in cust_by and cid not in case["candidate_customer_ids"]:
                    case["candidate_customer_ids"].append(cid)
                    needed_customers.add(cid)

    # Search results: cited plus a few whose query matches the hit name
    print("Selecting search results…", flush=True)
    search_by_query_tokens = []
    for s in search_results:
        qtok = tuple(name_tokens(s.get("query") or ""))
        search_by_query_tokens.append((qtok, s["result_id"]))

    # group by exact folded query
    by_query = defaultdict(list)
    for s in search_results:
        by_query[fold(s.get("query") or "")].append(s["result_id"])

    for h in hits:
        names = [h.get("name") or ""] + list(h.get("aliases") or [])
        sids = []
        for nm in names:
            sids.extend(by_query.get(fold(nm), []))
            # try without comma reorder
            parts = [p.strip() for p in (nm or "").replace(" (AKA)", "").split(",") if p.strip()]
            if len(parts) == 2:
                sids.extend(by_query.get(fold(f"{parts[1]} {parts[0]}"), []))
                sids.extend(by_query.get(fold(f"{parts[0]} {parts[1]}"), []))
        # unique, cap
        seen = []
        for sid in sids:
            if sid not in seen:
                seen.append(sid)
            if len(seen) >= 6:
                break
        needed_search.update(seen)
        case = cases_by_alert.get(h.get("alert_id"))
        if case:
            for sid in seen:
                if sid not in case["search_ids"]:
                    case["search_ids"].append(sid)

    preds, live = load_predictions(output_path)
    sample = not live
    if sample:
        preds = sample_from_labels(labels)
        source = "sample:practice_labels"
    else:
        source = str(output_path)
        for p in preds:
            ingest_cited(p.get("evidence") if isinstance(p.get("evidence"), list) else [])
            cid = p.get("customer_record_id")
            if cid and cid in cust_by:
                needed_customers.add(cid)
                case = cases_by_alert.get(p.get("alert_id"))
                if case and cid not in case["candidate_customer_ids"]:
                    case["candidate_customer_ids"].append(cid)

    # After ingesting cited kyc/notes/accounts, pull their related customers too
    for kid in list(needed_kyc):
        k = kyc_by[kid]
        for o in onb_by_applicant.get(k.get("applicant_id"), []):
            if o.get("customer_id"):
                needed_customers.add(o["customer_id"])
            key = (o.get("account_id"), o.get("customer_id"), o.get("kyc_applicant_id"))
            if key not in seen_onb:
                seen_onb.add(key)
                needed_onboarding.append(o)

    preds_by = {p["hit_id"]: p for p in preds if p.get("hit_id")}
    practice_score = score_predictions(list(preds_by.values()), labels_by)

    def pick(ids, mapping):
        return {i: mapping[i] for i in sorted(ids) if i in mapping}

    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample_predictions": sample,
        "prediction_source": source,
        "n_hits": len(hits),
        "n_alerts": len(alerts),
        "n_practice_labels": len(labels),
        "n_predictions": len(preds_by),
        "n_customers_in_bundle": len(needed_customers),
        "output_path": str(output_path),
        "output_mtime": output_path.stat().st_mtime if output_path.exists() else None,
        "practice_score": practice_score,
        "cost_matrix": COST,
    }

    bundle = {
        "meta": meta,
        "reason_codes": REASON_CODES,
        "name_variants": name_variants,
        "countries": country_bundle(track2),
        "hits": hits_by,
        "alerts": alerts_by,
        "customers": pick(needed_customers, cust_by),
        "accounts": pick(needed_accounts, acct_by),
        "kyc_checks": pick(needed_kyc, kyc_by),
        "notes": pick(needed_notes, notes_by),
        "search_results": pick(needed_search, search_by),
        "onboarding": needed_onboarding,
        "labels": labels_by,
        "predictions": preds_by,
        "cases": cases_by_alert,
    }

    print("Writing bundle…", flush=True)
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    size_mb = bundle_path.stat().st_size / 1e6
    print(f"Wrote {bundle_path} ({size_mb:.2f} MB) sample={sample} preds={len(preds_by)} customers={len(needed_customers)}", flush=True)
    return bundle_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track2", type=Path, default=DEFAULT_TRACK2)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--predictions-only", action="store_true")
    args = ap.parse_args()
    build(args.track2, args.out, predictions_only=args.predictions_only)


if __name__ == "__main__":
    main()
