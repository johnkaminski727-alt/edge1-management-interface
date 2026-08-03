#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
INTERFACE=""
INSTALL_PACKAGES=false
ENABLE_ZEEK=false
ACTIVATE=false
ALLOW_ADDRESSED=false
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_ROOT="${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/network-sensor}"
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
BACKUP_DIR="$EVIDENCE_DIR/backups"
MUTATION_STARTED=0

SENSOR_UNITS="wwcx-network-sensor-suricata.service wwcx-network-sensor-pcap.service wwcx-network-sensor-zeek.service wwcx-network-sensor-exporter.service wwcx-network-sensor-exporter.timer wwcx-network-sensor-prune.service wwcx-network-sensor-prune.timer"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --interface) INTERFACE="${2:?missing interface}"; shift 2 ;;
    --install-packages) INSTALL_PACKAGES=true; shift ;;
    --enable-zeek) ENABLE_ZEEK=true; shift ;;
    --activate) ACTIVATE=true; shift ;;
    --allow-addressed-interface) ALLOW_ADDRESSED=true; shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ -d "$ROOT/.git" ] || fail "repository not found: $ROOT"
[ -n "$INTERFACE" ] || fail "--interface is required"
[ "$INTERFACE" != lo ] || fail "loopback is not a sensor interface"
for command in bash git ip install systemctl python3 cp sha256sum stat find; do
  command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done
BRANCH="$(git -C "$ROOT" branch --show-current)"
[ "$BRANCH" = main ] || fail "deployment requires main; current branch is $BRANCH"
[ -z "$(git -C "$ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work"
ip link show dev "$INTERFACE" >/dev/null
if [ "$ALLOW_ADDRESSED" = false ] && ip -o addr show dev "$INTERFACE" | grep -q .; then
  fail "interface $INTERFACE has an IP address; use a dedicated mirror/TAP NIC or explicitly pass --allow-addressed-interface"
fi

for source in \
  "$ROOT/config/network-sensor/owner-full.env" \
  "$ROOT/config/network-sensor/wwcx-owner-full.zeek" \
  "$ROOT/server/network_sensor_exporter.py" \
  "$ROOT/server/security_correlation_sensor_exporter.py" \
  "$ROOT/server/network_defense_sensor_exporter.py" \
  "$ROOT/tools/networking/network-sensor-pcap.sh" \
  "$ROOT/tools/networking/network-sensor-zeek.sh" \
  "$ROOT/tools/networking/network-sensor-prune.sh" \
  "$ROOT/tools/networking/validate-edge1-network-sensor.sh" \
  "$ROOT/deploy/systemd/wwcx-security-correlation.service" \
  "$ROOT/deploy/systemd/wwcx-network-defense.service" \
  "$ROOT/src/web/network-sensor/index.html"; do
  [ -f "$source" ] || fail "required source is missing: $source"
done

mkdir -p "$BACKUP_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
printf '%s\n' "$INTERFACE" > "$EVIDENCE_DIR/interface.txt"
printf 'activate=%s\nenable_zeek=%s\ninstall_packages=%s\n' "$ACTIVATE" "$ENABLE_ZEEK" "$INSTALL_PACKAGES" > "$EVIDENCE_DIR/options.txt"
git -C "$ROOT" rev-parse HEAD > "$EVIDENCE_DIR/revision.txt"
git -C "$ROOT" status --short --branch > "$EVIDENCE_DIR/git-status-before.txt"
ip -br link show dev "$INTERFACE" > "$EVIDENCE_DIR/interface-link-before.txt"
ip -br addr show dev "$INTERFACE" > "$EVIDENCE_DIR/interface-address-before.txt"

backup_path() {
  local path=$1
  local label=$2
  if [ -e "$path" ]; then
    cp -a "$path" "$BACKUP_DIR/$label"
    printf 'present\n' > "$BACKUP_DIR/$label.state"
  else
    printf 'absent\n' > "$BACKUP_DIR/$label.state"
  fi
}

restore_path() {
  local path=$1
  local label=$2
  local state
  state="$(cat "$BACKUP_DIR/$label.state" 2>/dev/null || printf absent)"
  if [ "$state" = present ]; then
    install -d -m 0755 "$(dirname "$path")"
    rm -rf "$path"
    cp -a "$BACKUP_DIR/$label" "$path"
  else
    rm -rf "$path"
  fi
}

record_unit_states() {
  : > "$EVIDENCE_DIR/unit-states-before.tsv"
  for unit in $SENSOR_UNITS; do
    printf '%s\t%s\t%s\n' \
      "$unit" \
      "$(systemctl is-enabled "$unit" 2>/dev/null || true)" \
      "$(systemctl is-active "$unit" 2>/dev/null || true)" \
      >> "$EVIDENCE_DIR/unit-states-before.tsv"
  done
}

restore_unit_states() {
  [ -f "$EVIDENCE_DIR/unit-states-before.tsv" ] || return 0
  while IFS="$(printf '\t')" read -r unit enabled active; do
    case "$enabled" in
      enabled|enabled-runtime) systemctl enable "$unit" >/dev/null 2>&1 || true ;;
      *) systemctl disable "$unit" >/dev/null 2>&1 || true ;;
    esac
    if [ "$active" = active ]; then
      systemctl start "$unit" >/dev/null 2>&1 || true
    fi
  done < "$EVIDENCE_DIR/unit-states-before.tsv"
}

