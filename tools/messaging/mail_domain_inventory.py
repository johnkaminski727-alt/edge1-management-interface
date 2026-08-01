#!/usr/bin/env python3
"""Capture a read-only DNS inventory for the managed mail domains.

The tool queries two public DNS-over-HTTPS resolvers, records normalized
answers, compares resolver consensus, and infers only the likely mail-provider
family from published MX hostnames. It never changes DNS or provider state.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DOMAINS = (
    "ww.cx",
    "creekco.ca",
    "spiritcreekgardens.com",
    "scgardens.ca",
    "omegafx.com",
)

RESOLVERS = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "google": "https://dns.google/resolve",
}

TYPE_CODES = {
    "A": 1,
    "NS": 2,
    "CNAME": 5,
    "MX": 15,
    "TXT": 16,
}


def _normalize_record_data(record_type: str, data: str) -> str:
    value = data.strip()
    if record_type in {"NS", "CNAME"}:
        return value.rstrip(".").casefold()
    if record_type == "MX":
        parts = value.split()
        if len(parts) == 2 and parts[0].isdigit():
            return f"{int(parts[0])} {parts[1].rstrip('.').casefold()}"
    if record_type == "TXT" and len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def query_resolver(
    resolver_name: str,
    resolver_url: str,
    name: str,
    record_type: str,
    timeout: float,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({"name": name, "type": record_type})
    request = urllib.request.Request(
        f"{resolver_url}?{params}",
        headers={
            "Accept": "application/dns-json",
            "User-Agent": "wwcx-mail-domain-inventory/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # network evidence must preserve partial failures
        return {
            "resolver": resolver_name,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "answers": [],
        }

    expected_type = TYPE_CODES[record_type]
    answers = sorted(
        {
            _normalize_record_data(record_type, str(item.get("data", "")))
            for item in payload.get("Answer", [])
            if item.get("type") == expected_type and str(item.get("data", "")).strip()
        }
    )
    return {
        "resolver": resolver_name,
        "status": "ok",
        "dns_status": int(payload.get("Status", -1)),
        "authenticated_data": bool(payload.get("AD", False)),
        "answers": answers,
    }


def consensus(responses: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in responses if item.get("status") == "ok"]
    answer_sets = [tuple(item["answers"]) for item in successful]
    agreed = bool(answer_sets) and len(set(answer_sets)) == 1
    union = sorted({answer for item in successful for answer in item["answers"]})
    return {
        "successful_resolvers": len(successful),
        "resolver_count": len(responses),
        "agreed": agreed,
        "answers": list(answer_sets[0]) if agreed else union,
    }


def infer_mail_provider(mx_records: list[str]) -> dict[str, str]:
    hosts = [item.split(maxsplit=1)[-1].casefold() for item in mx_records]
    joined = " ".join(hosts)
    if any(token in joined for token in ("aspmx.l.google.com", "smtp.google.com", "googlemail.com")):
        return {"provider_family": "google_workspace", "confidence": "high"}
    if "mail.protection.outlook.com" in joined:
        return {"provider_family": "microsoft_365", "confidence": "high"}
    if "privateemail.com" in joined:
        return {"provider_family": "namecheap_private_email", "confidence": "high"}
    if "jellyfish.systems" in joined:
        return {"provider_family": "namecheap_shared_hosting", "confidence": "high"}
    if "mx.cloudflare.net" in joined:
        return {"provider_family": "cloudflare_email_routing", "confidence": "high"}
    if "zoho." in joined:
        return {"provider_family": "zoho_mail", "confidence": "high"}
    if not hosts:
        return {"provider_family": "no_published_mx_observed", "confidence": "high"}
    if len(hosts) == 1 and hosts[0] in DOMAINS:
        return {"provider_family": "domain_local_or_cpanel", "confidence": "medium"}
    return {"provider_family": "unclassified", "confidence": "low"}


def build_inventory(timeout: float) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    domains: dict[str, Any] = {}
    for domain in DOMAINS:
        records: dict[str, Any] = {}
        for record_name, query_name, record_type in (
            ("mx", domain, "MX"),
            ("spf_txt", domain, "TXT"),
            ("dmarc_txt", f"_dmarc.{domain}", "TXT"),
            ("ns", domain, "NS"),
        ):
            responses = [
                query_resolver(name, url, query_name, record_type, timeout)
                for name, url in RESOLVERS.items()
            ]
            record_consensus = consensus(responses)
            if record_name == "spf_txt":
                record_consensus["answers"] = [
                    item for item in record_consensus["answers"] if item.casefold().startswith("v=spf1")
                ]
            if record_name == "dmarc_txt":
                record_consensus["answers"] = [
                    item for item in record_consensus["answers"] if item.casefold().startswith("v=dmarc1")
                ]
            records[record_name] = {
                "query_name": query_name,
                "record_type": record_type,
                "consensus": record_consensus,
                "resolver_evidence": responses,
            }
        provider = infer_mail_provider(records["mx"]["consensus"]["answers"])
        domains[domain] = {
            "records": records,
            "provider_inference": provider,
        }
    return {
        "contract": "wwcx.mail-domain-dns-inventory.v1",
        "observed_at": observed_at,
        "read_only": True,
        "resolvers": list(RESOLVERS),
        "domains": domains,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1.0 <= args.timeout <= 60.0:
        raise SystemExit("--timeout must be between 1 and 60 seconds")
    inventory = build_inventory(args.timeout)
    rendered = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    successful = sum(
        1
        for domain in inventory["domains"].values()
        if domain["records"]["mx"]["consensus"]["successful_resolvers"] > 0
    )
    return 0 if successful == len(DOMAINS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
