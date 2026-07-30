#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight}
PUBLIC_BASE=${EDGE1_PUBLIC_BASE_URL:-https://edge1.ww.cx/edge1-status}
LOCAL_BASE=${EDGE1_LOCAL_BASE_URL:-http://127.0.0.1/edge1-status}
SURICATA_SOURCE=${EDGE1_SURICATA_SOURCE:-/var/lib/bigbird/operations-center/latest.json}
SECURITY_SOURCE=${EDGE1_SECURITY_SOURCE:-$STATUS_ROOT/security-operations.json}
NETWORK_DEFENSE_SOURCE=${EDGE1_NETWORK_DEFENSE_SOURCE:-$STATUS_ROOT/network-defense/data/network-defense.json}
OPERATIONS_HEALTH_SOURCE=${EDGE1_OPERATIONS_HEALTH_SOURCE:-$STATUS_ROOT/operations-health.json}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"
STAGED_PUBLIC_DIR="$EVIDENCE_DIR/staged-public-summary"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root, for example: sudo $0"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found: $REPO_ROOT"
for command in bash git python3 curl find stat sha256sum df hostname id systemctl; do
    command -v "$command" >/dev/null 2>&1 || fail "required command is unavailable: $command"
done

install -d -o root -g root -m 0700 "$EVIDENCE_DIR" "$STAGED_PUBLIC_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
hostname -f > "$EVIDENCE_DIR/hostname.txt" 2>&1 || hostname > "$EVIDENCE_DIR/hostname.txt"
id > "$EVIDENCE_DIR/principal.txt"
uname -a > "$EVIDENCE_DIR/uname.txt"
df -Pk "$REPO_ROOT" "$STATUS_ROOT" /var/lib 2>&1 > "$EVIDENCE_DIR/filesystem-capacity.txt" || true

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
printf '%s\n' "$BRANCH" > "$EVIDENCE_DIR/repository-branch.txt"
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/repository-revision.txt"
git -C "$REPO_ROOT" remote -v > "$EVIDENCE_DIR/repository-remotes.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/repository-status.txt"
[ "$BRANCH" = main ] || fail "preflight requires main; current branch is $BRANCH"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository has uncommitted or untracked work; preserve it before preflight"

python3 -m unittest \
    tests.test_network_defense_freshness_policy \
    tests.test_network_defense_deployment \
    tests.validate_edge1_public_status \
    2>&1 | tee "$EVIDENCE_DIR/repository-targeted-tests.txt"

for unit in \
    wwcx-network-defense.service \
    wwcx-network-defense.timer \
    wwcx-security-operations.service \
    wwcx-security-correlation.service \
    wwcx-operations-health.service; do
    systemctl show "$unit" \
        -p Id -p LoadState -p ActiveState -p SubState -p Result -p ExecMainStatus \
        > "$EVIDENCE_DIR/systemd-${unit}.txt" 2>&1 || true
done
systemctl cat wwcx-network-defense.service > "$EVIDENCE_DIR/network-defense-unit.txt" 2>&1 || true
systemctl cat wwcx-network-defense.timer > "$EVIDENCE_DIR/network-defense-timer.txt" 2>&1 || true

APACHE_CTL=""
for candidate in apachectl apache2ctl httpd; do
    if command -v "$candidate" >/dev/null 2>&1; then
        APACHE_CTL=$candidate
        break
    fi
done
printf '%s\n' "${APACHE_CTL:-unavailable}" > "$EVIDENCE_DIR/apache-command.txt"
if [ -n "$APACHE_CTL" ]; then
    "$APACHE_CTL" -S > "$EVIDENCE_DIR/apache-vhosts.txt" 2>&1 || true
    "$APACHE_CTL" -M > "$EVIDENCE_DIR/apache-modules.txt" 2>&1 || true
    "$APACHE_CTL" -t > "$EVIDENCE_DIR/apache-config-test.txt" 2>&1 || true
fi

python3 - "$EVIDENCE_DIR/apache-directives.txt" <<'PY'
import pathlib
import re
import sys

output = pathlib.Path(sys.argv[1])
roots = [pathlib.Path("/etc/apache2"), pathlib.Path("/etc/httpd")]
plain = {
    "servername", "serveralias", "documentroot", "alias", "redirect",
    "directory", "location", "require", "authtype", "options", "header",
    "proxypass", "proxypassreverse", "rewriterule", "setenvif",
    "directoryindex", "accessfilename",
}
redacted = {"authuserfile", "authgroupfile", "authbasicprovider"}
rows = []
for root in roots:
    if not root.is_dir():
        continue
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"<?([A-Za-z][A-Za-z0-9]*)\b(.*)", line)
            if not match:
                continue
            directive = match.group(1).lower()
            if directive in redacted:
                rows.append(f"{path}:{number}: {match.group(1)} <redacted>")
            elif directive in plain:
                value = re.sub(r"(?i)(password|secret|token|cookie|authorization)\s+\S+", r"\1 <redacted>", line)
                rows.append(f"{path}:{number}: {value[:1000]}")
output.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
PY

if [ -d "$STATUS_ROOT" ]; then
    find "$STATUS_ROOT" -xdev -maxdepth 5 -type f \
        -printf '%m\t%u\t%g\t%s\t%TY-%Tm-%TdT%TH:%TM:%TSZ\t%p\n' \
        | sort > "$EVIDENCE_DIR/public-filesystem-inventory.txt"
    find "$STATUS_ROOT" -xdev -maxdepth 5 -type f -print0 \
        | sort -z \
        | xargs -0 -r sha256sum > "$EVIDENCE_DIR/public-filesystem-sha256.txt"
else
    printf 'missing\t%s\n' "$STATUS_ROOT" > "$EVIDENCE_DIR/public-filesystem-inventory.txt"
fi

python3 - "$SURICATA_SOURCE" "$EVIDENCE_DIR/suricata-retention-sizing.json" <<'PY'
import json
import pathlib
import statistics
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
result = {
    "source_present": source.is_file(),
    "source_bytes": source.stat().st_size if source.is_file() else 0,
    "alert_count": 0,
    "serialized_alert_bytes_min": 0,
    "serialized_alert_bytes_median": 0,
    "serialized_alert_bytes_p95": 0,
    "serialized_alert_bytes_max": 0,
}

def candidate_alerts(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"recent_alerts", "alerts"} and isinstance(child, list):
                return child
            found = candidate_alerts(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = candidate_alerts(child)
            if found is not None:
                return found
    return None

if source.is_file():
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        alerts = candidate_alerts(document) or []
        sizes = [len(json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8")) for item in alerts]
        result["alert_count"] = len(sizes)
        if sizes:
            ordered = sorted(sizes)
            p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
            result.update({
                "serialized_alert_bytes_min": min(sizes),
                "serialized_alert_bytes_median": int(statistics.median(sizes)),
                "serialized_alert_bytes_p95": ordered[p95_index],
                "serialized_alert_bytes_max": max(sizes),
            })
    except Exception as exc:
        result["parse_error_type"] = type(exc).__name__
target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

python3 - "$EVIDENCE_DIR/sqlite-capability.json" <<'PY'
import json
import sqlite3
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
with sqlite3.connect(":memory:") as conn:
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    max_page_count = conn.execute("PRAGMA max_page_count").fetchone()[0]
    compile_options = sorted(row[0] for row in conn.execute("PRAGMA compile_options"))
result = {
    "sqlite_version": sqlite3.sqlite_version,
    "python_sqlite_version": sqlite3.version,
    "default_page_size": page_size,
    "default_max_page_count": max_page_count,
    "compile_options": compile_options,
}
target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

route_status() {
    local label=$1
    local url=$2
    local prefix="$EVIDENCE_DIR/route-$label"
    local code
    code=$(curl -sS --max-time 20 -D "$prefix.headers" -o /dev/null -w '%{http_code}' "$url" || true)
    printf '%s\t%s\t%s\n' "$label" "$code" "$url" >> "$EVIDENCE_DIR/route-matrix.tsv"
}

printf 'label\tstatus\turl\n' > "$EVIDENCE_DIR/route-matrix.tsv"
for base_label in local public; do
    if [ "$base_label" = local ]; then base=$LOCAL_BASE; else base=$PUBLIC_BASE; fi
    route_status "${base_label}-root" "$base/"
    route_status "${base_label}-security" "$base/security/"
    route_status "${base_label}-correlation" "$base/security/correlation.html"
    route_status "${base_label}-network-defense" "$base/network-defense/"
    route_status "${base_label}-security-json" "$base/security-operations.json"
    route_status "${base_label}-correlation-json" "$base/security-correlation.json"
    route_status "${base_label}-network-defense-json" "$base/network-defense/data/network-defense.json"
    route_status "${base_label}-inventory-json" "$base/operations-inventory.json"
    route_status "${base_label}-network-json" "$base/operations-network.json"
    route_status "${base_label}-incidents-json" "$base/operations-incidents.json"
    route_status "${base_label}-reports" "$base/reports/"
done

python3 - "$EVIDENCE_DIR" <<'PY'
import pathlib
import re
import sys
root = pathlib.Path(sys.argv[1])
summary = []
for header_path in sorted(root.glob("route-*.headers")):
    text = header_path.read_text(encoding="utf-8", errors="replace")
    headers = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    summary.append({
        "route": header_path.stem.removeprefix("route-"),
        "cache_control": headers.get("cache-control", ""),
        "content_security_policy": headers.get("content-security-policy", ""),
        "referrer_policy": headers.get("referrer-policy", ""),
        "x_content_type_options": headers.get("x-content-type-options", ""),
        "access_control_allow_origin": headers.get("access-control-allow-origin", ""),
        "strict_transport_security": headers.get("strict-transport-security", ""),
    })
import json
(root / "route-header-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

python3 "$REPO_ROOT/server/edge1_public_status_exporter.py" \
    --security "$SECURITY_SOURCE" \
    --network-defense "$NETWORK_DEFENSE_SOURCE" \
    --operations-health "$OPERATIONS_HEALTH_SOURCE" \
    --output "$STAGED_PUBLIC_DIR/status.json" \
    > "$EVIDENCE_DIR/minimized-exporter-result.json"
install -m 0644 "$REPO_ROOT/src/web/public-status/index.html" "$STAGED_PUBLIC_DIR/index.html"
install -m 0644 "$REPO_ROOT/src/web/public-status/app.js" "$STAGED_PUBLIC_DIR/app.js"

python3 - "$STAGED_PUBLIC_DIR/status.json" "$EVIDENCE_DIR/minimized-summary-validation.json" <<'PY'
import json
import pathlib
import sys
source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
document = json.loads(source.read_text(encoding="utf-8"))
expected = {
    "schema_version", "generated_at", "overall_state", "component_category",
    "maintenance_notice", "read_only", "traffic_controls_changed",
}
if set(document) != expected:
    raise SystemExit("minimized summary top-level field set is not exact")
if document.get("schema_version") != "wwcx.edge1-public-status.v1":
    raise SystemExit("unexpected minimized summary schema")
if document.get("read_only") is not True:
    raise SystemExit("read_only must be true")
if document.get("traffic_controls_changed") is not False:
    raise SystemExit("traffic_controls_changed must be false")
result = {
    "ok": True,
    "schema_version": document["schema_version"],
    "overall_state": document["overall_state"],
    "component_count": len(document.get("component_category") or []),
    "read_only": True,
    "traffic_controls_changed": False,
}
target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

find "$EVIDENCE_DIR" -xdev -type f ! -name sha256-manifest.txt -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > "$EVIDENCE_DIR/sha256-manifest.txt"
printf 'completed_at=%s\nread_only_host_inventory=true\nlive_configuration_changed=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$EVIDENCE_DIR/result.txt"

printf 'Edge1 completion preflight passed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No Apache, authentication, route, listener, firewall, DNS, or public files were changed.\n'
