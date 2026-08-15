# WW.CX Public NTP Server Runbook

## Objective

Operate a production Network Time Protocol endpoint at `ntp.ww.cx` from Edge1 while preserving the existing WW.CX Time Authority monitoring/dashboard as a separate observability service.

The first production phase provides standard NTPv4 on UDP/123. Network Time Security (NTS) is intentionally deferred to a later certificate-backed phase.

## Architecture

### Edge1 clock and server daemon

Use Debian's `chronyd` as the single host time daemon. It replaces `systemd-timesyncd` for system-clock discipline and also serves synchronized NTP responses to clients.

Configured upstream references:

- `sth1.ntp.se` — Netnod Stockholm;
- `sth2.ntp.se` — Netnod Stockholm;
- `mmo1.ntp.se` — Netnod Malmö;
- `time.nist.gov` — NIST;
- `time.cloudflare.com` — Cloudflare.

`minsources 3` requires multiple selectable upstreams before chronyd updates the host clock. The configuration does not enable chrony's `local` reference mode, so Edge1 must not intentionally present an unsynchronized free-running clock as a valid fallback source.

### Existing Time Authority monitor

The existing read-only Time Authority remains separate:

- dashboard/API: `127.0.0.1:8101`;
- scheduled source probes and local measurement history;
- no system-clock control;
- no public listener.

Do not add `ntp.ww.cx` as an upstream source for the Edge1 chronyd instance. A later independent observer (for example the shared-host collector) may probe `ntp.ww.cx` as an external service-health measurement without creating a synchronization loop.

## Repository assets

```text
modules/time-authority/config/edge1-chrony.conf
deploy/time-authority-ntp-server-edge1-preflight.sh
deploy/install-time-authority-ntp-server-edge1.sh
deploy/time-authority-ntp-server-edge1-smoke-test.sh
deploy/publish-time-authority-ntp-firewall-edge1.sh
tests/validate_time_authority_ntp_server.py
```

## Safety gates

The production installer refuses to run unless both variables are explicitly set:

```text
WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER=YES
WWCX_NTP_APPROVE_PUBLIC_UDP123=YES
```

These gates represent separate production decisions:

1. replace `systemd-timesyncd` with `chronyd` as Edge1's system-clock discipline daemon;
2. configure chronyd to listen as an NTP server on UDP/123.

The clock-daemon installer does **not** change the perimeter firewall or DNS. Those remain separate privileged production actions. The firewall publication helper separately requires `WWCX_NTP_APPROVE_PUBLIC_UDP123=YES`.

## Phase 1 — read-only preflight

From a clean Edge1 checkout of the approved `main` revision:

```bash
cd /opt/edge1-management-interface
sudo sh deploy/time-authority-ntp-server-edge1-preflight.sh
```

Expected checks:

- repository validation passes;
- UDP/123 is currently free before the chrony cutover;
- current `systemd-timesyncd` state is displayed but not changed;
- the Debian `chrony` package is available;
- all configured upstream hostnames resolve;
- current host time status is displayed;
- no package, service, firewall, DNS, or listener mutation occurs.

Stop if UDP/123 is already owned by an unidentified service or if the current clock discipline state is unexpected.

## Phase 2 — clock-daemon and local NTP cutover

Only after explicit approval of the two installer gates:

```bash
cd /opt/edge1-management-interface
sudo env \
  WWCX_NTP_APPROVE_CLOCK_DAEMON_CUTOVER=YES \
  WWCX_NTP_APPROVE_PUBLIC_UDP123=YES \
  sh deploy/install-time-authority-ntp-server-edge1.sh
```

The installer:

1. reruns preflight;
2. creates protected rollback evidence under `/var/lib/wwcx-deployment-evidence/public-ntp-server/`;
3. records the prior clock service, package state, UDP listeners and time status;
4. installs Debian `chrony`;
5. disables `systemd-timesyncd` to prevent dual clock discipline;
6. installs the reviewed WW.CX chrony configuration;
7. enables/restarts `chrony.service`;
8. waits for chronyd synchronization;
9. sends a real local NTP client request to `127.0.0.1:123`;
10. records post-cutover tracking, source, listener and package evidence.

Acceptance requires:

- `chrony.service` active;
- `systemd-timesyncd.service` inactive;
- chronyd synchronized to an external source;
- a valid NTP server-mode response on local UDP/123;
- stratum in the synchronized range 1–15;
- leap indicator not equal to unsynchronized (`3`);
- Time Authority dashboard on localhost port 8101 still healthy.

## Phase 3 — perimeter firewall publication

This is a separate privileged change.

The accepted Edge1 state on 2026-08-15 established `/etc/nftables.conf` as the boot-persistent nftables source, while the live `inet wwcxfw input` chain also contained runtime Big Bird blocklist/logging controls not represented in that base file. Therefore **do not reload the whole persistent file merely to publish NTP**; doing so would flush and reconstruct the live ruleset and could temporarily remove those runtime protections.

Use the guarded publication helper instead:

```bash
cd /opt/edge1-management-interface
sudo env \
  WWCX_NTP_APPROVE_PUBLIC_UDP123=YES \
  sh deploy/publish-time-authority-ntp-firewall-edge1.sh
```

The helper:

1. verifies `chrony.service` and the live UDP/123 listener;
2. requires `ntp.ww.cx` to resolve locally to the reviewed IPv4 address `89.147.109.253`;
3. backs up `/etc/nftables.conf` and the complete live ruleset under `/var/lib/wwcx-deployment-evidence/public-ntp-server/`;
4. adds the boot-persistent IPv4 rule `ip daddr 89.147.109.253 udp dport 123 accept comment "wwcx:public-ntp-v4"` immediately before the existing public-web rule;
5. syntax-checks the complete persistent nftables file without loading it;
6. inserts the equivalent rule into the live `inet wwcxfw input` chain immediately before the existing `wwcx:public-web` rule, preserving Big Bird runtime rules;
7. verifies both the live and persistent rules and reruns the local NTP packet smoke test;
8. records after-state evidence;
9. intentionally does **not** run `systemctl reload nftables` or `nft -f /etc/nftables.conf`.

