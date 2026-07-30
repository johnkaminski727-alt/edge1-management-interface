# Edge1 Public Access Boundary Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Design merge: `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`  
Design PR: `#130`

## Verified live baseline

- Network Defense and Security Correlation are deployed and accepted.
- Suricata drill-down, last-known-good caching, normalization, and enrichment are live.
- Spamhaus is `active_verified`; Fail2ban is `active_observed`; nftables is `ruleset_observed`.
- Network Defense remains `limited`, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls remain unchanged.

## Repository-complete boundary decision

The current `/edge1-status/` tree combines a public-facing dashboard with detailed operational artifacts. PR #130 records that the unchanged mixed tree is not the safest long-term boundary.

Target public design:

```text
/edge1-status/
/edge1-status/public/status.json
```

The public contract permits only aggregate states, bounded counts, coarse freshness, maintenance notices, and read-only/no-traffic-change flags.

Future restricted placeholder:

```text
/edge1-ops/
```

Detailed security, topology, Git/change, automation, incident, communications, financial, and report/evidence data is restricted. Browser authentication and proxy routing require separate exact authorization. Proposed scopes are `edge1.status.detail.read` and separately `security.suricata.history.read`.

## Accepted controls

- explicit public allowlist, never arbitrary redaction;
- no anonymous fallback for restricted detail;
- audited and rate-limited restricted reads;
- server-side `Cache-Control: no-store, max-age=0`;
- restrictive CSP, no-referrer, and nosniff;
- no wildcard CORS or directory listing;
- no new listener;
- unchanged TLS identity and HTTP-to-HTTPS redirect;
- rollback restores previous vhost/aliases/static files and preserves operational data.

## Validation and merge

Exact design head: `24eacfa1388b9c3b9bafb1c8f880af1da3355aea`

- `Validate repository` run 618: success.
- `Edge1 Operator Validation` run 450: success.
- PR #130 was mergeable and zero commits behind `main`.
- No unresolved review threads existed.
- Scope contained policy, schema, design, register, static validation, and `.agent` records only.
- Merged as `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`.

## Live evidence gap

No authenticated Edge1 shell is available. Complete current Apache authorization, aliases, headers, CORS, directory listing, and extra route/filesystem state remain unknown until read-only Phase 0 evidence is captured.

## Next safe repository sequence

Build Phase 1 without routing or publishing:

1. define `wwcx.edge1-public-status.v1`;
2. implement an allowlist-only summary exporter;
3. add hostile fixtures containing forbidden fields and prove none propagate;
4. add a static landing page that consumes only the minimized summary;
5. default output to a repository build/test path, never `/var/www`;
6. add validation proving no deploy script, systemd unit, Apache change, or live access change;
7. pass exact-head CI and merge review.

## Explicitly not implemented

- minimized public exporter/page;
- authenticated operations UI or browser session;
- proxy/vhost/alias/header changes;
- API scope activation;
- publication/removal under `/var/www`;
- service reload;
- Edge1 deployment or public cutover.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication boundary, certificate, listener, public access, published file, deletion, or production traffic is changed or authorized.
