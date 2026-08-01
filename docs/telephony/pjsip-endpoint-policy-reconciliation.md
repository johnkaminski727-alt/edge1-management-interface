# Asterisk PJSIP Endpoint Policy Reconciliation

## Purpose

This audit reconciles runtime PJSIP object visibility with generated `pjsip*.conf` endpoint policy on Edge1. It is designed to explain whether the absence or presence of runtime endpoints agrees with the generated Asterisk configuration without exposing endpoint identities or reading credential-bearing FreePBX sources.

**No channel, call, DTMF transmission, SIP request, database query, configuration change, service action, endpoint change, trunk change, route change, or carrier action is performed.**

The audit is implemented at:

```text
tools/telephony/asterisk_pjsip_endpoint_policy_reconciliation.sh
```

Protected evidence is written below:

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/<UTC timestamp>
```

## Evidence layers

### Runtime PJSIP object visibility

The audit runs only these read-only Asterisk CLI commands:

- `core show version`;
- `core show uptime`;
- `core show channels count`;
- `module show like chan_pjsip`;
- `module show like res_pjsip`;
- `pjsip show endpoints`;
- `pjsip show aors`;
- `pjsip show contacts`;
- `pjsip show transports`.

Runtime output is sanitized before it is retained. Endpoint, AOR, contact, transport, channel, SIP URI, address, long-number, email, and credential-like values are redacted. The evidence record retains object counts and sanitized command output rather than endpoint identities.

### Generated `pjsip*.conf` endpoint policy

The audit inspects `/etc/asterisk/pjsip*.conf` using a whitelist parser. For explicit `type=endpoint` sections, it records only:

- a per-file sequential endpoint index;
- `dtmf_mode`, or `implicit-rfc4733` when the field is absent;
- `direct_media`, or `implicit-default` when the field is absent;
- whether `transport`, `auth`, `outbound_auth`, `aors`, and `context` are set;
- counts of `allow` and `disallow` entries.

Section names and field values that identify endpoints, trunks, users, contacts, contexts, authentication objects, or routes are not retained. Configuration files are hashed and their ownership, mode, and size are recorded for auditability.

The parser reports explicit endpoint-policy records. It does not claim to fully resolve inherited templates or database-backed configuration that is not rendered into the inspected files.

### FreePBX source boundary

The audit confirms whether `fwconsole` is present and records its sanitized version output. It records metadata and SHA-256 hashes for `/etc/freepbx.conf` and `/etc/amportal.conf` when present.

The audit does not read `/etc/freepbx.conf`, does not read `/etc/amportal.conf`, and does not query the FreePBX database. Credential values are not requested, printed, stored, or inferred.

## Privacy and evidence boundary

Endpoint identifiers are not retained. The audit stores only sanitized runtime output, aggregate object counts, whitelisted policy flags, configuration metadata, hashes, warnings, decisions, and an evidence manifest.

The audit must not:

- display raw endpoint, AOR, contact, transport, SIP URI, telephone-number, username, password, secret, or authentication values;
- source or print FreePBX credential files;
- invoke MySQL or MariaDB clients;
- reload or restart Asterisk, FreePBX, Kamailio, MariaDB, or any telephony service;
- originate a call or channel;
- transmit DTMF, RTP telephone events, SIP INFO, or in-band audio;
- alter endpoint, trunk, dialplan, transport, codec, route, carrier, firewall, certificate, package, or emergency-calling configuration.

## Repository validation

From the repository root:

```bash
python3 tests/validate_asterisk_pjsip_endpoint_policy_reconciliation.py
```

The validator checks shell syntax, the exact Asterisk CLI allowlist, identifier redaction, the metadata-only FreePBX boundary, evidence-path restrictions, and the absence of live or mutating behavior.

## Authenticated Edge1 execution

Use a clean, synchronized `main` checkout:

```bash
cd /opt/edge1-management-interface
set -Eeuo pipefail
umask 077

test "$(hostname -f)" = "edge1.ww.cx"
test "$(id -un)" = "wwadmin"
test -z "$(git status --porcelain)"

TS=$(date -u +%Y%m%dT%H%M%SZ)
EVID="/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/$TS"

sudo install -d -m 0700 "$EVID"

set +e
sudo sh tools/telephony/asterisk_pjsip_endpoint_policy_reconciliation.sh \
  --expected-host edge1.ww.cx \
  --evidence-dir "$EVID" 2>&1 | \
  sudo tee "$EVID/operator-console.txt"
RC=${PIPESTATUS[0]}
set -e

sudo sha256sum "$EVID/operator-console.txt" | \
  sudo tee "$EVID/operator-console.txt.sha256"

printf 'audit_exit_code=%s\n' "$RC"
printf 'evidence=%s\n' "$EVID"
exit "$RC"
```

Expected terminal states are:

```text
Audit state: READ-ONLY RECONCILIATION COMPLETE
```

or:

```text
Audit state: READ-ONLY RECONCILIATION COMPLETE WITH WARNINGS
```

A warning is expected when runtime endpoints and generated endpoint-policy records are both absent, when counts differ, when a runtime count cannot be parsed, when `fwconsole` is absent, or when an unrecognized DTMF mode is encountered.

## Interpretation

A result showing zero runtime endpoints and zero generated explicit endpoint-policy records supports the conclusion that no active endpoint policy was observed in either inspected layer. It does not prove that no endpoint data exists in every FreePBX database table, module, backup, inactive configuration source, or external provisioning system.

A count mismatch indicates a reconciliation gap. It does not authorize a reload, restart, regeneration, database query, endpoint edit, or trunk change.

Even when runtime and generated counts match, carrier interoperability remains `unverified`. Provider documentation or a separate controlled live test is required before recording support for RFC 4733 negotiation, SIP INFO, in-band DTMF, ordinary digits, extended `A-D`, codec survival, transcoding behavior, or an end-to-end route.

## Decision boundary

Permitted after review:

- accept a consistent zero-endpoint or nonzero-endpoint observation;
- identify which generated files contain explicit endpoint policy;
- record aggregate `dtmf_mode` distribution;
- plan a narrower metadata-only or separately authorized database reconciliation if the generated layer is insufficient.

Not authorized by this audit:

- reading or exporting credential-bearing configuration;
- querying or changing the FreePBX database;
- endpoint, trunk, transport, dialplan, route, codec, firewall, or carrier changes;
- Asterisk or FreePBX reload/restart;
- production or test calls;
- DTMF transmission;
- emergency-calling testing;
- carrier, regulatory, certification, NPAS, EAS, or Alert Ready claims.
