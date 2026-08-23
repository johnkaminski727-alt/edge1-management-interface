# Edge1 Operator Privileged Broker v1 — 2026-08-23

## Decision

Do not use the full Edge1 Agent Shell as the routine privilege boundary for the
public Operator control plane.

The Agent Shell is intentionally a root/full-mode administrative escape hatch. Its
service runs as root and its MCP implementation includes arbitrary shell, arbitrary
file operations and general service control. That is useful for attended recovery
and administration, but it is deliberately broader than the authority required by a
normal Operator capability.

Operator Controls v1 therefore uses a separate fixed privileged broker.

## Architecture

```text
public Edge1 Operator MCP
        |
        | capability + scope
        v
unprivileged edge1-operations-api.service (wwadmin)
        |
        | fixed JSON over AF_UNIX
        | SO_PEERCRED + cgroup verified
        v
edge1-operator-privileged-broker.service (root)
        |
        | hard-coded only
        v
systemctl restart wwcx-telephony-console.service
```

The broker has no TCP/UDP listener and no generic command endpoint.

## Peer authorization

The Unix socket is `root:wwadmin 0660`, but filesystem permission is not considered
sufficient authority. On every connection the root broker obtains `SO_PEERCRED` and
requires:

- peer UID is the `wwadmin` UID; and
- peer PID is currently in the systemd cgroup for
  `edge1-operations-api.service`.

Thus an ordinary interactive `wwadmin` process cannot use the socket merely because
it shares the account/group.

## Request protocol

Protocol version 1 accepts exactly one action, `telephony_console_reload`, and
exactly these fields:

- protocol version;
- fixed action name;
- correlation request ID;
- expected current Telephony Console PID;
- expected source SHA-256;
- expected repository HEAD.

It has no service, command, argv, path, URL, host, port, environment, SQL, route,
dialplan, number, carrier, recipient, message or media input.

## Independent preconditions

The root broker does not blindly trust the unprivileged Operations API. It repeats
critical checks itself:

- target console is active;
- Asterisk and Messaging Gateway are active;
- console PID exactly matches the inspected PID;
- source digest exactly matches the inspected digest;
- repository HEAD exactly matches the inspected HEAD;
- `server/telephony_status_server.py` is tracked and has no diff from HEAD;
- Asterisk and Messaging Gateway PIDs remain unchanged after the console restart.

The unprivileged Operations API then independently verifies loopback application
health and process results after the broker returns.

## Root-side audit

Before `systemctl` is called, the broker fsyncs an `authorized_attempt` record to a
root-only state directory. If this durable audit write fails, mutation does not
occur. Completion/failure records contain correlation and process metadata only; no
secrets or message/call content are stored.

## Runtime immutability

The broker must never execute Python from the `wwadmin`-managed working checkout.
`install-privileged-broker-v1.sh` copies the reviewed standalone broker source into:

`/usr/local/libexec/edge1-operator-privileged-broker/releases/<commit>/`

as root-owned read-only content and points the root-owned `current` symlink to that
release. The service executes only through that immutable path while reading the
working repository solely to verify the Telephony Console source/HEAD precondition.

## Service sandbox

The broker service is intentionally root because its only purpose is the fixed
systemd operation, but it retains:

- `NoNewPrivileges=true`;
- `CapabilityBoundingSet=` (empty);
- `AmbientCapabilities=` (empty);
- `RestrictAddressFamilies=AF_UNIX`;
- strict system/home/kernel/control-group protections;
- private temporary/devices namespaces;
- root-only state and audit data.

No network address family is available to the broker.

## Activation remains separate

Merging this source does not install the root broker and does not enable Operator
writes. The deployment sequence remains separate:

1. review/merge source and CI;
2. dry-run the immutable broker installer;
3. explicitly authorize and install/start the broker;
4. deploy the reviewed Operations API/Operator runtimes with all mutation gates off;
5. verify read-only `edge1.capabilities` and Telephony control status;
6. separately enable only the `telephony_safe_controls` broker gate;
7. separately grant the Operator process scope `edge1.telephony.control.safe`;
8. exercise one read-before-write acceptance and verify Asterisk/Messaging PIDs did
   not change;
9. preserve rollback and both unprivileged/root-side audit evidence.

At no point is the legacy global mutation gate required for this control.
