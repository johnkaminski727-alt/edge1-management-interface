#!/usr/bin/env python3
"""Fixed typed handlers for privileged Edge1 Operations API actions.

The unprivileged Operations API performs policy, precondition and application-health
checks. Privileged process control is delegated over one fixed Unix socket to the
separately sandboxed root broker.
"""
from __future__ import annotations

import hashlib
import json
import re
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from dataclasses import asdict
import sqlite3

from tools.unified_contacts.connections import mutate_candidate

from server.unified_contacts_merge import (
    ContactMergeError,
    UnifiedContactsMerge,
)
from server.unified_contacts_crud import (
    ContactsConflict,
    ContactsCrudError,
    ContactsNotFound,
    UnifiedContactsCrud,
)

from server.asterisk_process_identity import resolve_asterisk_pid

REPO = Path("/opt/edge1-management-interface")
SOURCE = REPO / "server" / "telephony_status_server.py"
SERVICE = "wwcx-telephony-console.service"
ASTERISK_SERVICE = "asterisk.service"
MESSAGING_SERVICE = "wwcx-messaging-gateway.service"
HEALTH_URL = "http://127.0.0.1:8096/healthz"
BROKER_SOCKET = "/run/edge1-operator-privileged/control.sock"
BROKER_MAX_RESPONSE = 8192
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


class TypedActionValidationError(ValueError):
    pass


def _run(argv: list[str], timeout: float = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)


def _value(argv: list[str]) -> str:
    result = _run(argv)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _pid(service: str) -> int:
    raw = _value(["systemctl", "show", service, "-p", "MainPID", "--value"])
    return int(raw) if raw.isdigit() else 0


