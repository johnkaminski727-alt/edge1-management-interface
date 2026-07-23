#!/usr/bin/env python3
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web" / "telephony"
DOCS = ROOT / "docs" / "telephony"

required = [
    WEB / "index.html",
    WEB / "telephony.css",
    WEB / "telephony.js",
    WEB / "telephony.fixture.json",
    ROOT / "src" / "api" / "telephony_status_contract.json",
    ROOT / "server" / "telephony_status_server.py",
    ROOT / "deploy" / "telephony" / "wwcx-telephony-console.service",
    ROOT / "deploy" / "telephony" / "install-telephony-console.sh",
    ROOT / "deploy" / "telephony" / "telephony-console-smoke-test.sh",
    DOCS / "README.md",
    DOCS / "operator-acceptance-checklist.md",
]
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

javascript = (WEB / "telephony.js").read_text(encoding="utf-8")
for marker in ("/api/telephony/status", "telephony.fixture.json", "fixture fallback"):
    if marker not in javascript:
        raise SystemExit("JavaScript missing live/fallback marker: " + marker)

server_path = ROOT / "server" / "telephony_status_server.py"
ast.parse(server_path.read_text(encoding="utf-8"), filename=str(server_path))
server = server_path.read_text(encoding="utf-8")
for marker in (
    "127.0.0.1",
    "/api/telephony/status",
    "/healthz",
    "asterisk_snapshot",
    "process_running",
    '"interconnects": interconnects',
    '"registrations": []',
    "wwcx-numbering-node.service",
):
    if marker not in server:
        raise SystemExit("server missing safety or integration marker: " + marker)

unit = (ROOT / "deploy" / "telephony" / "wwcx-telephony-console.service").read_text(encoding="utf-8")
for marker in ("--host 127.0.0.1", "NoNewPrivileges=true", "ProtectSystem=strict", "WantedBy=multi-user.target"):
    if marker not in unit:
        raise SystemExit("systemd unit missing marker: " + marker)

installer = (ROOT / "deploy" / "telephony" / "install-telephony-console.sh").read_text(encoding="utf-8")
for marker in ("for attempt in", "journalctl -u wwcx-telephony-console.service", "REPO_ROOT"):
    if marker not in installer:
        raise SystemExit("installer missing readiness marker: " + marker)

docs_readme = (DOCS / "README.md").read_text(encoding="utf-8")
if "operator-acceptance-checklist.md" not in docs_readme:
    raise SystemExit("telephony README must link the operator acceptance checklist")

acceptance = (DOCS / "operator-acceptance-checklist.md").read_text(encoding="utf-8")
for marker in (
    "Repository preflight",
    "Safe installation boundary",
    "Read-only behavior",
    "Stop conditions",
    "Acceptance record",
    "127.0.0.1",
):
    if marker not in acceptance:
        raise SystemExit("operator acceptance checklist missing marker: " + marker)

print("telephony console validation passed")