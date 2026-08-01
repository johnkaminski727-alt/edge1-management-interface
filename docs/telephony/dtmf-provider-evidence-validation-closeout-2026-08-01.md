# Edge1 DTMF Provider-Evidence Validation Closeout

Date: 2026-08-01  
Host: `edge1.ww.cx`  
Principal: `wwadmin`  
Repository: `/opt/edge1-management-interface`  
Validated repository commit: `9dea2bb90d697225cb8570f6f75acb78dffb29cb`

## Scope

This record closes the Edge1 repository synchronization, repository-index metadata acceptance, and targeted validation of the privacy-safe DTMF provider-evidence scanner. It records repository and test evidence only. It does not record private provider material and does not authorize a live call, DTMF transmission, carrier change, service restart, route activation, or production traffic.

## Authenticated host validation

The operator executed the final validation on `edge1.ww.cx` as `wwadmin` against the canonical checkout at `/opt/edge1-management-interface`.

Preflight confirmed:

- expected host and principal;
- active branch `main`;
- existing evidence directory;
- repository index owned by `wwadmin:wwadmin`;
- repository index mode `0600`;
- repository state clean before synchronization.

The repository fast-forwarded from `af3f576` to the required merge commit `9dea2bb90d697225cb8570f6f75acb78dffb29cb`.

## Validated change

Commit `9dea2bb90d697225cb8570f6f75acb78dffb29cb` is the merge of PR #208, **Fix ISO date handling in DTMF evidence scanner**.

The scanner now masks only validated ISO calendar-date and UTC timestamp tokens before long-number scanning. Regression coverage confirms that:

- valid ISO dates and UTC timestamps are accepted in sanitized evidence summaries;
- account or personal numbers adjacent to valid timestamps remain rejected;
- invalid date-shaped numeric strings remain rejected;
- numeric strings with embedded date-shaped portions remain rejected.

## Validation results

The following targeted checks passed:

```text
DTMF provider evidence intake tests passed
DTMF provider evidence validation passed: examples/telephony/dtmf-provider-evidence.example.json
provider_id=provider-candidate-001
route_id=route-candidate-001
review_state=unverified
matrix_eligible=false
carrier_interoperability=unverified
live_test_authorized=false
```

Post-synchronization checks confirmed:

- repository head exactly matched `9dea2bb90d697225cb8570f6f75acb78dffb29cb`;
- scanner fix present;
- temporary probe files absent;
- repository worktree clean;
- repository index remained owned by `wwadmin:wwadmin` with mode `0600`;
- no service restart occurred;
- no runtime change occurred.

## Evidence retention

Authoritative host evidence directory:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z
```

Primary validation log:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/validation-final.log
```

Evidence checksum manifest:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/evidence-files.sha256
```

Observed SHA-256 for the evidence checksum manifest:

```text
7b103a0b9ea219a3037d167d8fe105d8a8d007b90c9d3759ca665283bf17fa5d
```

The host-local evidence directory remains authoritative. This repository record contains only sanitized operational metadata and does not copy provider evidence, credentials, account identifiers, telephone numbers, private endpoints, or customer material into Git.

## Final disposition

The repository metadata repair and DTMF scanner validation are complete.

The operational provider capability gate remains closed:

- carrier matrix entries: zero;
- carrier interoperability: unverified;
- matrix eligibility: false for the example record;
- live-test authorization: false;
- service restart: none;
- runtime change: none.

Further progress requires provider-specific retained technical evidence for the exact route and direction, or a separately authorized controlled test. General Asterisk or FreePBX suitability is not sufficient evidence for RFC 4733, SIP INFO, in-band DTMF, event-range, codec, SBC, or extended `A-D` interoperability claims.
