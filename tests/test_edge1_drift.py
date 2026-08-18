import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "server" / "edge1_drift.py"
SPEC = importlib.util.spec_from_file_location("edge1_drift", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def snapshot(head="abc", listener="127.0.0.1:8097"):
    return {
        "contract": "wwcx.edge1.snapshot.v1",
        "repository": {
            "head": {"status": "ok", "result": head},
            "configuration_digests": [{"path": "config/a", "status": "ok", "sha256": "d1"}],
        },
        "services": {"relevant": [{"unit": "svc.service", "properties": {"ActiveState": "active"}}]},
        "network": {"listening_sockets": {"status": "ok", "result": listener}},
    }


def expected(head="abc"):
    return {
        "repositories": {"edge1": {"head": head}},
        "configuration_digests": [{"path": "config/a", "sha256": "d1"}],
        "services": {"required_active": ["svc.service"]},
        "security_boundaries": {"operations_api_loopback_only": True},
    }


def test_all_matching_passes():
    result = MODULE.compare(expected(), snapshot())
    assert result["summary"]["result"] == "PASS"
    assert all(item["classification"] == "MATCH" for item in result["items"])


def test_hash_difference_is_version_drift_not_auto_replacement():
    result = MODULE.compare(expected("new"), snapshot("old"))
    item = next(row for row in result["items"] if row["component"] == "repository.head")
    assert item["classification"] == "VERSION_DRIFT"
    assert item["change_appears_required"] is False
    assert item["mutation_authorization_exists"] is False


def test_configuration_drift_is_high_but_non_mutating():
    live = snapshot()
    live["repository"]["configuration_digests"][0]["sha256"] = "live"
    result = MODULE.compare(expected(), live)
    item = next(row for row in result["items"] if row["component"] == "config:config/a")
    assert item["classification"] == "CONFIGURATION_DRIFT"
    assert item["severity"] == "high"
    assert result["mutation_performed"] is False


def test_inactive_required_service_is_service_state_drift():
    live = snapshot()
    live["services"]["relevant"][0]["properties"]["ActiveState"] = "failed"
    result = MODULE.compare(expected(), live)
    item = next(row for row in result["items"] if row["component"] == "service:svc.service")
    assert item["classification"] == "SERVICE_STATE_DRIFT"
    assert item["change_appears_required"] is True


def test_wildcard_operations_listener_is_critical_security_drift():
    result = MODULE.compare(expected(), snapshot(listener="0.0.0.0:8097"))
    item = next(row for row in result["items"] if row["component"] == "security.operations_api_listener")
    assert item["classification"] == "SECURITY_BOUNDARY_DRIFT"
    assert item["severity"] == "critical"
    assert result["summary"]["result"] == "FAIL"


def test_missing_evidence_is_unverifiable_not_assumed_match():
    live = snapshot()
    live["repository"]["head"] = {"status": "unavailable"}
    live["network"]["listening_sockets"] = {"status": "unavailable"}
    result = MODULE.compare(expected(), live)
    classes = {item["component"]: item["classification"] for item in result["items"]}
    assert classes["repository.head"] == "UNKNOWN"
    assert classes["security.operations_api_listener"] == "UNVERIFIABLE"
