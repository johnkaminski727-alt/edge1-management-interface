#!/bin/bash

set -u

REPO_ROOT=/opt/edge1-management-interface
ROOT=/usr/local/libexec/ava-physical-effects
RELEASES=$ROOT/releases
CURRENT=$ROOT/current
UNIT_SOURCE=deploy/ava-physical-effects/ava-physical-effects-broker.service
UNIT_TARGET=/etc/systemd/system/ava-physical-effects-broker.service
EVIDENCE_ROOT=/var/lib/wwcx-deployment-evidence/ava-physical-effects
EXPECTED_COMMIT=
APPLY=0

usage() {
    echo "usage: sudo bash $0 --expected-commit <40-hex-sha> [--apply]" >&2
}

fail() {
    echo "FAIL: $*" >&2
    return 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-commit)
            [ "$#" -ge 2 ] || {
                usage
                false
            }
            EXPECTED_COMMIT=$2
            shift 2
            ;;
        --apply)
            APPLY=1
            shift
            ;;
        *)
            usage
            false
            ;;
    esac
done

OK=1

if ! printf '%s\n' "$EXPECTED_COMMIT" |
     grep -Eq '^[0-9a-f]{40}$'
then
    echo "FAIL: full expected commit is required."
    OK=0
fi

HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"

if [ "$HEAD" != "$EXPECTED_COMMIT" ]; then
    echo "FAIL: HEAD does not match expected commit."
    echo "expected=$EXPECTED_COMMIT"
    echo "actual=$HEAD"
    OK=0
fi

FILES="
server/ava_physical_effects.py
server/ava_physical_effects_broker.py
server/ava_physical_effects_protocol.py
server/ava_physical_effects_transport.py
server/ava_physical_effects_state.py
server/ava_physical_effects_daemon.py
$UNIT_SOURCE
"

echo "=================================================="
echo " AVA PHYSICAL EFFECTS — INERT BROKER INSTALLER"
echo " expected_commit=$EXPECTED_COMMIT"
echo " apply=$APPLY"
echo "=================================================="

echo
echo "=== COMMITTED SOURCE VERIFICATION ==="

for FILE in $FILES; do
    if git -C "$REPO_ROOT" cat-file -e \
        "$EXPECTED_COMMIT:$FILE" 2>/dev/null
    then
        echo "PASS: $FILE"
    else
        echo "FAIL: committed source missing: $FILE"
        OK=0
    fi
done

echo
echo "=== COMMITTED SAFETY CONTRACT ==="

DAEMON="$(
    git -C "$REPO_ROOT" show \
        "$EXPECTED_COMMIT:server/ava_physical_effects_daemon.py" \
        2>/dev/null || true
)"

if printf '%s\n' "$DAEMON" |
   grep -Fq 'enabled=False'
then
    echo "PASS: broker master-disabled"
else
    echo "FAIL: broker is not provably master-disabled"
    OK=0
fi

if printf '%s\n' "$DAEMON" |
   grep -Fq 'durable_ledger=self.ledger'
then
    echo "PASS: durable reservation ledger wired"
else
    echo "FAIL: durable reservation ledger is not wired"
    OK=0
fi

if printf '%s\n' "$DAEMON" |
   grep -Eq '/dev/input|event[0-9]+|SND_TONE|EV_SND|subprocess|os\.system|shell=True'
then
    echo "FAIL: daemon contains prohibited execution/hardware primitive"
    OK=0
else
    echo "PASS: no hardware executor in daemon"
fi

UNIT="$(
    git -C "$REPO_ROOT" show \
        "$EXPECTED_COMMIT:$UNIT_SOURCE" \
        2>/dev/null || true
)"

for CONTRACT in \
    'PrivateDevices=true' \
    'RestrictAddressFamilies=AF_UNIX' \
    'CapabilityBoundingSet=' \
    'AmbientCapabilities=' \
    'NoNewPrivileges=true' \
    'StateDirectory=ava-physical-effects' \
    'StateDirectoryMode=0700'
do
    if printf '%s\n' "$UNIT" | grep -Fqx "$CONTRACT"; then
        echo "PASS: $CONTRACT"
    else
        echo "FAIL: unit missing $CONTRACT"
        OK=0
    fi
done

if printf '%s\n' "$UNIT" | grep -Fq 'DeviceAllow='; then
    echo "FAIL: inert unit must not grant device access"
    OK=0
else
    echo "PASS: no DeviceAllow"
fi

echo
echo "=== INSTALLER MODE ==="

if [ "$OK" -ne 1 ]; then
    echo "INSTALLER PREFLIGHT: FAIL"
elif [ "$APPLY" -ne 1 ]; then
    echo "INSTALLER PREFLIGHT: PASS"
    echo "DRY RUN ONLY — no mutation performed."
