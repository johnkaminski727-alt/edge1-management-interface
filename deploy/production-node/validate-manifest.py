#!/usr/bin/env python3
"""Validate a WW.CX production-node manifest without external dependencies."""
import json
import pathlib
import sys

ALLOWED_STATES = {
    "provisioning", "isolated", "validated", "production-candidate",
    "canary", "active", "draining", "retired",
}
SAFETY_FLAGS = (
    "production_traffic_enabled", "carrier_trunks_enabled",
    "emergency_calling_enabled", "stir_shaken_signing_enabled",
    "number_porting_enabled", "authoritative_writes_enabled",
)


def fail(message):
    print("manifest validation failed: %s" % message, file=sys.stderr)
    return 1


def main():
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "config/production-node/node-manifest.example.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return fail(str(exc))

    if data.get("schema_version") != 1:
        return fail("schema_version must be 1")
    node = data.get("node") or {}
    if node.get("environment") != "production-candidate":
        return fail("node.environment must be production-candidate")
    lifecycle = data.get("lifecycle") or {}
    if lifecycle.get("state") not in ALLOWED_STATES:
        return fail("invalid lifecycle state")
    declared = set(lifecycle.get("allowed_states") or [])
    if declared != ALLOWED_STATES:
        return fail("allowed_states must match the lifecycle contract")
    safety = data.get("safety") or {}
    for flag in SAFETY_FLAGS:
        if safety.get(flag) is not False:
            return fail("%s must be false in the staging manifest" % flag)
    host = data.get("host") or {}
    if not host.get("required_commands"):
        return fail("host.required_commands must not be empty")
    if not isinstance(data.get("services"), list) or not isinstance(data.get("listeners"), list):
        return fail("services and listeners must be lists")
    print("production node manifest validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
