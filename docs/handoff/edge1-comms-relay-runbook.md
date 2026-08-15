# Edge1 Communications Relay Runbook

## Scope

This runbook operates the repository implementation of the WW.CX Edge1 Communications Relay. It does not authorize public exposure, DNS changes, firewall changes, certificate issuance, external federation, or production communication traffic.

## Validate repository assets

```sh
python3 -m compileall -q server tests
python3 tests/validate_comms_relay.py
python3 server/edge1_comms_cli.py config validate config/comms-relay.example.json
sh -n deploy/comms-relay/install.sh
node --check src/web/comms-relay/app.js
```

The protocol validation uses ephemeral `127.0.0.1` sockets only. It exercises IRC capability negotiation/registration/JOIN/TOPIC and NNTP GROUP/POST/OVER in an explicitly anonymous laboratory configuration, while shared storage separately validates randomized credential hashing/authentication and moderated authorization. It also exercises configuration rollback and the read-only HTTP status API. Production defaults remain authentication-required.

## Deployment preflight

The installer defaults to dry-run:

```sh
deploy/comms-relay/install.sh
```

Review the reported repository, unit, configuration, data paths, and activation intent.

Install without starting:

```sh
sudo deploy/comms-relay/install.sh --apply
```

This creates or confirms the `wwcx-comms` system identity, installs the systemd unit, creates `/var/lib/wwcx-comms`, and installs the loopback-only example configuration only when no running configuration exists. An existing configuration is preserved and validated.

Local activation is a separate explicit action:

```sh
sudo deploy/comms-relay/install.sh --apply --start
```

Do not use `--start` as a substitute for the acceptance checks below.

## First account

Create an account without placing the password in process arguments or shell history:

```sh
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json \
  account add john --role founder
```

For controlled automation, `--password-stdin` is available. The caller is responsible for using a pipe or file descriptor that does not expose the password in logs.

## Local acceptance

After local activation:

```sh
systemctl is-enabled edge1-comms-relay.service
systemctl is-active edge1-comms-relay.service
systemctl --no-pager --full status edge1-comms-relay.service
ss -ltnp | grep -E ':(16667|1119|8099)[[:space:]]'
curl --fail --silent http://127.0.0.1:8099/api/comms/status | python3 -m json.tool
journalctl -u edge1-comms-relay.service --since '-5 minutes' --no-pager
```

Expected default listeners are loopback only:

```text
127.0.0.1:16667  IRC laboratory listener
127.0.0.1:1119   NNTP laboratory listener
127.0.0.1:8099   read-only control UI/API
```

Any wildcard or non-loopback listener during this acceptance is a failure unless a separately approved public-exposure change is being executed.

## Client smoke checks

IRC clients must negotiate SASL and authenticate before registration completes. For local protocol debugging, an IRC client can connect to `127.0.0.1:16667` without TLS because the socket is loopback-only.

NNTP reader/poster clients can use `127.0.0.1:1119` and `AUTHINFO USER/PASS`. Posting requires an authenticated account and group policy authorization.

## Newsgroup administration

List groups:

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json group list
```

Add a group:

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json \
  group add wwcx.projects.example 'Example project discussion' --retention-days 3650
```

Add `--moderated` when only `founder`, `moderator`, or `moderator:<group>` accounts should post.

## Configuration change

Validate and inspect before staging:

```sh
bin/commsctl config validate /path/to/candidate.json
bin/commsctl config diff /etc/wwcx/comms-relay.json /path/to/candidate.json
```

Stage:

```sh
sudo -u wwcx-comms bin/commsctl config stage /path/to/candidate.json
```

Apply atomically with backup evidence:

```sh
sudo bin/commsctl config apply
```

`config apply` does not restart the service. Review the new file and the record under `/var/lib/wwcx-comms/config-control/last-applied.json` before any restart.

Rollback the most recent apply:

```sh
sudo bin/commsctl config rollback
```

A service restart remains explicit after apply or rollback.

## Public exposure gate

Do not expose IRC or NNTP publicly until all of these have separate approval and evidence:

- intended public hostnames and DNS records;
- listener addresses;
- TLS certificate identity and renewal path;
- firewall policy;
- rate-limit and abuse policy;
- account/provisioning model;
- operational monitoring and retention;
- external client compatibility testing;
- decision on federation policy.

The intended standards-facing ports are IRC/TLS `6697` and NNTP/TLS `563`. The configuration validator rejects a public listener without TLS even when `network_exposure.enabled=true`.

## Incident containment

To stop the relay without deleting state:

```sh
sudo systemctl stop edge1-comms-relay.service
```

Do not delete `/var/lib/wwcx-comms` during containment. Preserve the database and configuration-control records for investigation.

To prevent boot activation while retaining the installed unit:

```sh
sudo systemctl disable edge1-comms-relay.service
```

## Data protection notes

- SQLite state is mode-protected by the service directory and systemd umask.
- Audit metadata does not contain credentials or message bodies by design.
- IRC channel message history exists only when explicitly enabled.
- Direct/private IRC message bodies are never written to history by version 0.1.
- NNTP article content is durable discussion content and should be backed up according to future records policy before public use.
