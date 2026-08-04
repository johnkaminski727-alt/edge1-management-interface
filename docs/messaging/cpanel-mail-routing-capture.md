# cPanel mail-routing evidence capture

## Purpose

Capture the hosting-side mail-routing mode for managed shared-hosting domains without changing mail routing, MX records, mailboxes, aliases, forwarders, filters, or DNS. The routing result supplements the existing cPanel UAPI mailbox inventory and is normalized into a routing-only `wwcx.provider-mail-objects.v1` record.

The capture is intentionally separate because cPanel documents the required read operation through deprecated API 2 `Email::getmxcheck`; no equivalent UAPI function is available in the accepted tooling contract.

## Safety boundary

The committed PowerShell capture permits only the read-only `Email::getmxcheck` request. It rejects storage inside a Git working tree, writes restricted evidence, creates `SHA256SUMS`, and removes temporary API-token material from memory. It does not call `setmxcheck`, change MX records, add or delete forwarders, alter default addresses, or modify mailbox settings.

A fresh, short-lived cPanel API token is required for a live capture. Do not paste a token into chat, GitHub, a command argument, the evidence directory, browser storage, or a shared document. Revoke the token immediately after capture. Creating or using that token is a separately authorized credential action.

## Capture

Run from an approved Windows operator host with PowerShell and network access to the cPanel HTTPS API:

```powershell
$credential = Get-Credential -UserName '<cpanel-account>'

& .\tools\messaging\capture_cpanel_mail_routing.ps1 `
  -CpanelHost '<approved-cpanel-host>' `
  -Credential $credential `
  -Domains @('creekco.ca','scgardens.ca','omegafx.com') `
  -OutputRoot 'C:\Restricted\wwcx-mail-routing-evidence'
```

Review the script's accepted parameters before execution. The credential object must contain the short-lived API token, not the account password.

## Evidence acceptance

Before normalization:

1. Confirm the evidence path is outside every Git working tree.
2. Confirm the directory and files are restricted to the operator account.
3. Confirm the capture summary reports only `Email::getmxcheck`.
4. Confirm every requested domain returned a bounded response or an explicit error.
5. Verify the manifest:

```powershell
Get-Content .\SHA256SUMS
```

The normalizer independently verifies `SHA256SUMS` before parsing.

## Offline normalization

```sh
python3 tools/messaging/normalize_cpanel_mail_routing.py \
  --evidence-dir /restricted/cpanel-mail-routing/<timestamp> \
  --output /restricted/namecheap-shared-hosting-routing.json
```

The normalizer performs no network access and no subprocess execution. It converts known primary/local routing states conservatively and leaves secondary or ambiguous states as `unknown`. Unknown routing is a blocker, not a reason to guess.

## Reconciliation

Combine the routing-only inventory with the accepted mailbox inventory and WW.CX Private Email inventory:

```sh
python3 tools/messaging/reconcile_mail_provider_objects.py \
  --inventory /restricted/namecheap-shared-hosting.json \
  --inventory /restricted/namecheap-shared-hosting-routing.json \
  --inventory records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json \
  --output /restricted/mail-provider-reconciliation.json \
  --strict
```

A strict exit code of `2` is expected while canonical objects, forwarding/filter state, access ownership, or routing evidence remain incomplete. Do not enable a sender or delivery path merely because one domain reports local routing.

## Stop conditions

Stop before creating or exposing a token, changing cPanel routing, changing DNS, provisioning or deleting mailboxes, adding aliases or forwarders, modifying filters, activating a sender, enabling the outbound gateway, or sending a message unless that exact action is separately authorized and rollback evidence exists.
