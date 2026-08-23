#!/usr/bin/env python3
"""Sync Edge1 VPN enrollment devices into the authenticated registration API."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
import urllib.request
from pathlib import Path

API_BASE = os.environ.get("EDGE1_VPN_REGISTRATION_API", "http://127.0.0.1:8097").rstrip("/")
SECRET_FILE = Path(os.environ.get("EDGE1_OPS_SECRET_FILE", "/etc/edge1-operations-api.secret"))
ENROLL_DB = Path(os.environ.get("EDGE1_VPN_ENROLL_DB", "/var/lib/edge1-vpn-enroll/enroll.db"))
ACTOR = os.environ.get("EDGE1_VPN_REGISTRATION_SYNC_ACTOR", "edge1-vpn-enroll-sync")


def signed_request(method: str, path: str, payload: dict | None = None) -> dict:
    body = b"" if payload is None else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, timestamp, nonce, ACTOR, body_hash)).encode()
    secret = SECRET_FILE.read_bytes().strip()
    signature = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    headers = {
        "X-WWCX-Actor": ACTOR,
        "X-WWCX-Timestamp": timestamp,
        "X-WWCX-Nonce": nonce,
        "X-WWCX-Signature": signature,
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = body
    request = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"{}")


def enrollment_rows() -> list[sqlite3.Row]:
    connection = sqlite3.connect(str(ENROLL_DB))
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            "SELECT id, label, peer_public_key, address, revoked_at, owner_subject FROM devices ORDER BY id"
        ).fetchall()
    finally:
        connection.close()


def sync_once() -> dict:
    current = signed_request("GET", "/v1/vpn-access/devices").get("devices", [])
    by_fingerprint = {
        device.get("peer_key_sha256"): device
        for device in current
        if device.get("peer_key_sha256")
    }
    imported = updated = quarantined = 0
    for row in enrollment_rows():
        public_key = row["peer_public_key"]
        fingerprint = hashlib.sha256(public_key.encode()).hexdigest()
        existing = by_fingerprint.get(fingerprint)
        if row["revoked_at"]:
            if existing and existing.get("status") != "quarantined":
                signed_request(
                    "POST",
                    "/v1/vpn-access/quarantine",
                    {
                        "device_id": existing["id"],
                        "quarantined": True,
                        "reason": "VPN enrollment device revoked",
                    },
                )
                quarantined += 1
            continue

        desired_addresses = [row["address"]]
        owner_subject = (row["owner_subject"] or "").strip()
        needs_upsert = (
            existing is None
            or sorted(existing.get("assigned_addresses") or []) != desired_addresses
            or (existing.get("display_name") or "") != row["label"]
            or (existing.get("owner") or "") != owner_subject
        )
        if needs_upsert:
            result = signed_request(
                "POST",
                "/v1/vpn-access/devices",
                {
                    "peer_public_key": public_key,
                    "assigned_addresses": desired_addresses,
                    "display_name": row["label"],
                    "owner": owner_subject,
                },
            )
            by_fingerprint[fingerprint] = result
            if existing is None:
                imported += 1
            else:
                updated += 1

    summary = signed_request("GET", "/v1/vpn-access/summary")
    return {
        "imported": imported,
        "updated": updated,
        "quarantined": quarantined,
        "total_devices": summary.get("total_devices"),
        "device_counts": summary.get("device_counts"),
        "enforcement_active": summary.get("enforcement_active"),
    }


def main() -> None:
    print(json.dumps(sync_once(), sort_keys=True))


if __name__ == "__main__":
    main()
