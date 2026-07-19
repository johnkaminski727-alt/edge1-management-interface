#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web" / "telephony"

required = [WEB / "index.html", WEB / "telephony.css", WEB / "telephony.js", WEB / "telephony.fixture.json", ROOT / "src" / "api" / "telephony_status_contract.json"]
missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
if missing:
    raise SystemExit("missing telephony assets: " + ", ".join(missing))

fixture = json.loads((WEB / "telephony.fixture.json").read_text(encoding="utf-8"))
contract = json.loads((ROOT / "src" / "api" / "telephony_status_contract.json").read_text(encoding="utf-8"))
for key in contract["required"]:
    if key not in fixture:
        raise SystemExit("fixture missing required key: " + key)
if fixture["mode"] != "sanitized_fixture":
    raise SystemExit("public fixture must use sanitized_fixture mode")
if fixture["overall_status"] not in {"healthy", "degraded", "critical", "unknown"}:
    raise SystemExit("invalid overall status")
if not fixture["services"] or not fixture["interconnects"]:
    raise SystemExit("fixture must exercise services and interconnects")

html = (WEB / "index.html").read_text(encoding="utf-8")
for marker in ("Telephony Operations", "service-grid", "peer-rows", "registration-rows", "telephony.js"):
    if marker not in html:
        raise SystemExit("HTML missing marker: " + marker)

print("telephony console validation passed")
