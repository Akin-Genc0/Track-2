#!/usr/bin/env python3
"""Convert 'Screening Dev Set - browse.xlsx' into the dev/*.jsonl layout screen.py reads.
Only needed if you don't have the data room's dev/ JSONL files (those are the source of truth).

    python xlsx_to_jsonl.py "Screening Dev Set - browse.xlsx" dev
"""
import json, os, sys
import openpyxl

TABS = {"Alerts": "alerts", "Hits": "hits", "Customers": "customers", "Accounts": "accounts",
        "Onboarding": "onboarding", "KYC checks": "kyc_checks", "Notes": "notes",
        "Search results": "search_results", "Practice labels": "practice_labels"}

src = sys.argv[1] if len(sys.argv) > 1 else "Screening Dev Set - browse.xlsx"
out = sys.argv[2] if len(sys.argv) > 2 else "dev"
os.makedirs(out, exist_ok=True)
wb = openpyxl.load_workbook(src, read_only=True)
for tab, stem in TABS.items():
    rows = wb[tab].iter_rows(values_only=True)
    hdr = next(rows)
    n = 0
    with open(os.path.join(out, stem + ".jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            if r is None or all(c is None for c in r):
                continue
            f.write(json.dumps({h: (r[i] if i < len(r) else None) for i, h in enumerate(hdr)},
                               default=str, ensure_ascii=False) + "\n")
            n += 1
    print(f"{stem}: {n}")
