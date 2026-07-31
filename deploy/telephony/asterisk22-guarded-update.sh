#!/bin/sh
set -eu
umask 077

APPLY=0
EXPECTED_HOST="edge1.ww.cx"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply)
            APPLY=1
            shift
            ;;
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 [--expected-host HOST] [--apply]"
            echo "Without --apply, performs read-only package and call-state inspection."
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}

for command in asterisk apt-cache apt-get dpkg-query dpkg awk tar sha256sum ss grep sed sort tee cat mktemp hostname id date mkdir sleep systemctl; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing $command" >&2
        exit 2
    }
done

channel_state=$(asterisk -rx 'core show channels count')
printf '%s\n' "$channel_state"
active_channels=$(printf '%s\n' "$channel_state" | awk '/active channels/{value=$1} END{print value}')
case "$active_channels" in
    ''|*[!0-9]*)
        echo "ERROR cannot determine channel count" >&2
        exit 3
        ;;
esac
[ "$active_channels" -eq 0 ] || {
    echo "ERROR active calls prevent update" >&2
    exit 3
}

current=$(dpkg-query -W -f='${Version}' asterisk22)
candidate=$(apt-cache policy asterisk22 | awk '/^[[:space:]]*Candidate:/{value=$2} END{print value}')
echo "Installed: $current"
echo "Candidate: ${candidate:-none}"
[ -n "$candidate" ] && [ "$candidate" != "(none)" ] || {
    echo "ERROR no candidate" >&2
    exit 3
}
case "${candidate#*:}" in
    22.*) ;;
    *)
        echo "ERROR candidate is not Asterisk 22" >&2
        exit 3
        ;;
esac

packages=$(dpkg-query -W -f='${binary:Package}\t${db:Status-Abbrev}\n' 'asterisk22*' 2>/dev/null |
    awk '$2 ~ /^ii/ {sub(/:.*/, "", $1); print $1}' |
    sort -u)
[ -n "$packages" ] || { echo "ERROR no installed asterisk22 packages" >&2; exit 3; }
printf '%s\n' "$packages" | sed 's/^/Package: /'

# Package names cannot contain whitespace. Deliberately split the validated list.
# shellcheck disable=SC2086
set -- $packages
simulation=$(mktemp)
trap 'rm -f "$simulation"' EXIT HUP INT TERM
if ! apt-get -s --only-upgrade install "$@" >"$simulation" 2>&1; then
    cat "$simulation" >&2
    echo "ERROR package simulation failed" >&2
    exit 4
fi
cat "$simulation"
if grep -Eq '^(Remv |The following packages will be REMOVED:)' "$simulation"; then
    echo "ERROR simulation proposes removal" >&2
    exit 4
fi

if ! dpkg --compare-versions "$candidate" gt "$current"; then
    echo "No newer Asterisk 22 package is currently available."
    exit 0
fi

if [ "$APPLY" -ne 1 ]; then
    echo "DRY RUN COMPLETE: rerun with --apply to update after reviewing the simulation."
    exit 0
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)
EVID="/var/lib/wwcx-deployment-evidence/asterisk-security-update/$TS"
mkdir -p "$EVID"

echo "Evidence: $EVID" | tee -a "$EVID/update.log"
dpkg-query -W -f='${binary:Package}\t${Version}\t${db:Status-Abbrev}\n' 'asterisk22*' \
    >"$EVID/packages-before.txt" 2>/dev/null || true
if [ -e /var/lib/asterisk/astdb ]; then
    tar -C / -czf "$EVID/asterisk-config-before.tgz" \
        etc/asterisk var/lib/asterisk/astdb
else
    tar -C / -czf "$EVID/asterisk-config-before.tgz" etc/asterisk
fi
sha256sum "$EVID/asterisk-config-before.tgz" \
    >"$EVID/asterisk-config-before.tgz.sha256"
asterisk -rx 'core show version' >"$EVID/version-before.txt"
asterisk -rx 'pjsip show transports' >"$EVID/transports-before.txt"
ss -lntup | grep -E 'asterisk|kamailio|:5060|:5061|:5038|:8088|:8089' \
    >"$EVID/listeners-before.txt" || true

