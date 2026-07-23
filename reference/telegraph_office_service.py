#!/usr/bin/env python3
"""Non-production HTTP reference service for a WW.CX Telegraph Office.

The service intentionally uses Python's standard library HTTP server so the
transport behaviour can be exercised without adding a web-framework runtime.
TLS and mutual authentication are deployment concerns and are not enabled by
this development fixture.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from reference.telegraph_crypto import verify_document, verify_identity
from reference.telegraph_federation_demo import Office, canonical_json, sha256
from reference.telegraph_storage import TelegraphStore


@dataclass
class TelegraphOfficeState:
    office: Office
    store: TelegraphStore | None = None
    peers: dict[str, dict[str, Any]] = field(default_factory=dict)
    messages: dict[str, dict[str, Any]] = field(default_factory=dict)
    receipts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        if self.store is None:
            return
        self.peers = self.store.load_peers()
        self.messages = self.store.load_messages()
        self.receipts = self.store.load_receipts()
        for office_id, record in self.peers.items():
            self.office.trust[office_id] = record["trust_status"]
        all_receipts = [receipt for chain in self.receipts.values() for receipt in chain]
        if all_receipts:
            latest = max(all_receipts, key=lambda receipt: int(receipt.get("sequence", 0)))
            self.office.receipt_sequence = int(latest.get("sequence", 0))
            self.office.last_receipt_digest = sha256(canonical_json(latest))

    def capabilities(self) -> dict[str, Any]:
        return {
            "office_id": self.office.office_id,
            "envelope_versions": ["1.0"],
            "transports": ["http-development"],
            "media": sorted(self.office.media),
            "security": sorted(self.office.security),
            "persistent_storage": self.store is not None,
            "production_ready": False,
        }

    def directory(self) -> dict[str, Any]:
        with self.lock:
            return {
                "office_id": self.office.office_id,
                "peers": list(self.peers.values()),
                "count": len(self.peers),
            }

    def register_peer(self, document: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
        office_id = document.get("office_id")
        identity = document.get("identity")
        trust_status = document.get("trust_status", "observed")
        if not isinstance(office_id, str) or not isinstance(identity, dict):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_peer_record"}
        if identity.get("office_id") != office_id:
            return HTTPStatus.BAD_REQUEST, {"error": "peer_identity_mismatch"}
        if trust_status not in {"observed", "trusted", "restricted"}:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_trust_status"}
        if not verify_identity(identity):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid_peer_signature"}

        record = {
            "office_id": office_id,
            "identity": identity,
            "trust_status": trust_status,
            "updated_at": int(time.time()),
            "identity_verified": True,
        }
        with self.lock:
            if self.store is not None:
                self.store.save_peer(record)
            self.peers[office_id] = record
            self.office.trust[office_id] = trust_status
        return HTTPStatus.CREATED, record

    def _accept_nonce(self, nonce: str, now: float) -> bool:
        if self.store is not None:
            return self.store.accept_nonce(nonce, now, 3600)
        return self.office.replay_cache.accept(nonce, now, 3600)

    def _record_receipt(self, receipt: dict[str, Any], recorded_at: int) -> None:
        if self.store is not None:
            self.store.save_receipt(receipt, recorded_at)
        self.receipts.setdefault(receipt["message_id"], []).append(receipt)

    def accept_message(self, envelope: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
        required = {"message_id", "origin", "destination", "nonce", "payload", "security_state", "signature"}
        missing = sorted(required - envelope.keys())
        if missing:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_envelope", "missing": missing}
        if envelope["destination"] != self.office.office_id:
            return HTTPStatus.CONFLICT, {
                "error": "wrong_destination",
                "expected": self.office.office_id,
                "received": envelope["destination"],
            }

        origin = envelope.get("origin")
        with self.lock:
            peer = self.peers.get(origin) if isinstance(origin, str) else None
        if peer is None:
            return HTTPStatus.FORBIDDEN, {"error": "unknown_origin"}
        if peer["trust_status"] == "restricted":
            return HTTPStatus.FORBIDDEN, {"error": "restricted_origin"}
        if not verify_document(envelope, peer["identity"]):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid_envelope_signature"}

        now = time.time()
        recorded_at = int(now)
        with self.lock:
            accepted = self._accept_nonce(str(envelope["nonce"]), now)
            if not accepted:
                receipt = self.office.receipt(envelope, "duplicate_rejected", duplicate=True)
                self._record_receipt(receipt, recorded_at)
                return HTTPStatus.CONFLICT, {"status": "duplicate_rejected", "receipt": receipt}

            if self.store is not None:
                self.store.save_message(envelope, recorded_at)
            self.messages[envelope["message_id"]] = envelope
            receipt = self.office.receipt(envelope, "accepted")
            self._record_receipt(receipt, recorded_at)
            return HTTPStatus.ACCEPTED, {
                "status": "accepted",
                "message_id": envelope["message_id"],
                "envelope_digest": sha256(canonical_json(envelope)),
                "signature_verified": True,
                "receipt": receipt,
            }

    def record_external_receipt(self, document: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
        message_id = document.get("message_id")
        office_id = document.get("office_id")
        receipt_id = document.get("receipt_id")
        if not all(isinstance(value, str) for value in (message_id, office_id, receipt_id)):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid_receipt"}
        with self.lock:
            peer = self.peers.get(office_id)
        if peer is None:
            return HTTPStatus.FORBIDDEN, {"error": "unknown_receipt_office"}
        if not verify_document(document, peer["identity"]):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid_receipt_signature"}
        with self.lock:
            self._record_receipt(document, int(time.time()))
        return HTTPStatus.ACCEPTED, {
            "status": "receipt_recorded",
            "message_id": message_id,
            "signature_verified": True,
        }

    def close(self) -> None:
        if self.store is not None:
            self.store.close()
            self.store = None


class TelegraphOfficeHandler(BaseHTTPRequestHandler):
    server_version = "WWCXTelegraphOffice/0.3"

    @property
    def state(self) -> TelegraphOfficeState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > 10 * 1024 * 1024:
            return None
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._json(HTTPStatus.OK, {
                "status": "ok",
                "office_id": self.state.office.office_id,
                "uptime_seconds": max(0, int(time.time() - self.state.started_at)),
                "persistent_storage": self.state.store is not None,
                "production_ready": False,
            })
            return
        if path == "/identity":
            self._json(HTTPStatus.OK, self.state.office.identity_document())
            return
        if path == "/capabilities":
            self._json(HTTPStatus.OK, self.state.capabilities())
            return
        if path == "/directory":
            self._json(HTTPStatus.OK, self.state.directory())
            return
        if path.startswith("/receipts/"):
            message_id = path.removeprefix("/receipts/")
            with self.state.lock:
                receipts = self.state.receipts.get(message_id)
            if receipts is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "receipt_not_found"})
            else:
                self._json(HTTPStatus.OK, {"message_id": message_id, "receipts": receipts})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        document = self._read_json()
        if document is None:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return
        if path == "/message":
            status, payload = self.state.accept_message(document)
            self._json(status, payload)
            return
        if path == "/directory/peers":
            status, payload = self.state.register_peer(document)
            self._json(status, payload)
            return
        if path == "/receipt":
            status, payload = self.state.record_external_receipt(document)
            self._json(status, payload)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


class TelegraphOfficeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: TelegraphOfficeState):
        super().__init__(address, TelegraphOfficeHandler)
        self.state = state

    def server_close(self) -> None:
        try:
            super().server_close()
        finally:
            self.state.close()


def build_state(office_id: str, database_path: str | Path | None = None) -> TelegraphOfficeState:
    office = Office(
        office_id=office_id,
        media={"secure_message", "attachment", "rtt_t140"},
        security={
            "end_to_end_encryption",
            "forward_secrecy",
            "mutual_tls",
            "signed_receipts",
            "code_word_commitments",
        },
        trust={},
    )
    store = TelegraphStore(database_path) if database_path is not None else None
    return TelegraphOfficeState(office=office, store=store)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--office-id", default="alpha.telegraph.ww.cx")
    parser.add_argument("--database", help="SQLite database path; omit for ephemeral in-memory state")
    args = parser.parse_args()

    server = TelegraphOfficeHTTPServer(
        (args.host, args.port),
        build_state(args.office_id, args.database),
    )
    print(f"Telegraph Office {args.office_id} listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
