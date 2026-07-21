# Electrum Watch-Only Service Runbook

## Purpose

Run Electrum on Edge1 as a localhost-only, watch-only Bitcoin wallet service. The business159 website must not hold a seed, private key, or Electrum daemon. A separate narrow WW.CX application API may later call the local Electrum JSON-RPC endpoint and expose only approved payment-status and address-allocation operations to business159 over authenticated HTTPS.

## Security boundary

- Create the wallet from an extended public key or another watch-only source.
- Never import a seed phrase, private key, wallet password, or hardware-wallet secret onto Edge1.
- Bind Electrum JSON-RPC only to `127.0.0.1`.
- Store RPC credentials in `/etc/electrum-watch/rpc.env`, owned by root and readable only by the service group.
- Do not expose the RPC port through Apache, firewall rules, port forwarding, or a public reverse proxy.
- Do not permit business159 to call Electrum RPC directly.
- Keep signing and spending offline or on a hardware wallet.

## Version and provenance

At the time this runbook was prepared, the official Electrum site listed 4.8.0 as the latest release and required Python 3.10 or newer. Operators must re-check the official site immediately before installation, download only from electrum.org, and verify the published GPG signatures.

Pin the approved release rather than installing an unbounded `latest` version. Record the release, source URL, SHA-256 digest, signer fingerprints, and signature-verification result in the operator evidence directory.

## Preflight

```bash
cd /opt/edge1-management-interface

git status --short
git branch --show-current
python3 --version
command -v curl
command -v systemctl
command -v gpg
ss -lntp | grep ':7777' || true
```

Confirm that Python satisfies the selected release, port 7777 is unused, and no unrelated repository changes will be included.

## Install Electrum into an isolated environment

Follow the verified upstream source-install instructions. The target executable expected by this repository is:

```text
/opt/electrum-watch/bin/electrum
```

Create an isolated virtual environment, install the pinned and signature-verified release, then record:

```bash
/opt/electrum-watch/bin/electrum version
```

Do not start the service yet.

## Create the service account and directories

The installer uses:

```text
electrum-watch                 system account
/var/lib/electrum-watch        service home
/var/lib/electrum-watch/.electrum
/var/lib/electrum-watch/wallets
```

The operator may create these before wallet import using the same ownership and permissions defined in `deploy/install-electrum-watch-service.sh`.

## Import the watch-only wallet

Run the verified Electrum executable as `electrum-watch` and restore from an xpub or another watch-only export. Avoid placing the xpub in shell history, logs, tickets, or Git.

The required final path is:

```text
/var/lib/electrum-watch/wallets/wwcx-watch-only
```

Verify that the wallet is watch-only before enabling the service. Stop immediately if Electrum reports that private keys are available.

## Configure localhost RPC

```bash
cd /opt/edge1-management-interface
sudo bash deploy/configure-electrum-watch-rpc.sh
```

The helper binds RPC to `127.0.0.1`, uses port 7777 by default, generates a high-entropy password locally, stores credentials at `/etc/electrum-watch/rpc.env`, and never prints the password.

To select another unused loopback port:

```bash
sudo ELECTRUM_RPC_PORT=17777 bash deploy/configure-electrum-watch-rpc.sh
```

## Install and start the managed service

```bash
cd /opt/edge1-management-interface
sudo bash deploy/install-electrum-watch-service.sh
```

The installer refuses to proceed unless the Electrum executable and watch-only wallet already exist.

## Validate

```bash
sudo bash deploy/electrum-watch-service-smoke-test.sh
sudo systemctl --no-pager --full status edge1-electrum-watch.service
sudo journalctl -u edge1-electrum-watch.service -n 100 --no-pager
sudo ss -lntp | grep ':7777'
```

The only acceptable RPC listener is loopback, normally:

```text
127.0.0.1:7777
```

No `0.0.0.0`, public IPv4, or non-loopback IPv6 listener is acceptable.

## Business159 integration boundary

The next phase should add a narrow application service on Edge1 with operations such as:

- allocate or return a receiving address from a controlled pool;
- query payment status for a known invoice identifier;
- return confirmations and transaction identifiers;
- expose health without returning wallet internals.

That application API must authenticate business159, validate replay-resistant requests, rate-limit clients, avoid returning RPC credentials, and preserve an audit record. It must not expose arbitrary Electrum methods.

## Stop and rollback

```bash
sudo systemctl disable --now edge1-electrum-watch.service
sudo rm -f /etc/systemd/system/edge1-electrum-watch.service
sudo systemctl daemon-reload
```

Preserve the watch-only wallet and configuration for investigation unless deletion is separately authorized. Removing this package does not authorize deletion of wallet data.
