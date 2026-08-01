# cPanel Mail-Routing Mode Capture

## Purpose

The shared-hosting mailbox capture records mailboxes, forwarders, filters, autoresponders, and default-address behavior, but cPanel's email-routing mode is a separate provider setting.

cPanel documents `Email::getmxcheck` as the read-only function that returns one of these provider values:

- `auto`;
- `local`;
- `remote`;
- `secondary`.

The function belongs to deprecated cPanel API 2. cPanel currently documents that no equivalent UAPI function exists. This repository therefore uses it only for a narrowly scoped, read-only evidence supplement.

No routing mode is changed by this procedure.

## Safety boundary

The capture script:

- calls only `Email::getmxcheck`;
- performs a read-only authentication probe before creating evidence;
- uses a short-lived cPanel API token supplied through a secure PowerShell prompt;
- never writes the token, authorization header, password, session URL, or cookie to disk;
- writes into an atomic staging directory and removes it after failure;
- refuses output inside a Git working tree;
- records only raw read-only responses, restricted metadata, and SHA-256 checksums;
- does not call `setmxcheck`, `setalwaysaccept`, or any MX, mailbox, forwarding, filter, DNS, or authentication mutation.

Raw evidence remains restricted operational metadata.

## Capture from Windows PowerShell

Create a short-lived cPanel API token in **Manage API Tokens**. Do not paste it into chat, a script file, command history, or a document.

Run from a checkout containing the current branch:

```powershell
$Repo = 'C:\path\to\edge1-management-interface'
$Timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$Evidence = Join-Path $env:USERPROFILE `
    "Documents\WWCX\Private Mail Evidence\business159-routing-$Timestamp"

& "$Repo\tools\messaging\capture_cpanel_mail_routing.ps1" `
    -Domain creekco.ca, scgardens.ca, omegafx.com `
    -OutputDirectory $Evidence
```

The script prompts securely for the temporary token and creates:

```text
getmxcheck-creekco_ca.json
getmxcheck-scgardens_ca.json
getmxcheck-omegafx_com.json
metadata.json
SHA256SUMS
```

Revoke the temporary token immediately after successful capture.

## Offline normalization

Normalize the routing evidence into a separate provider inventory:

```powershell
$RoutingInventory = Join-Path $Evidence 'namecheap-shared-hosting-routing.normalized.json'

python "$Repo\tools\messaging\normalize_cpanel_mail_routing.py" `
    --evidence-dir $Evidence `
    --output $RoutingInventory
```

The normalized inventory contains no mailbox objects. It contains only `domain_routing` entries and can be supplied alongside the mailbox inventory:

```powershell
python "$Repo\tools\messaging\reconcile_mail_provider_objects.py" `
    --inventory 'C:\restricted\namecheap-shared-hosting.normalized.json' `
    --inventory $RoutingInventory `
    --output 'C:\restricted\shared-hosting-reconciliation.json'
```

Mode mapping is conservative:

- `auto` becomes `automatic` and remains a reconciliation warning;
- `local` becomes `local`;
- `remote` becomes `remote`;
- `secondary` becomes `unknown` because the current provider-object contract does not treat a secondary exchanger as an accepted local or remote terminal state.

## Acceptance

The routing evidence is accepted only when:

1. every expected JSON file is covered by `SHA256SUMS`;
2. every API response reports success;
3. each returned domain matches the requested domain;
4. each returned mode is one of cPanel's documented values;
5. the temporary token is revoked;
6. the normalized inventory and reconciliation report remain outside Git;
7. no provider mutation occurred.

A known routing mode closes an evidence gap. It does not authorize changing email routing, MX records, DNS, mailboxes, aliases, forwarders, or production traffic.

## Official references

- cPanel API 2 `Email::getmxcheck`: `https://api.docs.cpanel.net/cpanel-api-2/cpanel-api-2-modules-email/cpanel-api-2-functions-email-getmxcheck`
- cPanel API 2 guide and port requirements: `https://api.docs.cpanel.net/cpanel-api-2`
- cPanel API-token authentication: `https://api.docs.cpanel.net/cpanel/tokens`
