#!/usr/bin/env bash
set -euo pipefail

install -d -m 2770 -o root -g wwadmin /var/lib/edge1-ai-fs-connector
install -d -m 2770 -o root -g wwadmin /var/lib/edge1-ai-fs-connector/staged
install -d -m 2770 -o root -g wwadmin /var/log/edge1-ai-fs-connector
touch /var/log/edge1-ai-fs-connector/audit.jsonl
chown root:wwadmin /var/log/edge1-ai-fs-connector/audit.jsonl
chmod 0660 /var/log/edge1-ai-fs-connector/audit.jsonl
