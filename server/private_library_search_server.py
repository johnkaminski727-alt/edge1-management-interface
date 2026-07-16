#!/usr/bin/env python3
"""Local read-only server for the Edge1 Private Library Search UI."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "web"
FIXTURE_PATH = WEB_ROOT / "fixtures" / "private-library-search-results.json"
ALLOWED_COLLECTIONS = {"operations"}
DEFAULT_LIMIT = 10
MAX_LIMIT = 25


def clamp_limit(raw_limit: str | None) -> int:
    if not raw_limit:
        return DEFAULT_LIMIT
    try:
        value = int(raw_limit)
    except ValueError:
        return DEFAULT_LIMIT
    return min(max(value, 1), MAX_LIMIT)


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def normalize_result(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or item.get("document_id") or f"result-{index + 1}"),
        "title": str(item.get("title") or item.get("name") or "Untitled result"),
        "collection": str(item.get("collection") or "operations"),
        "path": str(item.get("path") or item.get("source") or ""),
        "updated_at": str(item.get("updated_at") or item.get("updated") or ""),
        "score": float(item.get("score") or 0),
        "snippet": str(item.get("snippet") or item.get("summary") or ""),
    }


def filter_fixture(query: str, collection: str, limit: int) -> dict[str, Any]:
    payload = load_fixture()
    query_terms = [term.casefold() for term in query.split() if term.strip()]
    results = []

    for index, item in enumerate(payload.get("results", [])):
        result = normalize_result(item, index)
        if result["collection"] != collection:
            continue
        haystack = " ".join(
            [result["title"], result["path"], result["snippet"], result["id"]]
        ).casefold()
        if query_terms and not all(term in haystack for term in query_terms):
            continue
        results.append(result)

    if query_terms and not results:
        results = [
            normalize_result(item, index)
            for index, item in enumerate(payload.get("results", []))
            if normalize_result(item, index)["collection"] == collection
        ]

    return {
        "query": query,
        "collection": collection,
        "mode": "fixture",
        "results": results[:limit],
    }


def query_backend(backend_url: str, query: str, collection: str, limit: int) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {"q": query, "collection": collection, "limit": str(limit)}
    )
    separator = "&" if "?" in backend_url else "?"
    request = urllib.request.Request(
        backend_url + separator + params,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    raw_results = payload.get("results", payload if isinstance(payload, list) else [])
    return {
        "query": query,
        "collection": collection,
        "mode": "live",
        "results": [
            normalize_result(item, index)
            for index, item in enumerate(raw_results[:limit])
            if isinstance(item, dict)
        ],
    }


def search_payload(query: str, collection: str, limit: int) -> tuple[int, dict[str, Any]]:
    if collection not in ALLOWED_COLLECTIONS:
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "unsupported_collection",
                "message": "Only the operations collection is available.",
            },
        )

    backend_url = os.environ.get("EDGE1_LIBRARY_SEARCH_URL", "").strip()
    if backend_url:
        try:
            return HTTPStatus.OK, query_backend(backend_url, query, collection, limit)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            fallback = filter_fixture(query, collection, limit)
            fallback["mode"] = "fixture_fallback"
            fallback["warning"] = f"live backend unavailable: {exc.__class__.__name__}"
            return HTTPStatus.OK, fallback

    return HTTPStatus.OK, filter_fixture(query, collection, limit)


class PrivateLibrarySearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/private-library/search":
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get("q", [""])[0].strip()
            collection = params.get("collection", ["operations"])[0].strip()
            limit = clamp_limit(params.get("limit", [None])[0])
            status, payload = search_payload(query, collection, limit)
            self.send_json(status, payload)
            return

        super().do_GET()

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PrivateLibrarySearchHandler)
    print(f"Serving Edge1 Private Library Search on http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

