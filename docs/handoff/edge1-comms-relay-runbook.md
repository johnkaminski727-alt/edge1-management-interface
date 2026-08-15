# Edge1 Communications Relay Runbook

Version: 1.0.0

## Preflight

Use a clean `main` checkout on Edge1. Confirm the intended commit and run:

```sh
cd /opt/edge1-management-interface
deploy/comms-relay/install.sh --dry-run --expected-commit=<COMMIT>
python3 tests/validate_comms_relay.py
```

Do not alter DNS, firewall rules, certificates or listener addresses as part of the loopback deployment.

## Install without activation

```sh
sudo deploy/comms-relay/install.sh --apply --expected-commit=<COMMIT>
```

This creates/preserves the dedicated service identity, safe configuration, data path and systemd unit. It does not start the service.

## Activate loopback service

```sh
sudo deploy/comms-relay/install.sh --apply --start --expected-commit=<COMMIT>
```

The installer validates the config and unit, enables/starts the service, checks active state, performs the bundled protocol/control smoke test and writes protected evidence under:

```text
/var/lib/wwcx-deployment-evidence/comms-relay/<UTC timestamp>/
```

If validation/start/smoke fails, the installer restores the prior unit, configuration and enabled/active state.

## Verify

```sh
systemctl is-enabled edge1-comms-relay.service
systemctl is-active edge1-comms-relay.service
python3 deploy/comms-relay/smoke-test.py --config /etc/wwcx/comms-relay.json
ss -ltnp | grep -E ':(16667|1119|8100)'
bin/commsctl --config /etc/wwcx/comms-relay.json status
journalctl -u edge1-comms-relay.service --since '-10 minutes' --no-pager
```

The default accepted result is loopback-only listeners at `127.0.0.1:16667`, `127.0.0.1:1119`, and `127.0.0.1:8100`. Port `8099` is reserved for the existing WW.CX telephony analytics API and must not be reused by the communications relay.

## Create the founder account

Use an interactive terminal rather than command-line password arguments:

```sh
sudo -u wwcx-comms bin/commsctl --config /etc/wwcx/comms-relay.json account add john --role founder
```

Passwords must meet the configured minimum length. Password values are never written to audit records.

## Operations

```sh
bin/commsctl --config /etc/wwcx/comms-relay.json account list
bin/commsctl --config /etc/wwcx/comms-relay.json group list
bin/commsctl --config /etc/wwcx/comms-relay.json article list wwcx.projects.edge1
bin/commsctl --config /etc/wwcx/comms-relay.json audit --limit 100
bin/commsctl --config /etc/wwcx/comms-relay.json maintenance prune
```

## Configuration changes

Preserve the candidate/running workflow:

```sh
bin/commsctl config validate candidate.json
bin/commsctl config diff /etc/wwcx/comms-relay.json candidate.json
sudo -u wwcx-comms bin/commsctl config stage candidate.json
sudo bin/commsctl config apply
sudo systemctl restart edge1-comms-relay.service
python3 deploy/comms-relay/smoke-test.py --config /etc/wwcx/comms-relay.json
```

Rollback is:

```sh
sudo bin/commsctl config rollback
sudo systemctl restart edge1-comms-relay.service
python3 deploy/comms-relay/smoke-test.py --config /etc/wwcx/comms-relay.json
```

## Incident containment

To stop communications without deleting state:

```sh
sudo systemctl stop edge1-comms-relay.service
```

Do not delete the SQLite database during incident handling. Preserve `/var/lib/wwcx-comms`, configuration, journal logs and deployment evidence for diagnosis.

## External exposure gate

Internet-facing IRC/NNTP is not part of this runbook. Before exposure, separately approve and validate TLS identity/certificate handling, DNS, firewall policy, public ports, client compatibility, abuse policy and monitoring. Federation remains disabled unless an explicit peer/trust design is approved.
