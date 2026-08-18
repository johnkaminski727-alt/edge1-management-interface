# Edge1 Operator Deployment Completion Record

> **Historical-record notice — reconciled 2026-08-18:** This document preserves an earlier deployment/validation claim and should not be deleted or rewritten as though it never occurred. The current permanent-operator workstream still requires fresh authenticated host validation of the present service implementation, listener/transport state and ChatGPT workspace attachment. See `docs/edge1-operator/08-mcp-integration-status.md`, `docs/edge1-operator/13-completion-status.md`, and `docs/archive/edge1-control-surfaces-operator-archive-readiness-20260818.md` before treating the service state below as current production evidence.

## Historical Status

Completed and validated at the time of this record.

## Production Deployment

Repository:

```
/opt/edge1-management-interface
```

Production branch:

```
main
```

Service:

```
edge1-operator-mcp.service
```

## Validation Completed

The following checks were recorded as passed:

```sh
sh -n deploy/edge1-operator/install-systemd-service.sh
```

```sh
sudo sh deploy/edge1-operator/install-systemd-service.sh
```

```sh
sudo sh deploy/edge1-operator/verify-edge1-operator-install.sh
```

```sh
sudo sh deploy/edge1-operator/validate-service-health.sh
```

## Operational Ownership Model

Source repository:

- Owned by deployment/development account (`wwadmin`).

Runtime state:

```
/var/lib/edge1-operator
```

Owned by:

```
edge1-operator
```

Configuration:

```
/etc/edge1-operator
```

Controlled by:

```
root
```

## Installer Behavior

The installer was recorded as provisioning:

- service account creation when missing;
- runtime directory creation;
- environment file creation;
- systemd service installation;
- systemd enablement.

## Recovery Lessons Captured

The deployment hardening work addressed:

- accidental deployment from non-production branches;
- incomplete installer provisioning;
- missing runtime directories;
- service validation drift;
- Python startup/import validation gaps.

## Historical Validation Result

The healthy state recorded by this document was:

```
service=edge1-operator-mcp.service
enabled=enabled
active=active
```

## Current-use rule

Do not use the historical state above as a substitute for a fresh authenticated host check. Before a new production mutation or permanent ChatGPT MCP attachment, verify the current host/principal, repository revision and dirty state, systemd unit content/status, listener binding, runtime logs, Operations API state, transport implementation and rollback path.
