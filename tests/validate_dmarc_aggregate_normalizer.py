#!/usr/bin/env python3
"""Validate minimized offline WW.CX DMARC aggregate normalization."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/messaging/normalize_dmarc_aggregate_report.py"
SCHEMA = ROOT / "schemas/messaging/dmarc-aggregate-evidence.schema.json"
DOC = ROOT / "docs/messaging-operations/dmarc-aggregate-normalization-20260804.md"
SPEC = importlib.util.spec_from_file_location("dmarc_normalizer", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load DMARC aggregate normalizer")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def aggregate_xml(*, report_id: str = "report-sensitive-id", policy: str = "none", domain: str = "ww.cx") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>Example Receiver</org_name>
    <email>dmarc-reports@example.net</email>
    <report_id>{report_id}</report_id>
    <date_range><begin>1785812400</begin><end>1785898800</end></date_range>
  </report_metadata>
  <policy_published>
    <domain>{domain}</domain><adkim>r</adkim><aspf>r</aspf><p>{policy}</p><sp>{policy}</sp><pct>100</pct>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.10</source_ip><count>4</count>
      <policy_evaluated><disposition>none</disposition><dkim>pass</dkim><spf>fail</spf></policy_evaluated>
    </row>
    <identifiers><envelope_from>ww.cx</envelope_from><header_from>ww.cx</header_from></identifiers>
    <auth_results>
      <dkim><domain>ww.cx</domain><selector>default</selector><result>pass</result></dkim>
      <spf><domain>spf.privateemail.com</domain><scope>mfrom</scope><result>fail</result></spf>
    </auth_results>
  </record>
  <record>
    <row>
      <source_ip>2001:db8::20</source_ip><count>2</count>
      <policy_evaluated><disposition>none</disposition><dkim>fail</dkim><spf>fail</spf></policy_evaluated>
    </row>
    <identifiers><envelope_from>bounce.example.net</envelope_from><header_from>ww.cx</header_from></identifiers>
    <auth_results>
      <dkim><domain>example.net</domain><selector>foreign-selector</selector><result>pass</result></dkim>
      <spf><domain>example.net</domain><scope>mfrom</scope><result>pass</result></spf>
    </auth_results>
  </record>
</feedback>
""".encode("utf-8")


def manifest(raw: bytes) -> dict:
    return {
        "contract": MODULE.MANIFEST_CONTRACT,
        "captured_at": "2026-08-04T04:00:00+00:00",
        "source_authentication": "authenticated_mailbox_attachment",
        "source_verified": True,
        "mailbox_identity_sha256": "a" * 64,
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "attachment_name_sha256": "b" * 64,
        "expected_policy_domain": "ww.cx",
        "raw_report_restricted": True,
        "credentials_included": False,
        "message_content_included": False,
    }


def rejects(raw: bytes, evidence: dict, label: str) -> None:
    try:
        MODULE.normalize(raw, evidence)
    except MODULE.DmarcAggregateError:
        return
    raise RuntimeError(f"unsafe aggregate evidence did not fail closed: {label}")


for path in (TOOL, SCHEMA, DOC):
    check(path.is_file(), f"missing {path}")
    check(path.stat().st_size > 500, f"undersized {path}")

schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
check(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", "schema draft mismatch")
check(schema["properties"]["contract"]["const"] == MODULE.MANIFEST_CONTRACT, "schema contract mismatch")
check(schema["additionalProperties"] is False, "schema permits extra fields")
check(schema["properties"]["source_verified"]["const"] is True, "schema permits unverified source")
check(schema["properties"]["credentials_included"]["const"] is False, "schema permits credentials")

raw = aggregate_xml()
report = MODULE.normalize(raw, manifest(raw))
serialized = json.dumps(report, sort_keys=True)
check(report["contract"] == MODULE.OUTPUT_CONTRACT, "output contract mismatch")
check(report["source_verified"] is True, "source verification was lost")
check(report["report"]["policy_domain"] == "ww.cx", "policy domain mismatch")
check(report["report"]["policy"] == "none", "policy was not monitoring-only")
check(report["report"]["dkim_alignment_mode"] == "relaxed", "DKIM mode mismatch")
check(report["report"]["spf_alignment_mode"] == "relaxed", "SPF mode mismatch")
check(report["summary"] == {
    "record_count": 2,
    "message_count": 6,
    "aligned_message_count": 4,
    "unaligned_message_count": 2,
    "receiver_computation_mismatch_count": 0,
    "source_authorization_assessed": False,
    "unknown_source_count": None,
}, "aggregate summary mismatch")
check(len(report["records"]) == 2, "record count mismatch")
first, second = report["records"]
check(first["source_ip_family"] == 4, "IPv4 family mismatch")
check(second["source_ip_family"] == 6, "IPv6 family mismatch")
check(first["computed_dkim_aligned_pass"] is True, "aligned DKIM pass missed")
check(first["computed_dmarc_aligned"] is True, "aligned record failed")
check(second["computed_dmarc_aligned"] is False, "unaligned record passed")
check(first["auth_results"]["dkim"][0]["selector_sha256"] == hashlib.sha256(b"default").hexdigest(), "selector was not hashed")
check(second["auth_results"]["spf"][0]["scope"] == "mfrom", "SPF scope mismatch")
check(first["report_scoped_source_sha256"] != second["report_scoped_source_sha256"], "source pseudonyms collided")
for key in (
    "raw_source_ip_stored",
    "stable_cross_report_source_identifier_created",
    "raw_xml_stored",
    "credentials_inspected",
    "mailbox_access_performed",
    "network_access_performed",
    "dns_modified",
    "message_sent",
):
    check(report[key] is False, f"safety marker changed: {key}")
for forbidden in (
    "192.0.2.10",
    "2001:db8::20",
    "dmarc-reports@example.net",
    "report-sensitive-id",
    "default",
    "foreign-selector",
):
    check(forbidden.casefold() not in serialized.casefold(), f"normalized output leaked {forbidden}")

repeat = MODULE.normalize(raw, manifest(raw))
check(
    [item["report_scoped_source_sha256"] for item in repeat["records"]]
    == [item["report_scoped_source_sha256"] for item in report["records"]],
    "same-report source pseudonyms are not deterministic",
)
changed_raw = aggregate_xml(report_id="different-report-id")
changed = MODULE.normalize(changed_raw, manifest(changed_raw))
check(
    changed["records"][0]["report_scoped_source_sha256"]
    != first["report_scoped_source_sha256"],
    "source pseudonym is stable across reports",
)

bad_hash = manifest(raw)
bad_hash["evidence_sha256"] = "f" * 64
rejects(raw, bad_hash, "hash mismatch")
unverified = manifest(raw)
unverified["source_verified"] = False
rejects(raw, unverified, "unverified source")
credentialed = manifest(raw)
credentialed["credentials_included"] = True
rejects(raw, credentialed, "credential-bearing evidence")
wrong_policy = aggregate_xml(policy="reject")
rejects(wrong_policy, manifest(wrong_policy), "enforcement policy")
wrong_domain = aggregate_xml(domain="example.com")
wrong_domain_manifest = manifest(wrong_domain)
rejects(wrong_domain, wrong_domain_manifest, "wrong policy domain")
dtd = b'<?xml version="1.0"?><!DOCTYPE feedback [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><feedback>&xxe;</feedback>'
rejects(dtd, manifest(dtd), "DTD/entity declaration")
malformed = b"<feedback><broken>"
rejects(malformed, manifest(malformed), "malformed XML")

mismatch_raw = raw.replace(b"<dkim>pass</dkim>", b"<dkim>fail</dkim>", 1)
mismatch_report = MODULE.normalize(mismatch_raw, manifest(mismatch_raw))
check(mismatch_report["summary"]["receiver_computation_mismatch_count"] == 4, "receiver/computation mismatch was not counted")

with tempfile.TemporaryDirectory() as temporary:
    folder = pathlib.Path(temporary)
    xml_path = folder / "report.xml"
    manifest_path = folder / "manifest.json"
    output_path = folder / "normalized.json"
    xml_path.write_bytes(raw)
    manifest_path.write_text(json.dumps(manifest(raw)), encoding="utf-8")
    process = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--xml", str(xml_path),
            "--manifest", str(manifest_path),
            "--output", str(output_path),
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(process.returncode == 0, f"aggregate CLI failed: {process.stderr}")
    cli = json.loads(output_path.read_text(encoding="utf-8"))
    check(cli["summary"]["message_count"] == 6, "aggregate CLI summary mismatch")
    check("192.0.2.10" not in output_path.read_text(encoding="utf-8"), "aggregate CLI leaked source IP")

    forbidden_output = ROOT / "var" / "forbidden-dmarc-aggregate.json"
    refused = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--xml", str(xml_path),
            "--manifest", str(manifest_path),
            "--output", str(forbidden_output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check(refused.returncode == 2, "aggregate CLI accepted output inside Git tree")
    check("refusing normalized aggregate output" in refused.stderr, "worktree refusal reason changed")
    check(not forbidden_output.exists(), "aggregate CLI wrote forbidden output")

source = TOOL.read_text(encoding="utf-8")
for required in (
    "replaces",
    "source IP addresses with report-scoped SHA-256 pseudonyms",
    "prohibited DTD or entity declarations",
    "raw aggregate SHA-256 does not match the manifest",
    "approved WW.CX p=none policy",
    "receiver_computation_mismatch",
    "source_authorization_assessed",
    "stable_cross_report_source_identifier_created",
    "refusing normalized aggregate output inside the Git working tree",
):
    check(required in source, f"normalizer missing safety marker: {required}")
for prohibited in (
    "requests.",
    "urllib.request",
    "subprocess.",
    "imaplib",
    "poplib",
    "smtplib",
    "socket.",
    "ET.parse(",
):
    check(prohibited not in source, f"normalizer contains prohibited operation: {prohibited}")

print("DMARC aggregate normalization validation passed")
print("Aligned/unaligned, IPv4/IPv6, receiver mismatch, forged, DTD, and policy-drift cases verified")
print("Raw IPs, report email/ID, selectors, XML, credentials, and message content are not retained")
print("Source identifiers are deterministic only within one report and authorization remains unassessed")
print("No mailbox, network, DNS mutation, provider activation, or message traffic occurs")
