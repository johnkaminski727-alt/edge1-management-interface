#!/usr/bin/env bash
set -euo pipefail
. /etc/default/wwcx-network-sensor
: "${SENSOR_INTERFACE:?SENSOR_INTERFACE is required}"
if command -v zeek >/dev/null 2>&1; then
  ZEEK_BIN="$(command -v zeek)"
elif [ -x /opt/zeek/bin/zeek ]; then
  ZEEK_BIN=/opt/zeek/bin/zeek
else
  echo "Zeek is not installed" >&2
  exit 127
fi
cd /var/log/wwcx-network-sensor/zeek
exec "$ZEEK_BIN" -C -i "$SENSOR_INTERFACE" /etc/wwcx-network-sensor/wwcx-owner-full.zeek
