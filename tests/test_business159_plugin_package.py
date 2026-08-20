import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "business159-authenticated-operator"

manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
assert manifest["name"] == "wwcx-business159-authenticated-operator"
assert manifest["skills"] == "./skills/"
assert manifest["apps"] == "./.app.json"

app_map = json.loads((PLUGIN / ".app.json").read_text())
app = app_map["apps"]["business159-live-shell"]
assert app["id"].startswith(("asdk_app_", "plugin_asdk_app_"))

skill_root = PLUGIN / "skills" / "business159-authenticated-operator"
skill = (skill_root / "SKILL.md").read_text()
agent = (skill_root / "agents" / "openai.yaml").read_text()
assert "business159_connection_test" in skill
assert "value: business159-live-shell" in agent
assert (skill_root / "docs" / "operator-pastebox-convention.md").is_file()

marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
entries = {entry["name"]: entry for entry in marketplace["plugins"]}
entry = entries["wwcx-business159-authenticated-operator"]
assert entry["source"]["source"] == "local"
assert entry["source"]["path"] == "./plugins/business159-authenticated-operator"
assert entry["policy"]["installation"] == "AVAILABLE"
assert entry["policy"]["authentication"] == "ON_INSTALL"

print("Business159 plugin package validation passed.")