backup_path /etc/default/wwcx-network-sensor sensor-default
backup_path /etc/wwcx-network-sensor sensor-policy-dir
backup_path /usr/local/libexec/wwcx-network-sensor-exporter.py sensor-exporter
backup_path /usr/local/libexec/wwcx-network-sensor-pcap.sh sensor-pcap-wrapper
backup_path /usr/local/libexec/wwcx-network-sensor-zeek.sh sensor-zeek-wrapper
backup_path /usr/local/libexec/wwcx-network-sensor-prune.sh sensor-prune-wrapper
backup_path /etc/systemd/system/wwcx-network-sensor-suricata.service sensor-suricata-unit
backup_path /etc/systemd/system/wwcx-network-sensor-pcap.service sensor-pcap-unit
backup_path /etc/systemd/system/wwcx-network-sensor-zeek.service sensor-zeek-unit
backup_path /etc/systemd/system/wwcx-network-sensor-exporter.service sensor-exporter-unit
backup_path /etc/systemd/system/wwcx-network-sensor-exporter.timer sensor-exporter-timer
backup_path /etc/systemd/system/wwcx-network-sensor-prune.service sensor-prune-unit
backup_path /etc/systemd/system/wwcx-network-sensor-prune.timer sensor-prune-timer
backup_path /etc/systemd/system/wwcx-security-correlation.service security-correlation-unit
backup_path /etc/systemd/system/wwcx-network-defense.service network-defense-unit
backup_path /var/www/edge1-status/network-sensor/index.html network-sensor-page
record_unit_states