def _active(service: str) -> bool:
    return _run(["systemctl", "is-active", "--quiet", service]).returncode == 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _health() -> bool:
    try:
        request = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "edge1-operations-api/telephony-control"})
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _validate_reload(parameters: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        raise TypedActionValidationError("telephony reload parameters must be an object")
    expected = {"expected_pid", "expected_source_sha256", "expected_repo_head", "idempotency_key"}
    if set(parameters) != expected:
        raise TypedActionValidationError("telephony reload parameters do not match the fixed schema")
    pid = parameters["expected_pid"]
    source_sha = parameters["expected_source_sha256"]
    repo_head = parameters["expected_repo_head"]
    key = parameters["idempotency_key"]
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise TypedActionValidationError("expected_pid must be a positive integer")
    if not isinstance(source_sha, str) or not HEX64.fullmatch(source_sha):
        raise TypedActionValidationError("expected_source_sha256 must be lowercase SHA-256")
    if not isinstance(repo_head, str) or not HEX40.fullmatch(repo_head):
        raise TypedActionValidationError("expected_repo_head must be a full lowercase commit SHA")
    if not isinstance(key, str) or not IDEMPOTENCY.fullmatch(key):
        raise TypedActionValidationError("idempotency_key format is invalid")
    return dict(parameters)


def _broker_reload(parameters: dict[str, Any], request_id: str) -> dict[str, Any]:
    request = {
        "version": 1,
        "action": "telephony_console_reload",
        "request_id": request_id,
        "expected_pid": parameters["expected_pid"],
        "expected_source_sha256": parameters["expected_source_sha256"],
        "expected_repo_head": parameters["expected_repo_head"],
    }
    encoded = (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect(BROKER_SOCKET)
        sock.sendall(encoded)
        sock.shutdown(socket.SHUT_WR)
        chunks = bytearray()
        while len(chunks) <= BROKER_MAX_RESPONSE:
            chunk = sock.recv(min(4096, BROKER_MAX_RESPONSE + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
            if b"\n" in chunk:
                break
    except (OSError, TimeoutError) as exc:
        raise RuntimeError("privileged broker is unavailable") from exc
    finally:
        sock.close()
    if not chunks or len(chunks) > BROKER_MAX_RESPONSE:
        raise RuntimeError("privileged broker returned an invalid response")
    try:
        response = json.loads(bytes(chunks).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("privileged broker returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("status") != "succeeded":
        raise RuntimeError("privileged broker denied or failed the fixed action")
    if response.get("action") != "telephony_console_reload" or response.get("request_id") != request_id:
        raise RuntimeError("privileged broker response correlation failed")
    return response


def telephony_console_reload(parameters: dict[str, Any]) -> dict[str, Any]:
    """Restart only the read-only Telephony Console after exact precondition checks."""
    p = _validate_reload(parameters)
    if not SOURCE.is_file():
        raise RuntimeError("reviewed Telephony Console source is unavailable")
    if not _active(SERVICE):
        raise RuntimeError("Telephony Console is not active")
    if not _active(ASTERISK_SERVICE) or not _active(MESSAGING_SERVICE):
        raise RuntimeError("PBX or Messaging prerequisite is not active")

    pid_before = _pid(SERVICE)
    asterisk_pid_before, asterisk_pid_source = resolve_asterisk_pid()
    messaging_pid_before = _pid(MESSAGING_SERVICE)
    source_sha = _sha256(SOURCE)
    repo_head = _value(["git", "-C", str(REPO), "rev-parse", "HEAD"])

    if pid_before != p["expected_pid"]:
        raise RuntimeError("Telephony Console PID precondition changed")
    if source_sha != p["expected_source_sha256"]:
        raise RuntimeError("Telephony Console source digest precondition changed")
    if repo_head != p["expected_repo_head"]:
        raise RuntimeError("repository HEAD precondition changed")
    if asterisk_pid_before <= 0 or messaging_pid_before <= 0:
        raise RuntimeError("PBX or Messaging PID is unavailable")

    broker_request_id = "ops-" + uuid.uuid4().hex
    broker = _broker_reload(p, broker_request_id)

    healthy = False
    for _ in range(10):
        if _active(SERVICE) and _health():
            healthy = True
            break
        time.sleep(1)

    pid_after = _pid(SERVICE)
    asterisk_pid_after, asterisk_pid_source_after = resolve_asterisk_pid()
    messaging_pid_after = _pid(MESSAGING_SERVICE)
    unchanged_dependencies = (
        asterisk_pid_after == asterisk_pid_before
        and messaging_pid_after == messaging_pid_before
    )
    broker_pid_after = broker.get("pid_after")

    if (
        not healthy
        or pid_after <= 0
        or pid_after == pid_before
        or broker_pid_after != pid_after
        or not unchanged_dependencies
    ):
        recovery = dict(p)
        recovery["expected_pid"] = pid_after if pid_after > 0 else int(broker_pid_after or 0)
        if recovery["expected_pid"] > 0:
            try:
                _broker_reload(recovery, broker_request_id + "-recovery")
            except Exception:
                pass
        raise RuntimeError("Telephony Console post-reload verification failed; bounded recovery attempted")

    return {
        "service": SERVICE,
        "status": "succeeded",
        "pid_before": pid_before,
        "pid_after": pid_after,
        "source_sha256": source_sha,
        "repo_head": repo_head,
        "loopback_health": True,
        "asterisk_pid": asterisk_pid_before,
        "asterisk_pid_source_before": asterisk_pid_source,
        "asterisk_pid_source_after": asterisk_pid_source_after,
        "asterisk_pid_unchanged": True,
        "messaging_pid_unchanged": True,
        "configuration_changed": False,
        "traffic_generated": False,
        "privilege_broker": "fixed_unix_socket_v1",
        "broker_request_id": broker_request_id,
        "rollback_policy": "one_bounded_recovery_restart_same_reviewed_unit",
    }



def _validate_contacts_candidate_mutation(
    parameters: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        raise TypedActionValidationError(
            "typed action parameters must be an object"
        )

    allowed = {
        "candidate_id",
        "idempotency_key",
    }

    if operation == "promote":
        allowed.update({
            "provenance_id",
            "evidence_role",
            "evidence_summary",
        })

    extra = set(parameters) - allowed
    if extra:
        raise TypedActionValidationError(
            "unsupported contacts mutation parameter"
        )

    candidate_id = parameters.get("candidate_id")
    key = parameters.get("idempotency_key")

    if (
        isinstance(candidate_id, bool)
        or not isinstance(candidate_id, int)
        or candidate_id < 1
    ):
        raise TypedActionValidationError(
            "candidate_id must be a positive integer"
        )

    if not isinstance(key, str) or not key.strip():
        raise TypedActionValidationError(
            "idempotency_key is required"
        )

    result = {
        "candidate_id": candidate_id,
        "idempotency_key": key.strip(),
    }

    if operation == "promote":
        provenance_id = parameters.get("provenance_id")

        if (
            isinstance(provenance_id, bool)
            or not isinstance(provenance_id, int)
            or provenance_id < 1
        ):
            raise TypedActionValidationError(
                "provenance_id must be a positive integer"
            )

        role = parameters.get(
            "evidence_role",
            "supporting",
        )
        summary = parameters.get(
            "evidence_summary",
            "",
        )

        if not isinstance(role, str):
            raise TypedActionValidationError(
                "evidence_role must be a string"
            )

        if not isinstance(summary, str):
            raise TypedActionValidationError(
                "evidence_summary must be a string"
            )

        result.update({
            "provenance_id": provenance_id,
            "evidence_role": role,
            "evidence_summary": summary,
        })

    return result


def _validate_contacts_candidate_accept(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _validate_contacts_candidate_mutation(
        parameters,
        "accept",
    )


def _validate_contacts_candidate_reject(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _validate_contacts_candidate_mutation(
        parameters,
        "reject",
    )


def _validate_contacts_candidate_promote(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _validate_contacts_candidate_mutation(
        parameters,
        "promote",
    )


def _run_contacts_candidate_mutation(
    parameters: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    db = sqlite3.connect(
        "/var/lib/edge1-phone-intelligence/"
        "phone-intelligence.sqlite",
        timeout=10,
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")

    try:
        kwargs = {}

        if operation == "promote":
            kwargs = {
                "provenance_id": parameters[
                    "provenance_id"
                ],
                "evidence_role": parameters[
                    "evidence_role"
                ],
                "evidence_summary": parameters[
                    "evidence_summary"
                ],
            }

        result = mutate_candidate(
            db,
            parameters["candidate_id"],
            operation,
            **kwargs,
        )

        return asdict(result)

    except ValueError as exc:
        raise TypedActionValidationError(
            str(exc)
        ) from exc

    finally:
        db.close()


def contacts_candidate_accept(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_candidate_mutation(
        parameters,
        "accept",
    )


def contacts_candidate_reject(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_candidate_mutation(
        parameters,
        "reject",
    )


def contacts_candidate_promote(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_candidate_mutation(
        parameters,
        "promote",
    )



CONTACTS_DB = Path(
    "/var/lib/edge1-phone-intelligence/"
    "phone-intelligence.sqlite"
)


def _positive_integer(name: str, value: Any) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise TypedActionValidationError(
            f"{name} must be a positive integer"
        )
    return value


def _contacts_crud_schema(
    parameters: dict[str, Any],
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(parameters, dict):
        raise TypedActionValidationError(
            "typed action parameters must be an object"
        )

    optional = optional or set()
    required = set(required)
    optional = set(optional)

    # Every typed mutation participates in the Operations
    # idempotency machinery before handler execution.
    required.add("idempotency_key")

    supplied = set(parameters)
    allowed = required | optional

    if supplied - allowed:
        raise TypedActionValidationError(
            "unsupported contacts CRUD parameter"
        )

    missing = required - supplied
    if missing:
        raise TypedActionValidationError(
            "missing contacts CRUD parameter: "
            + ", ".join(sorted(missing))
        )

    result = dict(parameters)

    key = result.get("idempotency_key")
    if (
        not isinstance(key, str)
        or not IDEMPOTENCY.fullmatch(key)
    ):
        raise TypedActionValidationError(
            "idempotency_key format is invalid"
        )

    for key in (
        "entity_id",
        "contact_point_id",
    ):
        if key in result:
            result[key] = _positive_integer(
                key,
                result[key],
            )

    return result


def _validate_contacts_entity_create(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {"entity_type", "canonical_name"},
        {
            "display_name",
            "verification_status",
            "notes",
        },
    )


def _validate_contacts_entity_update(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {
            "entity_id",
            "canonical_name",
            "verification_status",
        },
        {
            "display_name",
            "notes",
        },
    )


def _validate_contacts_entity_lifecycle(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {"entity_id"},
    )


def _validate_contacts_point_add(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {
            "entity_id",
            "point_type",
            "value",
        },
        {
            "classification",
            "confidence",
            "assertion_notes",
        },
    )


def _validate_contacts_point_update(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {
            "entity_id",
            "contact_point_id",
            "value",
        },
        {"classification"},
    )


def _validate_contacts_point_detach(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _contacts_crud_schema(
        parameters,
        {
            "entity_id",
            "contact_point_id",
        },
    )


def _run_contacts_crud(
    operation: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    connection = sqlite3.connect(str(CONTACTS_DB))

    try:
        connection.execute("BEGIN IMMEDIATE")
        crud = UnifiedContactsCrud(connection)

        if operation == "entity.create":
            result = crud.create_entity(
                entity_type=parameters["entity_type"],
                canonical_name=parameters[
                    "canonical_name"
                ],
                display_name=parameters.get(
                    "display_name"
                ),
                verification_status=parameters.get(
                    "verification_status",
                    "unverified",
                ),
                notes=parameters.get("notes"),
            )
            crud._manual_provenance(
                operation="entity.create",
                entity_id=result.entity_id,
                attribute="canonical_name",
                attested_value=parameters["canonical_name"],
                notes=parameters.get("notes"),
            )

        elif operation == "entity.update":
            result = crud.update_entity(
                entity_id=parameters["entity_id"],
                canonical_name=parameters[
                    "canonical_name"
                ],
                display_name=parameters.get(
                    "display_name"
                ),
                verification_status=parameters[
                    "verification_status"
                ],
                notes=parameters.get("notes"),
            )
            crud._manual_provenance(
                operation="entity.update",
                entity_id=result.entity_id,
                attribute="canonical_name",
                attested_value=parameters["canonical_name"],
                notes=parameters.get("notes"),
            )

        elif operation == "entity.archive":
            result = crud.set_entity_lifecycle(
                entity_id=parameters["entity_id"],
                lifecycle_status="inactive",
            )
            crud._manual_provenance(
                operation="entity.archive",
                entity_id=result.entity_id,
                attribute="lifecycle_status",
                attested_value="inactive",
            )

        elif operation == "entity.restore":
            result = crud.set_entity_lifecycle(
                entity_id=parameters["entity_id"],
                lifecycle_status="active",
            )
            crud._manual_provenance(
                operation="entity.restore",
                entity_id=result.entity_id,
                attribute="lifecycle_status",
                attested_value="active",
            )

        elif operation == "point.add":
            result = crud.add_contact_point(
                entity_id=parameters["entity_id"],
                point_type=parameters["point_type"],
                value=parameters["value"],
                classification=parameters.get(
                    "classification"
                ),
                confidence=parameters.get(
                    "confidence",
                    "unverified",
                ),
                assertion_notes=parameters.get(
                    "assertion_notes"
                ),
            )
            crud._manual_provenance(
                operation="point.add",
                entity_id=result.entity_id,
                contact_point_id=result.contact_point_id,
                assertion_id=result.assertion_id,
                attribute=parameters["point_type"],
                attested_value=parameters["value"],
                notes=parameters.get(
                    "assertion_notes"
                ),
            )

        elif operation == "point.update":
            result = crud.update_contact_point(
                entity_id=parameters["entity_id"],
                contact_point_id=parameters[
                    "contact_point_id"
                ],
                value=parameters["value"],
                classification=parameters.get(
                    "classification"
                ),
            )
            crud._manual_provenance(
                operation="point.update",
                entity_id=result.entity_id,
                contact_point_id=result.contact_point_id,
                assertion_id=result.assertion_id,
                attribute="contact_point",
                attested_value=parameters["value"],
            )

        elif operation == "point.detach":
            result = crud.detach_contact_point(
                entity_id=parameters["entity_id"],
                contact_point_id=parameters[
                    "contact_point_id"
                ],
            )
            crud._manual_provenance(
                operation="point.detach",
                entity_id=result.entity_id,
                contact_point_id=result.contact_point_id,
                assertion_id=result.assertion_id,
                attribute="contact_association",
                attested_value="detached",
            )

        else:
            raise TypedActionValidationError(
                "unknown contacts CRUD operation"
            )

        connection.commit()

        payload = result.as_dict()
        payload["status"] = "succeeded"
        return payload

    except (
        ContactsCrudError,
        sqlite3.Error,
    ):
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def contacts_entity_create(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "entity.create",
        parameters,
    )


def contacts_entity_update(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "entity.update",
        parameters,
    )


def contacts_entity_archive(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "entity.archive",
        parameters,
    )


def contacts_entity_restore(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "entity.restore",
        parameters,
    )


def contacts_point_add(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "point.add",
        parameters,
    )


def contacts_point_update(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "point.update",
        parameters,
    )


def contacts_point_detach(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return _run_contacts_crud(
        "point.detach",
        parameters,
    )



def _validate_contacts_entity_merge(parameters):
    if not isinstance(parameters, dict):
        raise TypedActionValidationError(
            "contacts merge parameters must be an object"
        )

    allowed = {
        "survivor_entity_id",
        "absorbed_entity_id",
        "idempotency_key",
    }

    extra = set(parameters) - allowed

    if extra:
        raise TypedActionValidationError(
            "unexpected contacts merge parameter: "
            + sorted(extra)[0]
        )

    for key in (
        "survivor_entity_id",
        "absorbed_entity_id",
        "idempotency_key",
    ):
        if key not in parameters:
            raise TypedActionValidationError(
                "missing contacts merge parameter: " + key
            )

    try:
        survivor = int(
            parameters["survivor_entity_id"]
        )
        absorbed = int(
            parameters["absorbed_entity_id"]
        )
    except (TypeError, ValueError) as exc:
        raise TypedActionValidationError(
            "contact merge entity ids must be integers"
        ) from exc

    if survivor <= 0 or absorbed <= 0:
        raise TypedActionValidationError(
            "contact merge entity ids must be positive"
        )

    if survivor == absorbed:
        raise TypedActionValidationError(
            "contact cannot be merged into itself"
        )

    key = parameters["idempotency_key"]

    if not isinstance(key, str) or not key.strip():
        raise TypedActionValidationError(
            "invalid contacts merge idempotency_key"
        )

    return {
        "survivor_entity_id": survivor,
        "absorbed_entity_id": absorbed,
        "idempotency_key": key,
    }


TYPED_ACTION_VALIDATORS = {
    "contacts_entity_merge": _validate_contacts_entity_merge,
    "contacts_candidate_accept": _validate_contacts_candidate_accept,
    "contacts_entity_create": _validate_contacts_entity_create,
    "contacts_entity_update": _validate_contacts_entity_update,
    "contacts_entity_archive": _validate_contacts_entity_lifecycle,
    "contacts_entity_restore": _validate_contacts_entity_lifecycle,
    "contacts_point_add": _validate_contacts_point_add,
    "contacts_point_update": _validate_contacts_point_update,
    "contacts_point_detach": _validate_contacts_point_detach,
    "contacts_candidate_promote": _validate_contacts_candidate_promote,
    "contacts_candidate_reject": _validate_contacts_candidate_reject,
    "telephony_console_reload": _validate_reload,
}

def contacts_entity_merge(
    parameters,
    *,
    database=None,
    actor=None,
    **kwargs,
):
    validated = _validate_contacts_entity_merge(
        parameters
    )

    db_path = (
        database
        or kwargs.get("database_path")
        or (
            "/var/lib/edge1-phone-intelligence/"
            "phone-intelligence.sqlite"
        )
    )

    try:
        result = UnifiedContactsMerge(
            db_path
        ).merge(
            validated["survivor_entity_id"],
            validated["absorbed_entity_id"],
            merged_by=(
                actor
                if isinstance(actor, str)
                and actor.strip()
                else "edge1.contacts.manage"
            ),
        )
    except ContactMergeError as exc:
        raise TypedActionValidationError(
            str(exc)
        ) from exc

    return {
        "operation": "entity.merge",
        "survivor_entity_id":
            result.survivor_entity_id,
        "absorbed_entity_id":
            result.absorbed_entity_id,
        "assertions_moved":
            result.assertions_moved,
        "assertions_reconciled":
            result.assertions_reconciled,
        "aliases_preserved":
            result.aliases_preserved,
        "attestations_moved":
            result.attestations_moved,
        "relationships_repointed":
            result.relationships_repointed,
        "correlations_repointed":
            result.correlations_repointed,
        "absorbed_lifecycle":
            result.absorbed_lifecycle,
    }


TYPED_ACTION_HANDLERS = {
    "contacts_entity_merge": contacts_entity_merge,
    "contacts_candidate_accept": contacts_candidate_accept,
    "contacts_entity_create": contacts_entity_create,
    "contacts_entity_update": contacts_entity_update,
    "contacts_entity_archive": contacts_entity_archive,
    "contacts_entity_restore": contacts_entity_restore,
    "contacts_point_add": contacts_point_add,
    "contacts_point_update": contacts_point_update,
    "contacts_point_detach": contacts_point_detach,
    "contacts_candidate_promote": contacts_candidate_promote,
    "contacts_candidate_reject": contacts_candidate_reject,
    "telephony_console_reload": telephony_console_reload,
}


def validate_typed_handler(name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    validator = TYPED_ACTION_VALIDATORS.get(name)
    if validator is None:
        raise TypedActionValidationError("unknown typed action handler")
    return validator(parameters)


def run_typed_handler(
    name: str,
    parameters: dict[str, Any],
    *,
    actor: str | None = None,
) -> dict[str, Any]:
    handler = TYPED_ACTION_HANDLERS.get(name)

    if handler is None:
        raise TypedActionValidationError(
            "unknown typed action handler"
        )

    if name == "contacts_entity_merge":
        return handler(
            parameters,
            actor=actor,
        )

    return handler(parameters)
