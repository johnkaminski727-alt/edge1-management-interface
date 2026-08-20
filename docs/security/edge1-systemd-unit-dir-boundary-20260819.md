# Edge1 systemd unit-directory trust boundary — 2026-08-19/20

Status: **LIVE / REPAIRED / VERIFIED**. Repository defect corrected and production parent-directory metadata restored to the root-controlled systemd trust boundary on 2026-08-20 after explicit approval.

## Discovery

The hardened Edge1 Secure MCP Tunnel compatibility validator failed closed with:

```text
EDGE1_TUNNEL_COMPAT_DOCTOR=FAIL
reason=Edge1 tunnel service unit unreadable
```

Read-only production inspection resolved the actual unit through systemd and found:

```text
FragmentPath=/etc/systemd/system/edge1-secure-mcp-tunnel.service
UnitFileState=disabled
unit mode=0644 owner=root:root
unit sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
```

The unit itself exactly matched the reviewed staged unit. The traversal failure was on its parent directory:

```text
/etc/systemd/system mode=0750 owner=bigbird-time group=bigbird-time
```

Because the directory owner had write permission, the `bigbird-time` Unix principal had filesystem authority to create/remove entries in the global systemd unit directory outside the protections of an individual service sandbox. That ownership was not an acceptable global systemd trust boundary.

The reviewed Time Authority service units themselves use `NoNewPrivileges=true` and `ProtectSystem=strict`, which reduced the immediate write surface of those particular service processes. It did not make service-account ownership of `/etc/systemd/system` an acceptable design.

## Root cause

`deploy/install-time-authority-edge1.sh` previously used one `install -d` invocation for both the application data directory and the systemd unit directory:

```sh
install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_USER" "$DATA_DIR" "$UNIT_DIR"
```

With the production defaults this assigned `bigbird-time:bigbird-time` ownership and mode `0750` to `/etc/systemd/system`.

## Repository correction

The corrected installer now:

- assigns `bigbird-time` ownership only to `/var/lib/edge1-time-authority`;
- treats `/etc/systemd/system` as a root-controlled trust boundary;
- requires production unit-directory metadata to be exactly `root:root` mode `0755` before writing units;
- records the accepted unit-directory owner/mode in installation evidence.

`deploy/time-authority-edge1-preflight.sh` independently checks the same boundary so future rollout attempts fail before service/user/unit mutation if the global unit directory is unsafe.

CI validation rejects the original joined `install -d ... "$DATA_DIR" "$UNIT_DIR"` regression and requires the fail-closed owner/mode checks.

## Accepted live remediation

Repository tool:

```text
deploy/repair-edge1-systemd-unit-dir-boundary.sh
```

A fail-closed dry run completed first and matched the exact reviewed preconditions. The human operator then provided explicit approval limited to changing only `/etc/systemd/system` ownership/mode from `bigbird-time:bigbird-time 0750` to `root:root 0755`, with protected evidence/rollback capture and no service lifecycle, DNS, firewall, certificate, listener, authentication, SIP/carrier, or production-traffic changes.

The approved `--apply` completed successfully at 2026-08-20T01:18:19Z. Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z
```

Verified post-apply state:

```text
/etc/systemd/system owner=root:root mode=0755
/etc/systemd/system/edge1-secure-mcp-tunnel.service owner=root:root mode=0644
edge1-secure-mcp-tunnel.service sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
edge1_operator_tunnel_unit_readable=yes
edge1-secure-mcp-tunnel active=inactive enabled=disabled
edge1-operator-mcp active=active enabled=enabled
bigbird-ai-tunnel active=active enabled=enabled
```

The remediation reported:

```text
live_configuration_changed=directory_metadata_only
service_state_changed=false
unit_contents_changed=false
EDGE1_SYSTEMD_UNIT_DIR_REPAIR=PASS
```

The wrapper independently re-verified the desired directory metadata, unchanged tunnel-unit SHA, `edge1-operator` readability, and unchanged relevant service states, then exited `apply_wrapper_rc=0`. No service start/stop/restart/reload/enable/disable command was run and no tunnel activation was requested.

The retained remediation evidence includes the guarded metadata-only rollback path. Do not roll back to the prior service-account-owned state except as an explicitly reviewed emergency action.

## Tunnel impact

The filesystem trust-boundary blocker is resolved. Do not weaken the Secure MCP validator. The next permitted step is a **read-only rerun** of `deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh`; only a full `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS` may advance to the separate attended tunnel-activation approval boundary.

The Edge1 tunnel remains disabled/inactive. `edge1-operator-mcp.service` and `bigbird-ai-tunnel.service` remain active/enabled. Tunnel start/enable remains separately approval-gated.
