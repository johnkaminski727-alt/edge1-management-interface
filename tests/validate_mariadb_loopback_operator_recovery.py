#!/usr/bin/env python3
"""Static regression checks for the MariaDB loopback activation operator."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/security/apply_mariadb_loopback_socket_hardening.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    require(
        "systemd-analyze verify --man=no" in text,
        "systemd verification must disable manual-page existence checks",
    )
    require(
        "systemd-analyze verify mariadb.socket mariadb.service" not in text,
        "the old manual-page-sensitive verification command remains",
    )

    rollback_start = text.index("rollback() {")
    rollback_end = text.index("\nfail_after_mutation() {", rollback_start)
    rollback = text[rollback_start:rollback_end]

    require("verify_rc=0" in rollback, "rollback must record verification status")
    require(
        'verify_units "$EVIDENCE_DIR/systemd-verify-rollback.txt"' in rollback,
        "rollback must preserve static verification evidence",
    )
    require(
        "|| verify_rc=$?" in rollback,
        "rollback verification must not return before service restoration",
    )
    require(
        "restart_mariadb_pair || return 1" in rollback,
        "rollback must always attempt and verify MariaDB service restoration",
    )
    require(
        rollback.index("verify_units") < rollback.index("restart_mariadb_pair"),
        "rollback must record diagnostics before restoring runtime service",
    )
    require(
        "ROLLBACK WARNING: static systemd verification failed" in rollback,
        "rollback must report a non-fatal static verification diagnostic",
    )

    print("MariaDB loopback operator recovery contract: PASS")


if __name__ == "__main__":
    main()
