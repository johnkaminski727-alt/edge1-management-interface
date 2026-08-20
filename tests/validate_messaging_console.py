#!/usr/bin/env python3

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "server"))

from messaging_gateway_collector import collect_gateway_health


snapshot = collect_gateway_health().to_dict()

assert snapshot["gateway"] == "wwcx-messaging-gateway"
assert snapshot["production_actions_enabled"] is False
assert snapshot["state"] in ("healthy", "degraded")

page = ROOT / "src/web/messaging-operations.html"

assert page.exists()

text = page.read_text()

assert "Messaging Operations" in text
assert "/messaging/status" in text
assert "/messaging/diagnostics" in text
assert "/messaging/history?limit=10" in text
assert "/messaging/sandbox/simulate" in text
assert "Draft is not send" in text
assert "messages.conversation.read" in text
assert "messages.draft.prepare" in text
assert "Authorize &amp; send" in text
assert "disabled aria-describedby=\"send-help\"" in text
assert "Production traffic" in text
assert "Not authorized" in text
assert "@media(max-width:720px)" in text
assert "focus-visible" in text

print("Messaging console validation passed")
print("Responsive sandbox-only operations boundary confirmed")
