# Edge1 Operations API

Status: live accepted on immutable runtime; repository reconciliation in progress

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
- `NoNewPrivileges=yes` remains enabled in production.
- Output is bounded before storage and response.

## Runtime isolation

The production Operations API must not execute from the shared mutable checkout at `/opt/edge1-management-interface`.

That checkout is used for attended Edge1 engineering and may legitimately switch between independent feature/live branches. Because allowlisted actions execute relative to `EDGE1_OPS_ROOT`, coupling the service to that checkout makes diagnostics and repository-state tools change when unrelated work changes branches.

Production therefore uses a detached, clean runtime worktree under:

`/opt/edge1-operations-api-runtimes/<revision-prefix>`

A root-owned systemd drop-in replaces `ExecStart`, `WorkingDirectory`, and `EDGE1_OPS_ROOT` with the immutable runtime and adds the runtime to `ReadOnlyPaths`. The base unit's loopback bind, mutation-disabled state, local audit database, secret-file location, account, capability bounding, and other hardening remain unchanged.

Prepare the detached worktree as `wwadmin` so Git worktree metadata remains owned by the repository account. Then validate and pin it with the root installer:

```sh
REVISION=<reviewed-full-commit-sha>
RUNTIME=/opt/edge1-operations-api-runtimes/${REVISION%${REVISION#????????????}}

sudo install -d -o wwadmin -g wwadmin -m 0755 /opt/edge1-operations-api-runtimes
git worktree add --detach "$RUNTIME" "$REVISION"

sudo sh deploy/pin-edge1-operations-api-runtime.sh --runtime "$RUNTIME"
sudo sh deploy/pin-edge1-operations-api-runtime.sh --runtime "$RUNTIME" --apply
```

The pinning installer validates the clean runtime, syntax, JSON allowlist, effective systemd unit, bounded readiness, loopback listener, mutation-disabled health contract, process working directory, and `NoNewPrivileges`. It creates a local rollback script and evidence bundle before changing the service.

## 2026-08-18 live acceptance

Reviewed runtime revision:

`7496da7550ee46ef81142081b0a63fced7894e90`

Production runtime:

`/opt/edge1-operations-api-runtimes/7496da7550ee`

Evidence:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260818T192709Z`

Rollback:

`/var/lib/wwcx-deployment-evidence/operations-api-runtime/20260818T192709Z/rollback.sh`

Accepted production checks:

- runtime worktree clean and exactly at the reviewed revision;
- Operations API core and allowlist blobs matched the previously running revision;
- passive Asterisk diagnostics: `limited`, native CLI `error`, fallback `ok`;
- passive Kamailio diagnostics: `limited`, native CLI `error`, fallback `ok`;
- passive FreePBX diagnostics: `limited`, native CLI `unavailable`, fallback `ok`;
- service became ready after the bounded readiness wait;
- `/healthz` returned `status=ok`, 27 actions, and `mutations_enabled=false`;
- service remained `wwadmin:wwadmin` with `NoNewPrivileges=yes`;
- process working directory became `/opt/edge1-operations-api-runtimes/7496da7550ee`;
- listener remained only `127.0.0.1:8097`;
- shared primary checkout stayed at its pre-deployment commit and branch state;
- no user/group, sudoers, socket-permission, firewall, DNS, SIP, SNMP, call, message, or certificate change was made.

An earlier trial changed the working directory/root but not the base unit's absolute `ExecStart`, and its single immediate health probe raced service startup. The automatic rollback succeeded. The accepted deployment explicitly replaces `ExecStart` and uses a bounded readiness loop. This failure mode is now encoded in the pinning installer.

## Initial actions

Read-only actions include repository status, interconnect validation, numbering-node tests, numbering health, telephony health, fixed Control Surfaces diagnostics, service/network/disk state, Apache status, BigBird health/tools, messaging health, time-authority summary, and configuration digest. Repository fetch and fast-forward actions remain disabled because production mutations are disabled.

## Base bootstrap

For a first installation of the base service only:

```sh
python3 -m unittest tests.test_edge1_operations_api -v
sudo sh deploy/install-edge1-operations-api.sh
sudo sh deploy/install-edge1-operations-api.sh --apply
curl -fsS http://127.0.0.1:8097/healthz | python3 -m json.tool
```

After base bootstrap, pin production to a reviewed immutable runtime as described above.

The base installer generates `/etc/edge1-operations-api.secret` locally when absent. Never commit, paste, email, or transmit that secret through chat.

## BigBird activation

The manifest under `integrations/bigbird-edge1-operations/` enables only read and validation tools. Mutation tools remain disabled. BigBird integration must reuse the gateway's existing authorization, scope, nonce, signing, audit, and result-bounding controls. The service secret must be read from protected local configuration.

## Public SQL server boundary

The Operations API does not connect to a public SQL listener. Its default audit store is local SQLite under `/var/lib/edge1-operations-api`.

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

For an immutable-runtime pin, use the rollback script recorded in that deployment's evidence directory.

For complete base-service removal only:

```sh
sudo systemctl disable --now edge1-operations-api.service
sudo rm -f /etc/systemd/system/edge1-operations-api.service
sudo rm -f /etc/systemd/system/edge1-operations-api.service.d/20-immutable-runtime.conf
sudo systemctl daemon-reload
```

Retain the audit database and secret until evidence retention and incident-review requirements are satisfied.
