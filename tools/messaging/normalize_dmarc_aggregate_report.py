#!/usr/bin/env python3
"""Normalize a verified DMARC aggregate XML report offline.

The normalizer verifies a restricted evidence manifest and raw-report SHA-256,
rejects DTD/entity content, parses the expected WW.CX p=none policy, replaces
source IP addresses with report-scoped SHA-256 pseudonyms, and emits bounded
authentication/alignment evidence. It never accesses a mailbox, performs a
network request, stores raw XML or IP addresses, inspects credentials, changes
DNS, or sends mail.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST_CONTRACT = "wwcx.dmarc-aggregate-evidence.v1"
OUTPUT_CONTRACT = "wwcx.dmarc-aggregate-normalization.v1"
HEX64 = set("0123456789abcdef")
MAX_XML_BYTES = 20 * 1024 * 1024
MAX_RECORDS = 10000
MAX_MESSAGE_COUNT = 10_000_000


class DmarcAggregateError(RuntimeError):
    """Raised when aggregate evidence is unsafe, malformed, or out of scope."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DmarcAggregateError(f"unable to read aggregate manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise DmarcAggregateError("aggregate manifest must be a JSON object")
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "contract",
        "captured_at",
        "source_authentication",
        "source_verified",
        "mailbox_identity_sha256",
        "evidence_sha256",
        "attachment_name_sha256",
        "expected_policy_domain",
        "raw_report_restricted",
        "credentials_included",
        "message_content_included",
    }
    if set(value) != expected:
        raise DmarcAggregateError("aggregate manifest keys are invalid")
    if value["contract"] != MANIFEST_CONTRACT:
        raise DmarcAggregateError("unsupported aggregate manifest contract")
    if value["source_authentication"] != "authenticated_mailbox_attachment":
        raise DmarcAggregateError("aggregate source authentication is unsupported")
    if value["source_verified"] is not True:
        raise DmarcAggregateError("aggregate source is not verified")
    if value["expected_policy_domain"] != "ww.cx":
        raise DmarcAggregateError("aggregate policy domain is not WW.CX")
    if value["raw_report_restricted"] is not True:
        raise DmarcAggregateError("raw aggregate report is not marked restricted")
    if value["credentials_included"] is not False:
        raise DmarcAggregateError("aggregate evidence includes credentials")
    if value["message_content_included"] is not False:
        raise DmarcAggregateError("aggregate evidence includes message content")
    for key in ("mailbox_identity_sha256", "evidence_sha256", "attachment_name_sha256"):
        if not _is_sha256(value[key]):
            raise DmarcAggregateError(f"aggregate manifest {key} is invalid")
    try:
        parsed = datetime.fromisoformat(str(value["captured_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DmarcAggregateError("captured_at is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise DmarcAggregateError("captured_at must include a timezone")
    return value


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in list(element) if _local(item.tag) == name]


def _child(element: ET.Element, name: str, *, required: bool = True) -> ET.Element | None:
    matches = _children(element, name)
    if len(matches) > 1:
        raise DmarcAggregateError(f"aggregate XML has duplicate {name} elements")
    if not matches:
        if required:
            raise DmarcAggregateError(f"aggregate XML is missing {name}")
        return None
    return matches[0]


def _text(element: ET.Element, name: str, *, required: bool = True) -> str:
    child = _child(element, name, required=required)
    if child is None:
        return ""
    value = (child.text or "").strip()
    if required and not value:
        raise DmarcAggregateError(f"aggregate XML {name} is empty")
    return value


def _integer(element: ET.Element, name: str, minimum: int, maximum: int) -> int:
    value = _text(element, name)
    try:
        number = int(value)
    except ValueError as exc:
        raise DmarcAggregateError(f"aggregate XML {name} is not an integer") from exc
    if not minimum <= number <= maximum:
        raise DmarcAggregateError(f"aggregate XML {name} is outside the allowed range")
    return number


def _domain(value: str, label: str) -> str:
    normalized = value.strip().rstrip(".").casefold()
    if not normalized or "@" in normalized or " " in normalized or "." not in normalized:
        raise DmarcAggregateError(f"aggregate {label} domain is invalid")
    return normalized


def _aligned(domain: str, policy_domain: str, mode: str) -> bool:
    if mode == "s":
        return domain == policy_domain
    return domain == policy_domain or domain.endswith("." + policy_domain)


def _result(value: str, label: str) -> str:
    normalized = value.strip().casefold()
    allowed = {
        "pass",
        "fail",
        "neutral",
        "softfail",
        "temperror",
        "permerror",
        "none",
        "policy",
        "unknown",
    }
    if normalized not in allowed:
        raise DmarcAggregateError(f"unsupported {label} result")
    return normalized


def _epoch_iso(value: int) -> str:
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError) as exc:
        raise DmarcAggregateError("aggregate report epoch is invalid") from exc


def _auth_results(record: ET.Element, policy_domain: str, adkim: str, aspf: str) -> dict[str, Any]:
    auth = _child(record, "auth_results")
    dkim_entries: list[dict[str, Any]] = []
    for item in _children(auth, "dkim"):
        domain = _domain(_text(item, "domain"), "DKIM")
        result = _result(_text(item, "result"), "DKIM")
        selector = _text(item, "selector", required=False)
        dkim_entries.append(
            {
                "domain": domain,
                "selector_sha256": hashlib.sha256(selector.encode("utf-8")).hexdigest() if selector else None,
                "result": result,
                "aligned": result == "pass" and _aligned(domain, policy_domain, adkim),
            }
        )
    spf_entries: list[dict[str, Any]] = []
    for item in _children(auth, "spf"):
        domain = _domain(_text(item, "domain"), "SPF")
        result = _result(_text(item, "result"), "SPF")
        scope = _text(item, "scope", required=False).casefold() or "mfrom"
        if scope not in {"mfrom", "helo"}:
            raise DmarcAggregateError("unsupported SPF scope")
        spf_entries.append(
            {
                "domain": domain,
                "scope": scope,
                "result": result,
                "aligned": scope == "mfrom" and result == "pass" and _aligned(domain, policy_domain, aspf),
            }
        )
    if not dkim_entries and not spf_entries:
        raise DmarcAggregateError("aggregate record has no authentication results")
    return {
        "dkim": dkim_entries,
        "spf": spf_entries,
        "dkim_aligned_pass": any(item["aligned"] for item in dkim_entries),
        "spf_aligned_pass": any(item["aligned"] for item in spf_entries),
    }


def normalize(raw_xml: bytes, manifest: dict[str, Any]) -> dict[str, Any]:
    evidence = validate_manifest(manifest)
    if len(raw_xml) < 32 or len(raw_xml) > MAX_XML_BYTES:
        raise DmarcAggregateError("aggregate XML size is outside the allowed range")
    lowered = raw_xml.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise DmarcAggregateError("aggregate XML contains prohibited DTD or entity declarations")
    digest = hashlib.sha256(raw_xml).hexdigest()
    if digest != evidence["evidence_sha256"]:
        raise DmarcAggregateError("raw aggregate SHA-256 does not match the manifest")
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise DmarcAggregateError(f"unable to parse aggregate XML: {exc}") from exc
    if _local(root.tag) != "feedback":
        raise DmarcAggregateError("aggregate XML root is not feedback")

    metadata = _child(root, "report_metadata")
    policy = _child(root, "policy_published")
    org_name = _text(metadata, "org_name")[:200]
    report_email = _text(metadata, "email")
    report_id = _text(metadata, "report_id")
    date_range = _child(metadata, "date_range")
    begin = _integer(date_range, "begin", 0, 4_102_444_800)
    end = _integer(date_range, "end", begin, 4_102_444_800)

    policy_domain = _domain(_text(policy, "domain"), "policy")
    if policy_domain != evidence["expected_policy_domain"]:
        raise DmarcAggregateError("aggregate policy domain does not match the manifest")
    adkim = _text(policy, "adkim", required=False).casefold() or "r"
    aspf = _text(policy, "aspf", required=False).casefold() or "r"
    p_value = _text(policy, "p").casefold()
    sp_value = _text(policy, "sp", required=False).casefold() or p_value
    pct = int(_text(policy, "pct", required=False) or "100")
    if adkim != "r" or aspf != "r" or p_value != "none" or sp_value != "none" or pct != 100:
        raise DmarcAggregateError("aggregate report does not match the approved WW.CX p=none policy")

    records = _children(root, "record")
    if not records or len(records) > MAX_RECORDS:
        raise DmarcAggregateError("aggregate record count is outside the allowed range")
    normalized_records: list[dict[str, Any]] = []
    total_messages = 0
    aligned_messages = 0
    receiver_mismatch_messages = 0
    for index, record in enumerate(records, start=1):
        row = _child(record, "row")
        identifiers = _child(record, "identifiers")
        source_ip_text = _text(row, "source_ip")
        try:
            source_ip = ipaddress.ip_address(source_ip_text)
        except ValueError as exc:
            raise DmarcAggregateError("aggregate source_ip is invalid") from exc
        count = _integer(row, "count", 1, MAX_MESSAGE_COUNT)
        total_messages += count
        if total_messages > MAX_MESSAGE_COUNT:
            raise DmarcAggregateError("aggregate total message count exceeds the allowed limit")
        evaluated = _child(row, "policy_evaluated")
        disposition = _text(evaluated, "disposition").casefold()
        if disposition not in {"none", "quarantine", "reject"}:
            raise DmarcAggregateError("aggregate disposition is unsupported")
        receiver_dkim = _result(_text(evaluated, "dkim"), "receiver DKIM")
        receiver_spf = _result(_text(evaluated, "spf"), "receiver SPF")
        header_from = _domain(_text(identifiers, "header_from"), "header_from")
        envelope_from_text = _text(identifiers, "envelope_from", required=False)
        envelope_from = _domain(envelope_from_text, "envelope_from") if envelope_from_text else None
        auth = _auth_results(record, policy_domain, adkim, aspf)
        dmarc_aligned = auth["dkim_aligned_pass"] or auth["spf_aligned_pass"]
        if dmarc_aligned:
            aligned_messages += count
        receiver_aligned = receiver_dkim == "pass" or receiver_spf == "pass"
        mismatch = receiver_aligned != dmarc_aligned
        if mismatch:
            receiver_mismatch_messages += count
        source_pseudonym = hashlib.sha256(
            (digest + ":" + source_ip.compressed).encode("utf-8")
        ).hexdigest()
        normalized_records.append(
            {
                "record_index": index,
                "report_scoped_source_sha256": source_pseudonym,
                "source_ip_family": source_ip.version,
                "count": count,
                "header_from": header_from,
                "envelope_from": envelope_from,
                "disposition": disposition,
                "receiver_policy_dkim": receiver_dkim,
                "receiver_policy_spf": receiver_spf,
                "computed_dkim_aligned_pass": auth["dkim_aligned_pass"],
                "computed_spf_aligned_pass": auth["spf_aligned_pass"],
                "computed_dmarc_aligned": dmarc_aligned,
                "receiver_computation_mismatch": mismatch,
                "auth_results": {"dkim": auth["dkim"], "spf": auth["spf"]},
            }
        )

    return {
        "contract": OUTPUT_CONTRACT,
        "normalized_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_evidence_sha256": digest,
        "source_authentication": "authenticated_mailbox_attachment",
        "source_verified": True,
        "report": {
            "organization": org_name,
            "report_email_sha256": hashlib.sha256(report_email.casefold().encode("utf-8")).hexdigest(),
            "report_id_sha256": hashlib.sha256(report_id.encode("utf-8")).hexdigest(),
            "begin": _epoch_iso(begin),
            "end": _epoch_iso(end),
            "policy_domain": policy_domain,
            "policy": "none",
            "subdomain_policy": "none",
            "dkim_alignment_mode": "relaxed",
            "spf_alignment_mode": "relaxed",
            "percentage": 100,
        },
        "summary": {
            "record_count": len(normalized_records),
            "message_count": total_messages,
            "aligned_message_count": aligned_messages,
            "unaligned_message_count": total_messages - aligned_messages,
            "receiver_computation_mismatch_count": receiver_mismatch_messages,
            "source_authorization_assessed": False,
            "unknown_source_count": None,
        },
        "records": normalized_records,
        "raw_source_ip_stored": False,
        "stable_cross_report_source_identifier_created": False,
        "raw_xml_stored": False,
        "credentials_inspected": False,
        "mailbox_access_performed": False,
        "network_access_performed": False,
        "dns_modified": False,
        "message_sent": False,
    }


def _inside_repo(path: pathlib.Path) -> bool:
    resolved = path.resolve()
    repo = ROOT.resolve()
    return resolved == repo or repo in resolved.parents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for label, path in (("aggregate XML", args.xml), ("manifest", args.manifest)):
        if _inside_repo(path):
            print(f"refusing {label} evidence inside the Git working tree", file=sys.stderr)
            return 2
    if args.output is not None and _inside_repo(args.output):
        print("refusing normalized aggregate output inside the Git working tree", file=sys.stderr)
        return 2
    try:
        report = normalize(args.xml.read_bytes(), load_json(args.manifest))
    except (OSError, DmarcAggregateError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
