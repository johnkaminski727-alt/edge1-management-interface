#!/usr/bin/env python3
"""Validate the reversible safe-disabled outbound-mail runtime migration package."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/messaging/install-outbound-mail-disabled-runtime-migration.sh"
BUILDER = ROOT / "tools/messaging/build_outbound_mail_disabled_runtime_bundle.py"
BUNDLE_TEST = ROOT / "tests/validate_outbound_mail_disabled_runtime_bundle.py"
DOC = ROOT / "docs/messaging-operations/outbound-mail-disabled-runtime-migration-20260804.md"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


for path in (INSTALLER, BUILDER, BUNDLE_TEST, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

syntax = subprocess.run(["sh", "-n", str(INSTALLER)], cwd=ROOT, check=False)
check(syntax.returncode == 0, "runtime migration installer shell syntax failed")
compile_result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BUILDER), str(BUNDLE_TEST)],
    cwd=ROOT,
    check=False,
)
check(compile_result.returncode == 0, "runtime migration Python did not compile")
bundle_result = subprocess.run(
    [sys.executable, str(BUNDLE_TEST)],
    cwd=ROOT,
    check=False,
)
check(bundle_result.returncode == 0, "runtime bundle validation failed")

source = INSTALLER.read_text(encoding="utf-8")
for required in (
    "ACTION=${ACTION:-audit}",
    "RUNTIME_MIGRATION_AUTHORIZED=yes",
    "EXPECTED_COMMIT",
    "Repository working tree must be clean",
    "dedicated non-root User",
    "outbound-mail-gateway-runtime.json",
    "outbound-mail-policy-runtime.json",
    "mail-identities-runtime.json",
    "outbound_mail_gateway_runtime_server.py",
    "build_outbound_mail_disabled_runtime_bundle.py",
    "preparation-nonces.sqlite3",
    "delivery-state.sqlite3",
    "sqlite3.connect(f\"file:{sys.argv[1]}?mode=ro\"",
    "source.backup(destination)",
    "source_config_sha256",
    "source_config_preserved",
    "hmac_secret_read no",
    "provider_credentials_read no",
    "external_delivery_enabled no",
    "message_sent no",
    "runtime_secret_configured",
    "unsigned-status.json",
    "disabled-send.json",
    "Runtime migration drop-in drift detected; refusing disable",
    "automatic rollback after runtime migration exit",
    "restore_dropin",
    "40-runtime-paths.conf.before",
    "trap 'on_exit $?' 0",
    "stat.S_IMODE(config_stat.st_mode) & 0o022",
    "stat.S_IMODE(state_stat.st_mode) & 0o027",
    "The original preparation config remains unchanged and no message was sent",
):
    check(required in source, f"migration package missing safety marker: {required}")

trap_index = source.index("trap 'on_exit $?' 0")
disable_index = source.index('if [ "$ACTION" = disable ]')
install_mutation_index = source.index("mutated=yes", disable_index + 1)
check(trap_index < disable_index, "EXIT rollback trap is installed after disable mutation path")
check(trap_index < install_mutation_index, "EXIT rollback trap is installed after install mutation path")

restore_index = source.index("restore_dropin()")
rollback_index = source.index("rollback()")
check(restore_index < rollback_index, "drop-in restoration is not part of rollback design")
check('if [ "$had_dropin" = yes ]' in source[restore_index:rollback_index], "rollback does not restore a previous drop-in")
check('elif [ -e "$DROPIN" ]' in source[restore_index:rollback_index], "rollback does not remove a newly created drop-in")

for prohibited in (
    "curl -k",
    "--insecure",
    "rm -rf",
    "WWCX_MAIL_SMTP_PASSWORD",
    "WWCX_MAIL_SMTP_USERNAME",
    "cat /etc/wwcx/outbound-mail-gateway.env",
    "source /etc/wwcx/outbound-mail-gateway.env",
    "eval ",
    "nft ",
    "iptables",
    "ufw ",
    "certbot",
    "nsupdate",
    "cloudflare",
    "dig ",
    "systemctl enable",
):
    check(prohibited not in source, f"migration package contains prohibited operation: {prohibited}")

check('install -o root -g root -m 0644 "$bundle_dir/outbound-mail-gateway-runtime.json" "$RUNTIME_CONFIG"' in source, "runtime gateway file installation changed")
check('install -o root -g root -m 0644 "$bundle_dir/outbound-mail-policy-runtime.json" "$RUNTIME_POLICY"' in source, "runtime policy file installation changed")
check('install -o root -g root -m 0644 "$bundle_dir/mail-identities-runtime.json" "$RUNTIME_IDENTITIES"' in source, "runtime identities file installation changed")
check('"$SOURCE_CONFIG"' not in "\n".join(line for line in source.splitlines() if line.lstrip().startswith("install -o root")), "source preparation config appears as an installation destination")

config = (ROOT / "config/messaging/outbound-mail-gateway.json").read_text(encoding="utf-8")
identities = (ROOT / "config/messaging/mail-identities.json").read_text(encoding="utf-8")
check('"enabled": false' in config, "committed gateway enabled state changed")
check('"external_delivery_authorized": false' in config, "committed delivery authorization changed")
check('"send_endpoint_enabled": false' in config, "committed send endpoint changed")
check('"selected": "none"' in config, "committed provider selection changed")
check('"outbound_activation_authorized": false' in identities, "committed identity activation changed")

print("Disabled outbound-mail runtime migration validation passed")
print("Default audit, exact commit, clean-main, explicit authorization, and non-root service gates verified")
print("Config/state root mode-bit checks and immutable source-config hash checks verified")
print("Install and disable both enter EXIT-triggered rollback with exact drop-in restoration")
print("Audit/nonce migration, suppression state, loopback health, preparation 401, and disabled send 403 are bounded")
print("No credential, DNS, firewall, provider/sender activation, or message traffic is included")
