#!/bin/sh
set -eu

SERVICE_USER=business159-operator
POLICY_DIR=/etc/business159-operator
POLICY_FILE=$POLICY_DIR/runtime-policy
MODE=${1:-status}

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "$SERVICE_USER account missing" >&2; exit 2; }

write_policy() {
    filesystem_value=$1
    tmp=$(mktemp "$POLICY_DIR/.runtime-policy.XXXXXX")
    trap 'rm -f "$tmp"' EXIT HUP INT TERM
    cat >"$tmp" <<EOF
BUSINESS159_ALLOW_DEPLOY=0
BUSINESS159_ALLOW_FILESYSTEM=$filesystem_value
BUSINESS159_ENABLE_RAW_SHELL=0
EOF
    chown root:"$SERVICE_USER" "$tmp"
    chmod 0640 "$tmp"
    mv -f "$tmp" "$POLICY_FILE"
    trap - EXIT HUP INT TERM
}

case "$MODE" in
    enable)
        write_policy 1
        echo "Business159 staged-filesystem smoke mode enabled in runtime policy; deployment apply and raw shell remain disabled. Restart the dedicated Business159 tunnel service for this policy to take effect."
        ;;
    disable)
        write_policy 0
        echo "Business159 staged-filesystem smoke mode disabled in runtime policy. Restart the dedicated Business159 tunnel service for this policy to take effect."
        ;;
    status)
        if [ ! -e "$POLICY_FILE" ]; then
            echo "Business159 runtime policy absent; all mutation gates default to disabled."
            exit 0
        fi
        owner=$(stat -c '%U:%G' "$POLICY_FILE")
        mode=$(stat -c '%a' "$POLICY_FILE")
        [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "unsafe owner/mode for $POLICY_FILE: $owner $mode" >&2; exit 3; }
        cat "$POLICY_FILE"
        ;;
    *)
        echo "usage: $0 {enable|disable|status}" >&2
        exit 4
        ;;
esac
