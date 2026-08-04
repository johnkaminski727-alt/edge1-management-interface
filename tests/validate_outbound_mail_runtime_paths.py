#!/usr/bin/env python3
"""Validate strict outbound-mail runtime config and mutable-state boundaries."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import outbound_mail_delivery_events as delivery_events
import outbound_mail_gateway_runtime_server as runtime_server
import outbound_mail_runtime_application as runtime_application
import outbound_mail_runtime_paths as runtime_paths


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def expect_path_error(label: str, function) -> None:
    failed = False
    try:
        function()
    except runtime_paths.RuntimePathError:
        failed = True
    check(failed, f"unsafe runtime path did not fail closed: {label}")


def http_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    method = "GET"
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    repo = folder / "repo"
    config_root = folder / "etc-wwcx"
    state_root = folder / "var-lib-wwcx"
    outside = folder / "outside"
    for path in (repo, config_root, state_root, outside):
        path.mkdir(mode=0o700)

    relative_config = repo / "relative.json"
    relative_config.write_text("{}", encoding="utf-8")
    check(
        runtime_paths.resolve_config_file(
            "relative.json",
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        )
        == relative_config.resolve(),
        "relative repository config did not resolve",
    )
    expect_path_error(
        "relative repository escape",
        lambda: runtime_paths.resolve_config_file(
            "../outside/config.json",
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        ),
    )

    absolute_config = config_root / "gateway.json"
    absolute_config.write_text("{}", encoding="utf-8")
    absolute_config.chmod(0o644)
    check(
        runtime_paths.resolve_config_file(
            absolute_config,
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        )
        == absolute_config.resolve(),
        "absolute runtime config did not resolve",
    )

    broad_config = config_root / "broad.json"
    broad_config.write_text("{}", encoding="utf-8")
    broad_config.chmod(0o664)
    expect_path_error(
        "group-writable config",
        lambda: runtime_paths.resolve_config_file(
            broad_config,
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        ),
    )

    outside_config = outside / "config.json"
    outside_config.write_text("{}", encoding="utf-8")
    outside_config.chmod(0o600)
    expect_path_error(
        "absolute config outside root",
        lambda: runtime_paths.resolve_config_file(
            outside_config,
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        ),
    )

    final_config_link = config_root / "config-link.json"
    final_config_link.symlink_to(absolute_config)
    expect_path_error(
        "final config symlink",
        lambda: runtime_paths.resolve_config_file(
            final_config_link,
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        ),
    )

    real_config_dir = config_root / "real"
    real_config_dir.mkdir()
    nested_config = real_config_dir / "nested.json"
    nested_config.write_text("{}", encoding="utf-8")
    nested_config.chmod(0o644)
    linked_config_dir = config_root / "linked"
    linked_config_dir.symlink_to(real_config_dir, target_is_directory=True)
    expect_path_error(
        "config parent symlink",
        lambda: runtime_paths.resolve_config_file(
            linked_config_dir / "nested.json",
            repo_root=repo,
            config_root=config_root,
            require_root_owned=False,
        ),
    )

    missing_state = state_root / "missing.sqlite3"
    check(
        runtime_paths.resolve_state_path(
            missing_state,
            repo_root=repo,
            state_root=state_root,
        )
        == missing_state.resolve(),
        "missing state path inside root was rejected",
    )
    private_state = state_root / "private.sqlite3"
    private_state.write_bytes(b"state")
    private_state.chmod(0o600)
    check(
        runtime_paths.resolve_state_path(
            private_state,
            repo_root=repo,
            state_root=state_root,
        )
        == private_state.resolve(),
        "private existing state was rejected",
    )
    broad_state = state_root / "broad.sqlite3"
    broad_state.write_bytes(b"state")
    broad_state.chmod(0o640)
    expect_path_error(
        "broad state permissions",
        lambda: runtime_paths.resolve_state_path(
            broad_state,
            repo_root=repo,
            state_root=state_root,
        ),
    )
    final_state_link = state_root / "state-link.sqlite3"
    final_state_link.symlink_to(private_state)
    expect_path_error(
        "final state symlink",
        lambda: runtime_paths.resolve_state_path(
            final_state_link,
            repo_root=repo,
            state_root=state_root,
        ),
    )
    real_state_dir = state_root / "real"
    real_state_dir.mkdir()
    linked_state_dir = state_root / "linked"
    linked_state_dir.symlink_to(real_state_dir, target_is_directory=True)
    expect_path_error(
        "state parent symlink",
        lambda: runtime_paths.resolve_state_path(
            linked_state_dir / "state.sqlite3",
            repo_root=repo,
            state_root=state_root,
        ),
    )
    expect_path_error(
        "state outside root",
        lambda: runtime_paths.resolve_state_path(
            outside / "state.sqlite3",
            repo_root=repo,
            state_root=state_root,
        ),
    )
    expect_path_error(
        "overlapping runtime roots",
        lambda: runtime_paths.validate_runtime_roots(
            config_root,
            config_root / "state",
        ),
    )

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    config_root = folder / "etc-wwcx"
    state_root = folder / "state"
    config_root.mkdir(mode=0o700)
    state_root.mkdir(mode=0o700)

    runtime_config = json.loads(
        (ROOT / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8")
    )
    runtime_policy = json.loads(
        (ROOT / "config/messaging/outbound-mail-policy.json").read_text(encoding="utf-8")
    )
    runtime_identities = json.loads(
        (ROOT / "config/messaging/mail-identities.json").read_text(encoding="utf-8")
    )

    config_path = config_root / "outbound-mail-gateway.json"
    policy_path = config_root / "outbound-mail-policy.json"
    identities_path = config_root / "mail-identities.json"
    runtime_config["paths"]["policy"] = str(policy_path)
    runtime_config["paths"]["audit_jsonl"] = str(state_root / "audit.jsonl")
    runtime_config["preparation_api"]["nonce_store"] = str(
        state_root / "preparation-nonces.sqlite3"
    )
    config_path.write_text(json.dumps(runtime_config), encoding="utf-8")
    policy_path.write_text(json.dumps(runtime_policy), encoding="utf-8")
    identities_path.write_text(json.dumps(runtime_identities), encoding="utf-8")
    for path in (config_path, policy_path, identities_path):
        path.chmod(0o644)

    application = runtime_application.RuntimeGatewayApplication(
        config_path,
        identities_path,
        config_root=config_root,
        state_root=state_root,
        require_root_owned_config=False,
    )
    config, policy, identities, audit_path, nonce_path = application.load()
    check(config["enabled"] is False, "runtime gateway became enabled")
    check(config["external_delivery_authorized"] is False, "runtime delivery became authorized")
    check(policy["enabled"] is False, "runtime policy became enabled")
    check(identities["outbound_activation_authorized"] is False, "runtime identities became active")
    check(audit_path == (state_root / "audit.jsonl").resolve(), "runtime audit path mismatch")
    check(
        nonce_path == (state_root / "preparation-nonces.sqlite3").resolve(),
        "runtime nonce path mismatch",
    )
    summary = application.resolved_path_summary()
    check(summary["config"] == str(config_path.resolve()), "runtime config summary mismatch")
    check(summary["policy"] == str(policy_path.resolve()), "runtime policy summary mismatch")
    check(summary["identities"] == str(identities_path.resolve()), "runtime identities summary mismatch")

    identities_path.chmod(0o664)
    expect_path_error("broad runtime identities", application.load)
    identities_path.chmod(0o644)

    audit_path.write_text("", encoding="utf-8")
    audit_path.chmod(0o644)
    expect_path_error("broad existing audit state", application.load)
    audit_path.chmod(0o600)
    application.load()

    suppression_database = state_root / "delivery-state.sqlite3"
    connection = delivery_events._connect(suppression_database)
    connection.close()
    suppression_database.chmod(0o600)
    server = runtime_server.suppressed.SuppressedGatewayServer(
        ("127.0.0.1", 0),
        application,
        runtime_paths.resolve_state_path(
            suppression_database,
            repo_root=ROOT,
            state_root=state_root,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    origin = f"http://{host}:{port}"
    try:
        health_status, health = http_json(origin + "/outbound-mail/healthz")
        check(health_status == 200 and health["status"] == "ok", "runtime health route failed")
        send_status, send = http_json(
            origin + "/outbound-mail/send",
            {
                "to": ["runtime.test@example.com"],
                "subject": "Runtime path boundary validation",
                "body": "Synthetic local request; committed delivery remains disabled.",
                "message_class": "business_correspondence",
                "confirm_send": True,
            },
        )
        check(send_status == 403, "disabled runtime send did not return HTTP 403")
        check(send["error"] == "delivery_disabled", "disabled runtime send error changed")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

for path in (
    SERVER / "outbound_mail_runtime_paths.py",
    SERVER / "outbound_mail_runtime_application.py",
    SERVER / "outbound_mail_gateway_runtime_server.py",
):
    source = path.read_text(encoding="utf-8")
    check("Refusing non-loopback bind" in source or path.name != "outbound_mail_gateway_runtime_server.py", "runtime server lost loopback refusal")
    for prohibited in (
        "smtplib",
        "requests.",
        "urllib.request",
        "chmod(0o777",
        "require_root_owned_config=False" if path.name == "outbound_mail_gateway_runtime_server.py" else "__never__",
    ):
        check(prohibited not in source, f"runtime boundary contains prohibited operation: {path.name}: {prohibited}")

print("Outbound mail runtime path-boundary validation passed")
print("Repository-relative compatibility and strict /etc config and /var/lib state roots verified")
print("Path escapes, final/parent symlinks, broad permissions, and overlapping roots fail closed")
print("Absolute runtime config loads while all committed delivery gates remain disabled")
print("Loopback health works and the runtime send route remains HTTP 403 with no message traffic")
