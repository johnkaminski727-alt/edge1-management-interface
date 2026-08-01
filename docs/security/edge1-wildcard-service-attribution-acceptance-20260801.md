# Edge1 Wildcard-Service Attribution Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/edge1-wildcard-service-attribution/20260801T031150Z/audit.txt
SHA-256: 5c47d5f4464fe1c179b2529cb5669eab6e825a80c5282e7d2964ce5e8f863719
```

The audit exited `0`, reported three warnings and zero failures, and made no database, service, process, unit, listener, firewall, configuration, package, logger, container or traffic change.

## MariaDB TCP 3306 attribution

TCP `3306` is jointly owned by systemd socket activation and MariaDB:

- `mariadb.socket` is active and enabled;
- it declares `ListenStream=3306`, rendered as `[::]:3306` with IPv4 compatibility;
- PID `1` and `mariadbd` PID `657251` both hold the listener;
- `mariadb.service` is active, running and correctly supervised in `/system.slice/mariadb.service`;
- one established TCP `3306` connection was present;
- the local Unix sockets `/run/mysqld/mysqld.sock` and `@mariadb` are also active.

`/etc/mysql/mariadb.conf.d/50-server.cnf` specifies `bind-address = 127.0.0.1`, but that setting does not narrow the inherited systemd socket. The wildcard exposure is therefore created by `mariadb.socket`, not by the MariaDB bind directive.

The current public firewall does not admit new public-interface TCP `3306` traffic. The broad `iifname "wg0" accept` rule still makes the wildcard socket reachable by authenticated WireGuard peers.

No socket-unit override should be deployed until the existing TCP consumer is classified by scope and local applications are checked for Unix-socket or loopback compatibility.

## FreePBX UCP TCP 8001 and 8003 attribution

TCP `8001` and `8003` are owned by Node PID `1652253`:

- executable `/usr/bin/node`;
- working directory `/var/www/html/admin/modules/ucp/node`;
- process identity `asterisk:asterisk`;
- cgroup `/system.slice/freepbx.service`;
- parent supervision through PM2 inside `freepbx.service`.

Both ports had zero established connections at the audit instant. No Apache, HAProxy or systemd proxy reference to either port was found in the searched configuration roots.

The absence of local proxy references does not prove that the ports are unused. They may be advertised directly by FreePBX/UCP application code to browsers or other clients. Source-level consumer and bind-policy attribution is required before listener narrowing or disablement.

As with TCP `3306`, new public-interface connections to `8001` and `8003` are dropped by the authoritative input policy, while authenticated WireGuard peers can reach them through the broad `wg0` trust rule.

## Permission anomaly

`/etc/mysql/my.cnf` was reported mode `0777`, owned by `root:root`. It resolves to the same content hash as `/etc/mysql/mariadb.cnf`, indicating a likely symlink or equivalent entry, but world-writable configuration metadata is unsafe and requires a separate path/symlink/ownership verification before any correction.

## Decision boundary

Accepted:

- MariaDB wildcard TCP is created by socket activation;
- the server bind directive alone is insufficient to narrow it;
- one live TCP consumer requires classification;
- UCP Node owns TCP `8001` and `8003`;
- no active UCP TCP connections were observed;
- all three ports are blocked for new public-interface traffic but admitted through WireGuard;
- consumer attribution is required before changes.

Not authorized or performed:

- database queries or grant inspection;
- client-address disclosure;
- socket-unit, listener, firewall, WireGuard, FreePBX, PM2 or Node changes;
- service restart or reload;
- external active scanning.
