from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "server" / "edge1_snapshot.py"
ALLOWLIST_PATH = REPO_ROOT / "config" / "edge1-operations-allowlist.json"
SPEC = importlib.util.spec_from_file_location("edge1_snapshot", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_commands_are_fixed_absolute_candidates_and_read_only_contract():
    for name, (candidates, arguments, timeout, mode) in MODULE.COMMANDS.items():
        assert name
        assert candidates
        assert all(candidate.startswith("/") for candidate in candidates)
        assert isinstance(arguments, tuple)
        assert 1 <= timeout <= 60
        assert mode in {"text", "json", "digest"}
    assert MODULE.COMMANDS["firewall"][3] == "digest"
    assert MODULE.COMMANDS["critical_errors"][3] == "digest"


def test_unknown_command_and_service_fail_closed():
    try:
        MODULE.run_fixed("shell")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown command must be rejected")
    try:
        MODULE._service("user-controlled.service")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown unit must be rejected")


def test_digest_mode_never_returns_raw_output():
    completed = mock.Mock(returncode=0, stdout=b"rule one\nrule two\n", stderr=b"")
    with mock.patch.object(MODULE, "_exe", return_value="/usr/sbin/nft"), \
         mock.patch.object(MODULE.subprocess, "run", return_value=completed):
        result = MODULE.run_fixed("firewall")
    encoded = json.dumps(result, sort_keys=True)
    assert result["result"]["line_count"] == 2
    assert result["result"]["raw_output_returned"] is False
    assert "rule one" not in encoded
    assert "rule two" not in encoded


def test_collect_snapshot_is_self_describing_and_non_mutating():
    fixed = {"status": "unavailable"}
    with mock.patch.object(MODULE, "run_fixed", return_value=fixed), \
         mock.patch.object(MODULE, "_service", side_effect=lambda unit: {"unit": unit, "status": "unavailable"}), \
         mock.patch.object(MODULE, "_config_digests", return_value=[]), \
         mock.patch.object(MODULE, "_timezone", return_value="UTC"), \
         mock.patch.object(MODULE, "_uptime", return_value=123.0), \
         mock.patch.object(MODULE, "_os_release", return_value={"id": "debian"}), \
         mock.patch.object(MODULE, "_memory", return_value={}):
        snapshot = MODULE.collect_snapshot()
    assert snapshot["contract"] == MODULE.CONTRACT
    assert snapshot["schema_version"] == 1
    assert snapshot["read_only"] is True
    assert snapshot["mutation_performed"] is False
    assert snapshot["secret_values_returned"] is False
    assert snapshot["identity"]["configured_timezone"] == "UTC"
    assert len(snapshot["services"]["relevant"]) == len(MODULE.SERVICES)


def test_markdown_contains_identity_and_safety_flags():
    snapshot = {
        "contract": MODULE.CONTRACT,
        "collected_at_utc": "2026-08-18T00:00:00+00:00",
        "mutation_performed": False,
        "secret_values_returned": False,
        "identity": {"hostname": "edge1", "configured_timezone": "UTC", "kernel": "6.x"},
        "services": {"relevant": [{"unit": "edge1-operator-mcp.service", "status": "unavailable"}]},
    }
    rendered = MODULE.render_markdown(snapshot)
    assert "# Edge1 Read-Only Snapshot" in rendered
    assert "edge1-operator-mcp.service" in rendered
    assert "Mutation performed: `false`" in rendered
    assert "Secret values returned: `false`" in rendered


def test_snapshot_operations_action_is_fixed_and_non_mutating():
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    assert payload["actions"]["edge1.snapshot"] == {
        "argv": ["python3", "server/edge1_snapshot.py", "--format", "json"],
        "mutating": False,
        "timeout_seconds": 180,
    }


def test_source_contains_no_mutating_interfaces():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = (
        "os.remove(", "os.unlink(", ".unlink(", ".rename(", ".replace(",
        ".write_text(", ".write_bytes(", "chmod(", "chown(", "mkdir(",
        "systemctl restart", "systemctl start", "systemctl stop", "systemctl enable",
        "iptables -", "nft add", "nft delete", "git fetch", "git pull", "git reset",
        "--output",
    )
    for token in forbidden:
        assert token not in source
