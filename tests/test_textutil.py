"""Name matcher edge cases. Run: python3 tests/test_textutil.py"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))
from textutil import NameMatcher

m = NameMatcher([], [])
fails = 0


def check(name, got, want):
    global fails
    fails += got != want
    print(("PASS " if got == want else "FAIL ") + name, "->", got)


# A very long name yields more than 18 candidate matches; the agreeing pair (ali+omar) comes after the 18th.
# A capped search saw only the 'ali' matches and wrongly found the names different (a clear on name).
long_a = ["ali"] * 19 + ["omar"]
check("long_name_not_cleared_on_truncated_set", m.agree_parts(long_a, ["ali", "omar"]), True)
check("long_name_symmetric", m.agree_parts(["ali", "omar"], long_a), True)
# still different when no two parts match
check("long_name_still_different", m.agree_parts(long_a[:-1] + ["khan"], ["omar", "hassan"]), False)
# bounded cost: a 60-part name against itself finishes quickly
t = time.time()
check("long_name_bounded_cost", m.agree_parts(["ali"] * 60, ["ali"] * 60), True)
check("long_name_under_1s", time.time() - t < 1.0, True)
# ordinary cases unchanged
check("one_part_of_shorter", m.agree_parts(["smith"], ["john", "smith"]), True)
check("single_overlap_not_enough", m.agree_parts(["john", "smith"], ["john", "jones"]), False)
# loose agreement (only ever stops a clear on the verified name): transliteration skeleton, split compounds, Cyrillic
loose = lambda a, b: m.agree_parts_loose(m.parts(a), m.parts(b))
for a, b in [("Yasin Khan", "Yaseen Khan"), ("Abdul Rahman Yasin", "Abdulrahman Yaseen"), ("Yusuf Qaradawi", "Yousef al-Qaradawi"),
             ("Alexei Navalny", "Aleksey Navalnyy"), ("Abd al-Rahman", "Abdulrahman"), ("Владимир Путин", "Vladimir Putin")]:
    check(f"loose {a} / {b}", loose(a, b), True)
    check(f"strict unchanged {a} / {b}", m.agree(a, b), False)
for a, b in [("John Smith", "John Jones"), ("Ali Omar", "Ali Hassan"), ("Starling Logistics", "ST Logistics")]:
    check(f"loose still different {a} / {b}", loose(a, b), False)
print(f"{22 - fails}/22 passed")
sys.exit(1 if fails else 0)
