# Edge1 systemd unit-directory trust boundary — 2026-08-19

Status: repository defect identified and corrected; live production remediation prepared but not yet applied because it changes privileged filesystem ownership/mode.

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

The unit itself exactly matches the reviewed staged unit. The traversal failure is on its parent directory:

```text
/etc/systemd/system mode=0750 owner=bigbird-time group=bigbird-time
```

Because the directory owner has write permission, the `bigbird-time` Unix principal has filesystem authority to create/remove entries in the global systemd unit directory outside the protections of an individual service sandbox. That ownership is not an acceptable global systemd trust boundary.

The currently reviewed Time Authority service units themselves use `NoNewPrivileges=true` and `ProtectSystem=strict`, which reduces the immediate write surface of those particular service processes. It does not make service-account ownership of `/etc/systemd/system` an acceptable design.

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

## Prepared live remediation

Repository tool:

```text
deploy/repair-edge1-systemd-unit-dir-boundary.sh
```

Default invocation is dry-run only. `--apply` is intentionally separate and must not be run without explicit production security-change approval.

The remediation is fail-closed:

- target must be exactly `/etc/systemd/system` on `edge1.ww.cx`;
- current metadata must be exactly the observed `bigbird-time:bigbird-time` mode `0750`, unless it is already the desired safe state;
- desired state is `root:root` mode `0755`;
- evidence captures before/after parent metadata, immediate directory-entry metadata, and relevant service active/enabled state;
- unit-directory entries must remain byte-for-byte identical as a metadata listing;
- relevant service active/enabled states must remain unchanged;
- no unit file content, symlink, service lifecycle, listener, firewall, DNS, certificate, SIP/carrier, or tunnel state is changed;
- an emergency metadata-only rollback script is retained in protected evidence.

Changing the live parent-directory owner/mode is a privileged security-boundary change and remains explicitly approval-gated.

## Tunnel impact

Do not weaken the Secure MCP validator to work around this condition. Once the global systemd directory is restored to the root-controlled state, the existing world-readable `edge1-secure-mcp-tunnel.service` can be traversed/read by `edge1-operator`, allowing the validator's reviewed hash/metadata check to proceed normally.

The Edge1 tunnel remains disabled/inactive. `edge1-operator-mcp.service` and `bigbird-ai-tunnel.service` remained active throughout discovery. No tunnel start/enable/reload command was run.
