#!/usr/bin/env python3
"""BigBird Edge1 Control Plane v2 client.

Initial migration implementation:
- consumes the v2 capability manifest;
- authenticates to the existing loopback Edge1 Operations API;
- discovers broker actions;
- executes only enabled read capabilities;
- refuses staged writes and privileged mutations until their dedicated
  backends and production authorization are enabled.

No arbitrary command, path, SQL, URL, or service target is accepted.
"""

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(os.environ.get("BIGBIRD_CONTROL_PLANE_ROOT", "/opt/edge1-management-interface"))
MANIFEST_PATH = Path(
    os.environ.get(
        "BIGBIRD_CONTROL_PLANE_MANIFEST",
        str(ROOT / "integrations/bigbird-edge1-control-plane/capabilities-v2.json"),
    )
)
SECRET_FILE = Path(os.environ.get("BIGBIRD_CONTROL_PLANE_SECRET_FILE", "/etc/edge1-operations-api.secret"))
ACTOR = os.environ.get("BIGBIRD_CONTROL_PLANE_ACTOR", "bigbird-edge1-control-plane-v2")
TIMEOUT = int(os.environ.get("BIGBIRD_CONTROL_PLANE_TIMEOUT", "15"))


class ControlPlaneError(RuntimeError):
    pass


def load_manifest():
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if value.get("version") != 2 or value.get("control_plane") != "bigbird-edge1":
        raise ControlPlaneError("unsupported control plane manifest")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ControlPlaneError("capability manifest is empty")
    names = [item.get("name") for item in capabilities]
    if any(not isinstance(name, str) or not name for name in names):
        raise ControlPlaneError("invalid capability name")
    if len(names) != len(set(names)):
        raise ControlPlaneError("duplicate capability name")
    return value


def capability_map(manifest):
    return {item["name"]: item for item in manifest["capabilities"]}


def operations_broker(manifest):
    broker = manifest.get("brokers", {}).get("operations_api")
    if not isinstance(broker, dict):
        raise ControlPlaneError("operations_api broker is not configured")
    base_url = broker.get("base_url", "")
    if base_url != "http://127.0.0.1:8097":
        raise ControlPlaneError("operations_api broker must remain loopback-bound at 127.0.0.1:8097")
    if broker.get("authentication") != "wwcx-hmac-sha256-v1":
        raise ControlPlaneError("unsupported operations_api authentication")
    return broker


def read_secret():
    value = SECRET_FILE.read_bytes().strip()
    if len(value) < 32:
        raise ControlPlaneError("operations API secret must contain at least 32 bytes")
    return value


def signed_request(base_url, method, path, body=b""):
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(24)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method, path, timestamp, nonce, ACTOR, body_hash)).encode()
    signature = hmac.new(read_secret(), canonical, hashlib.sha256).hexdigest()
    request = Request(
        base_url.rstrip("/") + path,
        data=body if method != "GET" else None,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-WWCX-Actor": ACTOR,
            "X-WWCX-Nonce": nonce,
            "X-WWCX-Timestamp": timestamp,
            "X-WWCX-Signature": signature,
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(payload)
        except json.JSONDecodeError:
            detail = {"error": "operations API HTTP error"}
        return exc.code, detail
    except URLError as exc:
        raise ControlPlaneError("operations API is unreachable: {}".format(exc.reason)) from exc


def public_health(base_url):
    request = Request(base_url.rstrip("/") + "/healthz", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (URLError, HTTPError) as exc:
        raise ControlPlaneError("operations API health check failed") from exc


def discover(manifest):
    broker = operations_broker(manifest)
    base_url = broker["base_url"]
    health = public_health(base_url)
    status, payload = signed_request(base_url, "GET", "/v1/actions")
    if status != 200:
        raise ControlPlaneError("operations API action discovery failed")
    advertised = {item["name"]: bool(item.get("mutating")) for item in payload.get("actions", [])}
    rows = []
    for capability in manifest["capabilities"]:
        backend = capability["backend"]
        action = capability.get("action")
        available = backend != "operations_api" or action in advertised
        broker_mutating = advertised.get(action) if backend == "operations_api" and action in advertised else None
        rows.append(
            {
                "name": capability["name"],
                "class": capability["class"],
                "scope": capability["scope"],
                "backend": backend,
                "action": action,
                "enabled": bool(capability["enabled"]),
                "available": available,
                "broker_mutating": broker_mutating,
            }
        )
    return {"health": health, "capabilities": rows}


def authorize_execution(manifest, capability):
    if not capability.get("enabled"):
        raise ControlPlaneError("capability is disabled")
    if manifest.get("mode") == "migration" and capability.get("class") != "read":
        raise ControlPlaneError("mutation capabilities are disabled while control plane is in migration mode")
    if capability.get("class") != "read":
        raise ControlPlaneError("this client revision only executes read capabilities")
    if capability.get("backend") != "operations_api":
        raise ControlPlaneError("backend execution is not implemented in this client revision")
    if not capability.get("action"):
        raise ControlPlaneError("operations API capability has no action")


def run_capability(manifest, name):
    capabilities = capability_map(manifest)
    capability = capabilities.get(name)
    if capability is None:
        raise ControlPlaneError("unknown capability")
    authorize_execution(manifest, capability)
    broker = operations_broker(manifest)
    path = "/v1/actions/{}/run".format(capability["action"])
    status, payload = signed_request(broker["base_url"], "POST", path, b"{}")
    if status != 200:
        raise ControlPlaneError("capability execution failed: {}".format(payload.get("error", status)))
    return payload


def status(manifest):
    discovery = discover(manifest)
    enabled = [item for item in discovery["capabilities"] if item["enabled"]]
    unavailable = [item["name"] for item in enabled if not item["available"]]
    return {
        "status": "ready" if not unavailable else "degraded",
        "version": manifest["version"],
        "mode": manifest["mode"],
        "actor": ACTOR,
        "enabled_capabilities": len(enabled),
        "unavailable_enabled_capabilities": unavailable,
        "broker_health": discovery["health"],
    }


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("discover")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("capability")
    args = parser.parse_args()

    manifest = load_manifest()
    if args.command == "status":
        result = status(manifest)
    elif args.command == "discover":
        result = discover(manifest)
    else:
        result = run_capability(manifest, args.capability)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
