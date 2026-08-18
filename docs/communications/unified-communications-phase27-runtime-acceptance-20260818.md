# Unified Communications Phase 27 — MMS and Mail Runtime Acceptance

Date: 2026-08-18
Status: repository procedure only; **not executed in this connector session**

## Purpose

This runbook closes the remaining safe-scope runtime gaps without carrier traffic, live mail routing, quarantine release, DNS/firewall/authentication changes, or broad service restarts.

Phase 27 repository code adds:

- `app.trusted_scanner.ClamAVScanner`, a fixed `/usr/bin/clamscan` adapter behind `TrustedMediaScanner`;
- `scripts/private-quarantine-acceptance.py`, a local synthetic clean/EICAR/restart probe;
- `server/mail_correspondence_store.py`, a private SQLite message/thread store with preserved message/provider/thread IDs, bounded bodies, explicit provenance, and untrusted-content markers;
- repository validation for the synthetic Mail store and scanner adapter.

None of those additions proves that Edge1 currently has ClamAV installed, proves the private quarantine runtime is deployed, or makes the synthetic Mail store an authoritative native source.

## 1. Mandatory Edge1 preflight

Use the approved authenticated Edge1 operator path. Capture evidence outside the repository. Verify host/principal before any mutation.

```sh
set -eu
hostname -f
id
uname -a
free -h
swapon --show
systemctl status wwcx-messaging-gateway.service --no-pager
systemctl show wwcx-messaging-gateway.service -p User -p Group -p FragmentPath -p ExecStart -p EnvironmentFiles
systemctl cat wwcx-messaging-gateway.service
ss -lntup
command -v clamscan || true
clamscan --version 2>/dev/null || true
find /var/lib /opt -maxdepth 3 -type d \( -iname '*quarantine*' -o -iname '*clam*' \) -print 2>/dev/null
```

Stop MMS deployment if the authenticated path cannot verify the real service identity, host resource state, existing scanner/runtime, or rollback location. Do not invent a scanner.

## 2. Scanner decision gate

If `/usr/bin/clamscan` and a usable local signature database already exist, validate them in place. The Phase 27 adapter uses only local `clamscan`; it does not upload content and does not use a public listener.

If ClamAV is absent, package installation is a separate conditional Edge1 operation. Before installation, re-check memory/swap and package impact. The prior Phase 19 record showed about 1.5 GiB available memory with the configured 1 GiB swap nearly consumed, so avoid adding a resident `clamd` service merely for convenience. The repository adapter intentionally supports one-shot `clamscan` and does not require `clamd`.

Do not install a package if the available authenticated operator policy does not authorize package installation. In that case the exact blocker is: **install/approve a trusted local scanner runtime that provides `/usr/bin/clamscan` and local signatures, or explicitly approve an alternative narrow local scanner adapter.**

## 3. Private quarantine root

The intended root is:

`/var/lib/wwcx-messaging-gateway/private-mms-quarantine`

Resolve the actual Messaging service `User=` and `Group=` from systemd first. Create the root as that identity with mode `0700`; files created by `PrivateQuarantineStore` remain `0600`.

The root must not be under a web document root and must not be reverse-proxied or otherwise published.

Before mutation, capture a timestamped backup/evidence directory. If the root already exists, record ownership, mode, filesystem, free space, and a recursive metadata listing without copying private content into the repository.

## 4. Local synthetic MMS acceptance

Run the acceptance script as the actual Messaging service identity from the reviewed repository revision:

```sh
cd /opt/edge1-management-interface/services/wwcx-messaging-gateway
PYTHONPATH=. python3 scripts/private-quarantine-acceptance.py
```

Required results:

- synthetic clean artifact -> `scanned_clean_held`;
- generated EICAR test artifact -> `quarantined_malicious`;
- both remain `release_authorized=false`;
- restart/re-open of the store preserves held state;
- root/subdirectories remain no broader than `0700` and blobs no broader than `0600`.

Then separately test fail-closed paths using repository tests or a bounded local harness:

- scanner executable unavailable -> `quarantined_scanner_unavailable`;
- scanner timeout -> `quarantined_scan_timeout`;
- scanner non-verdict/error -> held error state;
- digest mismatch -> rejected;
- corrupted blob -> `quarantined_integrity_error`;
- storage/disk-full failure -> no success claim.

Do not use carrier media for acceptance.

## 5. Listener and adjacent-service verification

After any allowed deployment/restart, capture:

```sh
systemctl is-active wwcx-messaging-gateway.service
systemctl status wwcx-messaging-gateway.service --no-pager
ss -lntup
curl --fail --silent http://127.0.0.1:58080/healthz
curl --fail --silent http://127.0.0.1:58080/readyz
systemctl is-active wwcx-communications-workspace.service
systemctl is-active edge1-comms-relay.service
```

Verify no new ClamAV public TCP/UDP listener appears. A one-shot `clamscan` adapter should add no listener.

## 6. Mail correspondence source gate

The repository now contains a private correspondence store foundation, but `mail.correspondence.read` must remain disabled until a native source is explicitly selected and authorized.

Current repository facts do **not** prove provider-side mailbox provisioning or expose a body/thread-history store. The existing inbound hub remains disabled and its configuration does not persist raw messages or body previews.

A valid authoritative source must be one of:

- a reviewed local MTA/Mail Room intake that persists the actual received messages into the store; or
- an explicitly authorized native mailbox/provider connector that supplies stable message/thread IDs and bodies.

For any chosen source, preserve native Message-ID, provider message/thread IDs, explicit thread relationships, and provenance. Treat bodies as untrusted data. Do not allow message content to grant scopes, send authority, routing authority, or tool authority.

Use synthetic records first to validate the local store. Production routing remains disabled during this validation.

## 7. Rollback

MMS rollback is to stop using the new quarantine/scanner binding, restore the previous Messaging service configuration from the pre-change backup, restart only the Messaging Gateway if necessary, and retain quarantined private files held for review. Rollback must not release or delete quarantined content.

Mail rollback is to disconnect the experimental local store adapter while leaving production inbound routing unchanged/disabled. Do not delete a unique store without a separately authorized retention decision.

## 8. Completion evidence

Only after the live checks pass may the readiness record set MMS `security_quarantine` to `security_ready`. `fresh_edge1_runtime_verified` may become true only if the Mail correspondence gap is also genuinely resolved or explicitly closed with evidence. Neither flag authorizes production carrier/mail traffic or quarantine release.
