# MariaDB and UCP Endpoint Summary Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/mariadb-ucp-endpoint-summary/20260801T040130Z/audit.txt
SHA-256: 30cb7bd4de6368328a0dacc1025dd40098944aacae9f941f7b7ebb25691f1d34
```

The operator-run audit exited `0`, reported zero audit warnings and zero failures, and made no database query, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, packet-capture, external-scan or traffic change.

The output contained an AWK diagnostic about an unnecessary escaped quotation mark in the process-name parser. The diagnostic did not alter endpoint direction, scope, PID or process attribution. The parser should nevertheless be corrected so future evidence is clean.

## MariaDB endpoint attribution

The compact audit resolved the complete TCP relationship:

- Node PID `1652253`, running as `asterisk:asterisk` from `/var/www/html/admin/modules/ucp/node` in `/system.slice/freepbx.service`, is the local TCP client;
- MariaDB PID `657251`, running as `mysql:mysql` in `/system.slice/mariadb.service`, is the local service endpoint;
- both endpoints are loopback scoped;
- one logical connection appears as two process-attributed socket rows, one from each endpoint;
- no WireGuard, public-interface or other-scope MariaDB connection was observed;
- the TCP `3306` listener remains wildcard scoped because `mariadb.socket` supplies the inherited listener.

This closes the earlier ambiguity caused by shifted `ss` columns. The live TCP consumer is FreePBX UCP on the same host, not a remote or WireGuard client.

## MariaDB narrowing decision

A loopback-only socket-activation design is technically supported by the observed runtime and configuration evidence:

- the only observed TCP consumer is local and loopback scoped;
- FreePBX, Asterisk realtime and ODBC transport candidates are configured for loopback or Unix-socket access;
- the existing abstract socket `@mariadb` and filesystem socket `/run/mysqld/mysqld.sock` can be preserved;
- no observed consumer requires wildcard or WireGuard TCP access.

This is approval to prepare a reversible candidate design, not approval to activate it. Activation requires a controlled MariaDB socket/service restart, immediate FreePBX/UCP reconnection verification and tested rollback.

## UCP endpoint and publication contract

TCP `8001` and `8003` remain wildcard scoped under Node PID `1652253`. No established UCP WebSocket connection was present at the observation instant.

The source contract proves direct browser publication:

- `server.js` defaults the HTTP and HTTPS listeners to `0.0.0.0` and ports `8001` and `8003`;
- FreePBX configuration can override the bind addresses and ports through `NODEJSBINDADDRESS`, `NODEJSBINDPORT`, `NODEJSHTTPSBINDADDRESS` and `NODEJSHTTPSBINDPORT`;
- the UCP PHP layer publishes the current HTTP host together with the configured Node ports;
- the browser constructs direct `ws://host:8001/...` or `wss://host:8003/...` connection strings.

Loopback-binding UCP without a replacement publication path would break remote browser WebSocket access. The current public firewall does not admit new public-interface traffic to `8001` or `8003`, while broad WireGuard acceptance still permits authenticated peers to reach them.

## Accepted split decision

- **MariaDB TCP 3306:** prepare a loopback-only socket override preserving both Unix sockets and loopback TCP; do not activate without a controlled restart and rollback evidence.
- **UCP TCP 8001/8003:** retain current listener behavior for now; do not narrow or disable. A future authenticated HTTPS/WebSocket reverse-proxy design must be validated before changing browser publication or bind scope.
- **Firewall:** no change is approved by this record.
- **Asterisk, calls and emergency services:** unaffected and outside this change.
