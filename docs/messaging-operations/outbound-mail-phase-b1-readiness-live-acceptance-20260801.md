# Outbound Mail Phase B1 Readiness — Live Acceptance

Date: 2026-08-01  
Host: `edge1.ww.cx`  
Operator session: authenticated SSH as `wwadmin`  
Audit principal: `root` through `sudo`  
Repository: `johnkaminski727-alt/edge1-management-interface`

## Accepted result

The read-only Phase B1 readiness audit completed successfully at `2026-08-01T17:45:48Z`.

The accepted result is:

```text
readiness_state=ready_for_explicit_b1_authorization
```

This means the live disabled Phase A foundation satisfied the measured prerequisites for a later, separately authorized B1 installation. It does not authorize secret generation, authentication activation, external exposure, or mail delivery.

## Repository evidence

```text
branch=main
head_commit=bf7c9186f416d69e20f289a68c7a45314baae6b8
phase_b_package_commit=c55059c2d0230ea273709bbb5a4169b00bb226c1
```

The audit verified a clean authoritative branch, Phase B package ancestry, and no changes to the protected outbound-mail deployment files after the approved package commit.

## Live safety checks

The passing audit establishes that:

- the Phase A gateway service remained active and enabled under the expected service account;
- port `8104` remained loopback-only at `127.0.0.1:8104`;
- gateway health and disabled-state status checks succeeded;
- the unsigned preparation API request remained denied with HTTP `403`;
- the send probe remained denied with HTTP `403`;
- the committed gateway, policy, providers, identities, and delivery controls remained disabled;
- no B1 runtime overlay or production secret file was present;
- no configured reverse-proxy path exposed the preparation API;
- the evidence bundle was written under the protected deployment-evidence tree with a SHA-256 inventory.

## Mutation record

The audit reported:

```text
secret_generated=no
secret_read=no
runtime_files_modified=no
service_restarted=no
proxy_modified=no
dns_modified=no
firewall_modified=no
message_sent=no
```

No credential value was generated, displayed, read, transmitted, copied into evidence, or committed to the repository.

## Protected evidence

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z
```

The evidence directory is authoritative for the live audit result. This repository record stores only the verified summary and path, not protected runtime contents.

## Activation state after acceptance

- Phase A disabled foundation: live and accepted;
- Phase B package: merged and CI-validated;
- B1 readiness: accepted as `ready_for_explicit_b1_authorization`;
- B1 runtime overlay: not installed;
- production HMAC secret: not generated or installed;
- B2 proxy and certificate: not installed;
- DNS and firewall: unchanged;
- website preparation bridge: inactive;
- public correspondence route: inactive;
- retention apply and scheduling: inactive;
- provider and sender activation: inactive;
- production mail delivery: inactive.

## Next approval boundary

The next privileged action requires explicit authorization materially equivalent to:

> Authorize generation of a new production HMAC secret on Edge1 and installation of Phase B1 loopback preparation authentication only. Do not install B2, a certificate, DNS or firewall changes, the website bridge, public records, retention, provider credentials, sender activation, or mail delivery.

Until that authorization is recorded, stop before generating or installing secret material, installing the B1 runtime overlay, or restarting the gateway for B1 activation.
