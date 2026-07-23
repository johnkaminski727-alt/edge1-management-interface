#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "cx_admin" / "control_centre_registry.json"
HTML = ROOT / "src" / "web" / "admin" / "control-centre" / "index.html"
CSS = ROOT / "src" / "web" / "admin" / "control-centre" / "styles.css"
APP = ROOT / "src" / "web" / "admin" / "control-centre" / "app.js"

VALID_CAPABILITIES = {"observe", "analyze", "control", "govern", "assist"}
VALID_RISKS = {"read_only", "sensitive_read", "conditional_change", "privileged_change"}
EXPECTED_BOUNDARIES = {
    "electrum-watch": "watch_only_read_only",
    "carrier-operations": "scoped_exported_summaries",
    "carrier-workflows": "request_only_no_execution",
    "carrier-review": "review_only_no_approval_or_execution",
}

registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
sections = {item["id"] for item in registry["sections"]}
modules = registry["modules"]
module_by_id = {item["id"]: item for item in modules}

ids = [item["id"] for item in modules]
routes = [item["route"] for item in modules]
assert len(ids) == len(set(ids)), "duplicate module id"
assert len(routes) == len(set(routes)), "duplicate module route"
assert sections == {"command", "observe", "analyze", "control", "govern"}

for module in modules:
    assert module["section"] in sections, module
    assert module["capability"] in VALID_CAPABILITIES, module
    assert module["risk"] in VALID_RISKS, module
    assert module["permission"], module
    if module["capability"] == "control" and module["risk"] == "privileged_change":
        assert module.get("transaction_required") is True, module

for module_id, boundary in EXPECTED_BOUNDARIES.items():
    assert module_by_id[module_id].get("operational_boundary") == boundary, module_id
assert "carrier-analysis" in module_by_id

states = registry["control_transaction"]["states"]
for state in ("draft", "validated", "approved", "executing", "verifying", "completed", "rolled_back"):
    assert state in states

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
app = APP.read_text(encoding="utf-8")
for marker in ("Decision Centre", "Change pipeline", 'script src="app.js"'):
    assert marker in html, marker
for marker in ("Command", "Observe", "Analyze", "Control", "Govern", "Electrum Watch Console", "Carrier Operations", "Carrier Analysis", "Carrier Requests", "Carrier Review Queue"):
    assert marker in app, marker
assert "@media" in css
assert "grid-template-columns" in css

print("Unified administration control centre validation passed")
print("sections:", len(sections))
print("modules:", len(modules))
print("privileged controls:", sum(m.get("transaction_required") is True for m in modules))