else
    if [ "$(id -u)" -ne 0 ]; then
        echo "FAIL: --apply requires root."
        OK=0
    fi

    if [ "$OK" -eq 1 ]; then
        STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
        RELEASE="$RELEASES/$EXPECTED_COMMIT"
        EVID="$EVIDENCE_ROOT/$STAMP"

        mkdir -p "$RELEASE/server" "$EVID"
        chmod 0755 "$ROOT" "$RELEASES" "$RELEASE" "$RELEASE/server"
        chmod 0700 "$EVID"

        for FILE in \
            server/ava_physical_effects.py \
            server/ava_physical_effects_broker.py \
            server/ava_physical_effects_protocol.py \
            server/ava_physical_effects_transport.py \
            server/ava_physical_effects_state.py \
            server/ava_physical_effects_daemon.py
        do
            TARGET="$RELEASE/$FILE"

            git -C "$REPO_ROOT" show \
                "$EXPECTED_COMMIT:$FILE" > "$TARGET" || {
                    echo "FAIL: extraction failed: $FILE"
                    OK=0
                    break
                }

            chown root:root "$TARGET"
            chmod 0644 "$TARGET"
        done

        if [ "$OK" -eq 1 ]; then
            git -C "$REPO_ROOT" show \
                "$EXPECTED_COMMIT:$UNIT_SOURCE" > "$UNIT_TARGET" || OK=0
        fi

        if [ "$OK" -eq 1 ]; then
            chown root:root "$UNIT_TARGET"
            chmod 0644 "$UNIT_TARGET"

            PREVIOUS=""
            if [ -L "$CURRENT" ]; then
                PREVIOUS="$(readlink "$CURRENT" || true)"
            fi

            printf '%s\n' "$PREVIOUS" > "$EVID/current.before.txt"

            TMP_LINK="$ROOT/.current-$STAMP"
            ln -s "releases/$EXPECTED_COMMIT" "$TMP_LINK" &&
            mv -Tf "$TMP_LINK" "$CURRENT" || OK=0
        fi

        if [ "$OK" -eq 1 ]; then
            cat > "$EVID/rollback.sh" <<ROLLBACK
#!/bin/bash
set -u

systemctl stop ava-physical-effects-broker.service 2>/dev/null || true

PREVIOUS=\$(cat '$EVID/current.before.txt' 2>/dev/null || true)

if [ -n "\$PREVIOUS" ]; then
    TMP='$ROOT/.rollback-current'
    rm -f "\$TMP"
    ln -s "\$PREVIOUS" "\$TMP"
    mv -Tf "\$TMP" '$CURRENT'

    systemctl daemon-reload

    if systemctl restart ava-physical-effects-broker.service; then
        ROLLBACK_PID=""
        ROLLBACK_CWD=""
        EXPECTED_ROLLBACK=\$(
            readlink -f '$CURRENT' 2>/dev/null || true
        )

        for ATTEMPT in 1 2 3 4 5 6 7 8 9 10; do
            ROLLBACK_PID=\$(
                systemctl show ava-physical-effects-broker.service \
                    --property=MainPID --value 2>/dev/null || true
            )

            if [ -n "\$ROLLBACK_PID" ] &&
               [ "\$ROLLBACK_PID" != "0" ] &&
               systemctl is-active --quiet \
                   ava-physical-effects-broker.service
            then
                ROLLBACK_CWD=\$(
                    readlink -f \
                        "/proc/\$ROLLBACK_PID/cwd" \
                        2>/dev/null || true
                )

                if [ "\$ROLLBACK_CWD" = "\$EXPECTED_ROLLBACK" ]; then
                    break
                fi
            fi

            sleep 0.2
        done

        if [ -n "\$ROLLBACK_PID" ] &&
           [ "\$ROLLBACK_PID" != "0" ] &&
           [ "\$ROLLBACK_CWD" = "\$EXPECTED_ROLLBACK" ]
        then
            echo "PASS: rollback broker uses restored immutable release"
        else
            echo "FAIL: rollback broker release mismatch"
            echo "rollback_pid=\$ROLLBACK_PID"
            echo "rollback_cwd=\$ROLLBACK_CWD"
            echo "expected_rollback=\$EXPECTED_ROLLBACK"
            exit 1
        fi
    else
        echo "FAIL: rollback broker restart failed"
        exit 1
    fi
else
    systemctl disable ava-physical-effects-broker.service 2>/dev/null || true
    rm -f '$UNIT_TARGET'
    rm -f '$CURRENT'
    systemctl daemon-reload
fi

