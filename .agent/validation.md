# Validation State

Last verified: 2026-08-01T19:48:46Z

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
