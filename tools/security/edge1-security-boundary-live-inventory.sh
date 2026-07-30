#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=${EDGE1_MANAGEMENT_ROOT:-/opt/edge1-management-interface}
STATUS_ROOT=${EDGE1_STATUS_ROOT:-/var/www/edge1-status}
EVIDENCE_ROOT=${EDGE1_DEPLOYMENT_EVIDENCE_ROOT:-/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory}
PUBLIC_ORIGIN=${EDGE1_PUBLIC_ORIGIN:-https://edge1.ww.cx}
LOCAL_ORIGIN=${EDGE1_LOCAL_ORIGIN:-http://127.0.0.1}
AUTHORIZATION="$REPO_ROOT/config/security/edge1-security-completion-authorization-20260730.json"
REDACTOR="$REPO_ROOT/tools/security/redact-edge1-boundary-text.py"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
EVIDENCE_DIR="$EVIDENCE_ROOT/$STAMP"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ -d "$REPO_ROOT/.git" ] || fail "repository not found: $REPO_ROOT"
for command in bash git python3 curl find stat sha256sum df hostname id systemctl ss; do
    command -v "$command" >/dev/null 2>&1 || fail "required command unavailable: $command"
done
[ -f "$REDACTOR" ] || fail "evidence redactor is unavailable"

BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
[ "$BRANCH" = main ] || fail "inventory requires main; current branch is $BRANCH"
[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ] || fail "repository is dirty; preserve unrelated work before inventory"

python3 - "$AUTHORIZATION" <<'PY'
import json, pathlib, sys
value=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
if value.get('contract') != 'wwcx.edge1-security-completion-authorization.v1':
    raise SystemExit('authorization contract mismatch')
if value.get('authorized_actions', {}).get('read_only_live_inventory') is not True:
    raise SystemExit('read-only live inventory is not authorized')
if value.get('guardrails', {}).get('credential_material_in_repository') is not False:
    raise SystemExit('credential guardrail mismatch')
PY

install -d -o root -g root -m 0700 "$EVIDENCE_DIR"
printf '%s\n' "$STAMP" > "$EVIDENCE_DIR/started-at.txt"
hostname -f > "$EVIDENCE_DIR/hostname.txt" 2>&1 || hostname > "$EVIDENCE_DIR/hostname.txt"
id > "$EVIDENCE_DIR/principal.txt"
uname -a > "$EVIDENCE_DIR/uname.txt"
df -Pk "$REPO_ROOT" "$STATUS_ROOT" /var/lib /var/log > "$EVIDENCE_DIR/filesystem-capacity.txt" 2>&1 || true
git -C "$REPO_ROOT" rev-parse HEAD > "$EVIDENCE_DIR/repository-revision.txt"
git -C "$REPO_ROOT" status --short --branch > "$EVIDENCE_DIR/repository-status.txt"
ss -H -lntup 2>/dev/null | sort > "$EVIDENCE_DIR/listeners.txt" || true

for unit in \
    wwcx-security-operations.service \
    wwcx-security-correlation.service \
    wwcx-network-defense.service \
    wwcx-network-defense.timer \
    wwcx-operations-health.service \
    wwcx-suricata-protected-retention.service \
    wwcx-suricata-protected-retention.timer \
    wwcx-edge1-public-summary-stager.service \
    wwcx-edge1-public-summary-stager.timer; do
    systemctl show "$unit" \
        -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState \
        -p Result -p ExecMainStatus -p FragmentPath -p DropInPaths \
        2>&1 | python3 "$REDACTOR" > "$EVIDENCE_DIR/systemd-${unit}.txt" || true
    systemctl cat "$unit" 2>&1 \
        | python3 "$REDACTOR" > "$EVIDENCE_DIR/systemd-${unit}-definition.txt" || true
done

APACHE_CTL=""
for candidate in apache2ctl apachectl httpd; do
    if command -v "$candidate" >/dev/null 2>&1; then
        APACHE_CTL=$candidate
        break
    fi
done
[ -n "$APACHE_CTL" ] || fail "Apache control command is unavailable"
printf '%s\n' "$APACHE_CTL" > "$EVIDENCE_DIR/apache-command.txt"
"$APACHE_CTL" -t 2>&1 | python3 "$REDACTOR" > "$EVIDENCE_DIR/apache-config-test.txt"
"$APACHE_CTL" -S 2>&1 | python3 "$REDACTOR" > "$EVIDENCE_DIR/apache-vhosts.txt"
"$APACHE_CTL" -M 2>&1 | python3 "$REDACTOR" > "$EVIDENCE_DIR/apache-modules.txt"

python3 - "$EVIDENCE_DIR/apache-boundary-readiness.json" "$EVIDENCE_DIR/apache-config-files.sha256" <<'PY'
import hashlib, json, pathlib, re, stat, sys
output=pathlib.Path(sys.argv[1])
hashes=pathlib.Path(sys.argv[2])
roots=[pathlib.Path('/etc/apache2'), pathlib.Path('/etc/httpd')]
interesting={
 'authtype','require','alias','directory','location','locationmatch','header',
 'session','sessioncookiename','sessioncryptopassphrasefile','cache','cacheenable',
 'oidcprovidermetadataurl','oidcclientid','oidcredirecturi','oidccryptopassphrase',
 'authformprovider','authformloginrequiredlocation','authformloginsuccesslocation',
 'customlog','setoutputfilter','setenv','proxypass','proxypassreverse'
}
secret_directives={
 'oidcclientsecret','oidccryptopassphrase','sessioncryptopassphrase',
 'authuserfile','authgroupfile'
}
records=[]
hash_rows=[]
for root in roots:
    if not root.is_dir():
        continue
    for path in sorted(root.rglob('*')):
        try:
            info=path.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > 2_000_000:
            continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        hash_rows.append(f'{digest}  {path}')
        try:
            lines=path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for number, raw in enumerate(lines, 1):
            line=raw.strip()
            if not line or line.startswith('#'):
                continue
            match=re.match(r'<?([A-Za-z][A-Za-z0-9]*)\b', line)
            if not match:
                continue
            directive=match.group(1).lower()
            if directive in interesting or directive in secret_directives:
                records.append({
                    'file': str(path),
                    'line': number,
                    'directive': directive,
                    'value_recorded': False,
                    'secret_bearing': directive in secret_directives,
                })
modules_text=(output.parent/'apache-modules.txt').read_text(encoding='utf-8', errors='replace').lower()
module_names=[
 'alias_module','headers_module','authz_core_module','auth_openidc_module',
 'session_module','session_cookie_module','session_crypto_module','socache_shmcb_module',
 'ratelimit_module','setenvif_module','proxy_module','proxy_http_module'
]
result={
 'apache_config_test_passed': True,
 'modules': {name: name in modules_text for name in module_names},
 'directive_occurrences': records,
 'directive_values_recorded': False,
 'credential_material_collected': False,
}
output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
hashes.write_text('\n'.join(hash_rows)+('\n' if hash_rows else ''), encoding='utf-8')
PY

python3 - "$STATUS_ROOT" "$EVIDENCE_DIR/public-filesystem-inventory.json" "$EVIDENCE_DIR/public-filesystem-anomalies.json" <<'PY'
import hashlib, json, pathlib, stat, sys
root=pathlib.Path(sys.argv[1])
inventory_path=pathlib.Path(sys.argv[2])
anomaly_path=pathlib.Path(sys.argv[3])
records=[]
anomalies=[]
if not root.is_dir():
    anomalies.append({'path': str(root), 'type': 'missing_source_root'})
else:
    for path in sorted(root.rglob('*')):
        try:
            info=path.lstat()
        except OSError as exc:
            anomalies.append({'path': str(path), 'type': type(exc).__name__})
            continue
        if stat.S_ISLNK(info.st_mode):
            anomalies.append({'path': str(path), 'type': 'symlink'})
            continue
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            anomalies.append({'path': str(path), 'type': 'non_regular'})
            continue
        digest=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(65536), b''):
                digest.update(chunk)
        records.append({
            'path': str(path),
            'sha256': digest.hexdigest(),
            'mode': f'{stat.S_IMODE(info.st_mode):04o}',
            'bytes': info.st_size,
        })
