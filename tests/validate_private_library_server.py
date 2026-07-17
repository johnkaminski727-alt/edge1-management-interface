#!/usr/bin/env python3
"""Validate the Edge1 private library search server behavior."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import textwrap
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "server" / "private_library_search_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("private_library_search_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load private_library_search_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class MockBackendHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "results": [
                        {
                            "document_id": "live-get",
                            "title": "Live GET result",
                            "collection": "operations",
                            "snippet": "GET backend works",
                        }
                    ]
                }
            ).encode("utf-8")
        )

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "documents": [
                        {
                            "document_id": "live-post",
                            "title": "Live POST result",
                            "collection": "operations",
                            "snippet": "POST backend works",
                        }
                    ]
                }
            ).encode("utf-8")
        )

    def log_message(self, format, *args):
        return


def run_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def make_fake_gateway(tmpdir: Path) -> Path:
    package = tmpdir / "app"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "library_engine.py").write_text(
        textwrap.dedent(
            """
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class SearchResult:
                document_id: str
                collection: str
                title: str
                source_path: str
                classification: str
                chunk_index: int
                locator: str
                excerpt: str
                score: float

            def contains_secret(text):
                return "secret-token" in text

            def search_library(db_path, query, collections, *, limit=6, excerpt_chars=1000):
                return [
                    SearchResult(
                        document_id="abcd" * 8,
                        collection=collections[0],
                        title="Direct live result",
                        source_path="operations/direct-live-result.md",
                        classification="internal",
                        chunk_index=2,
                        locator="section:1",
                        excerpt=f"Direct result for {query}"[:excerpt_chars],
                        score=-1.25,
                    )
                ][:limit]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return tmpdir


def ensure_fixture(module) -> None:
    if any(path.exists() for path in module.FIXTURE_PATHS):
        return
    fixture_path = module.FIXTURE_PATHS[0]
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        json.dumps(
            {
                "query": "",
                "collection": "operations",
                "mode": "fixture",
                "results": [
                    {
                        "id": "fixture-vpn-self-enrollment",
                        "title": "VPN self-enrollment runbook",
                        "collection": "operations",
                        "path": "operations/vpn-self-enrollment-runbook.md",
                        "updated_at": "2026-07-16T00:00:00Z",
                        "score": 0.94,
                        "snippet": "Self-enrollment steps for private VPN access.",
                    },
                    {
                        "id": "fixture-rollback-package",
                        "title": "Rollback package checklist",
                        "collection": "operations",
                        "path": "operations/rollback-package-checklist.md",
                        "updated_at": "2026-07-16T00:00:00Z",
                        "score": 0.86,
                        "snippet": "Checklist for rollback packages.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def main() -> int:
    module = load_server_module()
    ensure_fixture(module)

    assert module.clamp_limit(None) == 10
    assert module.clamp_limit("0") == 1
    assert module.clamp_limit("1000") == 20
    assert module.clamp_limit("bad") == 10

    old_env = {
        "EDGE1_LIBRARY_DIRECT_ENABLED": os.environ.get("EDGE1_LIBRARY_DIRECT_ENABLED"),
        "EDGE1_BIGBIRD_GATEWAY_ROOT": os.environ.get("EDGE1_BIGBIRD_GATEWAY_ROOT"),
        "BB_LIBRARY_DB": os.environ.get("BB_LIBRARY_DB"),
        "EDGE1_LIBRARY_SEARCH_URL": os.environ.get("EDGE1_LIBRARY_SEARCH_URL"),
        "EDGE1_LIBRARY_SEARCH_METHOD": os.environ.get("EDGE1_LIBRARY_SEARCH_METHOD"),
    }

    try:
        os.environ["EDGE1_LIBRARY_DIRECT_ENABLED"] = "0"
        status, payload = module.search_payload("VPN", "operations", 5)
        assert status == 200
        assert payload["collection"] == "operations"
        assert payload["results"], "fixture search should return results"

        status, payload = module.search_payload("VPN", "public", 5)
        assert status == 400
        assert payload["error"] == "unsupported_collection"

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmpdir = Path(raw_tmp)
            gateway_root = make_fake_gateway(tmpdir / "gateway")
            fake_db = tmpdir / "library.sqlite3"
            fake_db.write_text("fake db marker", encoding="utf-8")
            os.environ["EDGE1_LIBRARY_DIRECT_ENABLED"] = "1"
            os.environ["EDGE1_BIGBIRD_GATEWAY_ROOT"] = str(gateway_root)
            os.environ["BB_LIBRARY_DB"] = str(fake_db)
            status, payload = module.search_payload("VPN", "operations", 5)
            assert status == 200
            assert payload["mode"] == "live_direct"
            assert payload["results"][0]["id"].endswith(":2")
            assert payload["results"][0]["path"] == "operations/direct-live-result.md"

        os.environ["EDGE1_LIBRARY_DIRECT_ENABLED"] = "0"
        server, thread = run_server(module.PrivateLibrarySearchHandler)
        try:
            host, port = server.server_address
            status, payload = fetch_json(
                f"http://{host}:{port}/api/private-library/search?q=rollback&collection=operations&limit=2"
            )
            assert status == 200
            assert payload["query"] == "rollback"
            assert len(payload["results"]) <= 2

            status, payload = fetch_json(
                f"http://{host}:{port}/api/private-library/search?q=rollback&collection=public"
            )
            assert status == 400
            assert payload["error"] == "unsupported_collection"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        backend, backend_thread = run_server(MockBackendHandler)
        try:
            host, port = backend.server_address
            os.environ["EDGE1_LIBRARY_SEARCH_URL"] = f"http://{host}:{port}/search"
            os.environ["EDGE1_LIBRARY_SEARCH_METHOD"] = "GET"
            status, payload = module.search_payload("VPN", "operations", 5)
            assert status == 200
            assert payload["mode"] == "live"
            assert payload["results"][0]["id"] == "live-get"

            os.environ["EDGE1_LIBRARY_SEARCH_METHOD"] = "POST"
            status, payload = module.search_payload("VPN", "operations", 5)
            assert status == 200
            assert payload["mode"] == "live"
            assert payload["results"][0]["id"] == "live-post"
        finally:
            backend.shutdown()
            backend.server_close()
            backend_thread.join(timeout=5)
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("private library search server validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
