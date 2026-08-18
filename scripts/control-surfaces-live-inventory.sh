#!/bin/sh
set -u

# Read-only live inventory for the Edge1 Control Surfaces activation gate.
# This script intentionally performs no configuration writes, reloads, restarts,
# firewall mutations, telephony traffic generation, or credential reads.

umask 077
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BASE=${HOME}/.local/state/edge1-control-surfaces/evidence
OUT=${BASE}/${STAMP}
mkdir -p "$OUT"
MANIFEST="$OUT/manifest.tsv"
: > "$MANIFEST"

have() {
    command -v "$1" >/dev/null 2>&1
}

redact() {
    src=$1
    dst=$2
    # Evidence is protected locally, but sanitize common secret-bearing fields
    # before anything is retained or shared.
    sed -E \
        -e 's/^([[:space:]]*Set-Cookie:).*/\1 [REDACTED]/I' \
        -e 's/^([[:space:]]*Cookie:).*/\1 [REDACTED]/I' \
        -e 's/^([[:space:]]*Authorization:).*/\1 [REDACTED]/I' \
        -e 's/^([[:space:]]*(password|passwd|secret|token|api[_-]?key|private[_-]?key|preshared[_-]?key)[[:space:]]*[:=]).*/\1 [REDACTED]/I' \
        -e 's#(https?://)[^/@[:space:]]+@#\1[REDACTED]@#g' \
        -e 's/([?&](token|access_token|api[_-]?key|secret)=)[^&[:space:]]+/\1[REDACTED]/Ig' \
        "$src" > "$dst"
}

run_to_raw() {
    raw=$1
    err=$2
    shift 2
    if have timeout; then
        timeout 20 "$@" >"$raw" 2>"$err"
    else
        "$@" >"$raw" 2>"$err"
    fi
}

capture() {
    name=$1
    shift
    raw="$OUT/.${name}.raw"
    err="$OUT/.${name}.err"
    out="$OUT/${name}.txt"
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    rc=0
    run_to_raw "$raw" "$err" "$@" || rc=$?
    {
        printf '%s\n' "# command: $*"
        printf '%s\n' "# started_utc: $start"
        printf '%s\n' "# exit_code: $rc"
        printf '%s\n' "# stdout"
        cat "$raw"
        printf '%s\n' "# stderr"
        cat "$err"
    } > "$OUT/.${name}.combined"
    redact "$OUT/.${name}.combined" "$out"
    rm -f "$raw" "$err" "$OUT/.${name}.combined"
    printf '%s\t%s\t%s\n' "$name" "$rc" "$start" >> "$MANIFEST"
    return 0
}

capture_stdin_null() {
    name=$1
    shift
    raw="$OUT/.${name}.raw"
    err="$OUT/.${name}.err"
    out="$OUT/${name}.txt"
    start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    rc=0
    if have timeout; then
        timeout 20 "$@" </dev/null >"$raw" 2>"$err" || rc=$?
    else
        "$@" </dev/null >"$raw" 2>"$err" || rc=$?
    fi
    {
        printf '%s\n' "# command: $*"
        printf '%s\n' "# started_utc: $start"
        printf '%s\n' "# exit_code: $rc"
        printf '%s\n' "# stdout"
        cat "$raw"
        printf '%s\n' "# stderr"
        cat "$err"
    } > "$OUT/.${name}.combined"
    redact "$OUT/.${name}.combined" "$out"
    rm -f "$raw" "$err" "$OUT/.${name}.combined"
    printf '%s\t%s\t%s\n' "$name" "$rc" "$start" >> "$MANIFEST"
    return 0
}

capture_priv() {
    name=$1
    shift
    if "$@" >/dev/null 2>&1; then
        capture "$name" "$@"
    elif have sudo; then
        capture "$name" sudo -n "$@"
    else
        capture "$name" "$@"
    fi
}

capture_identity() {
    {
        printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'hostname=%s\n' "$(hostname 2>/dev/null || true)"
        printf 'fqdn=%s\n' "$(hostname -f 2>/dev/null || true)"
        printf 'user=%s\n' "$(id -un 2>/dev/null || true)"
        printf 'uid=%s\n' "$(id -u 2>/dev/null || true)"
        printf 'groups=%s\n' "$(id -Gn 2>/dev/null || true)"
        printf 'kernel=%s\n' "$(uname -srmo 2>/dev/null || true)"
    } > "$OUT/identity.txt"
    printf '%s\t0\t%s\n' identity "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MANIFEST"
}

