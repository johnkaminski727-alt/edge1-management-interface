#!/usr/bin/env python3
"""Read-only repository expectation vs observed Edge1 snapshot comparator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT = "wwcx.edge1.drift.v1"
VALID_RELATIONS = {"MATCH", "REPOSITORY_NEWER", "LIVE_NEWER", "UNKNOWN", "UNVERIFIABLE"}


def _result(command: Any) -> Any:
    if isinstance(command, dict) and command.get("status") == "ok":
        return command.get("result")
    return None


def _add(items: list[dict[str, Any]], *, component: str, classification: str,
         expected: Any, observed: Any, source: str, severity: str,
         required: bool, recommendation: str, authorized: bool = False,
         rollback: str = "No mutation performed by drift detector.") -> None:
    items.append({
        "component": component,
        "classification": classification,
        "expected_state": expected,
        "observed_state": observed,
        "evidence_source": source,
        "severity": severity,
        "change_appears_required": required,
        "recommended_next_action": recommendation,
        "mutation_authorization_exists": authorized,
        "rollback_considerations": rollback,
    })


def compare(expected: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    observed_contract = observed.get("contract")
    if observed_contract != "wwcx.edge1.snapshot.v1":
        _add(items, component="snapshot.contract", classification="UNVERIFIABLE",
             expected="wwcx.edge1.snapshot.v1", observed=observed_contract,
             source="observed.contract", severity="high", required=False,
             recommendation="Capture a compatible Edge1 snapshot before making deployment decisions.")

    expected_head = expected.get("repositories", {}).get("edge1", {}).get("head")
    observed_head = _result(observed.get("repository", {}).get("head"))
    relation = expected.get("repositories", {}).get("edge1", {}).get("relation_to_observed", "UNKNOWN")
    if relation not in VALID_RELATIONS:
        relation = "UNKNOWN"
    if expected_head and observed_head:
        if expected_head == observed_head:
            classification = "MATCH"
            severity = "info"
            required = False
            recommendation = "No repository-head action required."
        elif relation in {"REPOSITORY_NEWER", "LIVE_NEWER"}:
            classification = relation
            severity = "medium"
            required = False
            recommendation = "Review the commit delta and preserve newer working state before any deployment decision."
        else:
            classification = "VERSION_DRIFT"
            severity = "medium"
            required = False
            recommendation = "Establish commit ancestry before deciding whether repository or live state should change."
        _add(items, component="repository.head", classification=classification,
             expected=expected_head, observed=observed_head, source="repository.head",
             severity=severity, required=required, recommendation=recommendation)
    else:
        _add(items, component="repository.head", classification="UNKNOWN",
             expected=expected_head, observed=observed_head, source="repository.head",
             severity="medium", required=False,
             recommendation="Collect both expected and observed repository heads.")

    expected_digests = {
        row.get("path"): row.get("sha256")
        for row in expected.get("configuration_digests", [])
        if row.get("path") and row.get("sha256")
    }
    observed_digests = {
        row.get("path"): row.get("sha256")
        for row in observed.get("repository", {}).get("configuration_digests", [])
        if row.get("status") == "ok" and row.get("path") and row.get("sha256")
    }
    for path, expected_digest in sorted(expected_digests.items()):
        observed_digest = observed_digests.get(path)
        if observed_digest is None:
            classification, severity = "UNVERIFIABLE", "medium"
            recommendation = "Capture the approved configuration digest on Edge1."
        elif observed_digest == expected_digest:
            classification, severity = "MATCH", "info"
            recommendation = "No configuration action required."
        else:
            classification, severity = "CONFIGURATION_DRIFT", "high"
            recommendation = "Review the exact configuration difference; do not overwrite live state automatically."
        _add(items, component=f"config:{path}", classification=classification,
             expected=expected_digest, observed=observed_digest, source="repository.configuration_digests",
             severity=severity, required=False, recommendation=recommendation)

    service_rows = {
        row.get("unit"): row
        for row in observed.get("services", {}).get("relevant", [])
        if row.get("unit")
    }
    for unit in expected.get("services", {}).get("required_active", []):
        row = service_rows.get(unit)
        active = (row or {}).get("properties", {}).get("ActiveState")
        if active == "active":
            classification, severity, required = "MATCH", "info", False
            recommendation = "No service-state action required."
        elif row is None or active is None:
            classification, severity, required = "UNVERIFIABLE", "medium", False
            recommendation = "Capture service state before deciding on a restart or deployment."
        else:
            classification, severity, required = "SERVICE_STATE_DRIFT", "high", True
            recommendation = "Diagnose the service failure first; use a bounded restart only if separately justified."
        _add(items, component=f"service:{unit}", classification=classification,
             expected="active", observed=active, source="services.relevant",
             severity=severity, required=required, recommendation=recommendation,
             rollback="If a later service change is approved, preserve the pre-change service/config state and verification evidence.")

    boundaries = expected.get("security_boundaries", {})
    listeners = _result(observed.get("network", {}).get("listening_sockets"))
    if boundaries.get("operations_api_loopback_only") is True:
        if not isinstance(listeners, str):
            classification, severity = "UNVERIFIABLE", "high"
            observed_listener = None
            recommendation = "Capture listening sockets before asserting the Operations API boundary."
        else:
            wildcard = any(token in listeners for token in ("0.0.0.0:8097", "[::]:8097", "*:8097"))
            loopback = any(token in listeners for token in ("127.0.0.1:8097", "[::1]:8097"))
            if wildcard:
                classification, severity = "SECURITY_BOUNDARY_DRIFT", "critical"
                observed_listener = "wildcard:8097"
                recommendation = "Stop deployment progression and investigate the unexpected public/wildcard Operations API listener."
            elif loopback:
                classification, severity = "MATCH", "info"
                observed_listener = "loopback:8097"
                recommendation = "No listener-boundary action required."
            else:
                classification, severity = "UNVERIFIABLE", "high"
                observed_listener = "8097 not observed"
                recommendation = "Verify Operations API service/listener state before claiming the boundary is healthy."
        _add(items, component="security.operations_api_listener", classification=classification,
             expected="loopback-only:8097", observed=observed_listener, source="network.listening_sockets",
             severity=severity, required=classification == "SECURITY_BOUNDARY_DRIFT",
             recommendation=recommendation,
             rollback="No automatic network or firewall mutation is authorized by this detector.")

    mismatches = [item for item in items if item["classification"] != "MATCH"]
    critical = [item for item in items if item["severity"] == "critical"]
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "read_only": True,
        "mutation_performed": False,
        "summary": {
            "result": "FAIL" if critical else ("WARN" if mismatches else "PASS"),
            "total_items": len(items),
            "match_count": len(items) - len(mismatches),
            "non_match_count": len(mismatches),
            "critical_count": len(critical),
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("observed", type=Path)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    observed = json.loads(args.observed.read_text(encoding="utf-8"))
    print(json.dumps(compare(expected, observed), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
