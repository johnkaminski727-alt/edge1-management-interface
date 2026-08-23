from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/"deploy/ava-operator-broker/install.sh").read_text()
assert "systemctl restart wwcx-ava-operator-broker.service" in text
assert "systemctl enable --now wwcx-ava-operator-broker.service" not in text
assert "until curl -fsS http://127.0.0.1:8118/healthz" in text
