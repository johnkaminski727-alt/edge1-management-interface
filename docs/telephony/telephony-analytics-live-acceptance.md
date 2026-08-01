# Telephony Analytics Live Acceptance

## Purpose

Use the read-only live acceptance audit to verify that the existing telephony analytics API is active on Edge1, bound only to loopback port `8099`, exposes the three aggregate GET endpoints, rejects POST requests, returns privacy-minimized aggregate payloads, and is executing analytics source files that match the canonical repository.

The audit does not install, enable, start, stop, restart, or reload a service. It does not originate calls, transmit DTMF, query a CDR or FreePBX database, contact a carrier, change routing, inspect credentials, or expose the API publicly.

## Prerequisites

- authenticated shell on `edge1.ww.cx`;
- clean `main` checkout under `/opt/edge1-management-interface`;
- the analytics service already installed and active;
- `sudo` authority to create a protected evidence directory.

If the service is absent or inactive, the audit fails without changing it. Installation or service activation is a separate conditional operation.

The service may execute from the canonical checkout or another worktree, but acceptance requires the runtime `telephony_analytics_api.py` and `telephony_platform.py` SHA-256 hashes to match the canonical `main` checkout. A path difference alone is informational; a source-content difference prevents acceptance.

Although the audit itself runs as root for protected evidence, service metadata, and listener inspection, every Git command runs as the repository owner through `runuser`. The audit records `.git/index` ownership before and after Git inspection and fails if ownership no longer matches the repository owner. Root must not refresh or rewrite the repository index.

## Run

```bash
cd /opt/edge1-management-interface
TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVID="/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/$TS"

sudo sh tools/telephony/telephony_analytics_live_acceptance_audit.sh \
  --evidence-dir "$EVID"
```

## Accepted result

An accepted run ends with:

```text
warnings=0
failures=0
index_owner_preserved=yes
runtime_api_source_match=yes
runtime_platform_source_match=yes
listener_scope=loopback-only
api_mode=read-only
service_mutation=none
runtime_mutation=none
telephony_analytics_live_acceptance=passed
```

Warnings about hardening properties require review but do not themselves prove public exposure. Any failure, repository-index ownership mismatch, runtime-source hash mismatch, wildcard listener, non-405 POST response, malformed payload, privacy-scan finding, dirty repository, or unexpected service command prevents acceptance.

## Evidence

The protected directory contains:

- repository head, branch, and clean-tree status;
- repository and `.git/index` ownership before and after Git inspection;
- service state and selected hardening properties;
- parsed runtime analytics source paths, metadata, and SHA-256 hashes;
- runtime-to-canonical API and platform source comparison results;
- loopback listener evidence;
- HTTP status and JSON payloads for health, call summary, and interconnect summary;
- POST rejection evidence;
- payload-contract and privacy-scan results;
- repository asset metadata and hashes;
- SHA-256 evidence manifest.

Do not commit live evidence payloads to the public repository. Record only the protected path, manifest hash, accepted repository revision, runtime source paths, source-match decisions, warnings, failures, and high-level decision in a later acceptance record.
