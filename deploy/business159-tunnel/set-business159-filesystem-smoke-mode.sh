#!/bin/sh
set -eu

SERVICE_USER=business159-operator
POLICY_DIR=/etc/business159-operator
POLICY_FILE=$POLICY_DIR/runtime-policy
MODE=${1:-status}

[ "$(id -u)" -eq 0 ] || { echo "run with sudo/root" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "$SERVICE_USER account missing" >&2; exit 2; }
[ -d "$POLICY_DIR" ] && [ ! -L "$POLICY_DIR" ] || { echo "runtime policy directory unavailable or unsafe: $POLICY_DIR" >&2; exit 3; }
dir_owner=$(stat -c '%U:%G' "$POLICY_DIR")
dir_mode=$(stat -c '%a' "$POLICY_DIR")
[ "$dir_owner" = root:$SERVICE_USER ] && [ "$dir_mode" = 750 ] || { echo "unsafe owner/mode for $POLICY_DIR: $dir_owner $dir_mode" >&2; exit 4; }

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
        [ ! -L "$POLICY_FILE" ] && [ -f "$POLICY_FILE" ] || { echo "runtime policy must be a regular non-symlink file: $POLICY_FILE" >&2; exit 5; }
        owner=$(stat -c '%U:%G' "$POLICY_FILE")
        mode=$(stat -c '%a' "$POLICY_FILE")
        [ "$owner" = root:$SERVICE_USER ] && [ "$mode" = 640 ] || { echo "unsafe owner/mode for $POLICY_FILE: $owner $mode" >&2; exit 6; }
        cat "$POLICY_FILE"
        ;;
    *)
        echo "usage: $0 {enable|disable|status}" >&2
        exit 7
        ;;
esac
