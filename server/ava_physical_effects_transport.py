#!/usr/bin/env python3
"""Unix-domain transport for the AVA physical-effects protocol.

This transport derives peer identity from Linux SO_PEERCRED. Client payloads
cannot assert their own UID, GID, or PID.

There is deliberately no physical-effect executor in this module.
"""

from __future__ import annotations

import socket
import struct
from pathlib import Path

try:
    from ava_physical_effects_protocol import (
        MAX_REQUEST_BYTES,
        PeerIdentity,
        PhysicalEffectsProtocol,
        ProtocolError,
    )
except ImportError:
    from server.ava_physical_effects_protocol import (
        MAX_REQUEST_BYTES,
        PeerIdentity,
        PhysicalEffectsProtocol,
        ProtocolError,
    )


PEERCRED_FORMAT = "3i"
PEERCRED_SIZE = struct.calcsize(PEERCRED_FORMAT)


class TransportError(RuntimeError):
    """Raised when the local Unix transport fails closed."""


def peer_identity(connection: socket.socket) -> PeerIdentity:
    raw = connection.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        PEERCRED_SIZE,
    )

    if len(raw) != PEERCRED_SIZE:
        raise TransportError("invalid peer credential size")

    pid, uid, gid = struct.unpack(PEERCRED_FORMAT, raw)

    if pid <= 0 or uid < 0 or gid < 0:
        raise TransportError("invalid peer credentials")

    return PeerIdentity(pid=pid, uid=uid, gid=gid)


def receive_request(connection: socket.socket) -> bytes:
    data = bytearray()

    while len(data) <= MAX_REQUEST_BYTES:
        chunk = connection.recv(min(256, MAX_REQUEST_BYTES + 1 - len(data)))

        if not chunk:
            break

        data.extend(chunk)

        if b"\n" in chunk:
            break

    if not data:
        raise TransportError("empty request")

    if len(data) > MAX_REQUEST_BYTES:
        raise TransportError("request too large")

    if not data.endswith(b"\n"):
        raise TransportError("request must end with newline")

    payload = bytes(data[:-1])

    if b"\n" in payload:
        raise TransportError("multiple requests are not allowed")

    return payload


def handle_connection(
    connection: socket.socket,
    protocol: PhysicalEffectsProtocol,
) -> None:
    peer = peer_identity(connection)
    payload = receive_request(connection)

    try:
        response = protocol.handle(payload, peer)
    except ProtocolError as exc:
        raise TransportError("protocol rejected request") from exc

    connection.sendall(response)


def serve_once(
    socket_path: str,
    protocol: PhysicalEffectsProtocol,
    *,
    ready=None,
) -> None:
    path = Path(socket_path)

    if path.exists():
        raise TransportError("socket path already exists")

    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        listener.bind(str(path))
        path.chmod(0o600)
        listener.listen(1)

        if ready is not None:
            ready()

        connection, _ = listener.accept()

        try:
            handle_connection(connection, protocol)
        finally:
            connection.close()

    finally:
        listener.close()

        try:
            path.unlink()
        except FileNotFoundError:
            pass
