#!/bin/sh
set -eu
umask 077

EXPECTED_HOST="edge1.ww.cx"
EVIDENCE_DIR=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-host)
            [ "$#" -ge 2 ] || { echo "ERROR missing hostname" >&2; exit 2; }
            EXPECTED_HOST=$2
            shift 2
            ;;
        --evidence-dir)
            [ "$#" -ge 2 ] || { echo "ERROR missing evidence directory" >&2; exit 2; }
            EVIDENCE_DIR=$2
            shift 2
            ;;
        -h|--help)
            echo "Usage: sudo $0 --evidence-dir DIR [--expected-host HOST]"
            echo "Read-only Asterisk DTMF readiness and offline 16-key capability audit."
            exit 0
            ;;
        *)
            echo "ERROR unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR run with sudo" >&2; exit 2; }
[ -n "$EVIDENCE_DIR" ] || { echo "ERROR --evidence-dir is required" >&2; exit 2; }
case "$EVIDENCE_DIR" in
    /var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/*) ;;
    *)
        echo "ERROR evidence directory must be below /var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness" >&2
        exit 2
        ;;
esac

HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}

for command in asterisk awk date find grep hostname id install mkdir python3 sed sha256sum sort stat tail xargs; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OFFLINE_PROBE="$REPO_ROOT/tools/telephony/dtmf_offline_probe.py"

[ -f "$OFFLINE_PROBE" ] || {
    echo "ERROR offline probe is missing: $OFFLINE_PROBE" >&2
    exit 2
}

install -d -m 0700 "$EVIDENCE_DIR"

warnings=0
failures=0

warn() {
    warnings=$((warnings + 1))
    printf 'WARNING: %s\n' "$*"
}

fail() {
    failures=$((failures + 1))
    printf 'FAIL: %s\n' "$*"
}

section() {
    printf '\n=== %s ===\n' "$*"
}

sanitize_stream() {
    sed -E \
        -e 's#([sS][iI][pP][sS]?:)[^[:space:]>;,]+#\1[redacted]#g' \
        -e 's#PJSIP/[^[:space:]]+#PJSIP/[redacted]#g' \
        -e 's#[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}#[email]#g' \
        -e 's#([0-9]{1,3}\.){3}[0-9]{1,3}#[ip]#g' \
        -e 's#(^|[^0-9])[0-9]{7,}([^0-9]|$)#\1[number]\2#g' \
        -e 's#[A-Fa-f0-9]{32,}#[token]#g'
}

capture_asterisk() {
    name=$1
    command_text=$2
    output="$EVIDENCE_DIR/$name.txt"
    if asterisk -rx "$command_text" >"$output.raw" 2>&1; then
        sanitize_stream <"$output.raw" >"$output"
    else
        sanitize_stream <"$output.raw" >"$output"
        warn "Asterisk command did not return success: $command_text"
    fi
    rm -f "$output.raw"
}

parse_endpoint_policy() {
    file=$1
    awk '
        function trim(value) {
            sub(/^[[:space:]]+/, "", value)
            sub(/[[:space:]]+$/, "", value)
            return value
        }
        function reset_section() {
            active=0
            object_type=""
            dtmf_mode=""
            direct_media=""
            allow_count=0
            disallow_count=0
        }
        function flush() {
            if (!active || tolower(object_type) != "endpoint") return
            endpoint_count++
            mode=tolower(trim(dtmf_mode))
            if (mode == "") mode="implicit-rfc4733"
            media=tolower(trim(direct_media))
            if (media == "") media="implicit-default"
            printf "source=%s endpoint_index=%d dtmf_mode=%s direct_media=%s allow_entries=%d disallow_entries=%d\n", FILENAME, endpoint_count, mode, media, allow_count, disallow_count
        }
        BEGIN {reset_section()}
        /^[[:space:]]*[#;]/ {next}
        /^[[:space:]]*\[[^]]+\][[:space:]]*(!)?[[:space:]]*$/ {
            flush()
            reset_section()
            active=1
            next
        }
        !active {next}
        /^[[:space:]]*type[[:space:]]*=/ {
            value=$0
            sub(/^[^=]*=/, "", value)
            object_type=trim(value)
            next
        }
        /^[[:space:]]*dtmf_mode[[:space:]]*=/ {
            value=$0
            sub(/^[^=]*=/, "", value)
            dtmf_mode=trim(value)
            next
        }
        /^[[:space:]]*direct_media[[:space:]]*=/ {
            value=$0
            sub(/^[^=]*=/, "", value)
            direct_media=trim(value)
            next
        }
        /^[[:space:]]*allow[[:space:]]*=/ {allow_count++; next}
        /^[[:space:]]*disallow[[:space:]]*=/ {disallow_count++; next}
        END {flush()}
    ' "$file"
}

count_dialplan_token() {
    file=$1
    label=$2
    pattern=$3
    count=$(grep -Eic "$pattern" "$file" 2>/dev/null || true)
    printf 'source=%s token=%s count=%s\n' "$file" "$label" "$count"
}

printf 'WW.CX ASTERISK DTMF READINESS AUDIT\n'
printf 'Host: %s\n' "$HOST"
printf 'Time: %s\n' "$(date -Is)"
printf '%s\n' 'Mode: read-only runtime/configuration inventory plus offline synthetic generation/detection; no channel, call, tone transmission, SIP request, dialplan, service, module, endpoint, route, carrier, firewall, package, or configuration change'
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"

section "CORE AND CHANNEL STATE"
capture_asterisk "asterisk-version" "core show version"
capture_asterisk "asterisk-uptime" "core show uptime"
capture_asterisk "asterisk-channels-count" "core show channels count"
cat "$EVIDENCE_DIR/asterisk-version.txt"
cat "$EVIDENCE_DIR/asterisk-uptime.txt"
cat "$EVIDENCE_DIR/asterisk-channels-count.txt"

section "DTMF MODULE INVENTORY"
for module_query in app_senddtmf app_playtones app_read func_pjsip res_pjsip_sdp_rtp res_rtp_asterisk dsp; do
    safe_name=$(printf '%s' "$module_query" | tr -c 'A-Za-z0-9._-' '_')
    capture_asterisk "module-$safe_name" "module show like $module_query"
    cat "$EVIDENCE_DIR/module-$safe_name.txt"
done

if ! grep -Eqi 'app_senddtmf[^[:space:]]*\.so|1 modules loaded' "$EVIDENCE_DIR/module-app_senddtmf.txt"; then
    fail "app_senddtmf runtime capability was not confirmed"
fi
if ! grep -Eqi 'res_pjsip_sdp_rtp[^[:space:]]*\.so|1 modules loaded' "$EVIDENCE_DIR/module-res_pjsip_sdp_rtp.txt"; then
    fail "res_pjsip_sdp_rtp runtime capability was not confirmed"
fi
if ! grep -Eqi 'res_rtp_asterisk[^[:space:]]*\.so|1 modules loaded' "$EVIDENCE_DIR/module-res_rtp_asterisk.txt"; then
    fail "res_rtp_asterisk runtime capability was not confirmed"
fi

section "READ-ONLY CLI CAPABILITY HELP"
capture_asterisk "application-senddtmf" "core show application SendDTMF"
capture_asterisk "application-read" "core show application Read"
capture_asterisk "function-pjsip-dtmf-mode" "core show function PJSIP_DTMF_MODE"
capture_asterisk "function-pjsip-endpoint" "core show function PJSIP_ENDPOINT"
cat "$EVIDENCE_DIR/application-senddtmf.txt"
cat "$EVIDENCE_DIR/function-pjsip-dtmf-mode.txt"

if grep -Eq '0-9|0.*9' "$EVIDENCE_DIR/application-senddtmf.txt" && \
   grep -Eqi 'A-D|a-d' "$EVIDENCE_DIR/application-senddtmf.txt"; then
    echo "PASS: runtime SendDTMF help advertises standard digits and extended A-D"
else
    warn "runtime SendDTMF help did not clearly advertise the complete 16-key set"
fi

section "PJSIP ENDPOINT DTMF POLICY"
: >"$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt"
config_count=0
for file in /etc/asterisk/pjsip*.conf; do
    [ -f "$file" ] || continue
    config_count=$((config_count + 1))
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" >>"$EVIDENCE_DIR/asterisk-config-metadata.txt"
    sha256sum "$file" >>"$EVIDENCE_DIR/asterisk-config.sha256"
    parse_endpoint_policy "$file" >>"$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt"
done

if [ "$config_count" -eq 0 ]; then
    warn "no pjsip configuration files were found"
fi

cat "$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt"
endpoint_count=$(grep -Ec ' endpoint_index=' "$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt" || true)
printf 'endpoint_policy_records=%s\n' "$endpoint_count"

if [ "$endpoint_count" -eq 0 ]; then
    warn "no endpoint DTMF policy records were found; carrier path capability remains unverified"
fi

invalid_modes=$(awk '
    {
        for (field=1; field<=NF; field++) {
            if ($field ~ /^dtmf_mode=/) {
                split($field, pair, "=")
                mode=pair[2]
                if (mode != "rfc4733" && mode != "inband" && mode != "info" && mode != "auto" && mode != "auto_info" && mode != "implicit-rfc4733") print mode
            }
        }
    }
' "$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt" | sort -u)
if [ -n "$invalid_modes" ]; then
    printf '%s\n' "$invalid_modes"
    fail "one or more endpoint DTMF modes were not recognized"
fi

for mode in rfc4733 inband info auto auto_info implicit-rfc4733; do
    count=$(grep -Ec "dtmf_mode=$mode([[:space:]]|$)" "$EVIDENCE_DIR/pjsip-endpoint-dtmf-policy.txt" || true)
    printf 'dtmf_mode_%s=%s\n' "$mode" "$count" | tr '-' '_'
done

section "DIALPLAN DTMF USAGE COUNTS"
: >"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
for file in /etc/asterisk/extensions*.conf; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" >>"$EVIDENCE_DIR/asterisk-config-metadata.txt"
    sha256sum "$file" >>"$EVIDENCE_DIR/asterisk-config.sha256"
    count_dialplan_token "$file" "SendDTMF" 'SendDTMF[[:space:]]*\(' >>"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
    count_dialplan_token "$file" "PJSIP_DTMF_MODE" 'PJSIP_DTMF_MODE[[:space:]]*\(' >>"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
    count_dialplan_token "$file" "Read" 'Read[[:space:]]*\(' >>"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
    count_dialplan_token "$file" "WaitExten" 'WaitExten[[:space:]]*\(' >>"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
    count_dialplan_token "$file" "Background" 'Background[[:space:]]*\(' >>"$EVIDENCE_DIR/dialplan-dtmf-usage.txt"
done
cat "$EVIDENCE_DIR/dialplan-dtmf-usage.txt"

section "OFFLINE COMPLETE 16-KEY PROBE"
python3 "$OFFLINE_PROBE" --json >"$EVIDENCE_DIR/offline-dtmf-probe.json" || fail "offline DTMF probe failed"
python3 "$OFFLINE_PROBE" >"$EVIDENCE_DIR/offline-dtmf-probe.txt" || true
cat "$EVIDENCE_DIR/offline-dtmf-probe.txt"

if grep -Fq '"audit_state": "PASS"' "$EVIDENCE_DIR/offline-dtmf-probe.json" && \
   grep -Fq '"digits_tested": 16' "$EVIDENCE_DIR/offline-dtmf-probe.json"; then
    echo "PASS: all 16 DTMF keys were generated and detected offline"
else
    fail "offline probe did not confirm all 16 DTMF keys"
fi

section "CAPABILITY DECISION"
echo "local_senddtmf_application=inspected"
echo "local_rfc4733_implementation=inspected"
echo "rfc4733_event_range=0-15"
echo "standard_digits=0-9,*#"
echo "extended_digits=A-D"
echo "sip_info_policy=inventory_only"
echo "inband_policy=inventory_only"
echo "carrier_interconnect_capability=unverified"
echo "live_negotiation=not_tested"
echo "live_receive_path=not_tested"
echo "live_send_path=not_tested"
echo "call_originated=no"
echo "channel_created=no"
echo "tone_transmitted=no"

find "$EVIDENCE_DIR" -maxdepth 1 -type f ! -name 'evidence-files.sha256' -print0 2>/dev/null |
    sort -z |
    xargs -0 sha256sum >"$EVIDENCE_DIR/evidence-files.sha256" 2>/dev/null || true

section "RESULT"
printf 'Warnings: %s\n' "$warnings"
printf 'Failures: %s\n' "$failures"
if [ "$failures" -ne 0 ]; then
    echo "Audit state: FAILED"
    exit 1
fi

if [ "$warnings" -ne 0 ]; then
    echo "Audit state: READ-ONLY REVIEW COMPLETE WITH WARNINGS"
else
    echo "Audit state: READ-ONLY REVIEW COMPLETE"
fi

echo "No channel, call, tone transmission, SIP request, dialplan, service, module, endpoint, route, carrier, firewall, package, or configuration change was performed."
