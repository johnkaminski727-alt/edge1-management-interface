#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
INTERFACE=""
INSTALL_PACKAGES=false
ENABLE_ZEEK=false
ACTIVATE=false
ALLOW_ADDRESSED=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --interface) INTERFACE="${2:?missing interface}"; shift 2 ;;
    --install-packages) INSTALL_PACKAGES=true; shift ;;
    --enable-zeek) ENABLE_ZEEK=true; shift ;;
    --activate) ACTIVATE=true; shift ;;
    --allow-addressed-interface) ALLOW_ADDRESSED=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
[ -n "$INTERFACE" ] || { echo "--interface is required" >&2; exit 2; }
[ "$INTERFACE" != lo ] || { echo "loopback is not a sensor interface" >&2; exit 2; }
ip link show dev "$INTERFACE" >/dev/null
if [ "$ALLOW_ADDRESSED" = false ] && ip -o addr show dev "$INTERFACE" | grep -q .; then
  echo "Interface $INTERFACE has an IP address. Use a dedicated mirror/TAP NIC or pass --allow-addressed-interface after reviewing the risk." >&2
  exit 1
fi
if [ "$INSTALL_PACKAGES" = true ]; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y suricata tcpdump jq python3 ethtool
fi
for command in python3 suricata tcpdump ip install systemctl; do command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }; done
getent group wwsensor >/dev/null || groupadd --system wwsensor
id wwsensor >/dev/null 2>&1 || useradd --system --gid wwsensor --home-dir /var/lib/wwcx-network-sensor --shell /usr/sbin/nologin wwsensor
getent passwd suricata >/dev/null || { echo "Suricata service account missing" >&2; exit 1; }
install -d -o root -g root -m 0750 /etc/wwcx-network-sensor
install -d -o suricata -g suricata -m 0750 /var/log/wwcx-network-sensor/suricata
install -d -o wwsensor -g wwsensor -m 0750 /var/log/wwcx-network-sensor/zeek
install -d -o wwsensor -g wwsensor -m 0750 /var/lib/wwcx-network-sensor/pcap /var/lib/wwcx-network-sensor/extracted
install -d -o root -g root -m 0700 /var/lib/wwcx-network-sensor/restricted
install -d -o root -g root -m 0755 /var/www/edge1-status/network-sensor/data
zeek_value=no
[ "$ENABLE_ZEEK" = true ] && zeek_value=yes
sed "s/^SENSOR_INTERFACE=.*/SENSOR_INTERFACE=$INTERFACE/; s/^ENABLE_ZEEK=.*/ENABLE_ZEEK=$zeek_value/" "$ROOT/config/network-sensor/owner-full.env" > /etc/default/wwcx-network-sensor
chmod 0640 /etc/default/wwcx-network-sensor
install -o root -g root -m 0644 "$ROOT/config/network-sensor/wwcx-owner-full.zeek" /etc/wwcx-network-sensor/
install -o root -g root -m 0755 "$ROOT/server/network_sensor_exporter.py" /usr/local/libexec/wwcx-network-sensor-exporter.py
for script in network-sensor-pcap.sh network-sensor-zeek.sh network-sensor-prune.sh; do install -o root -g root -m 0755 "$ROOT/tools/networking/$script" "/usr/local/libexec/wwcx-$script"; done
for unit in "$ROOT"/deploy/systemd/wwcx-network-sensor-*; do install -o root -g root -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"; done
install -o root -g root -m 0644 "$ROOT/src/web/network-sensor/index.html" /var/www/edge1-status/network-sensor/index.html
python3 -m py_compile "$ROOT/server/network_sensor_exporter.py"
python3 "$ROOT/tests/test_network_sensor_exporter.py"
suricata -T -c /etc/suricata/suricata.yaml
systemctl daemon-reload
systemctl enable wwcx-network-sensor-exporter.timer wwcx-network-sensor-prune.timer
if [ "$ACTIVATE" = true ]; then
  systemctl enable --now wwcx-network-sensor-suricata.service wwcx-network-sensor-pcap.service
  if [ "$ENABLE_ZEEK" = true ]; then
    command -v zeek >/dev/null 2>&1 || [ -x /opt/zeek/bin/zeek ] || { echo "Zeek requested but not installed" >&2; exit 1; }
    systemctl enable --now wwcx-network-sensor-zeek.service
  fi
  systemctl start wwcx-network-sensor-exporter.service
  systemctl start wwcx-network-sensor-exporter.timer wwcx-network-sensor-prune.timer
fi
printf 'Installed Edge1 network sensor for interface %s. Activation=%s Zeek=%s\n' "$INTERFACE" "$ACTIVATE" "$ENABLE_ZEEK"