rollback() {
  local code=$?
  trap - ERR INT TERM
  set +e
  if [ "$MUTATION_STARTED" -eq 1 ]; then
    printf 'Network sensor deployment failed; restoring saved configuration.\n' >&2
    systemctl status $SENSOR_UNITS --no-pager > "$EVIDENCE_DIR/failure-systemd-status.txt" 2>&1 || true
    journalctl -u wwcx-network-sensor-suricata.service -u wwcx-network-sensor-pcap.service -u wwcx-network-sensor-zeek.service -n 200 --no-pager > "$EVIDENCE_DIR/failure-sensor-journal.txt" 2>&1 || true
    for unit in $SENSOR_UNITS; do systemctl disable --now "$unit" >/dev/null 2>&1 || true; done
    restore_path /etc/default/wwcx-network-sensor sensor-default
    restore_path /etc/wwcx-network-sensor sensor-policy-dir
    restore_path /usr/local/libexec/wwcx-network-sensor-exporter.py sensor-exporter
    restore_path /usr/local/libexec/wwcx-network-sensor-pcap.sh sensor-pcap-wrapper
    restore_path /usr/local/libexec/wwcx-network-sensor-zeek.sh sensor-zeek-wrapper
    restore_path /usr/local/libexec/wwcx-network-sensor-prune.sh sensor-prune-wrapper
    restore_path /etc/systemd/system/wwcx-network-sensor-suricata.service sensor-suricata-unit
    restore_path /etc/systemd/system/wwcx-network-sensor-pcap.service sensor-pcap-unit
    restore_path /etc/systemd/system/wwcx-network-sensor-zeek.service sensor-zeek-unit
    restore_path /etc/systemd/system/wwcx-network-sensor-exporter.service sensor-exporter-unit
    restore_path /etc/systemd/system/wwcx-network-sensor-exporter.timer sensor-exporter-timer
    restore_path /etc/systemd/system/wwcx-network-sensor-prune.service sensor-prune-unit
    restore_path /etc/systemd/system/wwcx-network-sensor-prune.timer sensor-prune-timer
    restore_path /etc/systemd/system/wwcx-security-correlation.service security-correlation-unit
    restore_path /etc/systemd/system/wwcx-network-defense.service network-defense-unit
    restore_path /var/www/edge1-status/network-sensor/index.html network-sensor-page
    systemctl daemon-reload >/dev/null 2>&1 || true
    restore_unit_states
    systemctl start wwcx-security-correlation.service >/dev/null 2>&1 || true
    systemctl start wwcx-network-defense.service >/dev/null 2>&1 || true
    printf 'rolled_back=true\nexit_code=%s\n' "$code" > "$EVIDENCE_DIR/rollback.txt"
    printf 'Failure evidence: %s\n' "$EVIDENCE_DIR" >&2
  fi
  exit "$code"
}
trap rollback ERR INT TERM

bash "$ROOT/tools/networking/validate-edge1-network-sensor.sh" | tee "$EVIDENCE_DIR/repository-validation.txt"

MUTATION_STARTED=1
if [ "$INSTALL_PACKAGES" = true ]; then
  apt-get update | tee "$EVIDENCE_DIR/apt-update.txt"
  DEBIAN_FRONTEND=noninteractive apt-get install -y suricata tcpdump jq python3 ethtool | tee "$EVIDENCE_DIR/apt-install.txt"
fi
for command in suricata tcpdump jq; do command -v "$command" >/dev/null 2>&1 || fail "required runtime command is unavailable: $command"; done
if [ "$ENABLE_ZEEK" = true ]; then
  if command -v zeek >/dev/null 2>&1; then
    ZEEK_BIN="$(command -v zeek)"
  elif [ -x /opt/zeek/bin/zeek ]; then
    ZEEK_BIN=/opt/zeek/bin/zeek
  else
    fail "Zeek was requested but is not installed"
  fi
  "$ZEEK_BIN" --version > "$EVIDENCE_DIR/zeek-version.txt" 2>&1
fi

getent group wwsensor >/dev/null || groupadd --system wwsensor
id wwsensor >/dev/null 2>&1 || useradd --system --gid wwsensor --home-dir /var/lib/wwcx-network-sensor --shell /usr/sbin/nologin wwsensor
getent passwd suricata >/dev/null || fail "Suricata service account is missing"
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
for script in network-sensor-pcap.sh network-sensor-zeek.sh network-sensor-prune.sh; do
  install -o root -g root -m 0755 "$ROOT/tools/networking/$script" "/usr/local/libexec/wwcx-$script"
done
for unit in "$ROOT"/deploy/systemd/wwcx-network-sensor-*; do
  install -o root -g root -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done
install -o root -g root -m 0644 "$ROOT/deploy/systemd/wwcx-security-correlation.service" /etc/systemd/system/wwcx-security-correlation.service
install -o root -g root -m 0644 "$ROOT/deploy/systemd/wwcx-network-defense.service" /etc/systemd/system/wwcx-network-defense.service
install -o root -g root -m 0644 "$ROOT/src/web/network-sensor/index.html" /var/www/edge1-status/network-sensor/index.html

