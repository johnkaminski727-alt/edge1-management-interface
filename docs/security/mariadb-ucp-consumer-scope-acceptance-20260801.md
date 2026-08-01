# MariaDB and UCP Consumer-Scope Audit Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/mariadb-ucp-consumer-scope/20260801T032636Z/audit.txt
SHA-256: 3d16082bd11a9be5a36783834e50c6db583e67abe7aa88470e5f882656ad56ba
```

The audit exited `0`, reported zero warnings and zero failures, and performed no database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, container or traffic change.

## Accepted MariaDB topology

- `/etc/mysql/my.cnf` is a symbolic link to `/etc/mysql/mariadb.cnf`.
- The apparent mode `0777` applies to the symlink entry; the effective regular-file target is `0644`, owned by `root:root`.
- This is not a world-writable MariaDB configuration-file defect.
- `mariadb.socket` remains active and enabled with `ListenStream=3306`, rendered as wildcard `[::]:3306` with IPv4 compatibility.
- The local Unix sockets `@mariadb` and `/run/mysqld/mysqld.sock` are also preserved by the socket unit.
- FreePBX, Asterisk realtime, and ODBC transport candidates refer to loopback and, in the ODBC case, a Unix socket.

## Scope-classification correction

The original output included:

```text
tcp_3306_scope_local_loopback__peer_other=1
```

That label is not accepted as a literal endpoint classification. With `ss -Htnp state established`, the output columns are receive queue, send queue, local endpoint, peer endpoint and process metadata. The audit treated columns four and five as local and peer, which shifted both fields by one.

The row selection matched a peer endpoint ending in port `3306`; therefore the observation is consistent with a local client connecting to MariaDB on loopback, while the `peer_other` value was derived from process metadata rather than an address. A corrected endpoint and process-attribution audit is required before a listener change.

## Accepted UCP topology

- FreePBX UCP Node PID `1652253` owns TCP `8001` and `8003`.
- The process runs as `asterisk:asterisk` under PM2 in `/system.slice/freepbx.service`.
- UCP source declares default ports `8001` and `8003` and creates Socket.IO listeners with `server.listen(port, host)` and `serverS.listen(portS, hostS)`.
- Both ports had zero established connections at the observation instant.
- Zero point-in-time connections do not establish that UCP is unused.
- Exact host defaults and client publication paths remain unresolved and must be inspected before binding to loopback or introducing a reverse proxy.

## Exposure boundary

The authoritative firewall still drops new public-interface traffic to TCP `3306`, `8001`, and `8003`. The broad `iifname "wg0" accept` rule admits these wildcard listeners from authenticated WireGuard peers.

## Decision boundary

Accepted:

- the MariaDB symlink permissions are normal and the effective target is not world-writable;
- the wildcard TCP listener is created by `mariadb.socket`;
- local configuration candidates support loopback or Unix-socket transports;
- the original established-connection scope label contains an `ss` field-index defect;
- UCP owns TCP `8001` and `8003` and uses Socket.IO;
- no public exposure is admitted by the current firewall, but WireGuard-wide exposure remains.

Not authorized or performed:

- MariaDB socket override or restart;
- UCP/PM2 configuration or restart;
- firewall or WireGuard changes;
- database queries or credential inspection;
- native Asterisk deployment.
