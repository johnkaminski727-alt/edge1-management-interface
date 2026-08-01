#!/usr/bin/env python3
"""Validate the durable live-acceptance record for the anomaly API and panel."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/telephony/telephony-anomaly-api-panel-live-acceptance-20260801.md"
README = ROOT / "docs/telephony/README.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    require(RECORD.is_file(), f"missing acceptance record: {RECORD.relative_to(ROOT)}")
    require(README.is_file(), f"missing telephony README: {README.relative_to(ROOT)}")

    record = RECORD.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    required_record_markers = (
        "Accepted for private, loopback-only, read-only operational use on Edge1",
        "cd17fc882eb2714fb7ec64c920d561628f7848f7",
        "20260801T214954Z",
        "20260801T215006Z",
        "a96ce9e6fbcf021d9a21ccfd163f5b89d5408840d495a468f265ee1db2849b2a",
        "9a16816c21324b4f0ad9f072ca05ec8f92fdd64620f176bc03955b9cd3573be5",
        "103befc105fa0bd2684125930d534860e92cca6efc6f30fe0051c5c153e42c43",
        "runtime_api_source_match=yes",
        "runtime_platform_source_match=yes",
        "runtime_anomaly_source_match=yes",
        "console_anomaly_contract=passed",
        "telephony_anomaly_api_panel_live_acceptance=passed",
        "anomaly_live_deployment=passed",
        "rollback_required=no",
        "HTTP `404` before the refresh to HTTP `200`",
        "127.0.0.1:8096",
        "127.0.0.1:8099",
        "Git index owner: wwadmin:wwadmin",
        "Git index mode: 0600",
    )
    for marker in required_record_markers:
        require(marker in record, f"acceptance record missing marker: {marker}")

    safety_markers = (
        "does not authorize live CDR",
        "carrier or end-to-end interoperability",
        "production call, message, or DTMF behavior",
        "emergency-calling readiness",
        "automated notification",
        "public listener, firewall, DNS, certificate, or authentication changes",
    )
    for marker in safety_markers:
        require(marker.lower() in record.lower(), f"acceptance record missing safety boundary: {marker}")

    require("telephony-anomaly-api-panel-live-acceptance-20260801.md" in readme,
            "telephony README does not link the live acceptance record")
    require("are live-accepted on Edge1" in readme,
            "telephony README still lacks live anomaly acceptance state")
    require("are repository-complete but are not yet deployed" not in readme,
            "telephony README retains stale console deployment status")
    require("The aggregate anomaly evaluator is repository-only" not in readme,
            "telephony README retains stale anomaly repository-only status")

    print("telephony anomaly live acceptance record validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
