#!/usr/bin/env python3
"""Validate bounded UCP readiness handling in the MariaDB activation operator."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/apply_mariadb_loopback_socket_hardening.sh"
text = SCRIPT.read_text(encoding="utf-8")

required = (
    "POST_CHANGE_ATTEMPTS=60",
    "wait_for_ucp_runtime() {",
    "wait_for_post_change_runtime() {",
    "Waiting up to $POST_CHANGE_ATTEMPTS seconds for MariaDB and FreePBX/UCP readiness",
    "post-change-readiness-attempts.txt",
    "UCP listeners did not recover within the readiness window",
    "Post-change MariaDB and UCP readiness gate passed",
    'wait_for_ucp_runtime "$EVIDENCE_DIR/tcp-listeners-after-rollback.txt" || return 1',
)
for token in required:
    if token not in text:
        raise SystemExit(f"missing bounded UCP readiness behavior: {token}")

main_start = text.index('log "Restarting MariaDB socket and service as one bounded maintenance action"')
main_end = text.index("ss -Htnpe state established 2>/dev/null |", main_start)
main = text[main_start:main_end]
if main.index("wait_for_post_change_runtime") > main.index("UCP listeners did not recover"):
    raise SystemExit("UCP failure may be evaluated before the readiness wait")
if 'while [ "$attempt" -le 30 ]' in main:
    raise SystemExit("obsolete relationship-only 30-second wait remains")

rollback_start = text.index("rollback() {")
rollback_end = text.index("fail_after_mutation() {", rollback_start)
rollback = text[rollback_start:rollback_end]
if rollback.index("restart_mariadb_pair") > rollback.index("wait_for_ucp_runtime"):
    raise SystemExit("rollback UCP wait must follow MariaDB restoration")

if '\\"node' in text:
    raise SystemExit("awk UCP regex contains an unnecessary escaped quote")

print("MariaDB loopback UCP readiness contract: PASS")
