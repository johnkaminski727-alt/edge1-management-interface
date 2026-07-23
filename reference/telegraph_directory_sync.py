#!/usr/bin/env python3
"""Bounded background synchronization for Telegraph federation directories.

This reference scheduler deliberately performs no TLS policy override. Production
callers must supply an HTTP client configured for the mutual-TLS requirements
advertised by each signed Office Identity document.
"""

from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from reference.telegraph_office_service import TelegraphOfficeState

DirectoryFetcher = Callable[[str, float], dict[str, Any]]


def directory_endpoint(identity: dict[str, Any]) -> str | None:
    """Return the signed federation service's directory endpoint."""
    services = identity.get("services")
    if not isinstance(services, list):
        return None
    for service in services:
        if not isinstance(service, dict) or service.get("type") != "federation_https":
            continue
        uri = service.get("uri")
        if isinstance(uri, str) and uri.startswith("https://"):
            return urljoin(uri.rstrip("/") + "/", "directory")
    return None


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "WWCXTelegraphSync/0.1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - signed HTTPS identity controls URL
        if response.status != HTTPStatus.OK:
            raise RuntimeError(f"directory returned HTTP {response.status}")
        content_type = response.headers.get_content_type()
        if content_type != "application/json":
            raise RuntimeError(f"directory returned unsupported content type {content_type}")
        document = json.load(response)
    if not isinstance(document, dict):
        raise RuntimeError("directory response must be an object")
    return document


@dataclass
class PeerSyncResult:
    office_id: str
    endpoint: str | None
    status: str
    attempts: int = 0
    detail: str | None = None
    response: dict[str, Any] | None = None


@dataclass
class TelegraphDirectorySynchronizer:
    state: TelegraphOfficeState
    interval_seconds: float = 300.0
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    jitter_fraction: float = 0.2
    fetcher: DirectoryFetcher = fetch_json
    sleep: Callable[[float], None] = time.sleep
    random_source: Callable[[], float] = random.random
    stop_event: threading.Event = field(default_factory=threading.Event)
    last_results: dict[str, PeerSyncResult] = field(default_factory=dict)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0 or self.timeout_seconds <= 0:
            raise ValueError("interval and timeout must be positive")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.backoff_seconds < 0 or not 0 <= self.jitter_fraction <= 1:
            raise ValueError("invalid backoff configuration")

    def _delay(self, attempt: int) -> float:
        base = self.backoff_seconds * (2 ** max(0, attempt - 1))
        jitter = base * self.jitter_fraction * self.random_source()
        return base + jitter

    def sync_peer(self, office_id: str, record: dict[str, Any]) -> PeerSyncResult:
        endpoint = directory_endpoint(record.get("identity", {}))
        if record.get("trust_status") == "restricted":
            return PeerSyncResult(office_id, endpoint, "skipped", detail="restricted_peer")
        if endpoint is None:
            return PeerSyncResult(office_id, None, "skipped", detail="missing_federation_https_service")

        for attempt in range(1, self.max_attempts + 1):
            try:
                document = self.fetcher(endpoint, self.timeout_seconds)
                if document.get("office_id") != office_id:
                    return PeerSyncResult(office_id, endpoint, "rejected", attempt, "directory_source_mismatch")
                status, response = self.state.sync_directory(document)
                if status == HTTPStatus.ACCEPTED:
                    return PeerSyncResult(office_id, endpoint, "synchronized", attempt, response=response)
                return PeerSyncResult(
                    office_id,
                    endpoint,
                    "rejected",
                    attempt,
                    str(response.get("error", status.phrase)),
                    response,
                )
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                if attempt >= self.max_attempts:
                    return PeerSyncResult(office_id, endpoint, "failed", attempt, f"{type(exc).__name__}: {exc}")
                self.sleep(self._delay(attempt))
        raise AssertionError("unreachable")

    def sync_once(self) -> dict[str, PeerSyncResult]:
        with self.state.lock:
            peers = [(office_id, dict(record)) for office_id, record in self.state.peers.items()]
        results = {office_id: self.sync_peer(office_id, record) for office_id, record in peers}
        self.last_results = results
        return results

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.sync_once()
            self.stop_event.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(target=self.run, name="telegraph-directory-sync", daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        self.stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
