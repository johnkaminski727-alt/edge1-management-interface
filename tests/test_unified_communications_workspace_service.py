from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"


def test_workspace_service_is_loopback_read_only_and_hardened() -> None:
    unit = (DEPLOY / "wwcx-communications-workspace.service").read_text(encoding="utf-8")

    assert "Environment=WWCX_COMMUNICATIONS_HOST=127.0.0.1" in unit
    assert "Environment=WWCX_COMMUNICATIONS_PORT=8095" in unit
    assert "ExecStart=/opt/edge1-management-interface/deploy/run-wwcx-communications-workspace.sh" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=true" in unit
    assert "PrivateTmp=true" in unit
    assert "PrivateDevices=true" in unit
    assert "CapabilityBoundingSet=" in unit
    assert "AmbientCapabilities=" in unit
    assert "ReadOnlyPaths=/opt/edge1-management-interface" in unit
    assert "PYTHONDONTWRITEBYTECODE=1" in unit
    assert "0.0.0.0" not in unit


def test_workspace_runner_rejects_non_loopback_and_has_optional_snapshot() -> None:
    runner = (DEPLOY / "run-wwcx-communications-workspace.sh").read_text(encoding="utf-8")

    assert "127.0.0.1|::1|localhost" in runner
    assert "refusing non-loopback" in runner
    assert "--event-snapshot" in runner
    assert "WWCX_COMMUNICATIONS_EVENT_SNAPSHOT" in runner
    assert "exec \"$@\"" in runner
    assert "eval " not in runner


def test_workspace_installer_is_dry_run_by_default_and_accepts_only_apply() -> None:
    installer = (DEPLOY / "install-wwcx-communications-workspace.sh").read_text(encoding="utf-8")

    assert 'case "$MODE" in' in installer
    assert "Dry run passed" in installer
    assert "--apply" in installer
    assert "systemctl enable --now" in installer
    assert "/communications/healthz" in installer
    assert "/communications/api/v1/readiness" in installer
    assert "/communications/api/v1/events?limit=1" in installer
    assert 'POST_CODE=$(curl' in installer
    assert 'test "$POST_CODE" = "405"' not in installer  # installer uses POSIX [ ] instead
    assert '[ "$POST_CODE" = "405" ]' in installer
    assert "mutation_authorized" in installer
    assert "0\\.0\\.0\\.0" in installer
    assert "rollback_backup=" in installer


def test_service_deployment_does_not_add_public_proxy_or_mutation_authority() -> None:
    combined = "\n".join(
        (DEPLOY / name).read_text(encoding="utf-8")
        for name in (
            "wwcx-communications-workspace.service",
            "run-wwcx-communications-workspace.sh",
            "install-wwcx-communications-workspace.sh",
        )
    )

    for forbidden in (
        "nginx",
        "apache",
        "haproxy",
        "caddy",
        "messages.send",
        "mail.send",
        "telephony.call.originate",
        "quarantine release",
    ):
        assert forbidden not in combined.lower()
