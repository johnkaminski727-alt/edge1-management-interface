import json
from types import SimpleNamespace

from tools.acceptance_evidence import LIVE_READ_ONLY_CHECKS, SOURCE_CHECKS, run_check, write_evidence


def test_command_registry_contains_only_fixed_argv():
    all_checks = SOURCE_CHECKS + LIVE_READ_ONLY_CHECKS
    assert all(isinstance(name, str) and name for name, _argv, _timeout in all_checks)
    assert all(isinstance(argv, tuple) and argv and all(isinstance(x, str) for x in argv) for _name, argv, _timeout in all_checks)
    assert all(timeout > 0 for _name, _argv, timeout in all_checks)
    flattened = " ".join(" ".join(argv) for _name, argv, _timeout in all_checks)
    assert "shell=True" not in flattened
    assert "rm " not in flattened
    assert "systemctl restart" not in flattened


def test_run_check_records_success(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
    monkeypatch.setattr("tools.acceptance_evidence.subprocess.run", fake_run)
    result = run_check("fixed", ("python3", "-V"), 5, root=tmp_path)
    assert result["status"] == "pass"
    assert result["exit_code"] == 0
    assert result["argv_id"] == "fixed"


def test_evidence_is_timestamped_summarized_and_hashed(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.acceptance_evidence.stamp", lambda: "20260818T063500Z")
    results = [{"name": "one", "started_utc": "2026-08-18T06:35:00Z", "argv_id": "one", "exit_code": 0, "status": "pass", "stdout": "ok", "stderr": ""}]
    directory = write_evidence(tmp_path, results, live_read_only=False)
    assert directory.name == "20260818T063500Z"
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["overall"] == "pass"
    sums = (directory / "SHA256SUMS").read_text()
    assert "one.json" in sums
    assert "summary.json" in sums
