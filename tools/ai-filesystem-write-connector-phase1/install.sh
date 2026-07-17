#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "install.sh must be run as root" >&2
  exit 1
fi

install -d -m 0755 /etc/bigbird-fsctl
install -d -m 0755 /usr/local/sbin
install -d -m 0750 /var/lib/bigbird-fsctl/staging
install -d -m 0750 /var/lib/bigbird-fsctl/backups
install -d -m 0750 /var/log/bigbird-fsctl

install -m 0644 etc/bigbird-fsctl-policy.json /etc/bigbird-fsctl/policy.json
install -m 0755 sbin/bigbird-fsctl /usr/local/sbin/bigbird-fsctl

/usr/local/sbin/bigbird-fsctl init

echo "Installed bigbird-fsctl Phase 1 docs-only connector."
echo "Policy: /etc/bigbird-fsctl/policy.json"
echo "Command: /usr/local/sbin/bigbird-fsctl"