inventory_path.write_text(json.dumps(records, indent=2, sort_keys=True)+'\n', encoding='utf-8')
anomaly_path.write_text(json.dumps(anomalies, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY

python3 "$REPO_ROOT/tools/security/reconcile-edge1-live-inventory.py" \
    --inventory "$EVIDENCE_DIR/public-filesystem-inventory.json" \
    --output "$EVIDENCE_DIR/reconciliation.json" \
    > "$EVIDENCE_DIR/reconciliation.stdout.json"

python3 - "$REPO_ROOT/config/security/edge1-restricted-artifact-migration-manifest.json" "$EVIDENCE_DIR/route-plan.tsv" <<'PY'
import json, pathlib, sys
manifest=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
rows=[('public-root','/edge1-status/'),('public-summary','/edge1-status/public/status.json'),('restricted-root','/edge1-ops/')]
for item in manifest['known_exact_artifacts']:
    rows.append(('public-'+item['source_relative'].replace('/','-'), '/edge1-status/'+item['source_relative']))
    restricted='/edge1-ops/' if item['target_relative']=='index.html' else '/edge1-ops/'+item['target_relative']
    rows.append(('restricted-'+item['target_relative'].replace('/','-'), restricted))
seen=set()
with pathlib.Path(sys.argv[2]).open('w', encoding='utf-8') as handle:
    handle.write('label\tpath\n')
    for label,path in rows:
        if path in seen:
            continue
        seen.add(path)
        handle.write(f'{label}\t{path}\n')
PY

printf 'origin\tlabel\tstatus\tpath\n' > "$EVIDENCE_DIR/route-matrix.tsv"
tail -n +2 "$EVIDENCE_DIR/route-plan.tsv" | while IFS=$'\t' read -r label path; do
    for origin_name in local public; do
        if [ "$origin_name" = local ]; then origin=$LOCAL_ORIGIN; else origin=$PUBLIC_ORIGIN; fi
        safe_label=$(printf '%s-%s' "$origin_name" "$label" | tr -c 'A-Za-z0-9._-' '_')
        code=$(curl -sS --max-time 20 -D - -o /dev/null -w '%{http_code}' "$origin$path" 2>/dev/null \
            | python3 "$REDACTOR" > "$EVIDENCE_DIR/route-${safe_label}.capture" || true)
        code=$(tail -n 1 "$EVIDENCE_DIR/route-${safe_label}.capture" | tr -d '\r')
        head -n -1 "$EVIDENCE_DIR/route-${safe_label}.capture" > "$EVIDENCE_DIR/route-${safe_label}.headers" || true
        printf '%s\t%s\t%s\t%s\n' "$origin_name" "$label" "$code" "$path" >> "$EVIDENCE_DIR/route-matrix.tsv"
    done
done

python3 - "$EVIDENCE_DIR" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
summary=[]
for path in sorted(root.glob('route-*.headers')):
    headers={}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if ':' in line:
            key,value=line.split(':',1)
            headers[key.strip().lower()]=value.strip()
    summary.append({
        'capture': path.name,
        'cache_control': headers.get('cache-control',''),
        'content_security_policy': headers.get('content-security-policy',''),
        'referrer_policy': headers.get('referrer-policy',''),
        'x_content_type_options': headers.get('x-content-type-options',''),
        'access_control_allow_origin': headers.get('access-control-allow-origin',''),
        'www_authenticate_scheme': headers.get('www-authenticate','').split(' ',1)[0],
        'set_cookie_present': 'set-cookie' in headers,
        'cookie_value_recorded': False,
    })
(root/'route-header-summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY

for root in /var/lib/wwcx-public-summary /var/lib/wwcx-edge1-ops /var/lib/bigbird-security/suricata-history /var/log/apache2 /var/log/httpd; do
    label=$(printf '%s' "$root" | tr '/-' '__')
    if [ -e "$root" ]; then
        find "$root" -xdev -maxdepth 4 -printf '%y\t%m\t%u\t%g\t%s\t%p\n' 2>/dev/null \
            | sort | python3 "$REDACTOR" > "$EVIDENCE_DIR/tree-${label}.txt" || true
    else
        printf 'absent\t%s\n' "$root" > "$EVIDENCE_DIR/tree-${label}.txt"
    fi
done

python3 - "$EVIDENCE_DIR" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
reconciliation=json.loads((root/'reconciliation.json').read_text(encoding='utf-8'))
anomalies=json.loads((root/'public-filesystem-anomalies.json').read_text(encoding='utf-8'))
apache=json.loads((root/'apache-boundary-readiness.json').read_text(encoding='utf-8'))
result={
 'contract':'wwcx.edge1-security-boundary-live-inventory-result.v1',
 'read_only_host_inventory':True,
 'live_configuration_changed':False,
 'source_tree_mutated':False,
 'credentials_collected':False,
 'cookie_values_recorded':False,
 'inventory_records':reconciliation['counts']['inventory'],
 'mapped_records':reconciliation['counts']['mapped'],
 'unknown_preserved':reconciliation['counts']['unknown_preserved'],
 'missing_known':reconciliation['counts']['missing_known'],
 'filesystem_anomalies':len(anomalies),
 'staging_ready':False,
 'cutover_ready':False,
 'apache_config_test_passed':apache['apache_config_test_passed'],
 'traffic_controls_changed':False,
}
(root/'result.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
PY

find "$EVIDENCE_DIR" -xdev -type f ! -name sha256-manifest.txt -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > "$EVIDENCE_DIR/sha256-manifest.txt"

printf 'Edge1 security-boundary live inventory completed.\n'
printf 'Evidence: %s\n' "$EVIDENCE_DIR"
printf 'No Apache, authentication, route, listener, firewall, DNS, service, source-tree, or public file was changed.\n'
