#!/usr/bin/env python3
"""Audit or execute one explicitly authorized outbound-mail pilot message.

Audit is the default and performs no mutation. Execute requires an exact clean
main commit, root, the Edge1 host, an explicit environment authorization, a
private unexpired authorization record, a verified activation bundle, one
private request file, an unsuppressed recipient, and a new restricted evidence
directory. After activation begins, every path restores the prior runtime files
and restarts the safe-disabled gateway. The fixed loopback send is attempted at
most once and is never retried.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVER = ROOT / "server"
TOOLS = ROOT / "tools" / "messaging"
for item in (SERVER, TOOLS):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import build_outbound_mail_controlled_activation_bundle as activation_bundle
import mail_identity_registry
import outbound_mail_delivery_events as delivery_events
import outbound_mail_gateway as gateway
import outbound_mail_policy


CONTRACT = "wwcx.outbound-mail-one-message-execution.v1"
BUNDLE_CONTRACT = activation_bundle.BUNDLE_CONTRACT
RUNTIME_FILENAMES = (
    "outbound-mail-gateway-runtime.json",
    "outbound-mail-policy-runtime.json",
    "mail-identities-runtime.json",
)
DEFAULT_RUNTIME_ROOT = pathlib.Path("/etc/wwcx")
DEFAULT_SUPPRESSION_DATABASE = pathlib.Path(
    "/var/lib/wwcx-outbound-mail/delivery-state.sqlite3"
)
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8104"
DEFAULT_SERVICE = "wwcx-outbound-mail-gateway.service"
EXPECTED_HOST = "edge1.ww.cx"
EXECUTION_ENVIRONMENT_GATE = "WWCX_ONE_MESSAGE_PILOT_AUTHORIZED"
HEX64 = set("0123456789abcdef")


class PilotExecutionError(RuntimeError):
    """Raised when pilot audit or execution cannot proceed safely."""


class RuntimeAdapter:
    """Production runtime operations. Tests replace this adapter."""

    def replace_runtime(
        self,
        source_files: dict[str, pathlib.Path],
        runtime_root: pathlib.Path,
    ) -> None:
        for filename in RUNTIME_FILENAMES:
            source = source_files[filename]
            target = runtime_root / filename
            temporary = target.with_name(f".{target.name}.pilot-{os.getpid()}")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor: int | None = None
            try:
                descriptor = os.open(temporary, flags, 0o644)
                with os.fdopen(descriptor, "wb", closefd=False) as handle:
                    handle.write(source.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                os.fchmod(descriptor, 0o644)
                os.fchown(descriptor, 0, 0)
                os.close(descriptor)
                descriptor = None
                os.replace(temporary, target)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        directory_descriptor = os.open(runtime_root, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)

    def restart_service(self, service: str) -> None:
        completed = subprocess.run(
            ["systemctl", "restart", service],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise PilotExecutionError("outbound-mail service restart failed")
        active = subprocess.run(
            ["systemctl", "is-active", "--quiet", service],
            check=False,
            timeout=10,
        )
        if active.returncode != 0:
            raise PilotExecutionError("outbound-mail service is not active")

    def get_json(self, url: str) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PilotExecutionError("loopback gateway status request failed") from exc

    def send_once(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        body = compact_json_bytes(payload)
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                response_body = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                response_body = {"error": "unparseable_gateway_response"}
            return exc.code, response_body
        except (urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PilotExecutionError("one-message loopback submission failed") from exc


class ExecutionContext:
    def __init__(
        self,
        *,
        runtime_root: pathlib.Path,
        bundle_dir: pathlib.Path,
        authorization_path: pathlib.Path,
        request_path: pathlib.Path,
        suppression_database: pathlib.Path,
        evidence_dir: pathlib.Path,
        expected_commit: str,
        service: str,
        gateway_url: str,
        expected_host: str,
    ) -> None:
        self.runtime_root = runtime_root
        self.bundle_dir = bundle_dir
        self.authorization_path = authorization_path
        self.request_path = request_path
        self.suppression_database = suppression_database
        self.evidence_dir = evidence_dir
        self.expected_commit = expected_commit
        self.service = service
        self.gateway_url = gateway_url.rstrip("/")
        self.expected_host = expected_host


def compact_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def canonical_document_bytes(value: dict[str, Any]) -> bytes:
    return activation_bundle.canonical_bytes(value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotExecutionError(f"unable to read {label}") from exc
    if not isinstance(value, dict):
        raise PilotExecutionError(f"{label} must be a JSON object")
    return value


def _inside(path: pathlib.Path, root: pathlib.Path) -> bool:
    resolved = path.resolve(strict=False)
    approved = root.resolve(strict=False)
    return resolved == approved or approved in resolved.parents


def _reject_symlink_components(path: pathlib.Path, label: str) -> pathlib.Path:
    absolute = pathlib.Path(os.path.abspath(os.fspath(path)))
    current = pathlib.Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise PilotExecutionError(f"{label} contains a symlink component")
    return absolute


def validate_private_file(
    path: pathlib.Path,
    label: str,
    *,
    owner_uid: int | None = None,
) -> pathlib.Path:
    absolute = _reject_symlink_components(path, label)
    try:
        details = absolute.lstat()
    except OSError as exc:
        raise PilotExecutionError(f"unable to inspect {label}") from exc
    if not stat.S_ISREG(details.st_mode):
        raise PilotExecutionError(f"{label} must be a regular file")
    if stat.S_IMODE(details.st_mode) & 0o077:
        raise PilotExecutionError(f"{label} must be mode 0600 or stricter")
    if owner_uid is not None and details.st_uid != owner_uid:
        raise PilotExecutionError(f"{label} has the wrong owner")
    return absolute


def validate_runtime_file(path: pathlib.Path) -> pathlib.Path:
    absolute = _reject_symlink_components(path, "runtime file")
    try:
        details = absolute.lstat()
    except OSError as exc:
        raise PilotExecutionError("runtime file is unavailable") from exc
    if not stat.S_ISREG(details.st_mode) or details.st_uid != 0:
        raise PilotExecutionError("runtime file is absent, unsafe, or not root-owned")
    if stat.S_IMODE(details.st_mode) & 0o022:
        raise PilotExecutionError("runtime file is group/world writable")
    return absolute


def validate_bundle_file(
    path: pathlib.Path,
    expected_sha256: str,
    *,
    owner_uid: int | None,
) -> pathlib.Path:
    absolute = validate_private_file(
        path,
        "activation bundle file",
        owner_uid=owner_uid,
    )
    if sha256_bytes(absolute.read_bytes()) != expected_sha256:
        raise PilotExecutionError("activation bundle file hash mismatch")
    return absolute


def normalize_recipient(address: str) -> str:
    normalized = address.strip().casefold()
    if normalized.count("@") != 1 or any(character.isspace() for character in normalized):
        raise PilotExecutionError("pilot recipient address is invalid")
    return normalized


def require_nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PilotExecutionError(f"{label} is missing")
    return value.strip()


def validate_request(
    request: dict[str, Any],
    authorization: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    expected = {
        "to",
        "subject",
        "body",
        "message_class",
        "identity_hint",
        "signer_name",
        "signer_title",
        "mailing_address",
        "confirm_send",
    }
    if set(request) != expected:
        raise PilotExecutionError("pilot request keys are invalid")
    recipients = request["to"]
    if (
        not isinstance(recipients, list)
        or len(recipients) != 1
        or not isinstance(recipients[0], str)
    ):
        raise PilotExecutionError("pilot request must contain exactly one recipient")
    recipient = normalize_recipient(recipients[0])
    require_nonempty_text(request["subject"], "pilot subject")
    require_nonempty_text(request["body"], "pilot body")
    require_nonempty_text(request["signer_name"], "pilot signer name")
    require_nonempty_text(request["signer_title"], "pilot signer title")
    mailing_address = require_nonempty_text(
        request["mailing_address"],
        "pilot mailing address",
    )
    if mailing_address != policy["organization"]["mailing_address"]:
        raise PilotExecutionError("pilot mailing address does not match runtime policy")
    if request["message_class"] != "business_correspondence":
        raise PilotExecutionError("pilot message class is not business_correspondence")
    if (
        str(request["identity_hint"]).strip().casefold()
        != str(authorization["sender_address"]).casefold()
    ):
        raise PilotExecutionError("pilot sender hint does not match authorization")
    if request["confirm_send"] is not True:
        raise PilotExecutionError("pilot request lacks explicit send confirmation")
    if (
        sha256_bytes(canonical_document_bytes(request))
        != authorization["pilot_payload_sha256"]
    ):
        raise PilotExecutionError("pilot request hash does not match authorization")
    if (
        sha256_bytes(recipient.encode("utf-8"))
        != authorization["pilot_recipient_sha256"]
    ):
        raise PilotExecutionError("pilot recipient hash does not match authorization")
    return {"request": request, "recipient": recipient}


def validate_runtime_documents(
    runtime_root: pathlib.Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, pathlib.Path],
]:
    paths = {
        filename: validate_runtime_file(runtime_root / filename)
        for filename in RUNTIME_FILENAMES
    }
    config = load_json(paths[RUNTIME_FILENAMES[0]], "runtime gateway config")
    policy = load_json(paths[RUNTIME_FILENAMES[1]], "runtime policy")
    identities = load_json(paths[RUNTIME_FILENAMES[2]], "runtime identities")
    try:
        gateway.validate_gateway_config(config)
        outbound_mail_policy.validate_policy(policy)
        mail_identity_registry.validate_registry(identities)
    except Exception as exc:
        raise PilotExecutionError(f"runtime document validation failed: {exc}") from exc
    return config, policy, identities, paths


def validate_manifest(
    manifest: dict[str, Any],
    authorization: dict[str, Any],
    runtime_documents: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    bundle_dir: pathlib.Path,
    *,
    now: datetime,
    owner_uid: int | None,
) -> dict[str, Any]:
    if manifest.get("contract") != BUNDLE_CONTRACT:
        raise PilotExecutionError("activation bundle contract is unsupported")
    config, policy, identities = runtime_documents
    try:
        expected_bundle = activation_bundle.build_bundle(
            config,
            policy,
            identities,
            authorization,
            now=now,
        )
    except activation_bundle.ActivationBundleError as exc:
        raise PilotExecutionError(str(exc)) from exc

    required_manifest_fields = (
        "authorization_id",
        "authorized_by",
        "authorization_reference",
        "authorization_sha256",
        "authorization_issued_at",
        "authorization_expires_at",
        "source_runtime_sha256",
        "provider_profile",
        "sender_identity_key",
        "sender_address_sha256",
        "pilot_recipient_sha256",
        "pilot_payload_sha256",
        "smtp_auth_canary_sha256",
        "max_recipient_count",
        "rollback_required",
        "changes",
        "credentials_read",
        "runtime_files_modified",
        "provider_contacted",
        "message_prepared",
        "message_sent",
    )
    for key in required_manifest_fields:
        if manifest.get(key) != expected_bundle.get(key):
            raise PilotExecutionError(f"activation bundle manifest mismatch: {key}")

    hashes = manifest.get("file_sha256")
    expected_inventory = {
        f"activated/{filename}" for filename in RUNTIME_FILENAMES
    } | {f"rollback/{filename}" for filename in RUNTIME_FILENAMES}
    if not isinstance(hashes, dict) or set(hashes) != expected_inventory:
        raise PilotExecutionError("activation bundle file inventory is invalid")

    files: dict[str, pathlib.Path] = {}
    documents: dict[str, dict[str, Any]] = {}
    for relative, digest in hashes.items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or set(digest) - HEX64
        ):
            raise PilotExecutionError("activation bundle contains an invalid file hash")
        path = validate_bundle_file(
            bundle_dir / relative,
            digest,
            owner_uid=owner_uid,
        )
        files[relative] = path
        documents[relative] = load_json(path, "activation bundle document")

    for section in ("activated", "rollback"):
        for filename in RUNTIME_FILENAMES:
            relative = f"{section}/{filename}"
            if documents[relative] != expected_bundle[section][filename]:
                raise PilotExecutionError(
                    f"activation bundle {section} document is not the expected document"
                )

    return {
        "activated": {
            filename: files[f"activated/{filename}"]
            for filename in RUNTIME_FILENAMES
        },
        "rollback": {
            filename: files[f"rollback/{filename}"]
            for filename in RUNTIME_FILENAMES
        },
        "expected_activated": expected_bundle["activated"],
    }


def validate_repository(
    repo: pathlib.Path,
    expected_commit: str,
    *,
    execute: bool,
) -> dict[str, Any]:
    if len(expected_commit) != 40 or set(expected_commit) - HEX64:
        raise PilotExecutionError("expected repository commit is invalid")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if any(item.returncode != 0 for item in (head, branch, status)):
        raise PilotExecutionError("unable to inspect repository state")
    clean = not status.stdout.strip()
    exact = head.stdout.strip() == expected_commit
    main = branch.stdout.strip() == "main"
    if execute and (not clean or not exact or not main):
        raise PilotExecutionError("execution requires exact clean main")
    return {
        "commit": head.stdout.strip(),
        "branch": branch.stdout.strip(),
        "clean": clean,
        "exact": exact,
    }


def validate_gateway_url(url: str) -> str:
    normalized = url.rstrip("/")
    if normalized != DEFAULT_GATEWAY_URL:
        raise PilotExecutionError("gateway URL is not the fixed loopback endpoint")
    return normalized


def validate_execution_targets(context: ExecutionContext) -> None:
    if context.runtime_root.resolve(strict=False) != DEFAULT_RUNTIME_ROOT:
        raise PilotExecutionError("execution runtime root is not /etc/wwcx")
    if (
        context.suppression_database.resolve(strict=False)
        != DEFAULT_SUPPRESSION_DATABASE
    ):
        raise PilotExecutionError("execution suppression database path is unexpected")
    if context.service != DEFAULT_SERVICE:
        raise PilotExecutionError("execution service name is unexpected")
    if context.expected_host.casefold() != EXPECTED_HOST:
        raise PilotExecutionError("execution expected host is unexpected")
    validate_gateway_url(context.gateway_url)


def prepare_evidence_directory(
    path: pathlib.Path,
    *,
    owner_uid: int,
) -> pathlib.Path:
    absolute = pathlib.Path(os.path.abspath(os.fspath(path)))
    _reject_symlink_components(absolute.parent, "evidence directory parent")
    if absolute.exists() or absolute.is_symlink():
        raise PilotExecutionError("evidence directory must not already exist")
    try:
        parent = absolute.parent.lstat()
    except OSError as exc:
        raise PilotExecutionError("evidence directory parent is unavailable") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != owner_uid
        or stat.S_IMODE(parent.st_mode) & 0o022
    ):
        raise PilotExecutionError("evidence directory parent is unsafe")
    absolute.mkdir(mode=0o700)
    return absolute


def secure_write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(canonical_document_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def copy_runtime_backup(
    runtime_paths: dict[str, pathlib.Path],
    evidence_dir: pathlib.Path,
) -> dict[str, pathlib.Path]:
    backup_dir = evidence_dir / "runtime-backup"
    backup_dir.mkdir(mode=0o700)
    backups: dict[str, pathlib.Path] = {}
    for filename, source in runtime_paths.items():
        destination = backup_dir / filename
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(source.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        backups[filename] = destination
    return backups


def minimize_submission(
    status: int,
    response: dict[str, Any],
) -> dict[str, Any]:
    provider_message_id = response.get("provider_message_id")
    audit_event = response.get("audit_event")
    return {
        "gateway_http_status": status,
        "accepted": status == 202 and response.get("status") == "accepted",
        "provider": str(response.get("provider", "unknown"))[:64],
        "provider_message_id_sha256": (
            sha256_bytes(str(provider_message_id).encode("utf-8"))
            if provider_message_id
            else None
        ),
        "response_sha256": sha256_bytes(canonical_document_bytes(response)),
        "audit_event_sha256": (
            sha256_bytes(canonical_document_bytes(audit_event))
            if isinstance(audit_event, dict)
            else None
        ),
        "raw_response_stored": False,
    }


def require_active_status(status_code: int, status: dict[str, Any]) -> None:
    if status_code != 200:
        raise PilotExecutionError("activated gateway status request failed")
    if status.get("external_delivery_enabled") is not True:
        raise PilotExecutionError("activated gateway did not enable external delivery")
    sender_selection = status.get("sender_selection")
    if (
        not isinstance(sender_selection, dict)
        or sender_selection.get("live_sender_count") != 1
    ):
        raise PilotExecutionError("activated gateway does not expose exactly one live sender")


def require_disabled_status(status_code: int, status: dict[str, Any]) -> None:
    if status_code != 200:
        raise PilotExecutionError("post-rollback gateway status request failed")
    if status.get("external_delivery_enabled") is not False:
        raise PilotExecutionError("post-rollback gateway is not safe-disabled")
    sender_selection = status.get("sender_selection")
    if (
        not isinstance(sender_selection, dict)
        or sender_selection.get("live_sender_count") != 0
    ):
        raise PilotExecutionError("post-rollback gateway retains a live sender")


def audit_context(
    context: ExecutionContext,
    *,
    now: datetime | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    current = datetime.now(timezone.utc) if now is None else now.astimezone(timezone.utc)
    repository = validate_repository(ROOT.resolve(), context.expected_commit, execute=execute)
    validate_gateway_url(context.gateway_url)
    runtime_config, runtime_policy, runtime_identities, runtime_paths = (
        validate_runtime_documents(context.runtime_root)
    )
    private_owner = 0 if execute else None
    authorization_path = validate_private_file(
        context.authorization_path,
        "pilot authorization",
        owner_uid=private_owner,
    )
    request_path = validate_private_file(
        context.request_path,
        "pilot request",
        owner_uid=private_owner,
    )
    authorization = load_json(authorization_path, "pilot authorization")
    request = load_json(request_path, "pilot request")
    request_status = validate_request(request, authorization, runtime_policy)
    manifest_path = validate_private_file(
        context.bundle_dir / "manifest.json",
        "activation bundle manifest",
        owner_uid=private_owner,
    )
    manifest = load_json(manifest_path, "activation bundle manifest")
    bundle_files = validate_manifest(
        manifest,
        authorization,
        (runtime_config, runtime_policy, runtime_identities),
        context.bundle_dir,
        now=current,
        owner_uid=private_owner,
    )
    suppression_path = validate_private_file(
        context.suppression_database,
        "suppression database",
        owner_uid=private_owner,
    )
    state = delivery_events.recipient_state(
        suppression_path,
        authorization["pilot_recipient_sha256"],
    )
    if state["suppression_active"]:
        raise PilotExecutionError("pilot recipient suppression is active")
    return {
        "repository": repository,
        "runtime_documents": {
            RUNTIME_FILENAMES[0]: runtime_config,
            RUNTIME_FILENAMES[1]: runtime_policy,
            RUNTIME_FILENAMES[2]: runtime_identities,
        },
        "runtime_paths": runtime_paths,
        "authorization": authorization,
        "request": request_status["request"],
        "recipient": request_status["recipient"],
        "manifest": manifest,
        "bundle_files": bundle_files,
        "suppression_state": state,
        "audited_at": current.isoformat(timespec="seconds"),
    }


def execute_pilot(
    context: ExecutionContext,
    adapter: RuntimeAdapter,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_execution_targets(context)
    if os.geteuid() != 0:
        raise PilotExecutionError("one-message execution requires root")
    if os.environ.get(EXECUTION_ENVIRONMENT_GATE) != "yes":
        raise PilotExecutionError(
            "one-message execution authorization environment gate is absent"
        )
    hostname = subprocess.run(
        ["hostname", "-f"],
        check=False,
        capture_output=True,
        text=True,
    )
    if (
        hostname.returncode != 0
        or hostname.stdout.strip().casefold() != context.expected_host.casefold()
    ):
        raise PilotExecutionError("one-message execution is on the wrong host")

    audit = audit_context(context, now=now, execute=True)
    evidence = prepare_evidence_directory(context.evidence_dir, owner_uid=0)
    backups = copy_runtime_backup(audit["runtime_paths"], evidence)
    source_hashes = {
        filename: sha256_bytes(path.read_bytes())
        for filename, path in audit["runtime_paths"].items()
    }
    activation_started = False
    send_attempted = False
    submission: dict[str, Any] | None = None
    failure: str | None = None
    rollback_error: str | None = None
    try:
        activation_started = True
        adapter.replace_runtime(
            audit["bundle_files"]["activated"],
            context.runtime_root,
        )
        active_config, active_policy, active_identities, _active_paths = (
            validate_runtime_documents(context.runtime_root)
        )
        expected_active = audit["bundle_files"]["expected_activated"]
        if (
            active_config != expected_active[RUNTIME_FILENAMES[0]]
            or active_policy != expected_active[RUNTIME_FILENAMES[1]]
            or active_identities != expected_active[RUNTIME_FILENAMES[2]]
        ):
            raise PilotExecutionError("installed activated runtime documents changed")
        adapter.restart_service(context.service)
        health_status, health = adapter.get_json(
            context.gateway_url + "/outbound-mail/healthz"
        )
        if health_status != 200 or health.get("status") != "ok":
            raise PilotExecutionError("activated gateway health check failed")
        status_code, status_payload = adapter.get_json(
            context.gateway_url + "/outbound-mail/status"
        )
        require_active_status(status_code, status_payload)
        send_attempted = True
        send_status, response = adapter.send_once(
            context.gateway_url + "/outbound-mail/send",
            audit["request"],
        )
        submission = minimize_submission(send_status, response)
        if not submission["accepted"]:
            raise PilotExecutionError("provider did not accept the one-message pilot")
    except Exception as exc:
        failure = str(exc)
    finally:
        if activation_started:
            try:
                adapter.replace_runtime(backups, context.runtime_root)
                adapter.restart_service(context.service)
                rollback_config, rollback_policy, rollback_identities, rollback_paths = (
                    validate_runtime_documents(context.runtime_root)
                )
                activation_bundle.validate_safe_sources(
                    rollback_config,
                    rollback_policy,
                    rollback_identities,
                )
                restored = {
                    filename: sha256_bytes(path.read_bytes())
                    for filename, path in rollback_paths.items()
                }
                if restored != source_hashes:
                    raise PilotExecutionError(
                        "post-rollback runtime hashes do not match preflight"
                    )
                rollback_health_status, rollback_health = adapter.get_json(
                    context.gateway_url + "/outbound-mail/healthz"
                )
                if (
                    rollback_health_status != 200
                    or rollback_health.get("status") != "ok"
                ):
                    raise PilotExecutionError(
                        "post-rollback gateway health check failed"
                    )
                rollback_status_code, rollback_status = adapter.get_json(
                    context.gateway_url + "/outbound-mail/status"
                )
                require_disabled_status(rollback_status_code, rollback_status)
            except Exception as exc:
                rollback_error = str(exc)

    record = {
        "contract": CONTRACT,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit": audit["repository"]["commit"],
        "authorization_id": audit["authorization"]["authorization_id"],
        "authorization_sha256": activation_bundle.sha256_document(
            audit["authorization"]
        ),
        "bundle_manifest_sha256": sha256_bytes(
            canonical_document_bytes(audit["manifest"])
        ),
        "pilot_recipient_sha256": audit["authorization"][
            "pilot_recipient_sha256"
        ],
        "pilot_payload_sha256": audit["authorization"]["pilot_payload_sha256"],
        "smtp_auth_canary_sha256": audit["authorization"][
            "smtp_auth_canary_sha256"
        ],
        "activation_started": activation_started,
        "send_attempted": send_attempted,
        "send_attempt_count": 1 if send_attempted else 0,
        "submission": submission,
        "rollback_attempted": activation_started,
        "rollback_succeeded": activation_started and rollback_error is None,
        "post_rollback_safe_disabled": (
            activation_started and rollback_error is None
        ),
        "failure": failure,
        "rollback_error": rollback_error,
        "recipient_address_stored": False,
        "message_content_stored": False,
        "provider_credentials_read": False,
        "raw_provider_response_stored": False,
    }
    secure_write_json(evidence / "execution.json", record)
    if rollback_error is not None:
        raise PilotExecutionError(f"automatic rollback failed: {rollback_error}")
    if failure is not None:
        raise PilotExecutionError(failure)
    return record


def audit_report(context: ExecutionContext) -> dict[str, Any]:
    audit = audit_context(context, execute=False)
    return {
        "contract": CONTRACT,
        "action": "audit",
        "audited_at": audit["audited_at"],
        "repository": audit["repository"],
        "authorization_id": audit["authorization"]["authorization_id"],
        "authorization_sha256": activation_bundle.sha256_document(
            audit["authorization"]
        ),
        "bundle_manifest_sha256": sha256_bytes(
            canonical_document_bytes(audit["manifest"])
        ),
        "pilot_recipient_sha256": audit["authorization"][
            "pilot_recipient_sha256"
        ],
        "pilot_payload_sha256": audit["authorization"]["pilot_payload_sha256"],
        "suppression_active": False,
        "runtime_mutated": False,
        "service_restarted": False,
        "message_sent": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("audit", "execute"), default="audit")
    parser.add_argument(
        "--runtime-root",
        type=pathlib.Path,
        default=DEFAULT_RUNTIME_ROOT,
    )
    parser.add_argument("--bundle-dir", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--request", type=pathlib.Path, required=True)
    parser.add_argument(
        "--suppression-database",
        type=pathlib.Path,
        default=DEFAULT_SUPPRESSION_DATABASE,
    )
    parser.add_argument("--evidence-dir", type=pathlib.Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL)
    parser.add_argument("--expected-host", default=EXPECTED_HOST)
    return parser.parse_args()


def main() -> int:
    os.umask(0o077)
    args = parse_args()
    context = ExecutionContext(
        runtime_root=args.runtime_root,
        bundle_dir=args.bundle_dir,
        authorization_path=args.authorization,
        request_path=args.request,
        suppression_database=args.suppression_database,
        evidence_dir=args.evidence_dir,
        expected_commit=args.expected_commit,
        service=args.service,
        gateway_url=args.gateway_url,
        expected_host=args.expected_host,
    )
    try:
        if args.action == "execute":
            result = execute_pilot(context, RuntimeAdapter())
        else:
            result = audit_report(context)
    except PilotExecutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
