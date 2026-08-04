#!/usr/bin/env python3
"""Capture a read-only public DNS inventory for configured DKIM candidates.

The tool queries two DNS-over-HTTPS resolvers and records minimized evidence
about published DKIM TXT records. It does not log in to a provider, enumerate a
DNS zone, modify DNS, inspect credentials, activate a sender, or send mail.
A published key is evidence of a DNS record only; signing and alignment require
separate message-header evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


CONTRACT = "wwcx.mail-dkim-dns-inventory.v1"
CANDIDATE_CONTRACT = "wwcx.mail-dkim-selector-candidates.v1"
RESOLVERS = {
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "google": "https://dns.google/resolve",
}
TXT_TYPE = 16
SELECTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
TAG_RE = re.compile(r"(?:^|;)\s*([A-Za-z][A-Za-z0-9]*)\s*=\s*([^;]*)")
QUOTED_CHUNK_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


class DkimInventoryError(RuntimeError):
    """Raised when candidate configuration or evidence is invalid."""


def load_candidates(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DkimInventoryError(f"unable to read selector candidates: {exc}") from exc
    if not isinstance(value, dict) or value.get("contract") != CANDIDATE_CONTRACT:
        raise DkimInventoryError("unsupported selector-candidate contract")
    if value.get("read_only") is not True:
        raise DkimInventoryError("selector candidates must be read-only")
    domains = value.get("domains")
    if not isinstance(domains, dict) or not domains:
        raise DkimInventoryError("selector candidates must contain domains")
    for domain, config in domains.items():
        if not isinstance(domain, str) or not domain or not isinstance(config, dict):
            raise DkimInventoryError("selector candidate domain is invalid")
        candidates = config.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise DkimInventoryError(f"{domain} must contain selector candidates")
        selectors: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise DkimInventoryError(f"{domain} selector candidate is invalid")
            selector = candidate.get("selector")
            if not isinstance(selector, str) or not SELECTOR_RE.fullmatch(selector):
                raise DkimInventoryError(f"{domain} selector is invalid")
            if candidate.get("authoritative_for_activation") is not False:
                raise DkimInventoryError("candidate discovery must not authorize activation")
            selectors.append(selector.casefold())
        if len(selectors) != len(set(selectors)):
            raise DkimInventoryError(f"{domain} selector candidates must be unique")
    boundary = value.get("activation_boundary")
    if not isinstance(boundary, dict) or not boundary or any(item is not False for item in boundary.values()):
        raise DkimInventoryError("selector candidate activation boundary is invalid")
    return value


def normalize_txt_data(value: str) -> str:
    raw = value.strip()
    chunks = QUOTED_CHUNK_RE.findall(raw)
    if chunks:
        decoded: list[str] = []
        for chunk in chunks:
            try:
                decoded.append(json.loads('"' + chunk + '"'))
            except json.JSONDecodeError:
                decoded.append(chunk.replace('\\"', '"').replace('\\\\', '\\'))
        return "".join(decoded).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        raw = raw[1:-1]
    return raw.strip()


def parse_tags(record: str) -> dict[str, str]:
    return {match.group(1).casefold(): match.group(2).strip() for match in TAG_RE.finditer(record)}


def minimized_answer(record: str) -> dict[str, Any]:
    normalized = normalize_txt_data(record)
    tags = parse_tags(normalized)
    key = tags.get("p", "")
    is_dkim = tags.get("v", "").casefold() == "dkim1"
    return {
        "record_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "record_character_count": len(normalized),
        "dkim_version_present": is_dkim,
        "key_type": tags.get("k", "rsa").casefold() if is_dkim else None,
        "public_key_character_count": len(key),
        "public_key_present": bool(key),
        "record_shape_valid": bool(is_dkim and key),
    }


def query_resolver(
    resolver_name: str,
    resolver_url: str,
    query_name: str,
    timeout: float,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({"name": query_name, "type": "TXT"})
    request = urllib.request.Request(
        f"{resolver_url}?{params}",
        headers={
            "Accept": "application/dns-json",
            "User-Agent": "wwcx-mail-dkim-inventory/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "resolver": resolver_name,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "dns_status": None,
            "authenticated_data": False,
            "answers": [],
        }

    answers = sorted(
        {
            normalize_txt_data(str(item.get("data", "")))
            for item in payload.get("Answer", [])
            if item.get("type") == TXT_TYPE and str(item.get("data", "")).strip()
        }
    )
    return {
        "resolver": resolver_name,
        "status": "ok",
        "dns_status": int(payload.get("Status", -1)),
        "authenticated_data": bool(payload.get("AD", False)),
        "answers": answers,
    }


def analyze_responses(responses: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in responses if item.get("status") == "ok"]
    answer_sets = [tuple(item.get("answers", [])) for item in successful]
    agreed = bool(answer_sets) and len(set(answer_sets)) == 1
    agreed_answers = list(answer_sets[0]) if agreed else sorted(
        {answer for item in successful for answer in item.get("answers", [])}
    )
    dkim_answers = [item for item in agreed_answers if parse_tags(item).get("v", "").casefold() == "dkim1"]
    minimized = [minimized_answer(item) for item in dkim_answers]

    if not successful:
        state = "query_failed"
    elif not agreed:
        state = "resolver_disagreement"
    elif not agreed_answers:
        state = "not_observed"
    elif not dkim_answers:
        state = "non_dkim_txt_observed"
    elif any(item["record_shape_valid"] for item in minimized):
        state = "published_valid_shape"
    else:
        state = "published_malformed_shape"

    return {
        "state": state,
        "successful_resolvers": len(successful),
        "resolver_count": len(responses),
        "resolver_consensus": agreed,
        "txt_answer_count": len(agreed_answers),
        "dkim_answer_count": len(dkim_answers),
        "records": minimized,
        "resolver_evidence": [
            {
                "resolver": item.get("resolver"),
                "status": item.get("status"),
                "dns_status": item.get("dns_status"),
                "authenticated_data": item.get("authenticated_data", False),
                "answer_count": len(item.get("answers", [])),
                "answer_sha256": [
                    hashlib.sha256(answer.encode("utf-8")).hexdigest()
                    for answer in item.get("answers", [])
                ],
                **({"error": item.get("error")} if item.get("status") == "error" else {}),
            }
            for item in responses
        ],
    }


def build_inventory(
    candidate_config: dict[str, Any],
    timeout: float,
    query: Callable[[str, str, str, float], dict[str, Any]] = query_resolver,
) -> dict[str, Any]:
    domains: dict[str, Any] = {}
    successful_queries = 0
    total_queries = 0
    for domain, domain_config in sorted(candidate_config["domains"].items()):
        candidates: list[dict[str, Any]] = []
        for candidate in domain_config["candidates"]:
            selector = candidate["selector"]
            query_name = f"{selector}._domainkey.{domain}"
            responses = [
                query(name, url, query_name, timeout)
                for name, url in RESOLVERS.items()
            ]
            analysis = analyze_responses(responses)
            total_queries += 1
            if analysis["successful_resolvers"] > 0:
                successful_queries += 1
            candidates.append(
                {
                    "selector": selector,
                    "query_name": query_name,
                    "basis": candidate["basis"],
                    "authoritative_for_activation": False,
                    "analysis": analysis,
                }
            )
        domains[domain] = {
            "provider_family": domain_config["provider_family"],
            "selection_status": domain_config["selection_status"],
            "candidates": candidates,
        }

    published = [
        (domain, candidate["selector"])
        for domain, value in domains.items()
        for candidate in value["candidates"]
        if candidate["analysis"]["state"] == "published_valid_shape"
    ]
    return {
        "contract": CONTRACT,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "read_only": True,
        "resolvers": list(RESOLVERS),
        "domains": domains,
        "summary": {
            "candidate_query_count": total_queries,
            "queries_with_resolver_response": successful_queries,
            "published_valid_shape_candidates": [
                {"domain": domain, "selector": selector} for domain, selector in published
            ],
            "dkim_dns_candidate_observed": bool(published),
            "provider_signing_verified": False,
            "header_alignment_verified": False,
            "ready_for_sender_activation": False,
            "credentials_inspected": False,
            "dns_modified": False,
            "message_sent": False,
        },
    }


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=repo_root / "config/messaging/mail-dkim-selector-candidates.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1.0 <= args.timeout <= 60.0:
        raise SystemExit("--timeout must be between 1 and 60 seconds")
    try:
        candidates = load_candidates(args.candidates)
        inventory = build_inventory(candidates, args.timeout)
    except DkimInventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(
        inventory,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(rendered)
    return 0 if inventory["summary"]["queries_with_resolver_response"] == inventory["summary"]["candidate_query_count"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
