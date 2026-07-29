# Security Observability and Spamhaus Live-State Handoff

Date: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Spamhaus verifier implementation merge: `e4002df7f7b6c523a76214804a3f5eb5b033561c`
Runtime wording-validation fix: `bfcbea8f971af864e5061824171da931225e1c26`

## Completed live work

- Network Defense and Security Correlation deployed and accepted.
- `edge1.ww.cx` HTTPS status pages and JSON feeds accepted.
- Accessible Suricata alert drill-down deployed.
- Last-known-good cache, normalized schema, and source collector enrichment deployed.
- All 22 alerts in the accepted enrichment run retained ports, application protocol, SID/GID/revision, and flow ID.
- Read-only Spamhaus live-state verifier implemented, validated, merged, and installed on Edge1.
- Initial verifier deployment attempt rolled back safely after a case-sensitive wording assertion.
- PR #119 repaired the assertion and both required workflows passed.
- The corrected installer completed successfully without rollback.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative evidence

```text
Security observability:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Failed Spamhaus verifier attempt, rolled back:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180002Z

Successful Spamhaus verifier deployment:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

## Spamhaus verifier live status

The final terminal excerpt confirmed:

```text
Spamhaus live-state observability deployment passed.
The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.
```

The installer verifies that Network Defense and the verifier snapshot agree and writes the exact result to:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

The exact state was not included in the pasted final lines. Read and record one of:

- `active_verified`;
- `partial`;
- `not_present`;
- `unavailable`.

Do not infer `active_verified` without the summary.

## Exact continuation command

```bash
cat /var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

After that value is recorded, the verifier phase is fully closed.

## Safety boundary

No Spamhaus list refresh, filter reload, nftables mutation, firewall mutation, Unbound or RPZ change, DNS-answer change, Fail2ban, proxy, routing, IDS-rule, reputation-list, authentication, or traffic-cutover change was performed. The verifier exposes no addresses, set elements, full ruleset, raw command output, credentials, or private keys.
