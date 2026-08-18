import json
from types import SimpleNamespace

import pytest

from tools.safe_change_runner import PHASES, execute, load_registry, public_plan


def operation():
    return {"description": "test reversible operation", "automatic_rollback_on_verify_failure": False, "phases": {phase: {"argv": ["true"], "argv_id": phase.lower(), "timeout_seconds": 5} for phase in PHASES}}


def test_initial_registry_is_empty_and_valid():
    registry = load_registry()
    assert registry == {"version": 1, "operations": {}}


def test_registry_requires_all_six_phases(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1, "operations": {"x": {"phases": {"PLAN": {"argv": ["true"], "timeout_seconds": 1}}}}}))
    with pytest.raises(ValueError, match="define exactly"):
        load_registry(path)


def test_public_plan_does_not_expose_argv():
    plan = public_plan("x", operation())
    assert [item["phase"] for item in plan["phases"]] == list(PHASES)
    assert all("argv" not in item for item in plan["phases"])


def test_execute_stops_before_apply_when_validation_fails(monkeypatch):
    calls = []
    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        code = 1 if len(calls) == 3 else 0
        return SimpleNamespace(returncode=code, stdout="", stderr="")
    monkeypatch.setattr("tools.safe_change_runner.subprocess.run", fake_run)
    results = execute("x", operation())
    assert [item["phase"] for item in results] == ["PLAN", "BACKUP", "VALIDATE"]
    assert len(calls) == 3


def test_verify_failure_does_not_auto_rollback_by_default(monkeypatch):
    calls = []
    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        code = 1 if len(calls) == 5 else 0
        return SimpleNamespace(returncode=code, stdout="", stderr="")
    monkeypatch.setattr("tools.safe_change_runner.subprocess.run", fake_run)
    results = execute("x", operation())
    assert [item["phase"] for item in results] == ["PLAN", "BACKUP", "VALIDATE", "APPLY", "VERIFY"]
    assert "ROLLBACK" not in [item["phase"] for item in results]
