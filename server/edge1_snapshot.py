#!/usr/bin/env python3
"""Deterministic, bounded, read-only Edge1 host snapshot.

The collector exposes no caller-controlled command, path, URL, unit, or argv.
It writes only the requested JSON/Markdown representation to stdout and never
changes files, services, listeners, routes, firewall policy, credentials, or
traffic controls. Potentially sensitive bulk command output (firewall rules
and critical journal entries) is summarized by count and SHA-256 only.
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
MAX_COMMAND_BYTES = 128 * 1024
SAFE_ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "NO_PROXY": "*",
    "no_proxy": "*",
}
REPO_ROOT = Path(os.environ.get("EDGE1_SNAPSHOT_REPO", "/opt/edge1-management-interface")).resolve()
CONFIG_DIGEST_PATHS = (
    "config/edge1-operations-allowlist.json",
    "config/security/edge1-live-boundary-inventory-policy.json",
)
SERVICE_UNITS = (
    "edge1-operations-api.service",
    "edge1-operator.service",
    "bigbird-ai-gateway.service",
    "apache2.service",
    "asterisk.service",
    "kamailio.service",
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


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def bounded_bytes(value: bytes, maximum: int = MAX_COMMAND_BYTES) -> tuple[bytes, bool]:
    return value[:maximum], len(value) > maximum


def resolve_executable(candidates: Iterable[str]) -> str | None:
    for candidate in candidates:
        path = Path(candidate)
        try:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        except OSError:
            continue
    return None


def _digest_summary(stdout: bytes, stderr: bytes, returncode: int | None, *, truncated: bool) -> dict[str, Any]:
    return {
        "returncode": returncode,
        "line_count": stdout.count(b"\n") + (1 if stdout and not stdout.endswith(b"\n") else 0),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_present": bool(stderr),
        "output_truncated": truncated,
        "raw_output_returned": False,
    }


def run_fixed_command(name: str) -> dict[str, Any]:
    if name not in COMMANDS:
        raise KeyError("unknown snapshot command")
    candidates, arguments, timeout, output_mode = COMMANDS[name]
    executable = resolve_executable(candidates)
    if executable is None:
        return {"status": "unavailable", "command": name}
    started = utc_now()
    try:
        completed = subprocess.run(
            [executable, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=SAFE_ENV,
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout or b""
        raw_err = exc.stderr or b""
        out, out_truncated = bounded_bytes(raw_out)
        err, err_truncated = bounded_bytes(raw_err)
        record: dict[str, Any] = {
            "status": "timed_out",
            "command": name,
            "started_at_utc": iso(started),
            "completed_at_utc": iso(utc_now()),
        }
        if output_mode == "digest":
            record["result"] = _digest_summary(out, err, None, truncated=out_truncated or err_truncated)
        return record
    except OSError as exc:
        return {
            "status": "unavailable",
            "command": name,
            "error_type": type(exc).__name__,
            "started_at_utc": iso(started),
            "completed_at_utc": iso(utc_now()),
        }

    raw_out, out_truncated = bounded_bytes(completed.stdout)
    raw_err, err_truncated = bounded_bytes(completed.stderr)
    record = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "command": name,
        "returncode": completed.returncode,
        "started_at_utc": iso(started),
        "completed_at_utc": iso(utc_now()),
        "output_truncated": out_truncated or err_truncated,
    }
    if output_mode == "digest":
        record["result"] = _digest_summary(
            raw_out,
            raw_err,
            completed.returncode,
            truncated=out_truncated or err_truncated,
        )
        return record

    stdout = raw_out.decode("utf-8", errors="replace")
    stderr = raw_err.decode("utf-8", errors="replace")
    if output_mode == "json" and completed.returncode == 0:
        try:
            record["result"] = json.loads(stdout)
        except json.JSONDecodeError:
            record["status"] = "failed"
            record["error"] = "invalid_json_output"
    else:
        record["result"] = stdout.rstrip("\n")
    if stderr:
        record["stderr"] = stderr.rstrip("\n")
    return record


def read_text(path: Path, maximum: int = 65536) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return data[:maximum].decode("utf-8", errors="replace")


def os_release() -> dict[str, str]:
    text = read_text(Path("/etc/os-release")) or ""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            result[key.lower()] = value.strip().strip('"')
    return result


def memory_summary() -> dict[str, int | None]:
    text = read_text(Path("/proc/meminfo")) or ""
    wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
    values: dict[str, int | None] = {key: None for key in wanted}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        if key not in wanted:
            continue
        fields = rest.strip().split()
        if fields and fields[0].isdigit():
            values[key] = int(fields[0]) * 1024
    return {
        "total_bytes": values["MemTotal"],
        "available_bytes": values["MemAvailable"],
        "swap_total_bytes": values["SwapTotal"],
        "swap_free_bytes": values["SwapFree"],
    }


def uptime_seconds() -> float | None:
    text = read_text(Path("/proc/uptime"), 256)
    if not text:
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def configured_timezone() -> str | None:
    text = read_text(Path("/etc/timezone"), 1024)
    if text:
        value = text.strip()
        if value and len(value) <= 128:
            return value
    localtime = Path("/etc/localtime")
    try:
        if localtime.is_symlink():
            target = os.readlink(localtime)
            marker = "/zoneinfo/"
            if marker in target:
                return target.split(marker, 1)[1]
    except OSError:
        pass
    return None


def config_digests() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in CONFIG_DIGEST_PATHS:
        path = (REPO_ROOT / relative).resolve()
        try:
            if REPO_ROOT != path and REPO_ROOT not in path.parents:
                records.append({"path": relative, "status": "rejected"})
                continue
            if path.is_symlink() or not path.is_file():
                records.append({"path": relative, "status": "unavailable"})
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            records.append({"path": relative, "status": "ok", "sha256": digest})
        except OSError:
            records.append({"path": relative, "status": "unavailable"})
    return records


def service_state(unit: str) -> dict[str, Any]:
    if unit not in SERVICE_UNITS:
        raise ValueError("service unit is not approved")
    systemctl = resolve_executable(("/usr/bin/systemctl", "/bin/systemctl"))
    if systemctl is None:
        return {"unit": unit, "status": "unavailable"}
    properties = "Id,LoadState,ActiveState,SubState,UnitFileState,MainPID,ExecMainStatus,Restart,FragmentPath"
    try:
        completed = subprocess.run(
            [systemctl, "show", unit, "--no-pager", f"--property={properties}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
            env=SAFE_ENV,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"unit": unit, "status": "unavailable", "error_type": type(exc).__name__}
    out, truncated = bounded_bytes(completed.stdout, 32768)
    values: dict[str, str] = {}
    for line in out.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return {
        "unit": unit,
        "status": "ok" if completed.returncode == 0 else "failed",
        "properties": values,
        "output_truncated": truncated,
    }


def collect_snapshot() -> dict[str, Any]:
    captured = utc_now()
    now_local = dt.datetime.now().astimezone()
    commands = {name: run_fixed_command(name) for name in COMMANDS}
    services = [service_state(unit) for unit in SERVICE_UNITS]
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "collected_at_utc": iso(captured),
        "read_only": True,
        "mutation_performed": False,
        "secret_values_returned": False,
        "identity": {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
            "configured_timezone": configured_timezone(),
            "local_time": now_local.isoformat(),
            "utc_time": iso(captured),
            "uptime_seconds": uptime_seconds(),
            "os_release": os_release(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory": memory_summary(),
        },
        "storage": {
            "filesystems": commands.pop("filesystems"),
            "inodes": commands.pop("inodes"),
        },
        "network": {
            "interfaces": commands.pop("interfaces"),
            "routes": commands.pop("routes"),
            "resolver": commands.pop("resolver"),
            "listening_sockets": commands.pop("listeners"),
            "firewall_summary": commands.pop("firewall"),
        },
        "services": {
            "failed": commands.pop("failed_services"),
            "relevant": services,
            "operations_api_health": commands.pop("operations_api_health"),
            "bigbird_health": commands.pop("bigbird_health"),
        },
        "repository": {
            "root": str(REPO_ROOT),
            "head": commands.pop("git_head"),
            "branch": commands.pop("git_branch"),
            "status": commands.pop("git_status"),
            "configuration_digests": config_digests(),
        },
        "recent_critical_errors": commands.pop("critical_errors"),
    }


def render_markdown(snapshot: dict[str, Any]) -> str:
    identity = snapshot["identity"]
    service_rows = snapshot["services"]["relevant"]
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
    for item in service_rows:
        props = item.get("properties", {})
        lines.append(
            "| {unit} | {load} | {active} | {sub} | {enabled} |".format(
                unit=item.get("unit", ""),
                load=props.get("LoadState", item.get("status", "")),
                active=props.get("ActiveState", ""),
                sub=props.get("SubState", ""),
                enabled=props.get("UnitFileState", ""),
            )
        )
    lines.extend((
        "",
        "## Evidence notes",
        "",
        "- Firewall and critical-journal bulk output are returned only as bounded counts/digests.",
        "- All command targets, paths, service units, and loopback health URLs are fixed server-side.",
        "- This snapshot is read-only and is not deployment evidence until collected on Edge1.",
    ))
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = collect_snapshot()
    if args.format == "markdown":
        print(render_markdown(snapshot), end="")
    else:
        print(json.dumps(snapshot, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