The first public publication is IPv4-only. Although chronyd also owns `[::]:123`, do not open public IPv6 NTP until Edge1 IPv6 reachability is reviewed and a corresponding AAAA record is intentionally published.

Do not expose chronyc's monitoring/control port; the reviewed chrony configuration sets `cmdport 0` and local administration uses the Unix-domain command socket.

The command socket is intentionally privileged on the live Edge1 host. An ordinary `wwadmin` shell can therefore receive `506 Cannot talk to daemon` from `chronyc` even while `chronyd` is healthy and serving NTP. Use `sudo chronyc ...` for operational inspection rather than broadening the socket permissions merely for convenience.

After the firewall change, verify from a host outside the Edge1 network that UDP/123 receives a valid NTP response. Do not treat a local test as evidence of Internet reachability.

Rate limiting is configured in chronyd as an application-layer guard, but it does not replace network-level filtering, abuse monitoring, or provider policy.

## Phase 4 — DNS publication

This is a separate privileged change.

Create DNS for:

```text
ntp.ww.cx
```

Publish an `A` record to the reviewed Edge1 public IPv4 address. Publish an `AAAA` record only if Edge1 has reviewed, working IPv6 reachability and the firewall permits UDP/123 over IPv6.

`ntp.ww.cx` is the canonical NTP service name. `time.ww.cx` may be published as an alternate name to the same reviewed service address; it must not point to a different clock source unless that is intentionally designed and independently validated.

Do not publish an address merely because it appears on an interface; confirm it is the intended stable public service address.

After publication, verify authoritative and recursive DNS resolution before testing NTP by hostname.

## Phase 5 — external acceptance

From at least one network outside Edge1:

1. resolve `ntp.ww.cx`;
2. send an ordinary NTP client request to UDP/123;
3. verify server mode, synchronized leap state and sensible stratum;
4. compare returned time/offset against independent public references;
5. repeat from a second independent network if available;
6. confirm Edge1 client statistics and logs show the requests without excessive or unexpected traffic.

A Windows operator workstation can perform an outside-in query with:

```powershell
w32tm /stripchart /computer:ntp.ww.cx /samples:5 /dataonly
```

Repeat against `time.ww.cx` if the alias is intended to be supported publicly.

The existing Time Authority should continue reporting all configured upstreams. A shared-host or other independent observer can later be extended to probe `ntp.ww.cx` for availability and latency.

## Operational checks

On Edge1:

```bash
systemctl status chrony.service --no-pager
sudo chronyc tracking
sudo chronyc sources -v
sudo chronyc clients
sudo ss -H -lunp 'sport = :123'
sudo sh deploy/time-authority-ntp-server-edge1-smoke-test.sh
```

Healthy operation requires a synchronized source selection (`*` in `sudo chronyc sources -v`), normal leap status, bounded offsets and a valid local NTP response.

## Rollback

If rollback is required after firewall publication but before any chrony rollback, first use the evidence directory printed by the firewall helper to restore the saved persistent `/etc/nftables.conf` and remove only the live rule carrying comment `wwcx:public-ntp-v4`. Do not reload the full base file while runtime Big Bird rules are present unless their reconstruction path has been explicitly reviewed.

If rollback is required after publication of the service itself:

1. withdraw or block public UDP/123 first so clients do not receive an unstable service;
2. stop/disable `chrony.service`;
3. reinstall `systemd-timesyncd` if the package transition removed it;
4. restore any saved `/etc/systemd/timesyncd.conf`;
5. enable/start `systemd-timesyncd.service`;
6. verify the host is synchronized before considering the rollback complete;
7. preserve the failed chrony configuration, logs and evidence rather than deleting them;
8. withdraw `ntp.ww.cx` DNS if the endpoint will remain unavailable.

Do not run two independent daemons that both attempt to discipline the Edge1 system clock.

## NTS follow-up

NTS is a later phase, not a prerequisite for the initial NTP endpoint. Chrony supports NTS-KE with a certificate and key and normally uses TCP/4460 for key establishment. Enabling it requires a deliberate certificate lifecycle, NTS-specific firewall publication, renewal/restart procedure and external client validation.

## Production authorization state — 2026-08-15

Explicit production authorization has been granted for:

- replacing Edge1's active system clock daemon with chronyd;
- opening/publicly exposing UDP/123;
- creating/changing `ntp.ww.cx` DNS to the reviewed Edge1 service address.

Verified live state before firewall publication:

- `chrony.service` active and synchronized;
- `systemd-timesyncd` removed/inactive;
- chronyd listening on `0.0.0.0:123` and `[::]:123`;
- local packet-level NTP smoke test passing at synchronized stratum 4;
- Time Authority dashboard healthy on `127.0.0.1:8101`;
- `ntp.ww.cx`, `time.ww.cx`, and `edge1.ww.cx` resolving on Edge1 to `89.147.109.253`;
- persistent firewall source confirmed as `/etc/nftables.conf`;
- public IPv4 UDP/123 not yet accepted by the `inet wwcxfw input` chain.

Firewall publication and outside-in UDP/123 acceptance still require live evidence before the public NTP endpoint is considered fully accepted.

Not authorized or performed in this phase:

- enabling NTS/certificates or TCP/4460;
- publishing an IPv6 AAAA record or opening public IPv6 NTP;
- changing unrelated firewall, DNS, authentication, routing, or service policy.
