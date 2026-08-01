# DTMF Provider-Public Evidence Live Acceptance — 2026-08-01

## Scope

This record accepts the authenticated, repository-only synchronization and validation of the privacy-minimized provider-public DTMF evidence package on Edge1.

The execution validated repository evidence and service continuity only. It did not activate, configure, test, or certify a carrier route and did not transmit DTMF.

## Execution identity

```text
host=edge1.ww.cx
principal=wwadmin
repository=/opt/edge1-management-interface
repository_branch=main
repository_head=ccb824c35cc54fa2d210ca7d03eb4cbb2ae39dc1
required_acceptance_commit=4207d39306960faa5532af23e50a2c43258f6d01
capability_merge=31fb4865f409bcf474ffd3d2c61a1727161cbe4c
```

The measured host head contained both required commits. The host checkout was clean before and after final validation.

## Protected evidence

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-evidence-repair-sync-20260801T194349Z
```

Final evidence-manifest SHA-256:

```text
09ea7aafdb274e50b948d31c5eb5304b3960e22abbcd79e23f5d5aec690e64a4
```

The final manifest verified every retained evidence file, including the original failed-heredoc output, corrected validation output, repository status records, ownership records, service snapshots, Git connectivity output, and final summary.

## Repository metadata repair

The preflight found exactly one incorrectly owned Git metadata entry:

```text
.git/index mode=0600 owner=root:root
```

The bounded repair:

- found no active Git lock files;
- found no unexpected third-party metadata ownership;
- changed only the root-owned Git metadata entry to `wwadmin:wwadmin`;
- retained index mode `0600`;
- preserved the index SHA-256 during the ownership repair;
- left the repository clean;
- left the index owned by `wwadmin:wwadmin` through finalization.

Accepted result:

```text
root_owned_git_metadata_repaired=1
index_owner=wwadmin:wwadmin
index_mode=600
index_stable_during_finalization=yes
repository_state=clean
```

This repair restored the repository ownership boundary. It did not rebuild, reset, or replace the index.

## Accepted DTMF evidence state

The following validations passed on Edge1:

```text
python3 tests/test_validate_dtmf_provider_evidence.py
python3 tests/validate_asterisk_dtmf_readiness_audit.py
python3 tools/telephony/validate_dtmf_provider_evidence.py config/telephony/dtmf-provider-evidence/provider-candidate-001-public-documentation.json
```

The corrected cross-record matrix verification also passed.

Accepted capability state:

```text
inband_status=documented
rfc4733_status=unknown
rfc4733_event_range=unknown
sip_info_status=unknown
extended_abcd_status=unknown
carrier_interoperability=partially-documented
live_test_authorized=false
```

`inband_status=documented` remains a narrow provider-documentation statement about an account-level automatic fallback. It does not establish codec survival, direction-specific applicability, endpoint or trunk behavior, SBC or media-relay behavior, or end-to-end carrier interoperability.

## Service continuity

The synchronization and validation recorded identical service state before and after:

```text
asterisk.service:
  ActiveState=active
  SubState=exited
  MainPID=0

wwcx-telephony-analytics.service:
  ActiveState=active
  SubState=running
  MainPID=1405962
```

Accepted outcome:

```text
service_state_changed=no
service_restart=none
runtime_change=none
```

No service command was issued by the acceptance procedure.

## Git connectivity note

`git fsck --connectivity-only` completed successfully. It reported three dangling tree objects. These objects were informational and did not indicate a connectivity failure, dirty worktree, or missing reachable object.

## Preserved validation correction

An initial inline Python verification attached its heredoc to `tee` instead of `python3`. The repository fast-forward and preceding validators had already completed successfully. The failed output was preserved as evidence, the heredoc was corrected, the targeted validators were repeated, and the final manifest was generated only after all logs were closed.

Accepted result:

```text
heredoc_failure_preserved=yes
heredoc_failure_corrected=yes
```

## Operational boundary

The accepted execution made no telephony or network-runtime change:

```text
call_originated=no
dtmf_transmitted=no
route_change=none
service_restart=none
runtime_change=none
live_test_authorized=false
```

No endpoint, trunk, route, DID, dialplan, carrier account, credential, listener, DNS record, firewall rule, certificate, emergency-calling path, or production traffic was changed.

## Decision

The provider-public DTMF evidence package is accepted on Edge1 at the measured repository head and protected evidence manifest above.

The only supported provider capability remains the documented account-level in-band fallback. RFC 4733 event range, SIP INFO, extended `A-D`, codec and transcoding behavior, exact directionality, carrier-route behavior, and end-to-end interoperability remain unknown or unverified. Any controlled live test remains separately gated and unauthorized by this acceptance.
