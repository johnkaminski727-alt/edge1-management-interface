#!/usr/bin/env python3
"""Discover a local read-only private library search backend for Edge1."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "private-library-search.env"
TEST_QUERY = "VPN"
COLLECTION = "operations"
LIMIT = 5


@dataclass(frozen=True)
class Candidate:
    url: str
    method: str = "GET"


def discover_ports() -> list[int]:
    ports = {8787}
    try:
        output = subprocess.run(
            ["ss", "-ltn"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout
    except OSError:
        return sorted(ports)

    for line in output.splitlines():
        if "127.0.0.1:" not in line:
            continue
        for token in line.split():
            if token.startswith("127.0.0.1:"):
                try:
                    port = int(token.rsplit(":", 1)[1])
                except ValueError:
                    continue
                if port in {8787, 8000, 8080, 8090, 8091, 5000, 5001}:
                    ports.add(port)
    return sorted(ports)


def candidate_paths() -> list[str]:
    return [
        "/api/private-library/search",
        "/api/library/search",
        "/api/v1/library/search",
        "/api/v1/private-library/search",
        "/api/search",
        "/library/search",
        "/private-library/search",
        "/search",
        "/v1/search",
        "/v1/library/search",
    ]


def candidates() -> list[Candidate]:
    found = []
    for port in discover_ports():
        for path in candidate_paths():
            base = f"http://127.0.0.1:{port}{path}"
            found.append(Candidate(base, "GET"))
            found.append(Candidate(base, "POST"))
    return found


def parse_json_response(body: bytes) -> Any:
    text = body.decode("utf-8", errors="replace")
    return json.loads(text)


def extract_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "documents", "items", "matches", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_results(value)
            if nested:
                return nested
    return []


def probe(candidate: Candidate) -> tuple[bool, str, int]:
    headers = {"Accept": "application/json"}
    try:
        if candidate.method == "POST":
            body = json.dumps(
                {
                    "q": TEST_QUERY,
                    "query": TEST_QUERY,
                    "collection": COLLECTION,
                    "limit": LIMIT,
                }
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"
            request = urllib.request.Request(
                candidate.url,
                data=body,
                headers=headers,
                method="POST",
            )
        else:
            params = urllib.parse.urlencode(
                {
                    "q": TEST_QUERY,
                    "query": TEST_QUERY,
                    "collection": COLLECTION,
                    "limit": str(LIMIT),
                }
            )
            separator = "&" if "?" in candidate.url else "?"
            request = urllib.request.Request(
                candidate.url + separator + params,
                headers=headers,
                method="GET",
            )

        with urllib.request.urlopen(request, timeout=2) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read(200000)
        if status < 200 or status >= 300:
            return False, f"HTTP {status}", 0
        if "json" not in content_type.lower():
            return False, f"non-json {content_type}", 0
        payload = parse_json_response(body)
        results = extract_results(payload)
        if not results:
            return False, "json response had no result list", 0
        return True, "compatible JSON search response", len(results)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}", 0
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        return False, exc.__class__.__name__, 0


def write_config(candidate: Candidate) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        "\n".join(
            [
                f'EDGE1_LIBRARY_SEARCH_URL="{candidate.url}"',
                f'EDGE1_LIBRARY_SEARCH_METHOD="{candidate.method}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(CONFIG_PATH, 0o600)


def main() -> int:
    print("Probing localhost library search candidates...")
    failures = []
    for candidate in candidates():
        ok, reason, count = probe(candidate)
        label = f"{candidate.method} {candidate.url}"
        if ok:
            write_config(candidate)
            print(f"FOUND {label} ({count} result(s))")
            print(f"Wrote {CONFIG_PATH}")
            return 0
        failures.append((label, reason))

    print("No compatible backend found.")
    print("Last probe results:")
    for label, reason in failures[-20:]:
        print(f"- {label}: {reason}")
    print("The wrapper can still run in fixture mode until the backend route is known.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

