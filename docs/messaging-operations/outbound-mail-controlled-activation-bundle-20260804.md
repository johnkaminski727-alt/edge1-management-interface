# Controlled outbound-mail activation and rollback bundle

Date: 2026-08-04

## Objective

Generate the exact runtime configuration changes required for one SMTP pilot message, together with exact rollback copies, without installing files, reading credentials, contacting the provider, preparing a message, or sending mail.

Components:

- authorization schema: `schemas/messaging/outbound-mail-controlled-activation.schema.json`;
- bundle builder: `tools/messaging/build_outbound_mail_controlled_activation_bundle.py`;
- validator: `tests/validate_outbound_mail_controlled_activation_bundle.py`;
- workflow: `.github/workflows/validate-outbound-mail-controlled-activation-bundle.yml`.

The package is source-only. It is not a production activation wrapper.

## Repository baseline

The bundle depends on the reviewed delivery-event/suppression foundation and the reconciled runtime-policy, sender-profile, DMARC, and runtime-path contracts now present on `main`. Repository-wide validation must pass against that baseline before this package may merge.

## Required safe source state

The three runtime input documents must already be the strict runtime copies created by the disabled migration package. They must validate and remain preparation-only:

```text
preparation_api_enabled=true
gateway_enabled=false
gateway_deployment_authorized=false
external_delivery_authorized=false
send_endpoint_enabled=false
selected_provider=none
all_provider_profiles_enabled=false
policy_enabled=false
policy_deployment_authorized=false
smtp_cutover_authorized=false
policy_delivery_provider=disabled
policy_allow_prepare=true
policy_allow_external_submission=false
policy_allow_live_delivery=false
policy_mailing_address_is_approved_and_non_placeholder=true
identity_activation_authorized=false
live_sender_allowlist=[]
all_sender_profiles_outbound_enabled=false
system_noreply_outbound_enabled=false
```

Any other state fails closed. In particular, the builder does not choose or insert a mailing address; an approved non-placeholder address must already exist in the runtime policy and remains unchanged by activation.

The CLI refuses runtime inputs inside the Git checkout. Input files must be regular, operator-owned files with no symlink component and must not be group/world writable.

## Closed authorization record

The private authorization file must be mode `0600` or stricter, operator-owned, outside Git, and free of final-file or parent-directory symlinks. It includes:

- a unique authorization ID;
- the authorizing actor identifier;
- a durable authorization reference;
- issuance and expiry timestamps;
- exact SHA-256 values for the runtime gateway config, policy, identities, successful SMTP authentication-only canary, one owned pilot recipient, and one exact pilot payload;
- one exact sender-profile key and sender address.

It requires all of the following to be true:

- SMTP authentication verified;
- provider capability for the sender verified;
- public DKIM DNS verified;
- monitoring-only DMARC published;
- aggregate-report mailbox ready;
- bounce ingestion ready;
- complaint ingestion ready;
- suppression gate ready;
- owned recipient verified;
- activation authorized;
- one message authorized;
- rollback required.

The authorization must already be valid when evaluated. Its complete issued-to-expiry lifetime may not exceed two hours. It authorizes exactly one recipient and explicitly keeps bulk, commercial, regulatory, and emergency traffic false.

## Exact activation changes

The builder permits only six gateway changes:

```text
enabled=true
deployment_authorized=true
external_delivery_authorized=true
admin.send_endpoint_enabled=true
provider.selected=smtp_submission
provider.profiles.smtp_submission.enabled=true
```

It permits only six policy changes:

```text
enabled=true
deployment_authorized=true
smtp_cutover_authorized=true
delivery.provider=smtp_submission
delivery.allow_external_submission=true
delivery.allow_live_delivery=true
```

It permits only three identity-registry changes:

```text
outbound_activation_authorized=true
sender_profiles.<exact-key>.outbound_enabled=true
sender_selection.live_sender_allowlist=[<exact-address>]
```

The preparation API and `delivery.allow_prepare` remain enabled. The approved mailing address, every other policy setting, every other provider profile, every other sender profile, the system sender, and all identity mappings remain unchanged.

The generated documents are passed through the existing gateway, policy, and identity validators. A path-level diff must exactly match the allowlists above.

## Bundle contents

The output path must not already exist. Its parent must be operator-owned, must not be group/world writable, and may not contain a symlink. The builder creates:

```text
activated/outbound-mail-gateway-runtime.json
activated/outbound-mail-policy-runtime.json
activated/mail-identities-runtime.json
rollback/outbound-mail-gateway-runtime.json
rollback/outbound-mail-policy-runtime.json
rollback/mail-identities-runtime.json
manifest.json
```

The bundle root and section directories are mode `0700`; every file is created exclusively as mode `0600` with no symlink following.

The manifest does not inline runtime documents. It contains:

- authorization ID, actor, reference, issued time, expiry, and authorization SHA-256;
- exact source-runtime SHA-256 values;
- sender-address, recipient, payload, and SMTP-canary hashes;
- exact allowed change paths;
- SHA-256 for every activated and rollback file;
- explicit no-action safety markers.

## Offline command

```sh
python3 tools/messaging/build_outbound_mail_controlled_activation_bundle.py \
  --config /etc/wwcx/outbound-mail-gateway-runtime.json \
  --policy /etc/wwcx/outbound-mail-policy-runtime.json \
  --identities /etc/wwcx/mail-identities-runtime.json \
  --authorization /restricted/outbound-mail/pilot/activation-authorization.json \
  --output-dir /restricted/outbound-mail/pilot/activation-bundle
```

Runtime inputs, authorization, and output must remain outside Git. The output directory must be new; the builder refuses reuse rather than merging or overwriting staged evidence.

## Required execution wrapper

A later production wrapper must be separately designed and authorized. It must:

1. confirm the authorization hash, complete issued-to-expiry window, and every bundle/source hash immediately before use;
2. confirm the SMTP canary result and DNS/mailbox/bounce/complaint evidence are accepted;
3. verify suppression state for the exact recipient before activation;
4. back up the active runtime files independently of the bundle rollback copies;
5. atomically install all three activated documents;
6. restart and validate the gateway;
7. prove exactly one provider and one sender are ready;
8. accept only the exact recipient and payload hashes;
9. send at most one message;
10. capture provider acceptance and delivery evidence;
11. immediately reinstall the rollback documents and restart the safe-disabled gateway;
12. automatically roll back on any failure, timeout, hash mismatch, second request, or unexpected provider outcome.

The source builder does not implement these operational steps.

## Current blockers

The authorization record cannot truthfully be completed yet because the following live evidence is still missing:

- disabled runtime migration executed and accepted on Edge1;
- approved mailing address configured in the runtime policy;
- provider credential installed through an approved path;
- SMTP authentication-only canary executed successfully;
- exact sender capability verified at the provider;
- aggregate-report mailbox access and processing proven;
- monitoring-only DMARC authorized, published, and validated;
- bounce and complaint ingestion operating;
- exact owned recipient and pilot payload selected;
- explicit provider/sender/external-delivery/one-message authorization.

## Preserved boundaries

This package reads no credential, contacts no provider, installs no runtime file, restarts no service, changes no DNS, activates no live gateway, prepares no production message, and sends no mail.
