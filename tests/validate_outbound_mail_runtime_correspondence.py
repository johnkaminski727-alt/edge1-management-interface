#!/usr/bin/env python3
"""Validate that the runtime-root-aware mail application exposes correspondence reads."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_runtime_application as runtime_application


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    config_root = folder / "etc-wwcx"
    state_root = folder / "state"
    config_root.mkdir(mode=0o700)
    state_root.mkdir(mode=0o700)

    config = json.loads(
        (ROOT / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8")
    )
    policy = json.loads(
        (ROOT / "config/messaging/outbound-mail-policy.json").read_text(encoding="utf-8")
    )
    identities = json.loads(
        (ROOT / "config/messaging/mail-identities.json").read_text(encoding="utf-8")
    )

    config_path = config_root / "outbound-mail-gateway.json"
    policy_path = config_root / "outbound-mail-policy.json"
    identities_path = config_root / "mail-identities.json"
    correspondence_db = state_root / "correspondence.sqlite3"

    config["paths"]["policy"] = str(policy_path)
    config["paths"]["audit_jsonl"] = str(state_root / "audit.jsonl")
    config["preparation_api"]["nonce_store"] = str(state_root / "preparation-nonces.sqlite3")

    config_path.write_text(json.dumps(config), encoding="utf-8")
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    identities_path.write_text(json.dumps(identities), encoding="utf-8")
    for path in (config_path, policy_path, identities_path):
        path.chmod(0o644)

    application = runtime_application.RuntimeGatewayApplication(
        config_path,
        identities_path,
        config_root=config_root,
        state_root=state_root,
        require_root_owned_config=False,
        correspondence_db_path=correspondence_db,
        correspondence_enabled=True,
    )

    application.load()
    state = application.correspondence_state()
    check(
        state["state"] == "blocked_store_unavailable",
        "runtime correspondence state did not delegate to the Mail AI adapter",
    )
    check(state["read_enabled"] is True, "runtime correspondence enablement was lost")
    check(state["send_authorized"] is False, "runtime correspondence path authorized send")
    check(state["mutation_authorized"] is False, "runtime correspondence path authorized mutation")

    for method_name in ("correspondence_message", "correspondence_thread"):
        check(callable(getattr(application, method_name, None)), f"missing runtime method: {method_name}")

print("Outbound mail runtime correspondence wiring validation passed")
print("Runtime application exposes status/message/thread delegation without enabling send or mutation")