capture_git_repo() {
    label=$1
    repo=$2
    if [ -d "$repo/.git" ]; then
        capture "git-${label}-status" git -C "$repo" status --short --branch
        capture "git-${label}-head" git -C "$repo" rev-parse HEAD
        capture "git-${label}-remote" git -C "$repo" remote -v
    else
        printf 'repository_not_present=%s\n' "$repo" > "$OUT/git-${label}-status.txt"
        printf '%s\t2\t%s\n' "git-${label}-status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MANIFEST"
    fi
}

capture_identity
capture os-release cat /etc/os-release
capture disk df -h / /var /opt
capture memory free -h
capture network-addresses ip -brief address
capture network-routes ip route show table all
capture listeners ss -H -lntup
capture running-services systemctl --no-pager --plain list-units --type=service --state=running

capture_git_repo edge1 /opt/edge1-management-interface
capture_git_repo bigbird-ai /opt/bigbird-ai-gateway

for unit in apache2 asterisk kamailio mariadb mysql postgresql edge1-operations-api bigbird-ai-gateway; do
    capture "service-${unit}" systemctl show "$unit" \
        -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
        -p FragmentPath -p MainPID -p ExecMainStatus -p ActiveEnterTimestamp
 done

if have apache2ctl; then
    capture apache-version apache2ctl -v
    capture apache-build apache2ctl -V
    capture apache-modules apache2ctl -M
    capture apache-vhosts apache2ctl -S
    capture apache-configtest apache2ctl configtest
    capture apache-sites-enabled ls -la /etc/apache2/sites-enabled
fi

if have nft; then
    capture_priv nftables-ruleset nft list ruleset
fi

if have wg; then
    capture_priv wireguard-state wg show
fi

if have resolvectl; then
    capture resolver-state resolvectl status
fi
capture resolv-conf cat /etc/resolv.conf

if have asterisk; then
    capture_priv asterisk-uptime asterisk -rx 'core show uptime'
    capture_priv asterisk-channels asterisk -rx 'core show channels'
    capture_priv asterisk-pjsip-endpoints asterisk -rx 'pjsip show endpoints'
    capture_priv asterisk-pjsip-transports asterisk -rx 'pjsip show transports'
    capture_priv asterisk-pjsip-registrations asterisk -rx 'pjsip show registrations'
    capture_priv asterisk-http-status asterisk -rx 'http show status'
    capture_priv asterisk-ami-settings asterisk -rx 'manager show settings'
    capture_priv asterisk-ari-status asterisk -rx 'ari show status'
    capture_priv asterisk-rtp-settings asterisk -rx 'rtp show settings'
fi

if have kamcmd; then
    capture_priv kamailio-version kamcmd core.version
    capture_priv kamailio-uptime kamcmd core.uptime
    capture_priv kamailio-processes kamcmd core.ps
fi

if have fwconsole; then
    capture_priv freepbx-status fwconsole status
fi

capture process-names ps -eo pid,user,comm

if have curl; then
    capture edge1-root-local curl -sS -I --max-time 10 \
        --resolve edge1.ww.cx:443:127.0.0.1 https://edge1.ww.cx/
    capture edge1-freepbx-admin-local curl -sS -I --max-time 10 \
        --resolve edge1.ww.cx:443:127.0.0.1 https://edge1.ww.cx/admin/
    capture edge1-freepbx-ucp-local curl -sS -I --max-time 10 \
        --resolve edge1.ww.cx:443:127.0.0.1 https://edge1.ww.cx/ucp/
    capture operations-api-local curl -sS -D - -o /dev/null --max-time 5 http://127.0.0.1:8097/
    capture bigbird-ai-health-local curl -sS -D - -o /dev/null --max-time 5 http://127.0.0.1:8787/health
fi

if have openssl; then
    capture_stdin_null edge1-tls-local openssl s_client -brief \
        -connect 127.0.0.1:443 -servername edge1.ww.cx
fi

if have sha256sum; then
    sha256sum "$OUT"/*.txt "$MANIFEST" > "$OUT/SHA256SUMS"
fi

printf '%s\n' "evidence_dir=$OUT"
printf '%s\n' "manifest=$MANIFEST"
printf '%s\n' 'Inventory only: no configuration, firewall, listener, service, or telephony mutation was performed.'
