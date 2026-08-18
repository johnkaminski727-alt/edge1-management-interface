from __future__ import annotations

from server import edge1_acceptance as acceptance
from server import edge1_state_manifest as state


def base_snapshot():
    return {
        "contract": "wwcx.edge1.snapshot.v1",
        "read_only": True,
        "mutation_performed": False,
        "collected_at_utc": "2026-08-18T00:00:00+00:00",
        "repository": {"head": {"status": "ok", "result": "abc"}},
        "services": {
            "operations_api_health": {"status": "ok", "result": {"status": "ok"}},
            "bigbird_health": {"status": "ok", "result": {"status": "ok"}},
            "failed": {"status": "ok", "result": ""},
        },
    }


def test_acceptance_pass_when_complete_evidence_matches():
    expected = {"repositories": {"edge1": {"head": "abc"}}, "security_boundaries": {}}
    drift = {"items": [
        {"component": "repository.head", "classification": "MATCH", "severity": "info"},
        {"component": "security.operations_api_listener", "classification": "MATCH", "severity": "info"},
    ]}
    report = acceptance.assess(expected, base_snapshot(), drift)
    assert report["result"] == "PASS"
    assert report["counts"]["FAIL"] == 0


def test_acceptance_blocks_missing_private_transport_evidence():
    expected = {"security_boundaries": {"operator_private": True, "generic_exec_disabled": True}}
    report = acceptance.assess(expected, base_snapshot(), {"items": []})
    assert report["result"] == "BLOCKED"
    ids = {row["id"] for row in report["unresolved_blockers"]}
    assert "security.operator_private_transport" in ids
    assert "security.generic_exec_disabled" in ids


def test_acceptance_fails_critical_security_drift():
    drift = {"items": [{
        "component": "security.operations_api_listener",
        "classification": "SECURITY_BOUNDARY_DRIFT",
        "severity": "critical",
        "recommended_next_action": "investigate",
    }]}
    report = acceptance.assess({}, base_snapshot(), drift)
    assert report["result"] == "FAIL"


def test_manifest_keeps_live_unverified_when_no_snapshot():
    manifest = state.build_manifest(expected={"repositories": {"edge1": {"head": "abc", "branch": "main"}}})
    assert manifest["repositories"]["edge1"]["head"] == "abc"
    assert manifest["live"]["last_verified_at"] is None
    assert manifest["blockers"][0]["id"] == "fresh-live-edge1-snapshot"
    assert manifest["secrets_present"] is False


def test_manifest_promotes_only_compatible_snapshot_to_live_verified():
    manifest = state.build_manifest(expected={"repositories": {"edge1": {"head": "abc"}}}, snapshot=base_snapshot())
    assert manifest["evidence_classification"] == "LIVE-VERIFIED"
    assert manifest["live"]["last_verified_at"] == "2026-08-18T00:00:00+00:00"
