# MariaDB/UCP Endpoint Attribution Partial Transcript — 2026-08-01

## Uploaded source

The operator supplied `send.zip` as a conversation upload after running the read-only endpoint-attribution audit.

Archive inventory:

```text
send.zip
SHA-256: 060234bbc126aff7ff2be71bc5e29b9c556cf38598e9172d8088cef2e670e19b
size: 241314 bytes
member: send.txt
member SHA-256: d017a1a5e8e4338c5d01ba28e0a808a178b04e8ebfb0f27ec55d70ead40481b2
member size: 1059862 bytes
```

The archive contained exactly one regular text member and no path-traversal or nested-archive entry.

## Transcript completeness boundary

The uploaded `send.txt` begins partway through the UCP client-publication reference output. It omits the audit header and the earlier corrected MariaDB endpoint, PID, listener, transport, corrected UCP endpoint and UCP PID sections. It is therefore not a complete copy of the authoritative Edge1 evidence file.

The preserved tail reports:

```text
/var/lib/wwcx-deployment-evidence/mariadb-ucp-endpoint-attribution/20260801T035149Z/audit.txt
SHA-256: 32f92589e0b5814583ddcfc4c3d7be9569d16d2e15dc9215a30904b3673770c0
Audit exit code: 0
Warnings: 0
Failures: 0
```

The run states that it was read-only and made no database query, grant inspection, service, process, PM2, unit, listener, firewall, WireGuard, configuration, package, client-address, logger, packet-capture, external-scan, container or traffic change.

## Accepted UCP source findings

The preserved transcript establishes:

- `node/lib/server.js` defaults TCP 8001 and 8003 to `0.0.0.0` and permits `NODEJSBINDADDRESS`, `NODEJSBINDPORT`, `NODEJSHTTPSBINDADDRESS` and `NODEJSHTTPSBINDPORT` overrides;
- the Node service calls `server.listen(port, host)` and `serverS.listen(portS, hostS)`;
- FreePBX UCP advanced-setting defaults include wildcard IPv6 address `::` for both Node bind addresses and ports 8001/8003;
- browser code builds a direct `ws://host:8001/...` or `wss://host:8003/...` connection from UCP publication data;
- the publication host is derived from the HTTP request host;
- the UCP page itself may be published through dedicated UCP ports or through the Apache ACP path `/ucp` on ports 80/443.

Simply rebinding the Node sockets to loopback would therefore break direct browser WebSocket access unless an authenticated reverse proxy is added and the browser publication data is changed consistently.

## Decision status

Accepted:

- the endpoint-attribution audit exited successfully;
- UCP is designed for direct browser WebSocket connectivity unless reverse-proxied;
- loopback-only UCP binding is not approved without a tested HTTPS/WebSocket proxy and matching publication behavior;
- the apparent `/etc/mysql/my.cnf` permission concern remains closed as symlink metadata with a root-owned mode-0644 target.

Not established from the uploaded transcript:

- corrected MariaDB endpoint direction and scope rows;
- MariaDB client-process identity;
- whether every active TCP 3306 connection is host-local;
- whether MariaDB socket narrowing is ready for a controlled change.

A compact read-only summary audit is required to capture only these missing fields without the large UCP source-reference dump.
