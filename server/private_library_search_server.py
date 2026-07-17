#!/usr/bin/env python3
"""Local read-only server for the Edge1 Private Library Search UI."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "src" / "web"
FIXTURE_PATHS = [
    WEB_ROOT / "fixtures" / "private-library-search-results.json",
    WEB_ROOT / "private-library-search.fixture.json",
]
ALLOWED_COLLECTIONS = {"operations"}
DEFAULT_LIMIT = 10
MAX_LIMIT = 20
DEFAULT_GATEWAY_ROOT = Path("/opt/bigbird-ai-gateway")
DEFAULT_LIBRARY_DB = Path("/var/lib/bigbird-ai-library/library.sqlite3")


def clamp_limit(raw_limit: str | None) -> int:
    if not raw_limit:
        return DEFAULT_LIMIT
    try:
        value = int(raw_limit)
    except ValueError:
        return DEFAULT_LIMIT
    return min(max(value, 1), MAX_LIMIT)


def load_fixture() -> dict[str, Any]:
    for path in FIXTURE_PATHS:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"query": "", "collection": "operations", "mode": "fixture", "results": []}


def result_attr(item: Any, name: str, fallback: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, fallback)
    return getattr(item, name, fallback)


def normalize_result(item: Any, index: int) -> dict[str, Any]:
    document_id = result_attr(item, "document_id", "") or result_attr(item, "id", "")
    chunk_index = result_attr(item, "chunk_index", "")
    result_id = result_attr(item, "id", "")
    if document_id and chunk_index != "":
        result_id = f"{document_id}:{chunk_index}"
    elif document_id:
        result_id = document_id
    return {
        "id": str(result_id or result_attr(item, "file_id", "") or f"result-{index + 1}"),
        "title": str(result_attr(item, "title", "") or result_attr(item, "name", "") or result_attr(item, "safe_name", "") or "Untitled result"),
        "collection": str(result_attr(item, "collection", "") or result_attr(item, "collection_name", "") or "operations"),
        "path": str(result_attr(item, "source_path", "") or result_attr(item, "path", "") or result_attr(item, "committed_path", "") or result_attr(item, "source", "")),
        "updated_at": str(result_attr(item, "updated_at", "") or result_attr(item, "updated", "") or result_attr(item, "created_at", "")),
        "score": float(result_attr(item, "score", 0) or result_attr(item, "rank", 0) or 0),
        "snippet": str(result_attr(item, "excerpt", "") or result_attr(item, "snippet", "") or result_attr(item, "summary", "") or result_attr(item, "text", "")),
    }


def extract_results(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("results", "documents", "items", "matches", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_results(value)
            if nested:
                return nested
    return []


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


def direct_search_enabled() -> bool:
    return os.environ.get("EDGE1_LIBRARY_DIRECT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def direct_search(query: str, collection: str, limit: int) -> dict[str, Any] | None:
    if not direct_search_enabled():
        return None

    gateway_root = Path(os.environ.get("EDGE1_BIGBIRD_GATEWAY_ROOT", str(DEFAULT_GATEWAY_ROOT)))
    library_db = Path(os.environ.get("BB_LIBRARY_DB", str(DEFAULT_LIBRARY_DB)))
    if not gateway_root.is_dir() or not library_db.is_file():
        return None

    gateway_root_string = str(gateway_root)
    if gateway_root_string not in sys.path:
        sys.path.insert(0, gateway_root_string)

    try:
        engine = importlib.import_module("app.library_engine")
        if engine.contains_secret(query):
            return {
                "query": query,
                "collection": collection,
                "mode": "live_direct",
                "results": [],
                "warning": "query rejected by secret-pattern guard",
            }
        raw_results = engine.search_library(
            library_db,
            query,
            [collection],
            limit=limit,
            excerpt_chars=1200,
        )
    except Exception:
        return None

    return {
        "query": query,
        "collection": collection,
        "mode": "live_direct",
        "results": [normalize_result(item, index) for index, item in enumerate(raw_results)],
    }


def backend_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    extra = os.environ.get("EDGE1_LIBRARY_SEARCH_HEADERS", "").strip()
    if extra:
        try:
            parsed = json.loads(extra)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            headers.update({str(key): str(value) for key, value in parsed.items()})
    return headers


def query_backend(backend_url: str, query: str, collection: str, limit: int) -> dict[str, Any]:
    method = os.environ.get("EDGE1_LIBRARY_SEARCH_METHOD", "GET").strip().upper()
    headers = backend_headers()

    if method == "POST":
        body = json.dumps({"q": query, "query": query, "collection": collection, "limit": limit}).encode("utf-8")
        headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            backend_url,
            data=body,
            headers=headers,
            method="POST",
        )
    else:
        params = urllib.parse.urlencode(
            {"q": query, "query": query, "collection": collection, "limit": str(limit)}
        )
        separator = "&" if "?" in backend_url else "?"
        request = urllib.request.Request(
            backend_url + separator + params,
            headers=headers,
            method="GET",
        )

    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    raw_results = extract_results(payload)
    return {
        "query": query,
        "collection": collection,
        "mode": "live",
        "results": [normalize_result(item, index) for index, item in enumerate(raw_results[:limit])],
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

    direct = direct_search(query, collection, limit)
    if direct is not None:
        return HTTPStatus.OK, direct

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
