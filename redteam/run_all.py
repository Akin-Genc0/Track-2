"""Run every red-team case.  python3 redteam/run_all.py [--strict] [-v]

Default: asserts each case still behaves as recorded (status VULNERABLE or HOLDS); a case whose decision moved
prints FIXED (now policy-safe) or CHANGED and fails the run so the change is noticed.
--strict: asserts every case is policy-safe (the gate to use once fixes land)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import CASES  # noqa: E402

strict, verbose = "--strict" in sys.argv, "-v" in sys.argv
fails = 0
counts = {}
for fn in sorted(CASES, key=lambda f: f.rank):
    row, safe, now, why = fn()
    d = row["decision"]
    ok_policy = d in safe
    if d == now:
        status = "HOLDS" if ok_policy else "VULNERABLE"
    else:
        status = "FIXED" if ok_policy else "CHANGED"
    counts[status] = counts.get(status, 0) + 1
    bad = (not ok_policy) if strict else (d != now)
    fails += bad
    print(f"{'FAIL' if bad else 'ok  '} {status:10} {fn.finding:7} {fn.__name__:52} {d:16} {row['reason_code']}")
    if verbose or bad:
        print(f"       expected {sorted(safe)} | {why}\n       {row['reason'][:260]}")
print(counts)
assert fails == 0, f"{fails} case(s) failed ({'policy' if strict else 'recorded-behaviour'} mode)"
