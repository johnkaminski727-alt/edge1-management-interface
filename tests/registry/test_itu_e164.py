import csv
import re

ROWS = list(csv.DictReader(
    open("data/registry/sources/itu-e164/e164.csv")
))

def test_codes_are_valid():
    for row in ROWS:
        assert re.fullmatch(r"\+[0-9]{1,3}", row["calling_code"])

def test_no_zero_code():
    assert not any(
        r["calling_code"] in ("+0","+00")
        for r in ROWS
    )

def test_known_codes():
    codes = {r["calling_code"] for r in ROWS}

    for code in ["+1","+44","+354","+81","+86"]:
        assert code in codes
