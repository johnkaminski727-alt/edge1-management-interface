# cPanel HTTPS Mail-Inventory Fallback

## Status

This runbook provides the read-only fallback for cPanel shared-hosting shells where `/usr/local/cpanel/bin/uapi` is visible but the backend `/usr/local/cpanel/cpanel` executable is unavailable inside the account jail.

Verified on `business159.web-hosting.com` on 2026-08-01:

- account shell user: `wwcxjywl`;
- local `uapi`, `cpapi2`, and `whmapi1` paths resolve to wrappers;
- `/usr/local/cpanel/cpanel` is absent from the shell jail;
- local UAPI fails with `Failed to execute /usr/local/cpanel/cpanel`;
- the TLS-verified cPanel endpoint at `https://business159.web-hosting.com:2083/` returns HTTP 200;
- `$HOME/etc/creekco.ca/passwd` and `$HOME/etc/creekco.ca/quota` are readable;
- equivalent local mailbox files were not observed for `scgardens.ca` or `omegafx.com`;
- jailed `/etc/valiases`, `/etc/vfilters`, and `/etc/vdomainaliases` evidence was not available for the three domains.

The local filesystem evidence is therefore partial. It may corroborate CreekCo mailbox presence and quota metadata, but it cannot establish forwarders, filters, default-address behavior, autoresponders, domain routing, or complete coverage of the other domains.

## Safety boundary

The HTTPS collector:

- invokes only cPanel UAPI list/read functions;
- does not create, edit, delete, suspend, route, forward, or provision mail;
- prompts for the API token with terminal echo disabled;
- refuses to run while shell tracing is enabled;
- feeds the authorization header to curl through standard input rather than command-line arguments;
- does not write the token into logs, evidence metadata, checksums, or repository files;
- validates every UAPI response before retaining it;
- stores all evidence with restrictive permissions outside Git;
- creates a SHA-256 inventory.

A cPanel API token is still a privileged credential. Create it through the authenticated cPanel **Security > Manage API Tokens** interface, use it only for this bounded capture, and revoke it after the capture and checksum verification complete. Never paste it into chat, shell history, a command-line argument, a Git file, or a generally shared Drive location.

## Repository validation

Before host use, validate the collector in a current repository checkout:

```sh
cd ~/apps/edge1-management-interface
git fetch --prune origin main
git checkout -B main origin/main

sh -n tools/messaging/capture_cpanel_mail_inventory_https.sh
python3 -m unittest tests.test_capture_cpanel_mail_inventory_https
```

The tests use a fake curl endpoint. They verify that the token is delivered through curl configuration input, does not appear in curl's process arguments, and is not retained in metadata.

## Capture procedure

Extract the current script into the account's private executable directory without modifying the repository working tree:

```sh
set -eu
set +x
umask 077

REPO="$HOME/apps/edge1-management-interface"
SCRIPT="$HOME/.local/libexec/wwcx/capture_cpanel_mail_inventory_https.sh"

mkdir -p "$(dirname "$SCRIPT")"
git -C "$REPO" fetch --prune origin main
git -C "$REPO" show \
  origin/main:tools/messaging/capture_cpanel_mail_inventory_https.sh \
  > "$SCRIPT"
chmod 0700 "$SCRIPT"

EVIDENCE="$HOME/private-mail-evidence/$(date -u +%Y%m%dT%H%M%SZ)-https-uapi"

sh "$SCRIPT" \
  --output "$EVIDENCE" \
  --host business159.web-hosting.com \
  --user "$(id -un)" \
  --domain creekco.ca \
  --domain scgardens.ca \
  --domain omegafx.com
```

The script prompts:

```text
cPanel API token for wwcxjywl:
```

Terminal echo is disabled while the token is entered. The token must not be supplied on the command line.

## Acceptance checks

After the collector reports success:

```sh
(
  cd "$EVIDENCE"
  sha256sum -c SHA256SUMS
)

python3 - "$EVIDENCE" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))

assert metadata["contract"] == "wwcx.cpanel-mail-inventory-evidence.v1"
assert metadata["read_only"] is True
assert metadata["uapi_execution_mode"] == "https-api-token"
assert metadata["token_input_mode"] == "hidden-terminal-prompt"
assert metadata["token_retained"] is False
assert metadata["domains"] == ["creekco.ca", "scgardens.ca", "omegafx.com"]

json_files = sorted(path.name for path in root.glob("*.json"))
assert len(json_files) == 14, json_files

print("HTTPS UAPI CAPTURE VERIFIED")
print(f"Evidence directory: {root}")
print(f"JSON files: {len(json_files)}")
print("Token retained: no")
print("SHA-256 inventory: valid")
PY

printf 'READY-FOR-RECONCILIATION=%s\n' "$EVIDENCE"
```

The expected 14 JSON files are 13 UAPI response files plus `metadata.json`. `SHA256SUMS` is the fifteenth file.

## Captured functions

The HTTPS collector calls only:

```text
Email list_mail_domains
Email list_pops
Email list_domain_forwarders
Email list_filters
Email list_forwarders
Email list_default_address
Email list_auto_responders
```

## Closeout

After successful capture and checksum verification:

1. revoke the temporary cPanel API token in **Manage API Tokens**;
2. retain the raw directory as restricted operational evidence;
3. normalize it into `wwcx.provider-mail-objects.v1`;
4. run `tools/messaging/reconcile_mail_provider_objects.py` in strict mode;
5. do not perform provider mutations until the reconciliation is reviewed and separately authorized.

A successful inventory capture does not authorize mailbox creation, forwarding changes, DNS changes, gateway activation, or production mail traffic.

## Official references

- cPanel UAPI introduction: `https://api.docs.cpanel.net/cpanel/introduction`
- cPanel API-token authentication: `https://api.docs.cpanel.net/cpanel/tokens`
- cPanel `Email::list_pops`: `https://api.docs.cpanel.net/specifications/cpanel.openapi/email-accounts/list_pops`
