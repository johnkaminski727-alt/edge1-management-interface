#!/usr/bin/env bash
set -euo pipefail
. /etc/default/wwcx-network-sensor
: "${SENSOR_INTERFACE:?SENSOR_INTERFACE is required}"
: "${PCAP_ROTATE_SECONDS:=3600}"
export TZ=UTC
mkdir -p /var/lib/wwcx-network-sensor/pcap
exec /usr/bin/tcpdump \
  -i "$SENSOR_INTERFACE" \
  -n \
  -s 0 \
  -B 4096 \
  -G "$PCAP_ROTATE_SECONDS" \
  -w '/var/lib/wwcx-network-sensor/pcap/%Y%m%dT%H%M%SZ.pcap'
