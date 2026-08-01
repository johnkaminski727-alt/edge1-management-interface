# Namecheap Private Email Support Evidence Intake

## Purpose

This procedure converts a substantive, read-only Namecheap Private Email support response for `ww.cx` into:

- a normalized `wwcx.provider-mail-objects.v1` inventory for reconciliation;
- a restricted completeness summary covering subscription, DKIM, catch-all, forwarding, sender capability, and provider rules.

It does not contact Namecheap and does not change any mailbox, alias, forwarder, filter, authentication setting, DNS record, sender authorization, or production mail flow.

## Evidence boundary

Keep all provider response material outside Git in a restricted directory. The bundle should contain:

```text
support-evidence.json
NC-JDV-2953-response.eml    # or another preserved source export
SHA256SUMS
```

The source export filename is illustrative. Preserve the provider response in its original available form before manually transcribing its non-secret findings into `support-evidence.json`.

Never place these items in the evidence JSON or committed files:

- Support PINs;
- passwords or passphrases;
- API or access tokens;
- authorization headers;
- cookies or session identifiers;
- `cpsess` values or authenticated session URLs;
- password-reset links;
- private keys or other secrets.

A Support PIN is used only through the provider's secure verification process. It is not provider inventory evidence and must not be copied into the bundle.

## Structured intake file

Start from:

```text
examples/messaging/namecheap-private-email-support-evidence.example.json
```

Copy it into the restricted evidence directory as `support-evidence.json`, then transcribe only facts explicitly supported by the provider response.

The evidence contract is:

```text
wwcx.namecheap-private-email-support-evidence.v1
```

### Subscription

Record:

- status: `active`, `inactive`, `suspended`, `expired`, or `unknown`;
- plan name when explicitly provided;
- expiry date in `YYYY-MM-DD` form when explicitly provided;
- mailbox-slot count when explicitly provided.

Do not infer capacity from historical orders when the current provider response does not confirm it.

### Mail objects

For each confirmed object, record:

- address;
- object type: mailbox, alias, forwarder, distribution list, system account, or unknown;
- destinations for aliases or forwarders;
- active state;
- receive capability;
- sender capability;
- quota in bytes when explicitly known;
- short non-secret notes.

Use `null` for unproven boolean capabilities. The normalizer deliberately converts unproven booleans to `false` and records a warning, keeping activation fail-closed.

Access classification is not accepted from the provider response. The normalizer derives it from the canonical repository configuration:

- `john-inbox@ww.cx` and private John routes → `private_john`;
- `maildesk@ww.cx` and shared role routes → `shared_role`;
- `noreply@ww.cx` → `system`;
- unexpected addresses → `unknown`.

### Catch-all

Record one of:

- `reject`;
- `forward`, with a destination;
- `blackhole`;
- `unknown`.

### DKIM

Record:

- `enabled`;
- `disabled`;
- `unverified`;
- `unknown`.

Include only the public selector name when confirmed. Do not include keys, signing secrets, or authenticated control-panel URLs.

### Provider rules and completeness

The `provider_rules` block records whether forwarding and filters were actually reviewed and whether provider-side rules exist.

Every `completeness` field must be either `true` or `false`. A category is complete only when the response explicitly answers it or clearly states that no such object or setting exists.

## Hash the evidence

From PowerShell in the restricted directory:

```powershell
$EvidenceDir = 'C:\restricted\namecheap-private-email-ww-cx'

$Lines = Get-ChildItem -LiteralPath $EvidenceDir -File |
    Where-Object Name -ne 'SHA256SUMS' |
    Sort-Object Name |
    ForEach-Object {
        $Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        '{0}  {1}' -f $Hash.ToLowerInvariant(), $_.Name
    }

[IO.File]::WriteAllLines(
    (Join-Path $EvidenceDir 'SHA256SUMS'),
    [string[]] $Lines,
    [Text.Encoding]::ASCII
)
```

The normalizer rejects missing, changed, unsafe, duplicate, or unmanifested evidence files.

## Normalize

```powershell
$Repo = 'C:\path\to\edge1-management-interface'
$EvidenceDir = 'C:\restricted\namecheap-private-email-ww-cx'
$Inventory = Join-Path $EvidenceDir 'namecheap-private-email.normalized.json'
$Summary = Join-Path $EvidenceDir 'namecheap-private-email.summary.json'

python "$Repo\tools\messaging\normalize_namecheap_private_email_support.py" `
    --evidence-dir $EvidenceDir `
    --inventory-output $Inventory `
    --summary-output $Summary `
    --strict-completeness
```

Exit status:

- `0` — evidence normalized and no warning remains;
- `1` — malformed, unsafe, secret-bearing, or checksum-invalid evidence;
- `2` — outputs were written, but the response remains incomplete or contains a hazardous or unproven state.

Both generated outputs remain restricted operational metadata and must not be committed.

## Combined reconciliation

After the Private Email inventory is normalized, combine it with the accepted shared-hosting inventory and any optional routing supplement:

```powershell
python "$Repo\tools\messaging\reconcile_mail_provider_objects.py" `
    --inventory 'C:\restricted\namecheap-private-email.normalized.json' `
    --inventory 'C:\restricted\namecheap-shared-hosting.normalized.json' `
    --inventory 'C:\restricted\namecheap-shared-hosting-routing.normalized.json' `
    --output 'C:\restricted\mail-provider-reconciliation.json' `
    --strict
```

Omit the routing supplement only when it has not been captured. Its absence must remain a documented blocker.

## Review and merge gate

PR #198 remains unmerged until:

1. a substantive provider response is preserved and checksum-verified;
2. the response contains no retained secret material;
3. the Private Email inventory and completeness summary are generated;
4. combined reconciliation is reviewed;
5. remaining unknowns are explicitly documented;
6. hosted validation passes at the final PR head.

A normalized inventory does not authorize provider mutation or production activation.
