#!/usr/bin/env python3

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "web" / "carrier-review"

required = [MODULE / "index.html", MODULE / "styles.css", MODULE / "app.js"]
for path in required:
    assert path.is_file(), f"missing console asset: {path.relative_to(ROOT)}"
    assert path.read_text(encoding="utf-8").strip(), f"empty console asset: {path.relative_to(ROOT)}"

html = (MODULE / "index.html").read_text(encoding="utf-8")
js = (MODULE / "app.js").read_text(encoding="utf-8")
combined = (html + "\n" + js).lower()

for required_text in (
    "internal review console",
    "no approval or execution authority",
    "execution authorized",
    "approval granted",
    "review-only",
):
    assert required_text in combined, f"missing safety text: {required_text}"

for forbidden in (
    "client_secret",
    "private_key",
    "authorization: bearer",
    "x-portal-signature",
    "approve_change",
    "execute_change",
):
    assert forbidden not in combined, f"forbidden browser content: {forbidden}"

assert "execution_authorized:false" in js.replace(" ", ""), "fixtures must force execution_authorized false"
assert "approval_granted:false" in js.replace(" ", ""), "fixtures must force approval_granted false"

print("carrier review console validation passed")
