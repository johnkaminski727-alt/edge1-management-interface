# WW.CX Interconnect Monitoring and Evidence Controls

This document defines the read-only monitoring, evidence, and loopback-staging controls for the WW.CX SIP interconnect project. It does not authorize public SIP exposure, carrier routing, customer traffic, DNS, firewall, certificate, Asterisk, FreePBX, or production Kamailio changes.

## Scope

Covered components:

- `wwcx-numbering-node.service` on `127.0.0.1:8093`;
- staged Kamailio configuration restricted to `127.0.0.1:5061`;
- existing Asterisk and Big Bird health observations;
- repository validation and test results.

## Monitoring cadence

For staging, capture read-only health and listener evidence after every repository update, service restart, dataset import, or configuration validation. During an active staging session, repeat health checks at least every fifteen minutes and whenever an alert changes state.

Monitor:

- systemd active state;
- loopback listener address and port;
- `/healthz` response and latency;
- prefix and source counts;
- recent service journal errors;
- repository commit and working-tree cleanliness;
- validator and unit-test results.

## Alert thresholds

Treat the following as critical:

- service inactive or failed;
- listener absent;
- listener bound to a non-loopback address;
- health endpoint unavailable for more than twenty seconds after restart;
- unexpected source or prefix-count loss;
- validator or unit-test failure;
- secret or private-key detection in repository validation.

Treat isolated first-attempt connection refusal immediately after a controlled restart as a startup race only when the bounded readiness loop subsequently succeeds and the final listener remains loopback-only.

## Evidence bundle minimum

Each staging change must record, at minimum:

- UTC timestamp and operator;
- repository branch and commit SHA;
- `git status --short` output;
- staging-validator output;
- relevant unit-test output;
- `systemctl status` for affected services;
- listener snapshot for ports 5060, 5061, 5070, 8093, and other affected local ports;
- numbering health and source-list JSON;
- checksums for imported data or installed configuration;
- before-and-after observations;
- rollback action and its verification status;
- unresolved warnings, rejected rows, and known limitations.

Store evidence beneath the approved staging evidence directory. Do not commit secrets, private keys, customer records, message content, or unrestricted production logs to Git.

## Retention and integrity

Keep staging evidence long enough to support pull-request review, incident reconstruction, and the next acceptance checkpoint. Evidence files should be append-only or copied into a new timestamped directory rather than overwritten. Record SHA-256 values for source datasets and material staged configuration files.

## Loopback-only Kamailio staging gate

Kamailio may progress to a loopback-only staging exercise only after all of the following are true:

1. the repository worktree is clean;
2. staging validation and tests pass;
3. the proposed configuration binds only to `127.0.0.1:5061`;
4. public registration and public activation remain disabled;
5. no DNS, firewall, certificate, Asterisk, or FreePBX change is included;
6. rollback commands and evidence paths are prepared;
7. existing listeners are captured before the change;
8. syntax validation succeeds offline;
9. post-start listener and health checks are bounded by a readiness timeout;
10. any unsafe non-loopback listener causes immediate shutdown and rollback.

Loopback staging must not route customer traffic or connect to a carrier peer.

## Rollback expectations

A failed loopback staging attempt must:

- stop and disable the staged service;
- restore the previous unit or configuration when one existed;
- reload systemd only as required;
- verify the staged port is closed;
- verify existing Asterisk and numbering services retain their prior state;
- preserve failure journals and listener snapshots in the evidence bundle.

## No production activation

This document does not approve production activation. Public SIP listeners, carrier interconnects, certificates, DNS records, firewall policy, customer routing, emergency calling, number portability, STIR/SHAKEN, billing, authentication, or production Asterisk and FreePBX changes require a separate reviewed change and explicit approval at the applicable control boundary.