echo "AVA physical effects inert broker rollback complete."
ROLLBACK

            chmod 0700 "$EVID/rollback.sh"

            systemctl daemon-reload || OK=0
        fi

        if [ "$OK" -eq 1 ]; then
            systemctl enable \
                ava-physical-effects-broker.service || OK=0
        fi

        if [ "$OK" -eq 1 ]; then
            BEFORE_PID="$(
                systemctl show \
                    ava-physical-effects-broker.service \
                    --property=MainPID \
                    --value 2>/dev/null || true
            )"

            systemctl restart \
                ava-physical-effects-broker.service || OK=0
        fi

        if [ "$OK" -eq 1 ]; then
            sleep 1

            AFTER_PID="$(
                systemctl show \
                    ava-physical-effects-broker.service \
                    --property=MainPID \
                    --value 2>/dev/null || true
            )"

            if systemctl is-active --quiet \
                ava-physical-effects-broker.service
            then
                echo "PASS: broker active"
            else
                echo "FAIL: broker inactive"
                OK=0
            fi

            if [ -n "$AFTER_PID" ] &&
               [ "$AFTER_PID" != "0" ] &&
               [ "$AFTER_PID" != "$BEFORE_PID" ]
            then
                echo "PASS: broker process restarted"
            else
                echo "FAIL: broker process did not restart"
                echo "before_pid=$BEFORE_PID"
                echo "after_pid=$AFTER_PID"
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            INSTALLED_STATE="$(
                systemctl show \
                    ava-physical-effects-broker.service \
                    --property=StateDirectory \
                    --value 2>/dev/null || true
            )"

            INSTALLED_STATE_MODE="$(
                systemctl show \
                    ava-physical-effects-broker.service \
                    --property=StateDirectoryMode \
                    --value 2>/dev/null || true
            )"

            if [ "$INSTALLED_STATE" = "ava-physical-effects" ]; then
                echo "PASS: installed StateDirectory"
            else
                echo "FAIL: installed StateDirectory mismatch"
                echo "state_directory=$INSTALLED_STATE"
                OK=0
            fi

            if [ "$INSTALLED_STATE_MODE" = "0700" ]; then
                echo "PASS: installed StateDirectoryMode 0700"
            else
                echo "FAIL: installed StateDirectoryMode mismatch"
                echo "state_directory_mode=$INSTALLED_STATE_MODE"
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            STATE_DIR=/var/lib/ava-physical-effects

            if [ "$(stat -c '%U:%G:%a' "$STATE_DIR" 2>/dev/null)" = \
                 "root:bigbird-ai:700" ]
            then
                echo "PASS: state directory root:bigbird-ai 0700"
            else
                echo "FAIL: state directory ownership/mode mismatch"
                stat -c '%U:%G:%a %n' "$STATE_DIR" 2>/dev/null || true
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            SOCKET=/run/ava-physical-effects/control.sock

            if [ "$(stat -c '%U:%G:%a' "$SOCKET" 2>/dev/null)" = \
                 "root:bigbird-ai:660" ]
            then
                echo "PASS: socket root:bigbird-ai 0660"
            else
                echo "FAIL: socket ownership/mode mismatch"
                stat -c '%U:%G:%a %n' "$SOCKET" 2>/dev/null || true
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            CURRENT_RELEASE="$(readlink -f "$CURRENT" || true)"

            if [ "$CURRENT_RELEASE" = "$RELEASE" ]; then
                echo "PASS: immutable current release"
            else
                echo "FAIL: current release mismatch"
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            PROCESS_CWD="$(
                readlink -f "/proc/$AFTER_PID/cwd" 2>/dev/null || true
            )"

            if [ "$PROCESS_CWD" = "$RELEASE" ]; then
                echo "PASS: running broker uses immutable release"
            else
                echo "FAIL: running broker release mismatch"
                echo "process_cwd=$PROCESS_CWD"
                echo "expected_release=$RELEASE"
                OK=0
            fi
        fi

        if [ "$OK" -eq 1 ]; then
            echo "expected_commit=$EXPECTED_COMMIT" > "$EVID/result.txt"
            echo "current_release=$RELEASE" >> "$EVID/result.txt"
            echo "master_enabled=false" >> "$EVID/result.txt"
            echo "hardware_executor=false" >> "$EVID/result.txt"

            echo "INSTALL APPLY: PASS"
            echo "evidence=$EVID"
            echo "rollback=$EVID/rollback.sh"
        else
            echo "INSTALL APPLY: FAIL"

            if [ -n "${EVID:-}" ] && [ -x "$EVID/rollback.sh" ]; then
                echo "Automatic rollback:"
                "$EVID/rollback.sh" || true
            fi
        fi
    fi
fi

echo
echo "=================================================="

if [ "$OK" -eq 1 ]; then
    echo " AVA PHYSICAL EFFECTS INSTALLER RESULT: PASS"
    FINAL_RC=0
else
    echo " AVA PHYSICAL EFFECTS INSTALLER RESULT: FAIL"
    FINAL_RC=1
fi

echo "=================================================="
exit "$FINAL_RC"
