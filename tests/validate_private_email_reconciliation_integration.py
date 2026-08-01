#!/usr/bin/env python3
"""End-to-end synthetic validation for Private Email normalization and reconciliation."""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile

from tools.messaging import normalize_namecheap_private_email_support as private_normalizer
from tools.messaging import reconcile_mail_provider_objects as reconciler

ROOT = pathlib.Path(__file__).resolve().parents[1]
HUB_PATH = ROOT / "config" / "messaging" / "inbound-mail-hub.json"
IDENTITIES_PATH = ROOT / "config" / "messaging" / "mail-identities.json"

hub = json.loads(HUB_PATH.read_text(encoding="utf-8"))
identities = json.loads(IDENTITIES_PATH.read_text(encoding="utf-8"))
routes = hub["routing"]["routes"]
managed_domains = sorted(hub["domains"])

private_objects = []
for address, route in sorted(routes.items()):
    if address.endswith("@ww.cx"):
        private_objects.append(
            {
                "address": address,
                "object_type": "alias",
                "destinations": [route["destination"]],
                "active": True,
                "receives_mail": True,
                "can_send": True,
                "quota_bytes": None,
                "notes": "Synthetic complete Private Email alias evidence.",
            }
        )

private_objects.extend(
    [
        {
            "address": "john-inbox@ww.cx",
            "object_type": "mailbox",
            "destinations": [],
            "active": True,
            "receives_mail": True,
            "can_send": False,
            "quota_bytes": 1073741824,
            "notes": "Synthetic private delivery mailbox.",
        },
        {
            "address": "maildesk@ww.cx",
            "object_type": "mailbox",
            "destinations": [],
            "active": True,
            "receives_mail": True,
            "can_send": False,
            "quota_bytes": 1073741824,
            "notes": "Synthetic shared delivery mailbox.",
        },
        {
            "address": "noreply@ww.cx",
            "object_type": "system_account",
            "destinations": [],
            "active": True,
            "receives_mail": False,
            "can_send": True,
            "quota_bytes": None,
            "notes": "Synthetic outbound-only sender.",
        },
    ]
)

support_evidence = {
    "contract": "wwcx.namecheap-private-email-support-evidence.v1",
    "captured_at": "2026-08-01T18:00:00Z",
    "read_only": True,
    "provider_family": "namecheap_private_email",
    "domain": "ww.cx",
    "ticket_reference": "SYNTHETIC-COMPLETE",
    "subscription": {
        "status": "active",
        "plan": "Synthetic validation plan",
        "expiry_date": "2027-01-01",
        "mailbox_slots": 3,
    },
    "objects": private_objects,
    "catch_all": {"behavior": "reject", "destination": None},
    "dkim": {"status": "enabled", "selector": "synthetic"},
    "provider_rules": {
        "forwarding_reviewed": True,
        "filters_reviewed": True,
        "rules_present": False,
        "notes": "Synthetic no-rule state.",
    },
    "completeness": {
        "subscription": True,
        "mailboxes": True,
        "aliases_and_groups": True,
        "catch_all": True,
        "quotas": True,
        "forwarding": True,
        "dkim": True,
        "sender_capability": True,
        "filters_and_rules": True,
    },
}

with tempfile.TemporaryDirectory() as temp_dir:
    evidence_dir = pathlib.Path(temp_dir) / "private-email-evidence"
    evidence_dir.mkdir()
    files = {
        "support-evidence.json": json.dumps(support_evidence, indent=2) + "\n",
        "provider-response.txt": "Synthetic provider response for repository validation only.\n",
    }
    manifest = []
    for filename, content in sorted(files.items()):
        path = evidence_dir / filename
        path.write_text(content, encoding="utf-8")
        manifest.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {filename}")
    (evidence_dir / "SHA256SUMS").write_text(
        "\n".join(manifest) + "\n",
        encoding="ascii",
    )

    private_inventory, private_summary = private_normalizer.normalize_support_capture(
        evidence_dir
    )

assert private_summary["complete"] is True
assert private_summary["warnings"] == []
reconciler.validate_inventory(private_inventory, "private inventory")

shared_objects = []
for address, route in sorted(routes.items()):
    if not address.endswith("@ww.cx"):
        domain = address.rsplit("@", 1)[1]
        shared_objects.append(
            {
                "address": address,
                "domain": domain,
                "object_type": "forwarder",
                "destinations": [route["destination"]],
                "receives_mail": True,
                "can_send": True,
                "active": True,
                "access_class": (
                    "private_john"
                    if route["destination"] == "john-inbox@ww.cx"
                    else "shared_role"
                ),
                "quota_bytes": None,
                "notes": "Synthetic complete non-WW.CX provider object.",
            }
        )

non_ww_domains = [domain for domain in managed_domains if domain != "ww.cx"]
shared_inventory = {
    "contract": "wwcx.provider-mail-objects.v1",
    "provider_id": "synthetic-non-ww-provider",
    "provider_family": "other",
    "captured_at": "2026-08-01T18:00:00Z",
    "source": {
        "method": "manual_export",
        "read_only": True,
        "evidence_files": ["synthetic-validation-only"],
        "account_reference": None,
    },
    "objects": shared_objects,
    "default_addresses": [
        {"domain": domain, "behavior": "reject", "destination": None}
        for domain in non_ww_domains
    ],
    "domain_routing": [
        {"domain": domain, "mode": "local"} for domain in non_ww_domains
    ],
}

report = reconciler.reconcile(
    hub,
    identities,
    [private_inventory, shared_inventory],
)

assert report["summary"]["expected_route_count"] == 37
assert report["summary"]["missing_expected_count"] == 0
assert report["summary"]["inactive_expected_count"] == 0
assert report["summary"]["forwarder_mismatch_count"] == 0
assert report["summary"]["forwarder_cycle_count"] == 0
assert report["summary"]["critical_gap_count"] == 0
assert report["summary"]["warning_count"] == 0
assert report["summary"]["ready_for_pilot"] is True
assert all(item["status"] == "exact_forwarder" for item in report["route_results"])
assert all(item["status"] == "present" for item in report["internal_mailboxes"])

print("Private Email normalization and reconciliation integration passed")
print("Synthetic complete provider evidence reconciles all 37 canonical routes")
print("Internal private/shared mailboxes are observed with canonical access classes")
print("No network, provider, mailbox, DNS, or delivery change is performed")
