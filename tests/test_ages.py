"""Age-cue probes for hitfacts.years_from_age: real ages are read, counts / money / dates are not.  python3 tests/test_ages.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))
from hitfacts import years_from_age  # noqa: E402

AGES = [
    ("John Smith, 45, was arrested in March 2019.", 45),
    ("John Smith (45) was charged in March 2019.", 45),
    ("In March 2019 Smith, now 45, lives in Kyiv.", 45),
    ("In 2019 a man of 45 was detained.", 45),
    ("Age at the time of listing in 2019: 45", 45),
    ("Brooke Lefevre, aged forty-two, was questioned by police in June 1997.", 42),
    ("Reports from July 2014 put the age of Agnieszka Sjoberg at 39.", 39),
    ("Mark E Phillips, at 24, was taken into custody in May 1999.", 24),
    ("In 2019 he was 45 when he was listed.", 45),
]
NOT_AGES = [
    "In 2019 Ivan Petrov held accounts at 3 banks in Cyprus.",
    "In 2018 the assets were 40 apartments owned by Ivan Petrov.",
    "In 2016, Ivan Petrov turned 3 companies into shells.",
    "In March 2019, Ivan Petrov was 1 of 12 officials named.",
    "On May 12, 2019, 45 people were detained.",
    "In 2019 the fine was 45 million.",
    "Smith (2019) wrote that 45 officials attended.",
    "In 2015 he was sentenced to 45 months.",
    "The company, 45, Main Street, was raided in 2019.",
    "He paid forty-five thousand dollars in 2019.",
    "Ivan Petrov, at 7 different addresses, was linked to fraud in 2015.",
    "...without the security being (1)a federal-covered security, (2)exempt, or (3) registered under the Act of 2003.",
]
fails = 0
for text, age in AGES:
    got = [a[4] for a in years_from_age(text)]
    ok = got[:1] == [age]
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} age {age}: {got} | {text}")
for text in NOT_AGES:
    got = [a[4] for a in years_from_age(text)]
    fails += bool(got)
    print(f"{'PASS' if not got else 'FAIL'} no age: {got} | {text}")
print(f"{len(AGES) + len(NOT_AGES) - fails}/{len(AGES) + len(NOT_AGES)} passed")
assert fails == 0
