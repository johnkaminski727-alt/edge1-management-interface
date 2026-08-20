# Namecheap Private Email read-only IMAP canary

Date: 2026-08-20

## Objective

Provide one bounded, explicitly authorized proof that an existing Namecheap Private Email mailbox can be reached over verified TLS and inspected read-only without fetching message bodies, changing mailbox state, writing the WW.CX Mail Room correspondence store, or sending mail.

Components:

- authorization schema: `schemas/messaging/namecheap-imap-read-canary-authorization.schema.json`;
- canary: `tools/messaging/namecheap_imap_read_canary.py`;
- validator: `tests/validate_namecheap_imap_read_canary.py`.

The package is source-only. It contains no credential and has not been executed against a live provider mailbox.

## Provider boundary

The canary is hard-pinned to:

```text
host: mail.privateemail.com
port: 993
mailbox: INBOX
transport: IMAP over verified TLS
```

A live run performs only this bounded sequence:

```text
connect with verified system trust store
LOGIN
SELECT INBOX readonly=True
UID SEARCH ALL
for at most 5 newest UIDs: UID FETCH <uid> (BODY.PEEK[HEADER])
LOGOUT
```

It does not fetch `BODY.PEEK[]`, message text, MIME parts, or attachments. It does not issue `STORE`, `MOVE`, `COPY`, `DELETE`, `EXPUNGE`, `APPEND`, or any SMTP operation.

## Credentials

A live run reads only these environment variables:

```text
WWCX_NAMECHEAP_IMAP_USERNAME
WWCX_NAMECHEAP_IMAP_PASSWORD
```

The username must be a full mailbox address. The password is never accepted on the command line, written to the authorization file, printed, or returned in evidence.

The raw username is not emitted. The result records only its SHA-256 hash. Message UIDs and Message-ID values are also represented only as SHA-256 hashes.

## Authorization file

Every run, including audit-only mode, requires a private regular JSON file outside Git with mode `0600` or stricter. A live provider read additionally requires `--execute` and runtime credentials.

The authorization contract is:

```text
contract=wwcx.namecheap-imap-read-canary-authorization.v1
provider_read_canary_authorized=true
expected_host_sha256=<SHA-256 of mail.privateemail.com>
expected_port=993
expected_username_sha256=<SHA-256 of exact mailbox username>
mailbox=INBOX
max_messages=1..5
expires_at=<future timestamp no more than 24 hours away>
message_body_fetch_authorized=false
mailbox_mutation_authorized=false
store_write_authorized=false
mail_send_authorized=false
```

The canary refuses extra keys, a different provider host or port, any mailbox other than INBOX, a message count outside 1..5, an expired or longer-than-24-hour authorization, a username mismatch, or any authorization that permits body fetch, mailbox mutation, Mail Room writes, or sending.

## Audit-only default

Without `--execute`, the canary performs no network activity and reads no credential. It validates the authorization structure and reports only the bounded proposed operation.

This is the default mode so preparing or reviewing an authorization file cannot accidentally contact Namecheap.

## Sanitized live evidence

A successful live result may contain:

- result contract and UTC observation time;
- provider identifier;
- SHA-256 of the fixed host;
- port 993;
- SHA-256 of the mailbox username;
- authorization expiry;
- mailbox name and UIDVALIDITY if exposed by the server;
- count of inspected messages;
- for each inspected message: SHA-256 of UID, SHA-256 of Message-ID when present, and booleans indicating whether To/Cc/Bcc or known delivery-recipient header names were present;
- explicit safety markers proving verified TLS is required, mailbox selection is read-only, body fetch is false, store write is false, mail send is false, and credentials are not output.

No address value from message headers, subject, sender, recipient, body, attachment, or raw provider response is emitted.

## Execution prerequisites

A real provider canary remains a protected action because it uses mailbox credentials and performs authenticated provider access. Before execution:

1. identify which existing physical Namecheap mailbox will be inspected (`blank@ww.cx` or another explicitly approved mailbox);
2. place the exact username/password into an approved private secret location or service environment outside Git;
3. calculate the username hash without disclosing the username in evidence;
4. create a short-lived private authorization file bound to the fixed provider endpoint, exact username hash, INBOX, and a maximum of 1 to 5 headers;
5. verify all Mail Room sending, routing, DNS, and provider-mutation gates remain disabled;
6. run audit-only mode first and preserve the sanitized result;
7. after separate explicit approval for credential use and authenticated mailbox access, run one `--execute` canary;
8. preserve sanitized output and stop. Do not combine the read canary with provider ingestion, store writes, SMTP authentication, DNS changes, sender activation, or a production message.

## After a successful read canary

A successful canary establishes provider reachability and bounded read-only mailbox access only. It does not authorize ongoing ingestion.

The next separately controlled step would be to authorize a limited provider-native ingestion pass using `server/mail_namecheap_imap_source.py`, which fetches full messages with `BODY.PEEK[]` and persists validated messages as authoritative `production_native` correspondence. That step is intentionally outside this canary because it reads bodies and writes the private store.

## Preserved boundaries

This package does not create or rotate credentials, change Namecheap mailbox settings, provision aliases or forwarding, change MX/SPF/DKIM/DMARC, enable Mail Room routing, enable any sender, fetch message bodies, write correspondence records, release quarantine, send a message, or activate automatic replies.
