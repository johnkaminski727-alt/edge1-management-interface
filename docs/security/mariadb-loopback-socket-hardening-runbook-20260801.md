# MariaDB Loopback Socket Hardening Runbook — 2026-08-01

## Status

**Design complete; activation not yet performed.**

This runbook narrows the systemd-activated MariaDB TCP listener from wildcard scope to IPv4 and IPv6 loopback while preserving:

- the abstract Unix socket `@mariadb`;
- `/run/mysqld/mysqld.sock`;
- `127.0.0.1:3306`;
- `[::1]:3306`.

The candidate drop-in is:

```text
templates/systemd/mariadb.socket.d/10-loopback-only.conf
```

## Basis

The accepted endpoint summary observed exactly one logical MariaDB TCP relationship:

- FreePBX UCP Node PID `1652253` as the local client;
- MariaDB PID `657251` as the service endpoint;
- both sides loopback scoped;
- no WireGuard, public-interface or other-scope consumer;
- wildcard TCP supplied by `mariadb.socket`.

Configuration candidates for FreePBX, Asterisk realtime and ODBC support loopback or Unix-socket transport.

## Risk classification

Activation is a **conditional production change** because it requires:

- installing a shared systemd socket drop-in;
- `systemctl daemon-reload`;
- a controlled stop/start of `mariadb.service` and `mariadb.socket`;
- a brief database interruption affecting FreePBX and UCP;
- immediate verification and rollback if any consumer fails.

It does not change database contents, grants, schemas or credentials.

## Preconditions

Do not activate unless all are true immediately before the change:

1. The final preflight exits `0` with no non-loopback MariaDB TCP consumer.
2. MariaDB is healthy and systemd-owned.
3. FreePBX UCP Node remains the only observed TCP client.
4. The Unix sockets are present.
5. The candidate file matches the repository copy and passes static validation.
6. A timestamped evidence directory and rollback copy are prepared.
7. No calls, channels or emergency-service operations depend on the maintenance window.

## Proposed installation path

```text
/etc/systemd/system/mariadb.socket.d/10-loopback-only.conf
```

Never edit `/lib/systemd/system/mariadb.socket` directly.

## Controlled activation sequence

The following is an operator plan and has not been executed:

```bash
cd /opt/edge1-management-interface || exit 1
git pull --ff-only origin main || exit 1

TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVID="/var/lib/wwcx-deployment-evidence/mariadb-loopback-hardening/$TS"
DROPIN_DIR=/etc/systemd/system/mariadb.socket.d
DROPIN="$DROPIN_DIR/10-loopback-only.conf"
SOURCE=templates/systemd/mariadb.socket.d/10-loopback-only.conf

sudo mkdir -p "$EVID"
sudo chmod 0700 "$EVID"

sudo systemctl show mariadb.socket mariadb.service >"$EVID/systemd-before.txt"
sudo ss -H -ltnpe >"$EVID/listeners-before.txt"
sudo ss -H -lxnp >"$EVID/unix-sockets-before.txt"
sudo sha256sum "$SOURCE" >"$EVID/source.sha256"

if sudo test -e "$DROPIN"; then
    sudo cp -a "$DROPIN" "$EVID/10-loopback-only.conf.before"
else
    sudo touch "$EVID/dropin-was-absent"
fi

sudo install -d -m 0755 -o root -g root "$DROPIN_DIR"
sudo install -m 0644 -o root -g root "$SOURCE" "$DROPIN"
sudo systemctl daemon-reload

sudo systemctl stop mariadb.service
sudo systemctl stop mariadb.socket
sudo systemctl start mariadb.socket
sudo systemctl start mariadb.service
```

Do not combine this change with Asterisk, FreePBX, firewall, UCP or package changes.

## Required verification

Treat the activation as failed unless every item passes:

1. `mariadb.socket` is active and lists only the two Unix sockets plus `127.0.0.1:3306` and `[::1]:3306`.
2. `mariadb.service` is active with a nonzero `MainPID` in `/system.slice/mariadb.service`.
3. TCP `3306` has no wildcard, public-interface or WireGuard listener.
4. `/run/mysqld/mysqld.sock` and `@mariadb` remain present.
5. The FreePBX UCP Node process remains running in `/system.slice/freepbx.service`.
6. UCP ports `8001` and `8003` remain unchanged.
7. A local UCP-to-MariaDB connection can re-establish without exposing endpoint addresses in evidence.
8. Asterisk remains healthy with zero unexpected listener or call-state changes.
9. No MariaDB or FreePBX error appears in the bounded post-change journal review.

Recommended bounded checks:

```bash
sudo systemctl is-active mariadb.socket mariadb.service
sudo systemctl show mariadb.socket -p Listen -p ActiveState -p SubState -p FragmentPath
sudo systemctl show mariadb.service -p MainPID -p ControlGroup -p ActiveState -p SubState
sudo ss -H -ltnpe | grep -E ':3306[[:space:]]'
sudo ss -H -lxnp | grep -E '(@mariadb|/run/mysqld/mysqld.sock)'
sudo ss -H -ltnpe | grep -E ':(8001|8003)[[:space:]]'
sudo asterisk -rx 'core show uptime'
sudo asterisk -rx 'core show channels count'
sudo journalctl -u mariadb.service -u mariadb.socket -u freepbx.service --since '-10 minutes' --no-pager
```

Capture sanitized outputs and hashes under the evidence directory.

## Immediate rollback

Rollback immediately if MariaDB fails to start, any required consumer cannot connect, Unix sockets disappear, or the listener state differs from the approved design.

```bash
DROPIN_DIR=/etc/systemd/system/mariadb.socket.d
DROPIN="$DROPIN_DIR/10-loopback-only.conf"

sudo systemctl stop mariadb.service
sudo systemctl stop mariadb.socket

if sudo test -f "$EVID/10-loopback-only.conf.before"; then
    sudo install -m 0644 -o root -g root \
      "$EVID/10-loopback-only.conf.before" "$DROPIN"
else
    sudo rm -f "$DROPIN"
fi

sudo systemctl daemon-reload
sudo systemctl start mariadb.socket
sudo systemctl start mariadb.service
```

Rollback verification must confirm the prior listener contract, service health, Unix sockets, UCP process state and Asterisk health.

## UCP boundary

This runbook does not alter UCP TCP `8001` or `8003`. UCP publishes direct browser WebSocket URLs using the current HTTP host and configured Node ports. Listener narrowing requires a separately validated HTTPS/WebSocket reverse-proxy design and matching browser publication behavior.
