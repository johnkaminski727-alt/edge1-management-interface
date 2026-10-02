#!/usr/bin/env python3
"""Persistent local broker for bounded AVA physical-presentation requests.

This daemon terminates at policy decisions. It contains no hardware executor.
Physical effects are disabled by default and cannot be enabled by clients.
"""

from __future__ import annotations

import argparse
import grp
import os
import pwd
import signal
import socket
from pathlib import Path
from typing import Optional

try:
    from ava_physical_effects_broker import BrokerPolicy
    from ava_physical_effects_protocol import PhysicalEffectsProtocol
    from ava_physical_effects_transport import handle_connection
except ImportError:
    from server.ava_physical_effects_broker import BrokerPolicy
    from server.ava_physical_effects_protocol import PhysicalEffectsProtocol
    from server.ava_physical_effects_transport import handle_connection


DEFAULT_SOCKET_PATH = "/run/ava-physical-effects/control.sock"
DEFAULT_ALLOWED_USER = "bigbird-ai"
DEFAULT_ALLOWED_GROUP = "bigbird-ai"
DEFAULT_SOCKET_MODE = 0o660


class DaemonError(RuntimeError):
    """Raised when the broker daemon cannot start safely."""


def resolve_identity(user_name: str, group_name: str) -> tuple[int, int]:
    try:
        user = pwd.getpwnam(user_name)
        group = grp.getgrnam(group_name)
    except KeyError as exc:
        raise DaemonError("authorized peer identity does not resolve") from exc

    return user.pw_uid, group.gr_gid


def prepare_socket_path(path: Path) -> None:
    parent = path.parent

    if not parent.is_dir():
        raise DaemonError("socket directory does not exist")

    if path.exists() or path.is_socket():
        raise DaemonError("socket path already exists")


def create_listener(
    path: Path,
    *,
    socket_gid: int,
    owner_uid: int = 0,
    chown_fn=os.chown,
) -> socket.socket:
    prepare_socket_path(path)

    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        listener.bind(str(path))
        chown_fn(path, owner_uid, socket_gid)
        os.chmod(path, DEFAULT_SOCKET_MODE)
        listener.listen(8)
    except Exception:
        listener.close()

        try:
            path.unlink()
        except FileNotFoundError:
            pass

        raise

    return listener


class BrokerDaemon:
    def __init__(
        self,
        socket_path: str,
        *,
        allowed_user: str = DEFAULT_ALLOWED_USER,
        allowed_group: str = DEFAULT_ALLOWED_GROUP,
    ) -> None:
        self.path = Path(socket_path)
        self.allowed_uid, self.allowed_gid = resolve_identity(
            allowed_user,
            allowed_group,
        )

        # Deliberately fixed false in this phase.
        self.policy = BrokerPolicy(enabled=False)

        self.protocol = PhysicalEffectsProtocol(
            self.policy,
            allowed_uid=self.allowed_uid,
            allowed_gid=self.allowed_gid,
        )

        self.listener: Optional[socket.socket] = None
        self.stop_requested = False

    def request_stop(self, _signum=None, _frame=None) -> None:
        self.stop_requested = True

        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass

    def serve(self) -> None:
        if os.geteuid() != 0:
            raise DaemonError("broker daemon must run as root")

        self.listener = create_listener(
            self.path,
            socket_gid=self.allowed_gid,
        )

        try:
            while not self.stop_requested:
                try:
                    connection, _ = self.listener.accept()
                except OSError:
                    if self.stop_requested:
                        break
                    raise

                try:
                    handle_connection(connection, self.protocol)
                except Exception:
                    # A malformed or unauthorized client must not terminate
                    # the broker. The connection simply fails closed.
                    pass
                finally:
                    connection.close()

        finally:
            if self.listener is not None:
                self.listener.close()
                self.listener = None

            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--socket",
        default=DEFAULT_SOCKET_PATH,
    )
    parser.add_argument(
        "--allowed-user",
        default=DEFAULT_ALLOWED_USER,
    )
    parser.add_argument(
        "--allowed-group",
        default=DEFAULT_ALLOWED_GROUP,
    )

    args = parser.parse_args()

    daemon = BrokerDaemon(
        args.socket,
        allowed_user=args.allowed_user,
        allowed_group=args.allowed_group,
    )

    signal.signal(signal.SIGTERM, daemon.request_stop)
    signal.signal(signal.SIGINT, daemon.request_stop)

    daemon.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
