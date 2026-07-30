#!/usr/bin/env python3
"""Collect a bounded read-only Edge1 publication and authentication boundary inventory.

The committed policy is disabled. The collector writes only JSON to stdout. It
never changes files, services, routes, listeners, authentication, or traffic and
never reads secret file contents.
"""

from __future__ import annotations

import argparse
import datetime as dt
import grp
import hashlib
import json
import os
import platform
import pwd
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "security" / "edge1-live-boundary-inventory-policy.json"
CONTRACT = "wwcx.edge1-live-boundary-inventory-policy.v1"
OUTPUT_CONTRACT = "wwcx.edge1-live-boundary-inventory.v1"
SAFE_ENV = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "NO_PROXY": "*",
    "no_proxy": "*",
}
TOP_LEVEL_FIELDS = {
    "contract",
    "status",
    "enabled",
    "execution_authorized",
    "expected_hostnames",
    "repository_root",
    "filesystem_roots",
    "metadata_only_paths",
    "apache_config_root",
    "route_host",
    "route_paths",
    "units",
    "command_candidates",
    "limits",
    "route_probe",
    "apache_directives",
    "output",
    "acceptance",
}
COMMAND_KEYS = {"git", "apachectl", "systemctl", "ss", "dpkg_query", "curl"}
SAFE_HEADER_NAMES = {
    "cache-control",
    "content-security-policy",
    "referrer-policy",
    "x-content-type-options",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "access-control-allow-origin",
    "content-type",
    "server",
}
APACHE_FILE_NAMES = {"apache2.conf", "ports.conf"}
APACHE_SUFFIXES = {".conf", ".load"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def load_policy(path: Path = DEFAULT_POLICY) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("inventory policy must be a JSON object")
    return value


def require_fields(value: Any, fields: Iterable[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{label} fields do not match the contract")
    return value


def safe_absolute_path(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise ValueError("absolute path required")
    normalized = os.path.normpath(value)
    if normalized != value or normalized == "/":
        raise ValueError("path must be normalized and must not be filesystem root")
    return value


def validate_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_FIELDS:
        raise ValueError("inventory policy fields do not match the contract")
    if policy.get("contract") != CONTRACT or policy.get("status") != "design_only":
        raise ValueError("unsupported inventory policy contract or status")
    for key in ("enabled", "execution_authorized"):
        if not isinstance(policy.get(key), bool):
            raise ValueError(f"{key} must be boolean")

    hostnames = policy.get("expected_hostnames")
    if not isinstance(hostnames, list) or not hostnames or len(hostnames) > 8:
        raise ValueError("expected_hostnames must be a bounded list")
    if any(not isinstance(value, str) or not value or len(value) > 253 for value in hostnames):
        raise ValueError("invalid expected hostname")

    repository_root = safe_absolute_path(policy.get("repository_root"))
    if repository_root != "/opt/edge1-management-interface":
        raise ValueError("repository root is not approved")

    roots = policy.get("filesystem_roots")
    expected_roots = [
        "/var/www/edge1-status",
        "/var/lib/wwcx-public-summary",
        "/var/lib/wwcx-edge1-ops",
    ]
    if roots != expected_roots:
        raise ValueError("filesystem roots do not match the approved boundary")
    for value in roots:
        safe_absolute_path(value)

    metadata_paths = policy.get("metadata_only_paths")
    expected_metadata = [
        "/etc/wwcx-edge1-ops",
        "/etc/wwcx-edge1-ops/oidc.json",
        "/etc/wwcx-edge1-ops/client-secret",
    ]
    if metadata_paths != expected_metadata:
        raise ValueError("metadata-only paths do not match the approved boundary")

    if policy.get("apache_config_root") != "/etc/apache2":
        raise ValueError("Apache configuration root is not approved")
    if policy.get("route_host") != "edge1.ww.cx":
        raise ValueError("route host is not approved")
    routes = policy.get("route_paths")
    if not isinstance(routes, list) or not routes or len(routes) > 64:
        raise ValueError("route_paths must be a bounded list")
    if any(
        not isinstance(path, str)
        or not path.startswith("/")
        or "?" in path
        or "#" in path
        or "%" in path
        or "\\" in path
        or "\x00" in path
        or "//" in path[1:]
        for path in routes
    ):
        raise ValueError("route path is unsafe")
    if len(routes) != len(set(routes)):
        raise ValueError("route paths must be unique")

    units = policy.get("units")
    if not isinstance(units, list) or not units or len(units) > 64:
        raise ValueError("units must be a bounded list")
    if any(not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]+", unit) for unit in units):
        raise ValueError("invalid systemd unit name")
    if len(units) != len(set(units)):
        raise ValueError("systemd units must be unique")

    commands = require_fields(policy.get("command_candidates"), COMMAND_KEYS, "command_candidates")
    for key, candidates in commands.items():
        if not isinstance(candidates, list) or not candidates or len(candidates) > 4:
            raise ValueError(f"command_candidates.{key} must be a bounded list")
        for candidate in candidates:
            path = safe_absolute_path(candidate)
            if not path.startswith(("/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/")):
                raise ValueError("command candidate is outside system command roots")

    limit_fields = {
        "command_timeout_seconds",
        "maximum_command_output_bytes",
        "maximum_files",
        "maximum_total_file_bytes",
        "maximum_single_file_bytes",
        "maximum_apache_config_files",
        "maximum_apache_config_bytes",
    }
    limits = require_fields(policy.get("limits"), limit_fields, "limits")
    numeric_bounds = {
        "command_timeout_seconds": (1, 120),
        "maximum_command_output_bytes": (4096, 8 * 1024 * 1024),
        "maximum_files": (1, 100000),
        "maximum_total_file_bytes": (1, 50 * 1024 * 1024 * 1024),
        "maximum_single_file_bytes": (1, 5 * 1024 * 1024 * 1024),
        "maximum_apache_config_files": (1, 10000),
        "maximum_apache_config_bytes": (1, 128 * 1024 * 1024),
    }
    for key, (minimum, maximum) in numeric_bounds.items():
        value = limits.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"limits.{key} is outside the accepted range")

    route_probe_expected = {
        "local_loopback": True,
        "public_network": True,
        "method": "HEAD",
        "maximum_redirects": 0,
        "timeout_seconds": 10,
        "capture_body": False,
        "capture_set_cookie_values": False,
        "capture_location_query": False,
    }
    route_probe = require_fields(policy.get("route_probe"), route_probe_expected, "route_probe")
    if route_probe != route_probe_expected:
        raise ValueError("route probe contract does not match")

    directive_fields = {"allowed_names", "sensitive_name_fragments"}
    directives = require_fields(policy.get("apache_directives"), directive_fields, "apache_directives")
    allowed_names = directives.get("allowed_names")
    sensitive_fragments = directives.get("sensitive_name_fragments")
    if not isinstance(allowed_names, list) or not allowed_names or len(allowed_names) > 128:
        raise ValueError("Apache directive allowlist is invalid")
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) for name in allowed_names):
        raise ValueError("invalid Apache directive name")
    if len({name.lower() for name in allowed_names}) != len(allowed_names):
        raise ValueError("Apache directive names must be unique")
    if not isinstance(sensitive_fragments, list) or not sensitive_fragments:
        raise ValueError("sensitive directive fragments are required")
    if any(not isinstance(fragment, str) or not fragment.islower() or not fragment for fragment in sensitive_fragments):
        raise ValueError("sensitive directive fragments must be lowercase strings")

    output_expected = {
        "stdout_only": True,
        "format": "json",
        "secret_contents": False,
        "raw_cookie_values": False,
        "raw_token_values": False,
        "raw_location_queries": False,
    }
    output = require_fields(policy.get("output"), output_expected, "output")
    if output != output_expected:
        raise ValueError("output contract does not match")

    acceptance_fields = {
        "read_only_commands_only",
        "filesystem_follow_symlinks",
        "sha256_regular_files",
        "metadata_only_secret_paths",
        "no_output_file",
        "no_configuration_change",
        "no_service_change",
        "no_listener_change",
        "no_route_change",
        "no_authentication_change",
        "no_traffic_change",
        "mutation_performed",
        "traffic_controls_changed",
        "live_execution_authorized",
    }
    acceptance = require_fields(policy.get("acceptance"), acceptance_fields, "acceptance")
    required_true = {
        "read_only_commands_only",
        "sha256_regular_files",
        "metadata_only_secret_paths",
        "no_output_file",
        "no_configuration_change",
        "no_service_change",
        "no_listener_change",
        "no_route_change",
        "no_authentication_change",
        "no_traffic_change",
    }
    for key in required_true:
        if acceptance.get(key) is not True:
            raise ValueError(f"acceptance.{key} must be true")
    if acceptance.get("filesystem_follow_symlinks") is not False:
        raise ValueError("filesystem symlinks must not be followed")
    for key in ("mutation_performed", "traffic_controls_changed"):
        if acceptance.get(key) is not False:
            raise ValueError(f"acceptance.{key} must remain false")
    if not isinstance(acceptance.get("live_execution_authorized"), bool):
        raise ValueError("acceptance.live_execution_authorized must be boolean")

    if policy["enabled"] or policy["execution_authorized"] or acceptance["live_execution_authorized"]:
        if not (
            policy["enabled"]
            and policy["execution_authorized"]
            and acceptance["live_execution_authorized"]
        ):
            raise ValueError("partial live inventory authorization is forbidden")
    return policy


def resolve_command(policy: Dict[str, Any], key: str) -> Optional[str]:
    if key not in COMMAND_KEYS:
        raise KeyError("unapproved command key")
    for candidate in policy["command_candidates"][key]:
        path = Path(candidate)
        try:
            info = path.stat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and os.access(path, os.X_OK):
            return str(path)
    return None


def bounded_text(value: bytes, maximum: int) -> Tuple[str, bool]:
    truncated = len(value) > maximum
    selected = value[:maximum]
    return selected.decode("utf-8", errors="replace"), truncated


def run_command(
    argv: Sequence[str],
    *,
    timeout_seconds: int,
    maximum_output_bytes: int,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    if not argv or not os.path.isabs(argv[0]):
        raise ValueError("command executable must be an absolute path")
    started = utc_now()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=SAFE_ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
        stdout, stdout_truncated = bounded_text(completed.stdout, maximum_output_bytes)
        stderr, stderr_truncated = bounded_text(completed.stderr, maximum_output_bytes)
        return {
            "available": True,
            "argv": list(argv),
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "started_at": iso(started),
            "completed_at": iso(utc_now()),
        }
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = bounded_text(exc.stdout or b"", maximum_output_bytes)
        stderr, stderr_truncated = bounded_text(exc.stderr or b"", maximum_output_bytes)
        return {
            "available": True,
            "argv": list(argv),
            "returncode": None,
            "timed_out": True,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "started_at": iso(started),
            "completed_at": iso(utc_now()),
        }
    except OSError as exc:
        return {
            "available": False,
            "argv": list(argv),
            "error_type": type(exc).__name__,
            "errno": getattr(exc, "errno", None),
            "started_at": iso(started),
            "completed_at": iso(utc_now()),
        }


def command_result(
    policy: Dict[str, Any],
    key: str,
    arguments: Sequence[str],
    *,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    executable = resolve_command(policy, key)
    if executable is None:
        return {"available": False, "command_key": key, "reason": "command_unavailable"}
    result = run_command(
        [executable, *arguments],
        timeout_seconds=policy["limits"]["command_timeout_seconds"],
        maximum_output_bytes=policy["limits"]["maximum_command_output_bytes"],
        cwd=cwd,
    )
    result["command_key"] = key
    return result


def identity_record() -> Dict[str, Any]:
    uid = os.geteuid()
    gid = os.getegid()
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    try:
        group = grp.getgrgid(gid).gr_name
    except KeyError:
        group = str(gid)
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "uid": uid,
        "gid": gid,
        "user": user,
        "group": group,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }


def validate_host(policy: Dict[str, Any], identity: Dict[str, Any]) -> None:
    candidates = {identity["hostname"].lower(), identity["fqdn"].lower()}
    expected = {value.lower() for value in policy["expected_hostnames"]}
    if not candidates.intersection(expected):
        raise RuntimeError("host identity does not match the authorized inventory policy")


def safe_name(uid: int, gid: int) -> Tuple[str, str]:
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError:
        user = str(uid)
    try:
        group = grp.getgrgid(gid).gr_name
    except KeyError:
        group = str(gid)
    return user, group


def file_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "other"


def metadata_record(path: Path, *, include_symlink_target: bool = True) -> Dict[str, Any]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"path": str(path), "exists": False}
    except OSError as exc:
        return {
            "path": str(path),
            "exists": None,
            "error_type": type(exc).__name__,
            "errno": getattr(exc, "errno", None),
        }
    user, group = safe_name(info.st_uid, info.st_gid)
    record = {
        "path": str(path),
        "exists": True,
        "type": file_type(info.st_mode),
        "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        "uid": info.st_uid,
        "gid": info.st_gid,
        "user": user,
        "group": group,
        "bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
    }
    if stat.S_ISLNK(info.st_mode):
        record["symlink_target"] = os.readlink(path) if include_symlink_target else "redacted"
    return record


def sha256_path(path: Path, maximum_bytes: int) -> Tuple[Optional[str], str]:
    info = path.stat(follow_symlinks=False)
    if info.st_size > maximum_bytes:
        return None, "single_file_limit"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    if HEX64.fullmatch(value) is None:
        raise RuntimeError("invalid SHA-256 result")
    return value, "hashed"


def inventory_tree(root: Path, limits: Dict[str, int]) -> Dict[str, Any]:
    root_record = metadata_record(root)
    result: Dict[str, Any] = {
        "root": str(root),
        "root_metadata": root_record,
        "entries": [],
        "counts": {"entries": 0, "regular_files": 0, "directories": 0, "symlinks": 0},
        "total_regular_file_bytes": 0,
        "complete": True,
        "limitations": [],
    }
    if root_record.get("exists") is not True or root_record.get("type") != "directory":
        result["complete"] = root_record.get("exists") is False
        return result

    maximum_files = limits["maximum_files"]
    maximum_total = limits["maximum_total_file_bytes"]
    maximum_single = limits["maximum_single_file_bytes"]
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(os.scandir(current), key=lambda entry: entry.name, reverse=True)
        except OSError as exc:
            result["complete"] = False
            result["limitations"].append({
                "path": str(current),
                "reason": "scan_error",
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
            })
            continue
        for child in children:
            if result["counts"]["entries"] >= maximum_files:
                result["complete"] = False
                result["limitations"].append({"reason": "maximum_files"})
                stack.clear()
                break
            path = Path(child.path)
            record = metadata_record(path)
            record["relative_path"] = path.relative_to(root).as_posix()
            entry_type = record.get("type")
            if entry_type == "directory":
                result["counts"]["directories"] += 1
                stack.append(path)
            elif entry_type == "symlink":
                result["counts"]["symlinks"] += 1
            elif entry_type == "regular":
                result["counts"]["regular_files"] += 1
                size = int(record.get("bytes", 0))
                result["total_regular_file_bytes"] += size
                if result["total_regular_file_bytes"] > maximum_total:
                    record["sha256"] = None
                    record["hash_state"] = "total_file_limit"
                    result["complete"] = False
                    result["limitations"].append({"reason": "maximum_total_file_bytes"})
                else:
                    try:
                        digest, state = sha256_path(path, maximum_single)
                        record["sha256"] = digest
                        record["hash_state"] = state
                        if state != "hashed":
                            result["complete"] = False
                            result["limitations"].append({
                                "path": record["relative_path"],
                                "reason": state,
                            })
                    except OSError as exc:
                        record["sha256"] = None
                        record["hash_state"] = "hash_error"
                        record["hash_error_type"] = type(exc).__name__
                        record["hash_errno"] = getattr(exc, "errno", None)
                        result["complete"] = False
            result["entries"].append(record)
            result["counts"]["entries"] += 1
    result["entries"].sort(key=lambda item: item.get("relative_path", ""))
    return result


def inventory_metadata_only(paths: Sequence[str]) -> List[Dict[str, Any]]:
    return [metadata_record(Path(path), include_symlink_target=False) for path in paths]


def apache_config_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    root = Path(policy["apache_config_root"])
    limits = policy["limits"]
    allowed = {name.lower(): name for name in policy["apache_directives"]["allowed_names"]}
    sensitive = tuple(policy["apache_directives"]["sensitive_name_fragments"])
    result: Dict[str, Any] = {
        "root": str(root),
        "root_metadata": metadata_record(root),
        "directives": [],
        "files_read": 0,
        "bytes_read": 0,
        "complete": True,
        "limitations": [],
    }
    if not root.is_dir() or root.is_symlink():
        return result

    candidates: List[Path] = []
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if not (Path(current) / name).is_symlink()
        )
        for name in sorted(file_names):
            path = Path(current) / name
            if path.is_symlink():
                continue
            if name in APACHE_FILE_NAMES or path.suffix in APACHE_SUFFIXES:
                candidates.append(path)
    for path in sorted(candidates):
        if result["files_read"] >= limits["maximum_apache_config_files"]:
            result["complete"] = False
            result["limitations"].append({"reason": "maximum_apache_config_files"})
            break
        try:
            info = path.stat(follow_symlinks=False)
        except OSError as exc:
            result["complete"] = False
            result["limitations"].append({
                "path": str(path),
                "reason": "stat_error",
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
            })
            continue
        if result["bytes_read"] + info.st_size > limits["maximum_apache_config_bytes"]:
            result["complete"] = False
            result["limitations"].append({"reason": "maximum_apache_config_bytes"})
            break
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result["complete"] = False
            result["limitations"].append({
                "path": str(path),
                "reason": "read_error",
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
            })
            continue
        result["files_read"] += 1
        result["bytes_read"] += info.st_size
        relative = path.relative_to(root).as_posix()
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or len(line) > 8192:
                continue
            pieces = line.split(None, 1)
            directive_key = pieces[0].lower()
            if directive_key not in allowed:
                continue
            canonical = allowed[directive_key]
            value = pieces[1].strip() if len(pieces) == 2 else ""
            if any(fragment in directive_key for fragment in sensitive):
                value = "[REDACTED]"
            else:
                value = " ".join(value.split())[:1024]
            result["directives"].append({
                "file": relative,
                "line": line_number,
                "directive": canonical,
                "value": value,
            })
    return result


