# Outbound mail Phase B1 read-only readiness audit

Date: 2026-08-01  
Phase B package: `c55059c2d0230ea273709bbb5a4169b00bb226c1`

## Purpose

Measure the live Phase A service before any production HMAC secret is generated or installed.

The audit is read-only with respect to repository, service, runtime configuration, proxy, DNS, firewall, and mail state. It writes only a restricted evidence bundle.

It does not authorize or perform B1 activation.

## Known accepted Phase A evidence

The disabled gateway was accepted from authenticated Edge1 operator evidence at:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-a/20260801T064714Z
```

The accepted baseline included:

- `wwcx-outbound-mail-gateway.service` active and enabled;
- service principal `wwcx-mail-gateway`;
- loopback listener `127.0.0.1:8104`;
- HTTP 200 health and status;
- HTTP 403 preparation API and send probes;
- no runtime HMAC secret;
- no enabled provider or sender;
- no external preparation, public route, retention apply, or mail delivery.

## Execute through an authenticated Edge1 path

```sh
cd /opt/edge1-management-interface

git fetch --prune origin main
git pull --ff-only origin main
git status --short --branch

sudo sh tools/messaging/outbound_mail_phase_b1_readiness_audit.sh
```

Optional exact-package override is available only for a separately reviewed replacement package:

```sh
sudo PHASE_B_PACKAGE_COMMIT=c55059c2d0230ea273709bbb5a4169b00bb226c1 \
  sh tools/messaging/outbound_mail_phase_b1_readiness_audit.sh
```

Do not bypass a package-ancestry or protected-file-change failure. Review and revalidate the changed files instead.

## Evidence output

Default evidence root:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/<UTC timestamp>/
```

Expected files include:

- `summary.txt`;
- `failures.txt`;
- `git-status.txt` and `git-head.txt`;
- `protected-paths.txt` and `protected-path-changes.txt`;
- `committed-safety.json`;
- `service-status.txt` and `service-properties.txt`;
- `listeners.txt`;
- `health.json` and `status.json`;
- `unsigned-api-status.json` and `send-probe.json`;
- `runtime-file-metadata.tsv`;
- `proxy-path-matches.txt`;
- `SHA256SUMS`.

The audit records only presence, type, owner UID, mode, and byte count for possible B1 runtime files. It does not read `/etc/wwcx/outbound-mail-gateway.env` or any secret value.

## Pass conditions

A passing result requires:

- host `edge1.ww.cx`;
- root execution;
- clean `main` checkout;
- Phase B package commit present in history;
- no protected outbound-mail file changes after that package;
- committed gateway, policy, provider, and identities still disabled;
- service active and enabled as `wwcx-mail-gateway`;
- port 8104 observed on loopback;
- health and status HTTP 200;
- unsigned preparation API HTTP 403;
- send probe HTTP 403;
- runtime status reports no secret, no live provider, and no live sender;
- B1 runtime overlay files absent;
- no web-server configuration references the preparation API path.

`readiness_state=ready_for_explicit_b1_authorization` is evidence of readiness only. It is not an activation instruction.

## Failure handling

When the script exits non-zero:

1. Preserve the evidence directory.
2. Do not generate or install a secret.
3. Do not restart the service.
4. Do not install B2 or alter a reverse proxy.
5. Review `failures.txt` and the smallest supporting evidence file.
6. Repair only through a separately reviewed, reversible repository or operational change.
7. Re-run the read-only audit after the repair.

## Explicit B1 authorization

After a passing live audit, the next privileged action still requires an explicit instruction materially equivalent to:

> Authorize generation of a new production HMAC secret on Edge1 and installation of Phase B1 loopback preparation authentication only. Do not install B2, a certificate, DNS or firewall changes, the website bridge, public records, retention, provider credentials, sender activation, or mail delivery.

Without that authorization, do not generate, display, transmit, rotate, or install secret material and do not run the B1 installer.

## Separate later gates

B1 authorization does not authorize:

- **B2** certificate, hostname, reverse proxy, source network, firewall, or external canary;
- website bridge activation;
- public correspondence records;
- telemetry retention apply or scheduling;
- provider credentials or DNS mail authentication;
- sender activation;
- production mail delivery.

No production secret exists as part of this audit package, and no mail delivery is enabled.
