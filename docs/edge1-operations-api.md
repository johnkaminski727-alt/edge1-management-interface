# Edge1 Operations API

Status: repository implementation; runtime bootstrap pending

## Purpose

Provide BigBird and approved operators with a narrow, auditable Edge1 execution surface without exposing SSH, arbitrary shell, arbitrary files, arbitrary SQL, or unrestricted service control.

## Security model

- Binds only to `127.0.0.1:8097`; non-loopback binds are refused in code.
- HMAC-SHA256 signs method, path, timestamp, nonce, actor, and body hash.
- Requests older than five minutes and reused nonces are rejected.
- Every executed, denied, failed, or timed-out action receives an audit identifier.
- Commands are complete fixed argv arrays loaded from a root-controlled allowlist.
- Request parameters are not accepted.
- Mutating actions require both an allowlist flag and `EDGE1_OPS_MUTATIONS_ENABLED=true`.
- The supplied systemd unit starts with mutations disabled and no Linux capabilities.
- Output is bounded before storage and response.

## Initial actions

Read-only actions include repository status, interconnect validation, numbering-node tests, numbering health, and telephony health. Repository fetch and fast-forward exist but remain disabled until a separately reviewed mutation activation.

## Bootstrap

From a clean, current checkout:

```sh
python3 -m unittest tests.test_edge1_operations_api -v
sudo sh deploy/install-edge1-operations-api.sh
sudo sh deploy/install-edge1-operations-api.sh --apply
curl -fsS http://127.0.0.1:8097/healthz | python3 -m json.tool
```

The installer generates `/etc/edge1-operations-api.secret` locally when absent. Never commit, paste, email, or transmit that secret through chat.

## BigBird activation

The manifest under `integrations/bigbird-edge1-operations/` enables only read and validation tools. Mutation tools remain disabled. BigBird integration must reuse the gateway's existing authorization, scope, nonce, signing, audit, and result-bounding controls. The service secret must be read from protected local configuration.

## Public SQL server boundary

The operations API does not connect to a public SQL listener. Its default audit store is local SQLite under `/var/lib/edge1-operations-api`.

Before any PostgreSQL backend is enabled:

1. Capture current listeners, `postgresql.conf`, `pg_hba.conf`, firewall state, clients, backups, and authentication logs.
2. Verify a restorable backup.
3. Bind PostgreSQL to loopback or an explicitly approved private management address.
4. Remove broad `0.0.0.0/0` and `::/0` client rules.
5. Require TLS for every non-local connection.
6. Create one least-privilege role limited to the operations schema; prohibit role, database, extension, file, replication, and superuser privileges.
7. Rotate credentials after public exposure is removed.
8. Test each legitimate client before closing the change window.

Changing database listeners, firewall rules, authentication, or credentials is a privileged production-security change and is intentionally not performed by the repository installer.

## Rollback

```sh
sudo systemctl disable --now edge1-operations-api.service
sudo rm -f /etc/systemd/system/edge1-operations-api.service
sudo systemctl daemon-reload
```

Retain the audit database and secret until evidence retention and incident-review requirements are satisfied.
