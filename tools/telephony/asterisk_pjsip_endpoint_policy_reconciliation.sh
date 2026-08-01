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
            echo "Read-only reconciliation of Asterisk PJSIP runtime visibility and generated endpoint policy."
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
    /var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/*) ;;
    *)
        echo "ERROR evidence directory must be below /var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy" >&2
        exit 2
        ;;
esac

HOST=$(hostname -f)
[ "$HOST" = "$EXPECTED_HOST" ] || {
    echo "ERROR expected $EXPECTED_HOST, found $HOST" >&2
    exit 2
}

for command in asterisk awk date find grep hostname id install sed sha256sum sort stat tail tr wc xargs; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "ERROR missing command: $command" >&2
        exit 2
    }
done

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
        -e 's#^([[:space:]]*Endpoint:)[[:space:]]+[^[:space:]]+#\1 [redacted]#g' \
        -e 's#^([[:space:]]*Aor:)[[:space:]]+[^[:space:]]+#\1 [redacted]#g' \
        -e 's#^([[:space:]]*Contact:)[[:space:]]+[^[:space:]]+#\1 [redacted]#g' \
        -e 's#^([[:space:]]*Transport:)[[:space:]]+[^[:space:]]+#\1 [redacted]#g' \
        -e 's#([sS][iI][pP][sS]?:)[^[:space:]>;,]+#\1[redacted]#g' \
        -e 's#PJSIP/[^[:space:]]+#PJSIP/[redacted]#g' \
        -e 's#[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}#[email]#g' \
        -e 's#([0-9]{1,3}\.){3}[0-9]{1,3}#[ip]#g' \
        -e 's#(^|[^0-9])[0-9]{7,}([^0-9]|$)#\1[number]\2#g' \
        -e 's#[A-Fa-f0-9]{32,}#[token]#g' \
        -e 's#^([[:space:]]*(username|password|secret|auth|outbound_auth)[[:space:]]*=).*#\1[redacted]#Ig'
}

capture_asterisk() {
    name=$1
    command_text=$2
    output="$EVIDENCE_DIR/$name.txt"
    if asterisk -rx "$command_text" 2>&1 | sanitize_stream >"$output"; then
        return 0
    fi
    warn "Asterisk command did not return success: $command_text"
    return 0
}

object_count() {
    file=$1
    if grep -Fq 'No objects found' "$file"; then
        echo 0
        return 0
    fi
    value=$(awk '/Objects found:/ {count=$NF} END {if (count ~ /^[0-9]+$/) print count}' "$file")
    if [ -n "$value" ]; then
        echo "$value"
    else
        echo unknown
    fi
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
            transport_set=0
            auth_set=0
            outbound_auth_set=0
            aors_set=0
            context_set=0
            allow_count=0
            disallow_count=0
        }
        function yn(value) {
            return value ? "yes" : "no"
        }
        function flush() {
            if (!active || tolower(trim(object_type)) != "endpoint") return
            endpoint_count++
            mode=tolower(trim(dtmf_mode))
            if (mode == "") mode="implicit-rfc4733"
            media=tolower(trim(direct_media))
            if (media == "") media="implicit-default"
            printf "source=%s endpoint_index=%d dtmf_mode=%s direct_media=%s transport_set=%s auth_set=%s outbound_auth_set=%s aors_set=%s context_set=%s allow_entries=%d disallow_entries=%d\n", FILENAME, endpoint_count, mode, media, yn(transport_set), yn(auth_set), yn(outbound_auth_set), yn(aors_set), yn(context_set), allow_count, disallow_count
        }
        BEGIN {reset_section()}
        /^[[:space:]]*[#;]/ {next}
        /^[[:space:]]*\[[^]]+\][[:space:]]*(\([^)]*\))?[[:space:]]*$/ {
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
        /^[[:space:]]*transport[[:space:]]*=/ {transport_set=1; next}
        /^[[:space:]]*auth[[:space:]]*=/ {auth_set=1; next}
        /^[[:space:]]*outbound_auth[[:space:]]*=/ {outbound_auth_set=1; next}
        /^[[:space:]]*aors[[:space:]]*=/ {aors_set=1; next}
        /^[[:space:]]*context[[:space:]]*=/ {context_set=1; next}
        /^[[:space:]]*allow[[:space:]]*=/ {allow_count++; next}
        /^[[:space:]]*disallow[[:space:]]*=/ {disallow_count++; next}
        END {flush()}
    ' "$file"
}

printf 'WW.CX ASTERISK PJSIP ENDPOINT POLICY RECONCILIATION\n'
printf 'Host: %s\n' "$HOST"
printf 'Time: %s\n' "$(date -Is)"
printf '%s\n' 'Mode: read-only runtime and generated-configuration reconciliation; no channel, call, DTMF transmission, SIP request, database query, configuration, service, module, endpoint, trunk, route, carrier, firewall, package, or certificate change'
printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"

section "CORE AND ZERO-CALL STATE"
capture_asterisk "asterisk-version" "core show version"
capture_asterisk "asterisk-uptime" "core show uptime"
capture_asterisk "asterisk-channels-count" "core show channels count"
cat "$EVIDENCE_DIR/asterisk-version.txt"
cat "$EVIDENCE_DIR/asterisk-uptime.txt"
cat "$EVIDENCE_DIR/asterisk-channels-count.txt"

if ! grep -Eq '0 active channels' "$EVIDENCE_DIR/asterisk-channels-count.txt" || \
   ! grep -Eq '0 active calls' "$EVIDENCE_DIR/asterisk-channels-count.txt"; then
    fail "zero-call safety gate was not satisfied"
fi

section "PJSIP MODULE AND RUNTIME OBJECT VISIBILITY"
capture_asterisk "module-chan-pjsip" "module show like chan_pjsip"
capture_asterisk "module-res-pjsip" "module show like res_pjsip"
capture_asterisk "pjsip-endpoints" "pjsip show endpoints"
capture_asterisk "pjsip-aors" "pjsip show aors"
capture_asterisk "pjsip-contacts" "pjsip show contacts"
capture_asterisk "pjsip-transports" "pjsip show transports"

runtime_endpoints=$(object_count "$EVIDENCE_DIR/pjsip-endpoints.txt")
runtime_aors=$(object_count "$EVIDENCE_DIR/pjsip-aors.txt")
runtime_contacts=$(object_count "$EVIDENCE_DIR/pjsip-contacts.txt")
runtime_transports=$(object_count "$EVIDENCE_DIR/pjsip-transports.txt")

printf 'runtime_endpoint_count=%s\n' "$runtime_endpoints"
printf 'runtime_aor_count=%s\n' "$runtime_aors"
printf 'runtime_contact_count=%s\n' "$runtime_contacts"
printf 'runtime_transport_count=%s\n' "$runtime_transports"

if [ "$runtime_endpoints" = "unknown" ]; then
    warn "runtime endpoint count could not be parsed"
elif [ "$runtime_endpoints" -eq 0 ]; then
    warn "PJSIP runtime registry exposes no endpoints"
fi

section "GENERATED PJSIP INCLUDE GRAPH"
: >"$EVIDENCE_DIR/pjsip-include-graph.txt"
for file in /etc/asterisk/pjsip.conf /etc/asterisk/pjsip*.conf; do
    [ -f "$file" ] || continue
    awk '
        /^[[:space:]]*#(include|tryinclude)[[:space:]]+/ {
            print FILENAME ":" FNR ":" $1 " " $2
        }
    ' "$file" >>"$EVIDENCE_DIR/pjsip-include-graph.txt"
done
sort -u "$EVIDENCE_DIR/pjsip-include-graph.txt" -o "$EVIDENCE_DIR/pjsip-include-graph.txt"
cat "$EVIDENCE_DIR/pjsip-include-graph.txt"

section "GENERATED ENDPOINT POLICY SUMMARY"
: >"$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt"
: >"$EVIDENCE_DIR/pjsip-config-metadata.txt"
: >"$EVIDENCE_DIR/pjsip-config.sha256"
config_files=0
for file in /etc/asterisk/pjsip*.conf; do
    [ -f "$file" ] || continue
    config_files=$((config_files + 1))
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" >>"$EVIDENCE_DIR/pjsip-config-metadata.txt"
    sha256sum "$file" >>"$EVIDENCE_DIR/pjsip-config.sha256"
    parse_endpoint_policy "$file" >>"$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt"
done

printf 'pjsip_config_files=%s\n' "$config_files"
config_endpoints=$(grep -Ec ' endpoint_index=' "$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt" || true)
printf 'generated_endpoint_policy_count=%s\n' "$config_endpoints"
cat "$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt"

if [ "$config_files" -eq 0 ]; then
    fail "no generated PJSIP configuration files were found"
elif [ "$config_endpoints" -eq 0 ]; then
    warn "generated PJSIP configuration contains no explicit endpoint policy records"
fi

for mode in rfc4733 inband info auto auto_info implicit-rfc4733; do
    count=$(grep -Ec "dtmf_mode=$mode([[:space:]]|$)" "$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt" || true)
    printf 'generated_dtmf_mode_%s=%s\n' "$mode" "$count" | tr '-' '_'
done

unknown_modes=$(awk '
    {
        for (field=1; field<=NF; field++) {
            if ($field ~ /^dtmf_mode=/) {
                split($field, pair, "=")
                mode=pair[2]
                if (mode != "rfc4733" && mode != "inband" && mode != "info" && mode != "auto" && mode != "auto_info" && mode != "implicit-rfc4733") print mode
            }
        }
    }
' "$EVIDENCE_DIR/pjsip-endpoint-policy-summary.txt" | sort -u)
if [ -n "$unknown_modes" ]; then
    printf '%s\n' "$unknown_modes" >"$EVIDENCE_DIR/unrecognized-dtmf-modes.txt"
    warn "one or more generated endpoint DTMF modes were not recognized"
fi

section "RUNTIME TO GENERATED POLICY COMPARISON"
if [ "$runtime_endpoints" = "unknown" ]; then
    comparison="indeterminate"
elif [ "$runtime_endpoints" -eq "$config_endpoints" ]; then
    comparison="counts-match"
else
    comparison="counts-differ"
    warn "runtime endpoint count differs from generated explicit endpoint-policy count"
fi
printf 'endpoint_count_comparison=%s\n' "$comparison"

if [ "$runtime_endpoints" != "unknown" ] && [ "$runtime_endpoints" -eq 0 ] && [ "$config_endpoints" -eq 0 ]; then
    printf '%s\n' 'reconciliation_state=no-runtime-or-generated-endpoints-observed'
elif [ "$runtime_endpoints" != "unknown" ] && [ "$runtime_endpoints" -gt 0 ] && [ "$config_endpoints" -gt 0 ]; then
    printf '%s\n' 'reconciliation_state=runtime-and-generated-endpoints-observed'
else
    printf '%s\n' 'reconciliation_state=partial-or-indeterminate'
fi

section "FREEPBX SOURCE BOUNDARY"
if command -v fwconsole >/dev/null 2>&1; then
    fwconsole --version 2>&1 | sanitize_stream >"$EVIDENCE_DIR/fwconsole-version.txt" || true
    cat "$EVIDENCE_DIR/fwconsole-version.txt"
    echo "freepbx_cli=present"
else
    echo "freepbx_cli=absent"
    warn "fwconsole was not found"
fi

: >"$EVIDENCE_DIR/freepbx-source-metadata.txt"
: >"$EVIDENCE_DIR/freepbx-source.sha256"
for file in /etc/freepbx.conf /etc/amportal.conf; do
    [ -f "$file" ] || continue
    stat -c 'mode=%a owner=%U group=%G bytes=%s path=%n' "$file" >>"$EVIDENCE_DIR/freepbx-source-metadata.txt"
    sha256sum "$file" >>"$EVIDENCE_DIR/freepbx-source.sha256"
done
cat "$EVIDENCE_DIR/freepbx-source-metadata.txt"
echo "freepbx_source_content=not_read"
echo "freepbx_database_content=not_queried"

section "CAPABILITY AND EVIDENCE DECISION"
printf 'runtime_endpoint_visibility=%s\n' "$runtime_endpoints"
printf 'generated_endpoint_policy_visibility=%s\n' "$config_endpoints"
echo "endpoint_identifiers_retained=no"
echo "credential_values_read=no"
echo "database_query_performed=no"
echo "carrier_interconnect_capability=unverified"
echo "live_sdp_negotiation=not_tested"
echo "live_dtmf_receive_path=not_tested"
echo "live_dtmf_send_path=not_tested"
echo "call_originated=no"
echo "channel_created=no"
echo "tone_transmitted=no"
echo "runtime_mutation=none"

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
    echo "Audit state: READ-ONLY RECONCILIATION COMPLETE WITH WARNINGS"
else
    echo "Audit state: READ-ONLY RECONCILIATION COMPLETE"
fi

echo "No channel, call, DTMF transmission, SIP request, database query, configuration, service, module, endpoint, trunk, route, carrier, firewall, package, or certificate change was performed."
