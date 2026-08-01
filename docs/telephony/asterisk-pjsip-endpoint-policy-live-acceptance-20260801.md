# Asterisk PJSIP Endpoint Policy Live Acceptance — 2026-08-01

## Authoritative execution record

Authenticated operator execution occurred on `edge1.ww.cx` as `wwadmin` with bounded `sudo` elevation. The repository was synchronized to clean `main` at:

```text
6906d1bb7f5aa517c249bf893ab23675b63f062f
```

The read-only reconciliation implementation was merged through PR #202 as the same commit.

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/20260801T085814Z
```

Primary console record:

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/20260801T085814Z/operator-console.txt
SHA-256: fa370b2a9fa085b7301fcf64c54326b1362321342873610e94710d9588bf3a26
```

Evidence manifest:

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/20260801T085814Z/evidence-files.sha256
SHA-256: c9183f3e7ff838dc2beae038c2a206b408114ed64eea0787b2b4195a9582623d
```

The audit exited `0`, reported two warnings and zero failures, and ended in:

```text
Audit state: READ-ONLY RECONCILIATION COMPLETE WITH WARNINGS
```

## Accepted observations

- Asterisk `22.10.1` was running.
- System uptime and time since last reload were approximately nine hours and twenty minutes.
- Zero active channels, zero active calls, and zero processed calls were observed.
- The PJSIP runtime registry exposed zero endpoints, zero AORs, zero contacts, and zero transports.
- The generated PJSIP include graph was present and referenced the expected endpoint, AOR, authentication, registration, identification, and transport files.
- Twenty-three `/etc/asterisk/pjsip*.conf` files were inspected using the whitelist parser.
- Zero explicit `type=endpoint` policy records were found in the inspected generated files.
- All generated DTMF-mode counts were zero because no explicit endpoint-policy records existed.
- Runtime and generated endpoint counts matched at zero.
- The reconciliation state was `no-runtime-or-generated-endpoints-observed`.
- FreePBX CLI `17.0.30` was present.
- `/etc/freepbx.conf` and `/etc/amportal.conf` metadata and hashes were recorded without reading their contents.
- The FreePBX database was not queried.
- Endpoint identifiers and credential values were not retained.

## Warning classification

The two warnings are accepted informational findings:

1. the PJSIP runtime registry exposes no endpoints;
2. generated PJSIP configuration contains no explicit endpoint-policy records.

These warnings are mutually consistent. They do not indicate a runtime/generated mismatch.

## Decision on further database inspection

A FreePBX database count is not required for the current active-configuration conclusion. The runtime registry and the complete inspected generated configuration layer both show zero active endpoint-policy records. Querying credential-bearing database sources would add access and privacy risk without changing that verified active-state result.

Dormant, historical, backup, module-private, or externally provisioned endpoint data remains outside this acceptance and is not claimed absent. A future metadata-only database audit would require a separately reviewed design and a demonstrated operational need.

## Accepted capability decision

```text
runtime_endpoint_count=0
runtime_aor_count=0
runtime_contact_count=0
runtime_transport_count=0
pjsip_config_files=23
generated_endpoint_policy_count=0
endpoint_count_comparison=counts-match
reconciliation_state=no-runtime-or-generated-endpoints-observed
freepbx_cli=present
freepbx_source_content=not_read
freepbx_database_content=not_queried
endpoint_identifiers_retained=no
credential_values_read=no
database_query_performed=no
carrier_interconnect_capability=unverified
live_sdp_negotiation=not_tested
live_dtmf_receive_path=not_tested
live_dtmf_send_path=not_tested
call_originated=no
channel_created=no
tone_transmitted=no
runtime_mutation=none
```

## Change and safety verification

- Repository state was clean before and after execution.
- No channel or call was created.
- No DTMF digit, RTP telephone event, SIP INFO request, in-band tone, or media was transmitted.
- No database query was performed.
- No Asterisk, FreePBX, Kamailio, MariaDB, endpoint, trunk, transport, dialplan, route, carrier, listener, service, module, firewall, package, certificate, or emergency-calling configuration changed.
- No rollback was needed because the audit was read-only and completed successfully.

## Decision boundary

Accepted:

- the active PJSIP runtime registry currently has no endpoint, AOR, contact, or transport objects;
- the inspected generated PJSIP configuration currently contains no explicit endpoint-policy records;
- runtime and generated endpoint counts consistently match at zero;
- the protected evidence and hashes above;
- deferral of database inspection unless a narrower operational need is established.

Not proven, authorized, or performed:

- absence of dormant or historical endpoint data in every FreePBX database table, backup, inactive source, or external provisioning system;
- live endpoint, trunk, carrier, SBC, or gateway interoperability;
- SDP negotiation, SIP INFO, in-band DTMF, codec, transcoding, or end-to-end behavior;
- production calls or test calls;
- emergency-calling path testing;
- endpoint, trunk, transport, route, or carrier changes;
- any certification, conformance, regulatory, NPAS, EAS, or Alert Ready claim.

## Next gate

The next safe telephony increment is documentation-only carrier capability intake. The sanitized carrier matrix may be populated only from reliable provider documentation, with unsupported or undocumented capabilities left `unknown`. Every live path remains `unverified` until separately authorized controlled evidence exists.
