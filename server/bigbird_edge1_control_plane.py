#!/usr/bin/env python3
"""BigBird Edge1 Control Plane v2 client.

Migration implementation:
- consumes the v2 capability manifest;
- authenticates to the existing loopback Edge1 Operations API;
- discovers broker actions and bounded backend availability;
- executes enabled read capabilities;
- permits only the explicitly enabled stage-only filesystem capability;
- refuses apply, rollback, privileged actions, arbitrary shell, paths, SQL,
  URLs, and service targets.
"""

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
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
FSCTL = Path(os.environ.get("BIGBIRD_CONTROL_PLANE_FSCTL", "/usr/local/sbin/bigbird-fsctl"))
ACTOR = os.environ.get("BIGBIRD_CONTROL_PLANE_ACTOR", "bigbird-edge1-control-plane-v2")
TIMEOUT = int(os.environ.get("BIGBIRD_CONTROL_PLANE_TIMEOUT", "15"))
FS_STAGE_MAX_BYTES = 200000
FS_STAGE_TARGET = re.compile(r"^/opt/edge1-management-interface/docs/[A-Za-z0-9._/\-]+$")
FS_STAGE_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$")
FS_STAGE_ACTOR = re.compile(r"^[A-Za-z0-9._@:\-]{1,80}$")


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


def backend_available(backend):
    if backend == "operations_api":
        return None
    if backend == "filesystem_write_connector":
        return FSCTL.is_file() and os.access(FSCTL, os.X_OK)
    return False


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
        if backend == "operations_api":
            available = action in advertised
            broker_mutating = advertised.get(action) if action in advertised else None
        else:
            available = backend_available(backend)
            broker_mutating = None
        rows.append(
            {
                "name": capability["name"],
                "class": capability["class"],
                "scope": capability["scope"],
                "backend": backend,
                "action": action,
                "enabled": bool(capability["enabled"]),
                "available": bool(available),
                "broker_mutating": broker_mutating,
            }
        )
    return {"health": health, "capabilities": rows}


def authorize_execution(manifest, capability):
    if not capability.get("enabled"):
        raise ControlPlaneError("capability is disabled")

    capability_class = capability.get("class")
    backend = capability.get("backend")

    if capability_class == "read":
        if backend != "operations_api":
            raise ControlPlaneError("read backend execution is not implemented in this client revision")
        if not capability.get("action"):
            raise ControlPlaneError("operations API capability has no action")
        return

    stage_only = (
        capability_class == "staged_write"
        and capability.get("mutation_policy") == "stage_only"
        and backend == "filesystem_write_connector"
        and capability.get("name") == "edge1.files.stage"
    )
    if manifest.get("mode") == "migration" and not stage_only:
        raise ControlPlaneError("only stage-only filesystem writes are allowed while control plane is in migration mode")
    if stage_only:
        return

    raise ControlPlaneError("capability class is not executable in this client revision")


def validate_stage_input(params):
    if not isinstance(params, dict):
        raise ControlPlaneError("filesystem stage input must be an object")
    allowed = {"target", "content", "actor", "reason"}
    unexpected = sorted(set(params) - allowed)
    if unexpected:
        raise ControlPlaneError("unexpected filesystem stage input: {}".format(", ".join(unexpected)))

    target = params.get("target")
    content = params.get("content")
    actor = params.get("actor", ACTOR)
    reason = params.get("reason")

    if not isinstance(target, str) or not FS_STAGE_TARGET.fullmatch(target):
        raise ControlPlaneError("filesystem stage target must be an approved Edge1 docs path")
    if ".." in Path(target).parts:
        raise ControlPlaneError("filesystem stage target must not contain parent traversal")
    if not isinstance(content, str) or not content:
        raise ControlPlaneError("filesystem stage content must be non-empty UTF-8 text")
    if len(content.encode("utf-8")) > FS_STAGE_MAX_BYTES:
        raise ControlPlaneError("filesystem stage content exceeds {} bytes".format(FS_STAGE_MAX_BYTES))
    if not isinstance(actor, str) or not FS_STAGE_ACTOR.fullmatch(actor):
        raise ControlPlaneError("filesystem stage actor is invalid")
    if not isinstance(reason, str) or not 3 <= len(reason) <= 240:
        raise ControlPlaneError("filesystem stage reason must contain 3 to 240 characters")

    return {"target": target, "content": content, "actor": actor, "reason": reason}


def run_fsctl_stage(params):
    if not FSCTL.is_file() or not os.access(FSCTL, os.X_OK):
        raise ControlPlaneError("bigbird-fsctl is unavailable")

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix="bigbird-control-plane-stage-", suffix=".txt", delete=False
    ) as handle:
        handle.write(params["content"])
        source = handle.name

    try:
        proc = subprocess.run(
            [
                str(FSCTL),
                "stage",
                "--source",
                source,
                "--target",
                params["target"],
                "--actor",
                params["actor"],
                "--reason",
                params["reason"],
            ],
            text=True,
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ControlPlaneError("bigbird-fsctl stage execution failed") from exc
    finally:
        try:
            Path(source).unlink()
        except FileNotFoundError:
            pass

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "bigbird-fsctl stage failed").strip()[:1200]
        raise ControlPlaneError("bigbird-fsctl stage rejected proposal: {}".format(detail))
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ControlPlaneError("bigbird-fsctl returned invalid JSON") from exc
    if result.get("status") != "staged":
        raise ControlPlaneError("bigbird-fsctl did not return staged status")
    stage_id = result.get("stage_id")
    if not isinstance(stage_id, str) or not FS_STAGE_ID.fullmatch(stage_id):
        raise ControlPlaneError("bigbird-fsctl returned invalid stage id")
    if result.get("target") != params["target"]:
        raise ControlPlaneError("bigbird-fsctl returned a mismatched target")
    return result


def run_capability(manifest, name, params=None):
    capabilities = capability_map(manifest)
    capability = capabilities.get(name)
    if capability is None:
        raise ControlPlaneError("unknown capability")
    authorize_execution(manifest, capability)

    if capability["class"] == "read":
        if params not in (None, {}):
            raise ControlPlaneError("read capability does not accept input")
        broker = operations_broker(manifest)
        path = "/v1/actions/{}/run".format(capability["action"])
        status_code, payload = signed_request(broker["base_url"], "POST", path, b"{}")
        if status_code != 200:
            raise ControlPlaneError("capability execution failed: {}".format(payload.get("error", status_code)))
        return payload

    if capability["name"] == "edge1.files.stage":
        validated = validate_stage_input(params)
        stage = run_fsctl_stage(validated)
        return {
            "capability": capability["name"],
            "backend": capability["backend"],
            "mutation_policy": capability["mutation_policy"],
            "stage": stage,
            "next_step": "Inspect and approve the stage separately before any operator/root apply.",
        }

    raise ControlPlaneError("capability backend execution is not implemented")


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
    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("--target", required=True)
    stage_parser.add_argument("--actor", default=ACTOR)
    stage_parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    manifest = load_manifest()
    if args.command == "status":
        result = status(manifest)
    elif args.command == "discover":
        result = discover(manifest)
    elif args.command == "stage":
        result = run_capability(
            manifest,
            "edge1.files.stage",
            {
                "target": args.target,
                "content": sys.stdin.read(),
                "actor": args.actor,
                "reason": args.reason,
            },
        )
    else:
        result = run_capability(manifest, args.capability)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
