# Validation State

Last verified: 2026-08-01T21:03:42Z

## DTMF provider technical-response intake live acceptance

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against a clean `main` checkout at:

```text
faaf7b04c5fd3648b42b9266eb2cf5fea0f2a5a7
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-response-intake-sync-20260801T210156Z
```

Final evidence-manifest SHA-256:

```text
fe414802b5e52089673e3231693fbc1cb89c615c65e1450d670d77bcb03d7db4
```

Validated results:

- repository synchronized from `92cdccd4c7bda627bd7c5e8986bd0ed301c0ccb7` to `faaf7b04c5fd3648b42b9266eb2cf5fea0f2a5a7`;
- repository state was clean on branch `main`;
- Git index ownership remained `wwadmin:wwadmin`, mode `0600`, with no repair required;
- technical-response schema and pending example JSON were valid;
- all nine required response questions occurred exactly once;
- service-guarantee scope and pending-state gates were present;
- provider-evidence intake tests passed;
- provider technical-response intake tests passed;
- Asterisk DTMF readiness validation passed;
- pending technical-response validation passed;
- `response_state=pending`;
- `matrix_update_allowed=false`;
- `live_test_authorized=false`;
- no provider technical reply had been received;
- Asterisk and telephony-analytics service state did not change;
- no service restart, runtime change, call, DTMF transmission, route change, or carrier-matrix promotion occurred;
- the initial brittle documentation-string failure was retained and corrected with a structural nine-question validation;
- the final SHA-256 manifest verified every retained evidence file.

Acceptance record:

```text
docs/telephony/dtmf-provider-response-intake-edge1-acceptance-20260801.md
```

Tracker:

```text
.agent/dtmf-provider-response-tracker.md
```

The three dangling tree objects reported by `git fsck --connectivity-only` were informational; connectivity validation exited successfully.

## DTMF provider-public evidence live acceptance

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against a clean `main` checkout at:

```text
ccb824c35cc54fa2d210ca7d03eb4cbb2ae39dc1
```

Required repository history present:

```text
provider-public evidence capability merge: 31fb4865f409bcf474ffd3d2c61a1727161cbe4c
repository acceptance merge: 4207d39306960faa5532af23e50a2c43258f6d01
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-evidence-repair-sync-20260801T194349Z
```

Final evidence-manifest SHA-256:

```text
09ea7aafdb274e50b948d31c5eb5304b3960e22abbcd79e23f5d5aec690e64a4
```

Validated results:

- one root-owned Git metadata entry, `.git/index`, was repaired to `wwadmin:wwadmin`;
- index mode remained `0600` and its contents were preserved during the ownership repair;
- repository state was clean;
- DTMF provider-evidence intake tests passed;
- Asterisk DTMF readiness validation passed;
- the provider-public evidence record passed validation;
- matrix-to-evidence cross-record validation passed;
- in-band fallback is `documented` with no codec constraint;
- RFC 4733 and its event range remain `unknown`;
- SIP INFO and extended `A-D` remain `unknown`;
- carrier interoperability remains `partially-documented` and end-to-end behavior remains unverified;
- live-test authorization remains false;
- Asterisk and telephony-analytics service state did not change;
- no service restart, runtime change, call, DTMF transmission, or route change occurred;
- the initial failed-heredoc output was retained and the corrected validation completed successfully;
- the final SHA-256 manifest verified every retained evidence file.

Acceptance record:

```text
docs/telephony/dtmf-provider-public-evidence-live-acceptance-20260801.md
```

The three dangling tree objects reported by `git fsck --connectivity-only` were informational; connectivity validation exited successfully.
