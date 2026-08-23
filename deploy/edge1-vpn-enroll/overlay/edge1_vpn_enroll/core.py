from __future__ import annotations

import base64
import fcntl
import hashlib
import html
import ipaddress
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .db import audit, connect, init_db


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def make_token() -> str:
    return secrets.token_urlsafe(32)


def run_command(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def wg_public_key(private_key: str) -> str:
    return run_command(["wg", "pubkey"], input_text=private_key + "\n")


def wg_genkey() -> str:
    return run_command(["wg", "genkey"])


def wg_show_allowed_ips(iface: str) -> set[str]:
    output = run_command(["wg", "show", iface, "allowed-ips"])
    used: set[str] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            used.add(parts[1].split("/", 1)[0])
    return used


def qr_svg(config_text: str) -> str | None:
    if not shutil.which("qrencode"):
        return None
    result = subprocess.run(
        ["qrencode", "-t", "SVG", "-o", "-"],
        input=config_text,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def allocate_address(config: dict, conn: sqlite3.Connection) -> str:
    network = ipaddress.ip_network(config["client_network"])
    used = {row["address"].split("/", 1)[0] for row in conn.execute("SELECT address FROM devices WHERE revoked_at IS NULL")}

    if not config.get("dry_run"):
        try:
            used |= wg_show_allowed_ips(config["wg_iface"])
        except subprocess.CalledProcessError:
            pass

    for host in network.hosts():
        ip = str(host)
        if ip.endswith(".1") or ip.endswith(".2"):
            continue
        if ip not in used:
            return f"{ip}/32"
    raise RuntimeError(f"No free address found in {network}")


def client_config(config: dict, private_key: str, address: str, profile: str) -> str:
    allowed = config["profiles"][profile]
    lines = [
        "[Interface]",
        f"PrivateKey = {private_key}",
        f"Address = {address}",
        f"DNS = {config['dns']}",
    ]
    if config.get("mtu"):
        lines.append(f"MTU = {config['mtu']}")
    lines.extend(
        [
            "",
            "[Peer]",
            f"PublicKey = {server_public_key(config)}",
            f"Endpoint = {config['endpoint']}",
            f"AllowedIPs = {allowed}",
            "PersistentKeepalive = 25",
            "",
        ]
    )
    return "\n".join(lines)


def server_public_key(config: dict) -> str:
    if config.get("dry_run"):
        return "DRY_RUN_SERVER_PUBLIC_KEY"
    return run_command(["wg", "show", config["wg_iface"], "public-key"])


def append_peer(config: dict, device_id: int, invite_id: int, public_key: str, address: str, label: str) -> None:
    if config.get("dry_run"):
        return

    wg_conf = Path(config["wg_config"])
    block = (
        f"\n# edge1-vpn-enroll device:{device_id} invite:{invite_id} label:{label}\n"
        "[Peer]\n"
        f"PublicKey = {public_key}\n"
        f"AllowedIPs = {address}\n"
    )
    with wg_conf.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(block)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    run_command(["wg", "set", config["wg_iface"], "peer", public_key, "allowed-ips", address])


def remove_peer_from_config(config: dict, device_id: int) -> None:
    if config.get("dry_run"):
        return

    wg_conf = Path(config["wg_config"])
    marker = f"# edge1-vpn-enroll device:{device_id} "
    lines = wg_conf.read_text(encoding="utf-8").splitlines(keepends=True)
    output: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith(marker):
            i += 1
            if i < len(lines) and lines[i].strip() == "[Peer]":
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("[") and not lines[i].startswith("# edge1-vpn-enroll"):
                    i += 1
            continue
        output.append(lines[i])
        i += 1
    wg_conf.write_text("".join(output), encoding="utf-8")


@dataclass
class EnrollmentResult:
    device_id: int
    label: str
    address: str
    profile: str
    config_text: str
    qr_svg: str | None


def create_invite(config: dict, label: str, profile: str, expires_hours: int, max_uses: int, created_by: str | None, owner_subject: str = "", owner_display_name: str = "") -> tuple[int, str]:
    if profile not in config["profiles"]:
        raise ValueError(f"Unknown profile: {profile}")
    init_db(config["db_path"])
    token = make_token()
    now = iso_now()
    expires_at = (utcnow() + timedelta(hours=expires_hours)).isoformat()
    conn = connect(config["db_path"])
    try:
        cur = conn.execute(
            """
            INSERT INTO invites (label, token_hash, profile, max_uses, expires_at, created_at, created_by, owner_subject, owner_display_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (label, hash_token(token), profile, max_uses, expires_at, now, created_by, owner_subject.strip()[:256], owner_display_name.strip()[:256]),
        )
        invite_id = int(cur.lastrowid)
        audit(conn, now, "invite.created", str(invite_id), {"label": label, "profile": profile, "max_uses": max_uses})
        conn.commit()
        return invite_id, token
    finally:
        conn.close()


def get_invite_by_token(config: dict, token: str) -> sqlite3.Row | None:
    init_db(config["db_path"])
    conn = connect(config["db_path"])
    try:
        return conn.execute("SELECT * FROM invites WHERE token_hash = ?", (hash_token(token),)).fetchone()
    finally:
        conn.close()


def invite_is_redeemable(invite: sqlite3.Row | None) -> tuple[bool, str]:
    if invite is None:
        return False, "Invite not found."
    if invite["revoked_at"]:
        return False, "Invite has been revoked."
    if invite["uses"] >= invite["max_uses"]:
        return False, "Invite has already been used."
    if parse_iso(invite["expires_at"]) < utcnow():
        return False, "Invite has expired."
    return True, "Invite is ready."


def enroll_device(config: dict, token: str, device_label: str) -> EnrollmentResult:
    init_db(config["db_path"])
    device_label = device_label.strip()[:80]
    if not device_label:
        raise ValueError("Device name is required.")

    conn = connect(config["db_path"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        invite = conn.execute("SELECT * FROM invites WHERE token_hash = ?", (hash_token(token),)).fetchone()
        ok, reason = invite_is_redeemable(invite)
        if not ok:
            raise ValueError(reason)

        private_key = wg_genkey() if not config.get("dry_run") else "DRY_RUN_CLIENT_PRIVATE_KEY"
        public_key = wg_public_key(private_key) if not config.get("dry_run") else "DRY_RUN_CLIENT_PUBLIC_KEY_" + secrets.token_hex(4)
        address = allocate_address(config, conn)
        now = iso_now()
        cur = conn.execute(
            """
            INSERT INTO devices (invite_id, label, peer_public_key, address, profile, created_at, owner_subject, owner_display_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (invite["id"], device_label, public_key, address, invite["profile"], now, invite["owner_subject"], invite["owner_display_name"]),
        )
        device_id = int(cur.lastrowid)
        conn.execute("UPDATE invites SET uses = uses + 1 WHERE id = ?", (invite["id"],))
        config_text = client_config(config, private_key, address, invite["profile"])

        if config.get("save_client_configs"):
            path = Path(config["client_config_dir"]) / f"device-{device_id}-{safe_filename(device_label)}.conf"
            path.write_text(config_text, encoding="utf-8")
            path.chmod(0o600)

        append_peer(config, device_id, int(invite["id"]), public_key, address, device_label)
        audit(conn, now, "device.enrolled", str(device_id), {"invite_id": invite["id"], "label": device_label, "address": address})
        conn.commit()
        return EnrollmentResult(device_id, device_label, address, invite["profile"], config_text, qr_svg(config_text))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revoke_device(config: dict, device_id: int) -> None:
    init_db(config["db_path"])
    conn = connect(config["db_path"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        device = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        if device is None:
            raise ValueError(f"No device with id {device_id}")
        if device["revoked_at"]:
            return
        now = iso_now()
        conn.execute("UPDATE devices SET revoked_at = ? WHERE id = ?", (now, device_id))
        audit(conn, now, "device.revoked", str(device_id), {"public_key": device["peer_public_key"], "address": device["address"]})
        remove_peer_from_config(config, device_id)
        if not config.get("dry_run"):
            run_command(["wg", "set", config["wg_iface"], "peer", device["peer_public_key"], "remove"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def list_owned_devices(config: dict, owner_subject: str) -> list[dict]:
    init_db(config["db_path"])
    owner_subject = owner_subject.strip()
    if not owner_subject:
        raise ValueError("owner subject is required")
    conn = connect(config["db_path"])
    try:
        rows = conn.execute(
            "SELECT id,label,address,profile,created_at,revoked_at,owner_subject,owner_display_name FROM devices WHERE owner_subject=? ORDER BY id DESC",
            (owner_subject,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def rename_owned_device(config: dict, device_id: int, owner_subject: str, label: str) -> dict:
    init_db(config["db_path"])
    label = label.strip()[:80]
    if not label:
        raise ValueError("device name is required")
    conn = connect(config["db_path"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM devices WHERE id=? AND owner_subject=?", (device_id, owner_subject)).fetchone()
        if row is None:
            raise ValueError("device not found for this account")
        if row["revoked_at"]:
            raise ValueError("revoked devices cannot be renamed")
        now = iso_now()
        conn.execute("UPDATE devices SET label=? WHERE id=?", (label, device_id))
        audit(conn, now, "device.renamed", str(device_id), {"owner_subject": owner_subject, "label": label})
        conn.commit()
        return dict(conn.execute("SELECT id,label,address,profile,created_at,revoked_at,owner_subject,owner_display_name FROM devices WHERE id=?", (device_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revoke_owned_device(config: dict, device_id: int, owner_subject: str) -> None:
    init_db(config["db_path"])
    conn = connect(config["db_path"])
    try:
        row = conn.execute("SELECT id FROM devices WHERE id=? AND owner_subject=?", (device_id, owner_subject)).fetchone()
        if row is None:
            raise ValueError("device not found for this account")
    finally:
        conn.close()
    revoke_device(config, device_id)

def revoke_invite(config: dict, invite_id: int) -> None:
    init_db(config["db_path"])
    conn = connect(config["db_path"])
    try:
        now = iso_now()
        conn.execute("UPDATE invites SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL", (now, invite_id))
        audit(conn, now, "invite.revoked", str(invite_id), {})
        conn.commit()
    finally:
        conn.close()


def list_rows(config: dict, table: str) -> list[sqlite3.Row]:
    init_db(config["db_path"])
    conn = connect(config["db_path"])
    try:
        if table == "invites":
            return list(conn.execute("SELECT id, label, profile, uses, max_uses, expires_at, revoked_at FROM invites ORDER BY id DESC"))
        if table == "devices":
            return list(conn.execute("SELECT id, label, address, profile, created_at, revoked_at FROM devices ORDER BY id DESC"))
        raise ValueError(table)
    finally:
        conn.close()


def safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in value).strip("-") or "device"


def svg_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64," + encoded


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def json_dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