def parse_cookie_metadata(values: Sequence[str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for value in values:
        parts = [part.strip() for part in value.split(";") if part.strip()]
        if not parts:
            continue
        name = parts[0].split("=", 1)[0].strip()[:128]
        flags = {part.lower(): part for part in parts[1:]}
        same_site = None
        path_present = False
        domain_present = False
        for part in parts[1:]:
            lowered = part.lower()
            if lowered.startswith("samesite="):
                same_site = part.split("=", 1)[1][:32]
            elif lowered.startswith("path="):
                path_present = True
            elif lowered.startswith("domain="):
                domain_present = True
        records.append({
            "name": name,
            "secure": "secure" in flags,
            "http_only": "httponly" in flags,
            "same_site": same_site,
            "path_present": path_present,
            "domain_present": domain_present,
            "value_captured": False,
        })
    return records


def parse_header_output(text: str) -> Dict[str, Any]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("HTTP/"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            if line == "":
                blocks.append(current)
                current = []
            else:
                current.append(line)
    if current:
        blocks.append(current)
    if not blocks:
        return {"parsed": False, "status": None, "headers": {}, "cookies": []}
    block = blocks[-1]
    status_parts = block[0].split(None, 2)
    status = int(status_parts[1]) if len(status_parts) > 1 and status_parts[1].isdigit() else None
    headers: Dict[str, List[str]] = {}
    for line in block[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.setdefault(name.strip().lower(), []).append(value.strip())
    safe: Dict[str, Any] = {}
    for name in sorted(SAFE_HEADER_NAMES):
        if name in headers:
            safe[name] = headers[name]
    location = None
    if headers.get("location"):
        parsed = urlsplit(headers["location"][-1])
        location = {
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "query_present": bool(parsed.query),
            "query_captured": False,
            "fragment_present": bool(parsed.fragment),
        }
    authenticate_schemes = []
    for value in headers.get("www-authenticate", []):
        scheme = value.split(None, 1)[0][:64]
        if scheme:
            authenticate_schemes.append(scheme)
    return {
        "parsed": True,
        "status": status,
        "headers": safe,
        "location": location,
        "www_authenticate_schemes": authenticate_schemes,
        "cookies": parse_cookie_metadata(headers.get("set-cookie", [])),
    }


def route_probe(policy: Dict[str, Any], path: str, *, local: bool) -> Dict[str, Any]:
    host = policy["route_host"]
    timeout = str(policy["route_probe"]["timeout_seconds"])
    arguments = [
        "--silent",
        "--show-error",
        "--head",
        "--max-time",
        timeout,
        "--max-redirs",
        "0",
    ]
    if local:
        arguments.extend(["--resolve", f"{host}:443:127.0.0.1"])
    arguments.append(f"https://{host}{path}")
    command = command_result(policy, "curl", arguments)
    parsed = parse_header_output(command.get("stdout", "")) if command.get("available") else {
        "parsed": False,
        "status": None,
        "headers": {},
        "cookies": [],
    }
    return {
        "path": path,
        "vantage": "loopback" if local else "public_network",
        "command": command,
        "response": parsed,
        "body_captured": False,
        "raw_cookie_values_captured": False,
        "raw_location_query_captured": False,
    }


def repository_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    root = Path(policy["repository_root"])
    commands = {
        "toplevel": ["rev-parse", "--show-toplevel"],
        "head": ["rev-parse", "--verify", "HEAD"],
        "branch": ["branch", "--show-current"],
        "status": ["status", "--porcelain=v1", "--untracked-files=all"],
    }
    return {
        "root": str(root),
        "root_metadata": metadata_record(root),
        "commands": {
            name: command_result(policy, "git", arguments, cwd=root)
            for name, arguments in commands.items()
        },
    }


def apache_command_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    commands = {
        "version": ["-V"],
        "modules": ["-M"],
        "virtual_hosts": ["-S"],
        "configuration_test": ["-t"],
        "runtime_configuration": ["-t", "-D", "DUMP_RUN_CFG"],
    }
    return {
        name: command_result(policy, "apachectl", arguments)
        for name, arguments in commands.items()
    }


def package_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    return command_result(
        policy,
        "dpkg_query",
        [
            "-W",
            "-f=${Package}\t${Status}\t${Version}\n",
            "apache2",
            "libapache2-mod-auth-openidc",
        ],
    )


def unit_inventory(policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    properties = "LoadState,ActiveState,SubState,UnitFileState,FragmentPath,MainPID"
    records = []
    for unit in policy["units"]:
        records.append({
            "unit": unit,
            "show": command_result(
                policy,
                "systemctl",
                ["show", unit, f"--property={properties}", "--no-pager"],
            ),
        })
    return records


def listener_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    return command_result(policy, "ss", ["-H", "-lntup"])


def capacity_inventory(paths: Sequence[str]) -> List[Dict[str, Any]]:
    records = []
    for value in paths:
        path = Path(value)
        probe = path if path.exists() else path.parent
        try:
            info = os.statvfs(probe)
            records.append({
                "path": value,
                "probe_path": str(probe),
                "block_size": info.f_frsize,
                "total_bytes": info.f_blocks * info.f_frsize,
                "free_bytes": info.f_bfree * info.f_frsize,
                "available_bytes": info.f_bavail * info.f_frsize,
            })
        except OSError as exc:
            records.append({
                "path": value,
                "probe_path": str(probe),
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
            })
    return records


def collect_inventory(policy: Dict[str, Any]) -> Dict[str, Any]:
    validate_policy(policy)
    identity = identity_record()
    validate_host(policy, identity)
    local_routes = [route_probe(policy, path, local=True) for path in policy["route_paths"]]
    public_routes = [route_probe(policy, path, local=False) for path in policy["route_paths"]]
    return {
        "contract": OUTPUT_CONTRACT,
        "generated_at": iso(utc_now()),
        "identity": identity,
        "repository": repository_inventory(policy),
        "apache": {
            "commands": apache_command_inventory(policy),
            "configuration": apache_config_inventory(policy),
            "packages": package_inventory(policy),
        },
        "routes": {
            "host": policy["route_host"],
            "loopback": local_routes,
            "public_network": public_routes,
        },
        "filesystems": [
            inventory_tree(Path(root), policy["limits"])
            for root in policy["filesystem_roots"]
        ],
        "metadata_only_paths": inventory_metadata_only(policy["metadata_only_paths"]),
        "units": unit_inventory(policy),
        "listeners": listener_inventory(policy),
        "capacity": capacity_inventory(policy["filesystem_roots"]),
        "secret_contents_read": False,
        "raw_cookie_values_captured": False,
        "raw_token_values_captured": False,
        "raw_location_queries_captured": False,
        "output_file_written": False,
        "mutation_performed": False,
        "traffic_controls_changed": False,
    }


def design_status(policy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "contract": "wwcx.edge1-live-boundary-inventory-status.v1",
        "state": policy["status"],
        "enabled": policy["enabled"],
        "execution_authorized": policy["execution_authorized"],
        "live_execution_authorized": policy["acceptance"]["live_execution_authorized"],
        "stdout_only": policy["output"]["stdout_only"],
        "mutation_performed": False,
        "traffic_controls_changed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack-read-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    policy = validate_policy(load_policy(args.policy))
    if not args.execute:
        print(json.dumps(design_status(policy), sort_keys=True))
        return
    if not args.ack_read_only:
        raise SystemExit("--ack-read-only is required for inventory execution")
    if not (
        policy["enabled"]
        and policy["execution_authorized"]
        and policy["acceptance"]["live_execution_authorized"]
    ):
        raise SystemExit("live inventory is not authorized by policy")
    print(json.dumps(collect_inventory(policy), sort_keys=True))


if __name__ == "__main__":
    main()
