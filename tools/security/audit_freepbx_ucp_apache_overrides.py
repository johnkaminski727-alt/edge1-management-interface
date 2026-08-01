#!/usr/bin/env python3
"""Capture a secret-minimized, read-only FreePBX/UCP Apache override audit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import socket
import stat
import subprocess
import sys
from typing import Iterable

CONTRACT = "wwcx.freepbx-ucp-apache-override-audit-policy.v1"
RESULT_CONTRACT = "wwcx.freepbx-ucp-apache-override-audit-result.v1"
DEFAULT_REPO = pathlib.Path("/opt/edge1-management-interface")
DEFAULT_POLICY = pathlib.Path("config/security/freepbx-ucp-apache-override-audit-policy.json")
REDACTOR_RELATIVE = pathlib.Path("tools/security/redact-edge1-boundary-text.py")

DIRECTIVE_RE = re.compile(r"^<?/?([A-Za-z][A-Za-z0-9]*)\b")
DIRECTORY_OPEN_RE = re.compile(r"^<(Directory|DirectoryMatch)\s+(.+?)>\s*$", re.IGNORECASE)
DIRECTORY_CLOSE_RE = re.compile(r"^</(Directory|DirectoryMatch)>\s*$", re.IGNORECASE)
SAFE_OVERRIDE_VALUE_RE = re.compile(r"^[A-Za-z0-9_=+\- ]{1,256}$")
SECRET_DIRECTIVES = {
    "authuserfile",
    "authgroupfile",
    "authdigestprovider",
    "oidcclientsecret",
    "oidccryptopassphrase",
    "sessioncryptopassphrase",
    "sessioncryptopassphrasefile",
    "sslcertificatekeyfile",
    "sslstaplingcache",
}
SENSITIVE_OUTPUT_LINE_RE = re.compile(
    r"(?i)^(authorization|proxy-authorization|cookie|set-cookie)\s*:"
)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|COOKIE|PRIVATE_KEY|CLIENT_SECRET)[A-Z0-9_]*)\s*=\s*([^\s]+)"
)
URL_USERINFO_RE = re.compile(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_text(path: pathlib.Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def normalize_path_token(value: str) -> str:
    value = value.strip().strip('"\'')
    if not value.startswith("/") or "\x00" in value:
        return "<non-literal-or-withheld>"
    normalized = pathlib.PurePosixPath(value)
    if ".." in normalized.parts:
        return "<unsafe-or-withheld>"
    return str(normalized)


def safe_override_value(value: str) -> str:
    value = " ".join(value.split())
    if SAFE_OVERRIDE_VALUE_RE.fullmatch(value):
        return value
    return "<withheld>"


def parse_apache_config_text(path: pathlib.Path, text: str) -> dict:
    """Return only directory paths, DocumentRoot paths and AllowOverride values."""
    directory_stack: list[dict] = []
    directory_blocks: list[dict] = []
    document_roots: list[dict] = []
    overrides: list[dict] = []

    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        close_match = DIRECTORY_CLOSE_RE.match(line)
        if close_match:
            if directory_stack:
                directory_stack.pop()
            continue
        open_match = DIRECTORY_OPEN_RE.match(line)
        if open_match:
            block = {
                "file": str(path),
                "line": number,
                "kind": open_match.group(1).lower(),
                "path": normalize_path_token(open_match.group(2)),
            }
            directory_stack.append(block)
            directory_blocks.append(block.copy())
            continue

        parts = line.split(None, 1)
        directive = parts[0].lower()
        value = parts[1].strip() if len(parts) == 2 else ""
        if directive == "documentroot":
            document_roots.append(
                {"file": str(path), "line": number, "path": normalize_path_token(value)}
            )
        elif directive == "allowoverride":
            context = directory_stack[-1].copy() if directory_stack else {
                "file": str(path),
                "line": None,
                "kind": "global",
                "path": "<global>",
            }
            overrides.append(
                {
                    "file": str(path),
                    "line": number,
                    "context_kind": context["kind"],
                    "context_path": context["path"],
                    "value": safe_override_value(value),
                }
            )

    return {
        "directory_blocks": directory_blocks,
        "document_roots": document_roots,
        "allowoverride_occurrences": overrides,
    }


def inspect_htaccess_bytes(path: pathlib.Path, payload: bytes, mode: int) -> dict:
    """Record metadata and directive names, never directive values."""
    directive_names: set[str] = set()
    secret_bearing: set[str] = set()
    text = payload.decode("utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = DIRECTIVE_RE.match(line)
        if not match:
            continue
        name = match.group(1).lower()
        directive_names.add(name)
        if name in SECRET_DIRECTIVES:
            secret_bearing.add(name)
    return {
        "path": str(path),
        "bytes": len(payload),
        "mode": f"{stat.S_IMODE(mode):04o}",
        "sha256": sha256_bytes(payload),
        "directive_names": sorted(directive_names),
        "secret_bearing_directive_names": sorted(secret_bearing),
        "directive_values_recorded": False,
    }


def walk_regular_files(
    roots: Iterable[pathlib.Path],
    *,
    maximum_files: int,
    maximum_bytes: int,
    maximum_depth: int,
    basename: str | None = None,
) -> list[pathlib.Path]:
    results: list[pathlib.Path] = []
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = pathlib.Path(current)
            depth = len(current_path.relative_to(root).parts)
            directories[:] = [
                name
                for name in directories
                if depth < maximum_depth and not (current_path / name).is_symlink()
            ]
            for name in sorted(files):
                path = current_path / name
                if basename is not None and name != basename:
                    continue
                try:
                    info = path.lstat()
                except OSError:
                    continue
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                    continue
                if info.st_size > maximum_bytes:
                    continue
                results.append(path)
                if len(results) >= maximum_files:
                    return sorted(results)
    return sorted(results)


def sanitize_fallback(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if SENSITIVE_OUTPUT_LINE_RE.match(line.strip()):
            key = line.split(":", 1)[0]
            lines.append(f"{key}: <redacted>")
            continue
        line = URL_USERINFO_RE.sub(r"\1<redacted>@", line)
        line = SENSITIVE_ASSIGNMENT_RE.sub(r"\1=<redacted>", line)
        lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def redact_text(text: str, redactor: pathlib.Path, timeout: int) -> str:
    completed = subprocess.run(
        [sys.executable, str(redactor)],
        input=text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        return sanitize_fallback(text)
    return sanitize_fallback(completed.stdout)


def run_capture(
    name: str,
    command: list[str],
    evidence_dir: pathlib.Path,
    redactor: pathlib.Path,
    timeout: int,
    maximum_output_bytes: int,
) -> dict:
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        combined = completed.stdout + completed.stderr
        encoded = combined.encode("utf-8", errors="replace")[:maximum_output_bytes]
        sanitized = redact_text(encoded.decode("utf-8", errors="replace"), redactor, timeout)
        write_text(evidence_dir / f"{name}.txt", sanitized)
        record = {
            "name": name,
            "command": command,
            "exit_code": completed.returncode,
            "timed_out": False,
            "output_truncated": len(combined.encode("utf-8", errors="replace")) > maximum_output_bytes,
            "raw_output_recorded": False,
        }
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        sanitized = redact_text(partial[:maximum_output_bytes], redactor, timeout)
        write_text(evidence_dir / f"{name}.txt", sanitized)
        record = {
            "name": name,
            "command": command,
            "exit_code": None,
            "timed_out": True,
            "output_truncated": len(partial.encode("utf-8", errors="replace")) > maximum_output_bytes,
            "raw_output_recorded": False,
        }
    write_text(evidence_dir / f"{name}.json", json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def load_policy(path: pathlib.Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("contract") != CONTRACT:
        raise SystemExit("policy contract mismatch")
    if value.get("execution_authorized") is not True:
        raise SystemExit("read-only audit is not authorized")
    guard = value.get("guardrails", {})
    required_true = ("read_only_host_inspection", "evidence_writes_only")
    required_false = (
        "follow_symlinks",
        "record_htaccess_values",
        "record_secret_directive_values",
        "record_authentication_material",
        "record_cookie_values",
        "record_environment",
        "apache_configuration_change",
        "service_reload_or_restart",
        "module_or_site_enablement",
        "route_or_authentication_change",
        "listener_or_firewall_change",
        "production_traffic_change",
    )
    if not all(guard.get(key) is True for key in required_true):
        raise SystemExit("required read-only guardrail is absent")
    if not all(guard.get(key) is False for key in required_false):
        raise SystemExit("mutation or disclosure guardrail mismatch")
    return value


def git_value(repo: pathlib.Path, *args: str) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def approved_candidate_root(path: str, configured: list[pathlib.Path]) -> pathlib.Path | None:
    if not path.startswith("/") or path.startswith("<"):
        return None
    candidate = pathlib.Path(path)
    allowed_prefixes = [pathlib.Path("/var/www"), pathlib.Path("/usr/share/freepbx")]
    if not any(candidate == prefix or prefix in candidate.parents for prefix in allowed_prefixes):
        return None
    if any(candidate == configured_root or configured_root in candidate.parents or candidate in configured_root.parents for configured_root in configured):
        return candidate
    return None


def build_manifest(evidence_dir: pathlib.Path) -> None:
    rows: list[str] = []
    for path in sorted(evidence_dir.iterdir()):
        if not path.is_file() or path.name == "sha256-manifest.txt":
            continue
        rows.append(f"{sha256_bytes(path.read_bytes())}  {path.name}")
    write_text(evidence_dir / "sha256-manifest.txt", "\n".join(rows) + ("\n" if rows else ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, default=DEFAULT_REPO)
    parser.add_argument("--policy", type=pathlib.Path)
    parser.add_argument("--evidence-root", type=pathlib.Path)
    arguments = parser.parse_args(argv)

    repo = arguments.repo.resolve()
    policy_path = arguments.policy or (repo / DEFAULT_POLICY)
    policy = load_policy(policy_path)
    redactor = repo / REDACTOR_RELATIVE

    if os.geteuid() != 0:
        raise SystemExit("run as root")
    if not (repo / ".git").is_dir():
        raise SystemExit(f"repository not found: {repo}")
    if not redactor.is_file():
        raise SystemExit("evidence redactor is unavailable")
    hostname = socket.getfqdn() or socket.gethostname()
    if hostname not in policy["expected_hostnames"] and socket.gethostname() not in policy["expected_hostnames"]:
        raise SystemExit(f"unexpected host: {hostname}")
    if git_value(repo, "branch", "--show-current") != "main":
        raise SystemExit("audit requires main")
    if git_value(repo, "status", "--porcelain"):
        raise SystemExit("repository is dirty; preserve unrelated work before audit")

    limits = policy["limits"]
    evidence_root = arguments.evidence_root or pathlib.Path(policy["evidence_root"])
    evidence_dir = evidence_root / utc_stamp()
    evidence_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(evidence_dir, 0o700)

    write_text(evidence_dir / "started-at.txt", dt.datetime.now(dt.timezone.utc).isoformat() + "\n")
    write_text(evidence_dir / "hostname.txt", hostname + "\n")
    write_text(evidence_dir / "principal.txt", f"uid={os.geteuid()} gid={os.getegid()}\n")
    write_text(evidence_dir / "repository-revision.txt", git_value(repo, "rev-parse", "HEAD") + "\n")
    write_text(evidence_dir / "repository-status.txt", git_value(repo, "status", "--short", "--branch") + "\n")

    apache_ctl = next(
        (pathlib.Path(value) for value in policy["apache_command_candidates"] if os.access(value, os.X_OK)),
        None,
    )
    if apache_ctl is None:
        raise SystemExit("Apache control command is unavailable")

    timeout = int(limits["command_timeout_seconds"])
    maximum_output = int(limits["maximum_command_output_bytes"])
    captures = {
        "apache-config-test": run_capture(
            "apache-config-test", [str(apache_ctl), "-t"], evidence_dir, redactor, timeout, maximum_output
        ),
        "apache-vhosts": run_capture(
            "apache-vhosts", [str(apache_ctl), "-S"], evidence_dir, redactor, timeout, maximum_output
        ),
        "apache-modules": run_capture(
            "apache-modules", [str(apache_ctl), "-M"], evidence_dir, redactor, timeout, maximum_output
        ),
        "apache-runtime-config": run_capture(
            "apache-runtime-config",
            [str(apache_ctl), "-t", "-D", "DUMP_RUN_CFG"],
            evidence_dir,
            redactor,
            timeout,
            maximum_output,
        ),
    }

    config_roots = [pathlib.Path(value) for value in policy["apache_config_roots"]]
    config_paths = walk_regular_files(
        config_roots,
        maximum_files=int(limits["maximum_config_files"]),
        maximum_bytes=int(limits["maximum_config_file_bytes"]),
        maximum_depth=int(limits["maximum_walk_depth"]),
    )
    parsed = {"directory_blocks": [], "document_roots": [], "allowoverride_occurrences": []}
    config_hashes: list[dict] = []
    for path in config_paths:
        payload = path.read_bytes()
        config_hashes.append({"path": str(path), "sha256": sha256_bytes(payload), "bytes": len(payload)})
        value = parse_apache_config_text(path, payload.decode("utf-8", errors="replace"))
        for key in parsed:
            parsed[key].extend(value[key])
    write_text(evidence_dir / "apache-config-hashes.json", json.dumps(config_hashes, indent=2, sort_keys=True) + "\n")
    write_text(evidence_dir / "apache-override-observations.json", json.dumps(parsed, indent=2, sort_keys=True) + "\n")

    configured_roots = [pathlib.Path(value) for value in policy["web_root_candidates"]]
    candidate_roots: set[pathlib.Path] = {path for path in configured_roots if path.is_dir() and not path.is_symlink()}
    for record in parsed["document_roots"] + parsed["directory_blocks"]:
        candidate = approved_candidate_root(record["path"], configured_roots)
        if candidate is not None and candidate.is_dir() and not candidate.is_symlink():
            candidate_roots.add(candidate)

    htaccess_paths = walk_regular_files(
        sorted(candidate_roots),
        maximum_files=int(limits["maximum_htaccess_files"]),
        maximum_bytes=int(limits["maximum_htaccess_file_bytes"]),
        maximum_depth=int(limits["maximum_walk_depth"]),
        basename=".htaccess",
    )
    htaccess_records: list[dict] = []
    for path in htaccess_paths:
        info = path.lstat()
        htaccess_records.append(inspect_htaccess_bytes(path, path.read_bytes(), info.st_mode))
    write_text(evidence_dir / "freepbx-htaccess-inventory.json", json.dumps(htaccess_records, indent=2, sort_keys=True) + "\n")

    result = {
        "contract": RESULT_CONTRACT,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "hostname": hostname,
        "repository_revision": git_value(repo, "rev-parse", "HEAD"),
        "apache_command": str(apache_ctl),
        "apache_config_test_passed": captures["apache-config-test"]["exit_code"] == 0,
        "runtime_config_dump_captured": (evidence_dir / "apache-runtime-config.txt").is_file(),
        "directory_blocks_observed": len(parsed["directory_blocks"]),
        "allowoverride_occurrences_observed": len(parsed["allowoverride_occurrences"]),
        "candidate_web_roots": [str(path) for path in sorted(candidate_roots)],
        "htaccess_files_observed": len(htaccess_records),
        "htaccess_values_recorded": False,
        "secret_directive_values_recorded": False,
        "authentication_material_recorded": False,
        "raw_command_output_recorded": False,
        "manual_effective_policy_review_required": True,
        "effective_policy_determined": False,
        "apache_configuration_changed": False,
        "service_reloaded_or_restarted": False,
        "module_or_site_enablement_changed": False,
        "route_or_authentication_changed": False,
        "listener_or_firewall_changed": False,
        "production_traffic_changed": False,
        "mutation_performed": False,
    }
    write_text(evidence_dir / "result.json", json.dumps(result, indent=2, sort_keys=True) + "\n")
    build_manifest(evidence_dir)

    print(f"FreePBX/UCP Apache override audit completed: {evidence_dir}")
    print("No Apache, module, site, service, authentication, route, listener, firewall, or traffic state was changed.")
    return 0 if result["apache_config_test_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
