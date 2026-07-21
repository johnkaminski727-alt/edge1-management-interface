#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/cx_admin/control_centre_registry.json"
HTML = ROOT / "src/web/admin/control-centre/index.html"
CSS = ROOT / "src/web/admin/control-centre/styles.css"

VALID_CAPABILITIES = {"observe", "analyze", "control", "govern", "assist"}
VALID_RISKS = {"read_only", "sensitive_read", "conditional_change", "privileged_change"}

registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
sections = {item["id"] for item in registry["sections"]}
modules = registry["modules"]

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

states = registry["control_transaction"]["states"]
for state in ("draft", "validated", "approved", "executing", "verifying", "completed", "rolled_back"):
    assert state in states

html = HTML.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")
for marker in ("Command", "Observe", "Analyze", "Control", "Govern", "Decision Centre", "Change pipeline"):
    assert marker in html, marker
assert "@media" in css
assert "grid-template-columns" in css

print("Unified administration control centre validation passed")
print("sections:", len(sections))
print("modules:", len(modules))
print("privileged controls:", sum(m.get("transaction_required") is True for m in modules))