python3 -m py_compile \
  "$ROOT/server/network_sensor_exporter.py" \
  "$ROOT/server/security_correlation_sensor_exporter.py" \
  "$ROOT/server/network_defense_sensor_exporter.py"
suricata -T -c /etc/suricata/suricata.yaml > "$EVIDENCE_DIR/suricata-config-test.txt" 2>&1
systemctl daemon-reload

if [ "$ACTIVATE" = true ]; then
  systemctl enable --now wwcx-network-sensor-suricata.service wwcx-network-sensor-pcap.service
  if [ "$ENABLE_ZEEK" = true ]; then
    systemctl enable --now wwcx-network-sensor-zeek.service
  fi
  systemctl enable --now wwcx-network-sensor-exporter.timer wwcx-network-sensor-prune.timer
  systemctl start wwcx-network-sensor-exporter.service
  systemctl start wwcx-security-correlation.service
  systemctl start wwcx-network-defense.service

  [ "$(systemctl is-active wwcx-network-sensor-suricata.service)" = active ]
  [ "$(systemctl is-active wwcx-network-sensor-pcap.service)" = active ]
  [ "$(systemctl is-enabled wwcx-network-sensor-exporter.timer)" = enabled ]
  [ "$(systemctl is-active wwcx-network-sensor-exporter.timer)" = active ]
  [ "$(systemctl is-enabled wwcx-network-sensor-prune.timer)" = enabled ]
  [ "$(systemctl show wwcx-network-sensor-exporter.service -p Result --value)" = success ]
  [ "$(systemctl show wwcx-security-correlation.service -p Result --value)" = success ]
  [ "$(systemctl show wwcx-network-defense.service -p Result --value)" = success ]

  python3 - <<'PY'
import json
from pathlib import Path
sensor = json.loads(Path('/var/lib/wwcx-network-sensor/restricted/latest.json').read_text())
correlation = json.loads(Path('/var/www/edge1-status/security/correlation/data/security-correlation.json').read_text())
defense = json.loads(Path('/var/www/edge1-status/network-defense/data/network-defense.json').read_text())
assert sensor['contract'] == 'wwcx.edge1-network-sensor.v1'
assert sensor['visibility'] == 'restricted-owner-full'
assert sensor['capture']['full_packet_capture'] is True
assert correlation['source_status']['network_sensor']['available'] is True
assert correlation['network_sensor_context']['restricted_payloads_copied'] is False
assert defense['components']['network_sensor']['state'] in {'ready', 'observed'}
assert defense['traffic_controls_changed'] is False
print('Integrated sensor contracts validated.')
PY
fi

systemctl status $SENSOR_UNITS --no-pager > "$EVIDENCE_DIR/systemd-status.txt" 2>&1 || true
journalctl -u wwcx-network-sensor-suricata.service -u wwcx-network-sensor-pcap.service -u wwcx-network-sensor-zeek.service -n 200 --no-pager > "$EVIDENCE_DIR/sensor-journal.txt" 2>&1 || true
ip -s link show dev "$INTERFACE" > "$EVIDENCE_DIR/interface-stats-after.txt"
sha256sum \
  /etc/default/wwcx-network-sensor \
  /etc/wwcx-network-sensor/wwcx-owner-full.zeek \
  /usr/local/libexec/wwcx-network-sensor-exporter.py \
  /etc/systemd/system/wwcx-network-sensor-suricata.service \
  /etc/systemd/system/wwcx-network-sensor-pcap.service \
  /etc/systemd/system/wwcx-security-correlation.service \
  /etc/systemd/system/wwcx-network-defense.service \
  /var/www/edge1-status/network-sensor/index.html \
  > "$EVIDENCE_DIR/sha256.txt"
printf 'completed_at=%s\nrolled_back=false\nactivated=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ACTIVATE" > "$EVIDENCE_DIR/result.txt"

trap - ERR INT TERM
printf 'Installed Edge1 network sensor for interface %s. Activation=%s Zeek=%s\n' "$INTERFACE" "$ACTIVATE" "$ENABLE_ZEEK"
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
