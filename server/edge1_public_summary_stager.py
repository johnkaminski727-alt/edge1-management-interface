#!/usr/bin/env python3
"""Build an atomic minimized Edge1 public-summary release in a non-public tree.

The committed policy is disabled. This module does not write to /var/www, alter
Apache, open a listener, execute commands, prune releases, or publish a route.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

from edge1_public_status_exporter import build_public_status, load_object, write_public_status

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config" / "security" / "edge1-public-summary-staging-policy.json"
APPROVED_STATIC_ROOT = Path("/opt/edge1-management-interface/src/web/public-status")
APPROVED_STAGING_ROOT = Path("/var/lib/wwcx-public-summary")
APPROVED_SOURCES = {
    "security": Path("/var/www/edge1-status/security-operations.json"),
    "network_defense": Path("/var/www/edge1-status/network-defense/data/network-defense.json"),
    "operations": Path("/var/www/edge1-status/operations-health.json"),
}
RELEASE_ASSETS = ("index.html", "app.js", "style.css", "public/status.json")
STATIC_ASSETS = ("index.html", "app.js", "style.css")
PUBLIC_ROOT_ROUTE = "/edge1-status/"
PUBLIC_FEED_ROUTE = "/edge1-status/public/status.json"
CSP = "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
MAX_STATIC_BYTES = 1_000_000
FORBIDDEN_PUBLIC_TOKENS = (
    "security-operations.json",
    "security-correlation.json",
    "network-defense.json",
    "operations-inventory.json",
    "operations-network.json",
    "operations-version.json",
    "operations-incidents.json",
    "bitcoin-wallet.json",
    "bitcoin-mining.json",
    "reports/index.json",
    "/edge1-ops/",
    "/edge1-status/security/",
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat()


def load_policy(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("staging policy must be an object")
    return value


def validate_policy(policy: dict[str, Any], *, enforce_production_paths: bool = True) -> None:
    if policy.get("contract") != "wwcx.edge1-public-summary-staging-policy.v1":
        raise ValueError("unsupported staging policy contract")
    if policy.get("status") != "design_only":
        raise ValueError("staging policy status must remain design_only")
    if policy.get("activation_requires_explicit_authorization") is not True:
        raise ValueError("explicit authorization gate is required")
    if policy.get("live_publication_authorized") is not False:
        raise ValueError("live publication must remain unauthorized")
    if policy.get("public_routes") != {"root": PUBLIC_ROOT_ROUTE, "feed": PUBLIC_FEED_ROUTE}:
        raise ValueError("public route contract does not match the approved boundary")
    if tuple(policy.get("release_assets") or ()) != RELEASE_ASSETS:
        raise ValueError("release asset allowlist is not exact")

    expected_headers = {
        "cache_control": "no-store, max-age=0",
        "content_security_policy": CSP,
        "referrer_policy": "no-referrer",
        "x_content_type_options": "nosniff",
        "cors_allow_origin": None,
        "directory_listing": False,
    }
    if policy.get("headers") != expected_headers:
        raise ValueError("public response header contract is not exact")

    expected_filesystem = {
        "staging_directory_mode": "0755",
        "release_directory_mode": "0755",
        "public_file_mode": "0644",
        "metadata_directory_mode": "0700",
        "metadata_file_mode": "0600",
        "current_pointer": "current",
        "release_directory": "releases",
        "metadata_directory": "metadata",
    }
    if policy.get("filesystem") != expected_filesystem:
        raise ValueError("staging filesystem contract is not exact")

    runtime = policy.get("runtime")
    runtime_false = (
        "network_access",
        "command_execution",
        "raw_suricata_access",
        "apache_mutation",
        "public_tree_write",
        "release_pruning",
    )
    if not isinstance(runtime, dict) or any(runtime.get(key) is not False for key in runtime_false):
        raise ValueError("staging runtime safety flags must all remain false")

    acceptance = policy.get("acceptance")
    if not isinstance(acceptance, dict):
        raise ValueError("staging acceptance contract is missing")
    acceptance_true = (
        "exact_asset_allowlist",
        "atomic_current_pointer",
        "sha256_metadata_required",
        "source_detail_exclusion_required",
        "strict_header_contract_required",
        "no_new_listener",
        "no_live_route_change",
    )
    for key in acceptance_true:
        if acceptance.get(key) is not True:
            raise ValueError(f"acceptance.{key} must be true")
    if acceptance.get("traffic_controls_changed") is not False:
        raise ValueError("traffic_controls_changed must remain false")

    if enforce_production_paths:
        if Path(str(policy.get("static_source_root"))) != APPROVED_STATIC_ROOT:
            raise ValueError("static source root is not approved")
        if Path(str(policy.get("staging_root"))) != APPROVED_STAGING_ROOT:
            raise ValueError("staging root is not approved")
        source_paths = policy.get("source_paths")
        if not isinstance(source_paths, dict):
            raise ValueError("source path contract is missing")
        normalized = {key: Path(str(value)) for key, value in source_paths.items()}
        if normalized != APPROVED_SOURCES:
            raise ValueError("source path allowlist is not exact")


def activation_allowed(policy: dict[str, Any]) -> bool:
    return policy.get("enabled") is True and policy.get("deployment_authorized") is True


def ensure_real_directory(path: Path, mode: int) -> None:
    if os.path.lexists(path) and path.is_symlink():
        raise ValueError(f"directory path must not be a symlink: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError(f"path is not a directory: {path}")
    os.chmod(path, mode)


def read_static_asset(static_root: Path, name: str) -> bytes:
    root = static_root.resolve(strict=True)
    path = static_root / name
    if path.is_symlink():
        raise ValueError(f"static asset must not be a symlink: {name}")
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"static asset escaped the approved root: {name}") from exc
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"static asset is not a regular file: {name}")
    if info.st_size > MAX_STATIC_BYTES:
        raise ValueError(f"static asset exceeds size limit: {name}")
    return resolved.read_bytes()


def validate_static_contract(static_content: dict[str, bytes]) -> None:
    if tuple(static_content) != STATIC_ASSETS:
        raise ValueError("static asset set is not exact")
    try:
        page = static_content["index.html"].decode("utf-8")
        app = static_content["app.js"].decode("utf-8")
        style = static_content["style.css"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("public static assets must be UTF-8") from exc
    if f'content="{CSP}"' not in page:
        raise ValueError("page CSP does not match the approved contract")
    if '<link rel="stylesheet" href="./style.css">' not in page:
        raise ValueError("page does not load the approved external stylesheet")
    if "<style" in page.lower() or "unsafe-inline" in page:
        raise ValueError("page requires forbidden inline presentation")
    if 'const STATUS_URL = "./public/status.json";' not in app:
        raise ValueError("page script does not use the canonical minimized feed")
    if not style.strip():
        raise ValueError("public stylesheet is empty")
    combined = "\n".join((page, app, style))
    for token in FORBIDDEN_PUBLIC_TOKENS:
        if token in combined:
            raise ValueError(f"restricted public token found: {token}")


def write_file(
    path: Path,
    content: bytes,
    *,
    parent_mode: int = 0o755,
    file_mode: int = 0o644,
) -> None:
    ensure_real_directory(path.parent, parent_mode)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, file_mode)
        os.replace(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_release(release_root: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(release_root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"release contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(release_root).as_posix()
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o644:
            raise ValueError(f"public release file mode is not 0644: {relative}")
        files[relative] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "mode": f"{mode:04o}",
        }
    if tuple(files) != tuple(sorted(RELEASE_ASSETS)):
        raise ValueError("staged release file set is not exact")
    return files


def validate_current_pointer(staging_root: Path) -> None:
    current = staging_root / "current"
    if os.path.lexists(current) and not current.is_symlink():
        raise ValueError("current pointer exists but is not a symlink")


def atomic_current_pointer(staging_root: Path, release_root: Path) -> None:
    validate_current_pointer(staging_root)
    current = staging_root / "current"
    relative_target = os.path.relpath(release_root, staging_root)
    temporary = staging_root / f".current.{os.getpid()}.tmp"
    try:
        if os.path.lexists(temporary):
            temporary.unlink()
        os.symlink(relative_target, temporary)
        os.replace(temporary, current)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def release_identifier(now: dt.datetime, status_document: dict[str, Any], static_content: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(status_document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    for name in STATIC_ASSETS:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(static_content[name])
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{digest.hexdigest()[:12]}"


def build_release(
    *,
    static_root: Path,
    source_paths: dict[str, Path],
    staging_root: Path,
    now: dt.datetime | None = None,
    maintenance_notice: str = "",
) -> dict[str, Any]:
    current_time = (now or utc_now()).astimezone(dt.timezone.utc)
    if set(source_paths) != set(APPROVED_SOURCES):
        raise ValueError("source key allowlist is not exact")

    static_content = {name: read_static_asset(static_root, name) for name in STATIC_ASSETS}
    validate_static_contract(static_content)
    status_document = build_public_status(
        load_object(source_paths["security"]),
        load_object(source_paths["network_defense"]),
        load_object(source_paths["operations"]),
        now=current_time,
        maintenance_notice=maintenance_notice,
    )
    release_id = release_identifier(current_time, status_document, static_content)

    ensure_real_directory(staging_root, 0o755)
    validate_current_pointer(staging_root)
    releases_root = staging_root / "releases"
    metadata_root = staging_root / "metadata"
    ensure_real_directory(releases_root, 0o755)
    ensure_real_directory(metadata_root, 0o700)

    final_release = releases_root / release_id
    if os.path.lexists(final_release):
        raise FileExistsError(f"release already exists: {release_id}")

    temporary_release = Path(tempfile.mkdtemp(prefix=".release-", dir=releases_root))
    try:
        os.chmod(temporary_release, 0o755)
        for name, content in static_content.items():
            write_file(temporary_release / name, content)
        ensure_real_directory(temporary_release / "public", 0o755)
        write_public_status(status_document, temporary_release / "public" / "status.json")
        inventory = inventory_release(temporary_release)
        os.replace(temporary_release, final_release)
    except Exception:
        if temporary_release.exists():
            shutil.rmtree(temporary_release)
        raise

    metadata = {
        "contract": "wwcx.edge1-public-summary-staged-release.v1",
        "release_id": release_id,
        "created_at": iso(current_time),
        "release_root": str(final_release),
        "public_routes": {"root": PUBLIC_ROOT_ROUTE, "feed": PUBLIC_FEED_ROUTE},
        "files": inventory,
        "read_only": True,
        "live_publication_authorized": False,
        "traffic_controls_changed": False,
    }
    metadata_path = metadata_root / f"{release_id}.json"
    encoded_metadata = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_file(metadata_path, encoded_metadata, parent_mode=0o700, file_mode=0o600)

    atomic_current_pointer(staging_root, final_release)
    return {
        "ok": True,
        "state": "staged",
        "changed": True,
        "release_id": release_id,
        "release_root": str(final_release),
        "current_pointer": str(staging_root / "current"),
        "metadata": str(metadata_path),
        "overall_state": status_document["overall_state"],
        "live_publication_authorized": False,
        "traffic_controls_changed": False,
    }


def run_from_policy(
    policy_path: Path,
    *,
    enforce_production_paths: bool = True,
    static_root_override: Path | None = None,
    source_paths_override: dict[str, Path] | None = None,
    staging_root_override: Path | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    validate_policy(policy, enforce_production_paths=enforce_production_paths)
    if not activation_allowed(policy):
        return {
            "ok": True,
            "state": "disabled",
            "changed": False,
            "live_publication_authorized": False,
            "traffic_controls_changed": False,
        }
    static_root = static_root_override or Path(str(policy["static_source_root"]))
    source_values = source_paths_override or {
        key: Path(str(value)) for key, value in policy["source_paths"].items()
    }
    staging_root = staging_root_override or Path(str(policy["staging_root"]))
    return build_release(
        static_root=static_root,
        source_paths=source_values,
        staging_root=staging_root,
        now=now,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(run_from_policy(args.policy), sort_keys=True))


if __name__ == "__main__":
    main()
