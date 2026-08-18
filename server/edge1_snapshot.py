#!/usr/bin/env python3
"""Deterministic, bounded, read-only Edge1 host snapshot.

This collector has no caller-controlled command, argv, path, URL, or service
name. It performs observation only. Potentially sensitive bulk firewall and
journal output is reduced to counts/digests and is never returned raw.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Any, Iterable

CONTRACT = "wwcx.edge1.snapshot.v1"
MAX_BYTES = 128 * 1024
SAFE_ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "NO_PROXY": "*",
    "no_proxy": "*",
}
REPO_ROOT = Path(os.environ.get("EDGE1_SNAPSHOT_REPO", "/opt/edge1-management-interface")).resolve()
SERVICES = (
    "edge1-operations-api.service",
    "edge1-operator.service",
    "edge1-operator-mcp.service",
    "bigbird-ai-gateway.service",
    "apache2.service",
    "asterisk.service",
    "kamailio.service",
)
CONFIG_PATHS = (
    "config/edge1-operations-allowlist.json",
    "deploy/edge1-operations-api.service",
    "deploy/edge1-operator/edge1-operator-mcp.service",
)
COMMANDS: dict[str, tuple[tuple[str, ...], tuple[str, ...], int, str]] = {
    "filesystems": (("/usr/bin/df", "/bin/df"), ("-P", "-B1"), 15, "text"),
    "inodes": (("/usr/bin/df", "/bin/df"), ("-Pi",), 15, "text"),
    "interfaces": (("/usr/sbin/ip", "/usr/bin/ip", "/sbin/ip"), ("-j", "addr", "show"), 15, "json"),
    "routes": (("/usr/sbin/ip", "/usr/bin/ip", "/sbin/ip"), ("-j", "route", "show", "table", "all"), 15, "json"),
    "resolver": (("/usr/bin/resolvectl", "/bin/resolvectl"), ("status", "--no-pager"), 15, "text"),
    "listeners": (("/usr/bin/ss", "/usr/sbin/ss", "/bin/ss"), ("-H", "-lntu"), 15, "text"),
    "failed_services": (("/usr/bin/systemctl", "/bin/systemctl"), ("--failed", "--no-legend", "--no-pager"), 20, "text"),
    "firewall": (("/usr/sbin/nft", "/usr/bin/nft", "/sbin/nft"), ("list", "ruleset"), 30, "digest"),
    "critical_errors": (("/usr/bin/journalctl", "/bin/journalctl"), ("-p", "0..3", "--since", "-1 hour", "--no-pager", "-o", "short-monotonic"), 30, "digest"),
    "git_head": (("/usr/bin/git", "/bin/git"), ("-C", str(REPO_ROOT), "rev-parse", "HEAD"), 15, "text"),
    "git_branch": (("/usr/bin/git", "/bin/git"), ("-C", str(REPO_ROOT), "branch", "--show-current"), 15, "text"),
    "git_status": (("/usr/bin/git", "/bin/git"), ("-C", str(REPO_ROOT), "status", "--short", "--branch"), 20, "text"),
    "operations_api_health": (("/usr/bin/curl", "/bin/curl"), ("-fsS", "--max-time", "5", "http://127.0.0.1:8097/healthz"), 10, "json"),
    "bigbird_health": (("/usr/bin/curl", "/bin/curl"), ("-fsS", "--max-time", "5", "http://127.0.0.1:8787/v1/health"), 10, "json"),
}


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def _exe(candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        path = Path(candidate)
        try:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        except OSError:
            pass
    return None


def _bounded(data: bytes, maximum: int = MAX_BYTES) -> tuple[bytes, bool]:
    return data[:maximum], len(data) > maximum


def _digest(data: bytes, stderr: bytes, returncode: int | None, truncated: bool) -> dict[str, Any]:
    return {
        "returncode": returncode,
        "line_count": data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
        "stdout_sha256": hashlib.sha256(data).hexdigest(),
        "stderr_present": bool(stderr),
        "output_truncated": truncated,
        "raw_output_returned": False,
    }


def run_fixed(name: str) -> dict[str, Any]:
    if name not in COMMANDS:
        raise KeyError("unknown snapshot command")
    candidates, args, timeout, mode = COMMANDS[name]
    executable = _exe(candidates)
    if executable is None:
        return {"status": "unavailable", "command": name}
    started = _utc_now()
    try:
        completed = subprocess.run(
            [executable, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=SAFE_ENV,
        )
    except subprocess.TimeoutExpired as exc:
        out, ot = _bounded(exc.stdout or b"")
        err, et = _bounded(exc.stderr or b"")
        result: dict[str, Any] = {
            "status": "timed_out",
            "command": name,
            "started_at_utc": _iso(started),
            "completed_at_utc": _iso(_utc_now()),
        }
        if mode == "digest":
            result["result"] = _digest(out, err, None, ot or et)
        return result
    except OSError as exc:
        return {"status": "unavailable", "command": name, "error_type": type(exc).__name__}

    out, ot = _bounded(completed.stdout)
    err, et = _bounded(completed.stderr)
    result = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "command": name,
        "returncode": completed.returncode,
        "started_at_utc": _iso(started),
        "completed_at_utc": _iso(_utc_now()),
        "output_truncated": ot or et,
    }
    if mode == "digest":
        result["result"] = _digest(out, err, completed.returncode, ot or et)
        return result
    stdout = out.decode("utf-8", errors="replace")
    if mode == "json" and completed.returncode == 0:
        try:
            result["result"] = json.loads(stdout)
        except json.JSONDecodeError:
            result.update(status="failed", error="invalid_json_output")
    else:
        result["result"] = stdout.rstrip("\n")
    if err:
        result["stderr"] = err.decode("utf-8", errors="replace").rstrip("\n")
    return result


def _read(path: Path, maximum: int = 65536) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_bytes()[:maximum].decode("utf-8", errors="replace")
    except OSError:
        return None


def _os_release() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in (_read(Path("/etc/os-release")) or "").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            result[key.lower()] = value.strip().strip('"')
    return result


def _memory() -> dict[str, int | None]:
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values: dict[str, int | None] = {key: None for key in wanted}
    for line in (_read(Path("/proc/meminfo")) or "").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        fields = rest.strip().split()
        if key in wanted and fields and fields[0].isdigit():
            values[key] = int(fields[0]) * 1024
    return {
        "total_bytes": values["MemTotal"],
        "available_bytes": values["MemAvailable"],
        "swap_total_bytes": values["SwapTotal"],
        "swap_free_bytes": values["SwapFree"],
    }


def _uptime() -> float | None:
    text = _read(Path("/proc/uptime"), 256)
    try:
        return float(text.split()[0]) if text else None
    except (ValueError, IndexError):
        return None


def _timezone() -> str | None:
    text = _read(Path("/etc/timezone"), 1024)
    if text and text.strip() and len(text.strip()) <= 128:
        return text.strip()
    try:
        target = os.readlink("/etc/localtime")
        return target.split("/zoneinfo/", 1)[1] if "/zoneinfo/" in target else None
    except OSError:
        return None


def _service(unit: str) -> dict[str, Any]:
    if unit not in SERVICES:
        raise ValueError("service unit is not approved")
    systemctl = _exe(("/usr/bin/systemctl", "/bin/systemctl"))
    if not systemctl:
        return {"unit": unit, "status": "unavailable"}
    props = "Id,LoadState,ActiveState,SubState,UnitFileState,MainPID,ExecMainStatus,Restart,FragmentPath"
    try:
        completed = subprocess.run(
            [systemctl, "show", unit, "--no-pager", f"--property={props}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
            env=SAFE_ENV,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"unit": unit, "status": "unavailable", "error_type": type(exc).__name__}
    out, truncated = _bounded(completed.stdout, 32768)
    values = dict(line.split("=", 1) for line in out.decode("utf-8", errors="replace").splitlines() if "=" in line)
    return {"unit": unit, "status": "ok" if completed.returncode == 0 else "failed", "properties": values, "output_truncated": truncated}


def _config_digests() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for relative in CONFIG_PATHS:
        path = (REPO_ROOT / relative).resolve()
        try:
            if REPO_ROOT != path and REPO_ROOT not in path.parents:
                rows.append({"path": relative, "status": "rejected"})
            elif path.is_symlink() or not path.is_file():
                rows.append({"path": relative, "status": "unavailable"})
            else:
                rows.append({"path": relative, "status": "ok", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        except OSError:
            rows.append({"path": relative, "status": "unavailable"})
    return rows


def collect_snapshot() -> dict[str, Any]:
    captured = _utc_now()
    local = dt.datetime.now().astimezone()
    results = {name: run_fixed(name) for name in COMMANDS}
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "collected_at_utc": _iso(captured),
        "read_only": True,
        "mutation_performed": False,
        "secret_values_returned": False,
        "identity": {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "configured_timezone": _timezone(),
            "local_time": local.isoformat(),
            "utc_time": _iso(captured),
            "uptime_seconds": _uptime(),
            "os_release": _os_release(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory": _memory(),
        },
        "storage": {"filesystems": results["filesystems"], "inodes": results["inodes"]},
        "network": {
            "interfaces": results["interfaces"],
            "routes": results["routes"],
            "resolver": results["resolver"],
            "listening_sockets": results["listeners"],
            "firewall_summary": results["firewall"],
        },
        "services": {
            "failed": results["failed_services"],
            "relevant": [_service(unit) for unit in SERVICES],
            "operations_api_health": results["operations_api_health"],
            "bigbird_health": results["bigbird_health"],
        },
        "repository": {
            "root": str(REPO_ROOT),
            "head": results["git_head"],
            "branch": results["git_branch"],
            "status": results["git_status"],
            "configuration_digests": _config_digests(),
        },
        "recent_critical_errors": results["critical_errors"],
    }


def render_markdown(snapshot: dict[str, Any]) -> str:
    identity = snapshot["identity"]
    lines = [
        "# Edge1 Read-Only Snapshot",
        "",
        f"- Contract: `{snapshot['contract']}`",
        f"- Collected UTC: `{snapshot['collected_at_utc']}`",
        f"- Hostname: `{identity.get('hostname')}`",
        f"- Configured timezone: `{identity.get('configured_timezone')}`",
        f"- Kernel: `{identity.get('kernel')}`",
        f"- Mutation performed: `{str(snapshot['mutation_performed']).lower()}`",
        f"- Secret values returned: `{str(snapshot['secret_values_returned']).lower()}`",
        "",
        "## Relevant services",
        "",
        "| Unit | Load | Active | Sub | Enabled |",
        "|---|---|---|---|---|",
    ]
    for row in snapshot["services"]["relevant"]:
        props = row.get("properties", {})
        lines.append(f"| {row.get('unit','')} | {props.get('LoadState',row.get('status',''))} | {props.get('ActiveState','')} | {props.get('SubState','')} | {props.get('UnitFileState','')} |")
    lines.extend((
        "",
        "## Evidence notes",
        "",
        "- Firewall and critical-journal bulk output is reduced to bounded counts/digests.",
        "- Commands, paths, service units, and loopback health URLs are fixed server-side.",
        "- This is not live deployment evidence until collected on Edge1.",
    ))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    snapshot = collect_snapshot()
    if args.format == "markdown":
        print(render_markdown(snapshot), end="")
    else:
        print(json.dumps(snapshot, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