if ! apt-get update >"$EVID/apt-update.txt" 2>&1; then
    tee -a "$EVID/update.log" <"$EVID/apt-update.txt" >&2
    echo "ERROR apt-get update failed" | tee -a "$EVID/update.log" >&2
    exit 5
fi
tee -a "$EVID/update.log" <"$EVID/apt-update.txt"
refreshed_candidate=$(apt-cache policy asterisk22 | awk '/^[[:space:]]*Candidate:/{value=$2} END{print value}')
[ "$refreshed_candidate" = "$candidate" ] || {
    echo "ERROR candidate changed after metadata refresh: $candidate -> $refreshed_candidate" \
        | tee -a "$EVID/update.log" >&2
    exit 5
}

channel_state=$(asterisk -rx 'core show channels count')
active_channels=$(printf '%s\n' "$channel_state" | awk '/active channels/{value=$1} END{print value}')
[ "$active_channels" = "0" ] || {
    echo "ERROR calls appeared before install" | tee -a "$EVID/update.log" >&2
    exit 5
}

if ! DEBIAN_FRONTEND=noninteractive apt-get install -y --only-upgrade \
    -o Dpkg::Options::=--force-confold "$@" >"$EVID/apt-install.txt" 2>&1; then
    tee -a "$EVID/update.log" <"$EVID/apt-install.txt" >&2
    echo "ERROR Asterisk package installation failed" | tee -a "$EVID/update.log" >&2
    exit 6
fi
tee -a "$EVID/update.log" <"$EVID/apt-install.txt"

if command -v fwconsole >/dev/null 2>&1; then
    if ! fwconsole restart >"$EVID/restart.txt" 2>&1; then
        tee -a "$EVID/update.log" <"$EVID/restart.txt" >&2
        echo "ERROR FreePBX restart failed" | tee -a "$EVID/update.log" >&2
        exit 7
    fi
else
    if ! systemctl restart asterisk >"$EVID/restart.txt" 2>&1; then
        tee -a "$EVID/update.log" <"$EVID/restart.txt" >&2
        echo "ERROR Asterisk restart failed" | tee -a "$EVID/update.log" >&2
        exit 7
    fi
fi
tee -a "$EVID/update.log" <"$EVID/restart.txt"
sleep 5

running=$(asterisk -V | awk '{print $2}')
installed=$(dpkg-query -W -f='${Version}' asterisk22)
expected=$(printf '%s\n' "${installed#*:}" | sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/')
echo "Installed package: $installed" | tee -a "$EVID/update.log"
echo "Running binary: $running" | tee -a "$EVID/update.log"
echo "Expected binary: $expected" | tee -a "$EVID/update.log"
[ "$running" = "$expected" ] || {
    echo "ERROR running binary mismatch" | tee -a "$EVID/update.log" >&2
    exit 6
}

asterisk -rx 'core show version' | tee "$EVID/version-after.txt"
asterisk -rx 'core show uptime' | tee "$EVID/uptime-after.txt"
asterisk -rx 'core show channels count' | tee "$EVID/channels-after.txt"
asterisk -rx 'module show like chan_pjsip' | tee "$EVID/chan-pjsip-after.txt"
asterisk -rx 'module show like app_playtones' | tee "$EVID/playtones-after.txt"
asterisk -rx 'pjsip show transports' | tee "$EVID/transports-after.txt"
systemctl is-active kamailio | tee "$EVID/kamailio-after.txt"
ss -lntup | grep -E 'asterisk|kamailio|:5060|:5061|:5038|:8088|:8089' \
    | tee "$EVID/listeners-after.txt" || true
dpkg-query -W -f='${binary:Package}\t${Version}\t${db:Status-Abbrev}\n' 'asterisk22*' \
    >"$EVID/packages-after.txt" 2>/dev/null || true

echo "ASTERISK UPDATE COMPLETED AND VALIDATED" | tee -a "$EVID/update.log"
echo "Evidence directory: $EVID" | tee -a "$EVID/update.log"
