import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { McpServer } from '@modelcontextprotocol/server';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';

const SSH_ALIAS = process.env.BUSINESS159_SSH_ALIAS || 'business159';
const EXPECTED_HOST = process.env.BUSINESS159_EXPECTED_HOST || 'business159.web-hosting.com';
const EXPECTED_PRINCIPAL = process.env.BUSINESS159_EXPECTED_PRINCIPAL || 'wwcxjywl';
const PUBLIC_HOST = process.env.BUSINESS159_PUBLIC_HOST || 'ww.cx';
const APP_ROOT = process.env.BUSINESS159_APP_ROOT || '/home/wwcxjywl/apps/ww-cx-website';
const PUBLIC_ROOT = process.env.BUSINESS159_PUBLIC_ROOT || '/home/wwcxjywl/public_html';
const SHARED_ROOT = process.env.BUSINESS159_SHARED_ROOT || '/home/wwcxjywl/shared/ww-cx-website';
const OPERATOR_ROOT = process.env.BUSINESS159_OPERATOR_ROOT || '/home/wwcxjywl/shared/ww-cx-operator';
const BRIDGE_SNAPSHOT = process.env.BUSINESS159_BRIDGE_SNAPSHOT || '/home/wwcxjywl/wwcx-store-private/operations-center/latest.json';
const TIMEOUT_MS = Math.min(Number(process.env.BUSINESS159_TIMEOUT_MS || 30000), 120000);
const MAX_OUTPUT_BYTES = Math.min(Number(process.env.BUSINESS159_MAX_OUTPUT_BYTES || 32000), 262144);
const ALLOW_DEPLOY = process.env.BUSINESS159_ALLOW_DEPLOY === '1';
const ALLOW_FILESYSTEM = process.env.BUSINESS159_ALLOW_FILESYSTEM === '1';
const ENABLE_RAW_SHELL = process.env.BUSINESS159_ENABLE_RAW_SHELL === '1';
const MAX_STAGE_BYTES = Math.min(Number(process.env.BUSINESS159_MAX_STAGE_BYTES || 24576), 65536);

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

function redact(text) {
  return String(text)
    .replace(/(authorization:\s*bearer\s+)[^\s]+/gi, '$1[REDACTED]')
    .replace(/((?:token|password|secret|api[_-]?key|cookie|session)\s*[=:]\s*)[^\s]+/gi, '$1[REDACTED]')
    .replace(/([a-z][a-z0-9+.-]*:\/\/)[^\s/@]+:[^\s/@]+@/gi, '$1[REDACTED]@')
    .replace(/(-----BEGIN [A-Z ]*PRIVATE KEY-----)[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----)/g, '$1\n[REDACTED]\n$2');
}

function runSsh(remoteCommand) {
  return new Promise((resolve) => {
    const started = new Date().toISOString();
    const child = spawn('ssh', [
      '-o', 'BatchMode=yes',
      '-o', 'StrictHostKeyChecking=yes',
      '-o', `ConnectTimeout=${Math.max(1, Math.ceil(TIMEOUT_MS / 1000))}`,
      SSH_ALIAS,
      remoteCommand
    ], { stdio: ['ignore', 'pipe', 'pipe'] });

    let stdout = Buffer.alloc(0);
    let stderr = Buffer.alloc(0);
    let outputLimited = false;
    let timedOut = false;

    const append = (current, chunk) => {
      const next = Buffer.concat([current, chunk]);
      if (next.length > MAX_OUTPUT_BYTES) {
        outputLimited = true;
        child.kill('SIGTERM');
        return next.subarray(0, MAX_OUTPUT_BYTES);
      }
      return next;
    };
    child.stdout.on('data', chunk => { stdout = append(stdout, chunk); });
    child.stderr.on('data', chunk => { stderr = append(stderr, chunk); });

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGTERM');
      setTimeout(() => child.kill('SIGKILL'), 1000).unref();
    }, TIMEOUT_MS);

    child.on('error', error => {
      clearTimeout(timer);
      resolve({ ok: false, exitCode: null, started, ended: new Date().toISOString(), stdout: '', stderr: redact(error.message), timedOut, outputLimited });
    });
    child.on('close', code => {
      clearTimeout(timer);
      resolve({ ok: code === 0 && !timedOut && !outputLimited, exitCode: code, started, ended: new Date().toISOString(), stdout: redact(stdout.toString('utf8')), stderr: redact(stderr.toString('utf8')), timedOut, outputLimited });
    });
  });
}

function guard(command) {
  return [
    'set -eu',
    `expected_host=${shellQuote(EXPECTED_HOST)}`,
    `expected_principal=${shellQuote(EXPECTED_PRINCIPAL)}`,
    'actual_principal=$(id -un)',
    'actual_host=$(hostname -f 2>/dev/null || hostname)',
    '[ "$actual_principal" = "$expected_principal" ] || { echo "principal_mismatch expected=$expected_principal actual=$actual_principal" >&2; exit 70; }',
    '[ "$actual_host" = "$expected_host" ] || { echo "host_mismatch expected=$expected_host actual=$actual_host" >&2; exit 71; }',
    command
  ].join('; ');
}

function payload(tool, result, extra = {}) {
  const body = { tool, host: EXPECTED_HOST, principal: EXPECTED_PRINCIPAL, ...extra, ...result };
  return { content: [{ type: 'text', text: JSON.stringify(body, null, 2) }], isError: !result.ok };
}

function fixedRead(tool, command, extra = {}) {
  return runSsh(guard(command)).then(result => payload(tool, result, { readOnly: true, ...extra }));
}

function validRelativePath(value) {
  if (typeof value !== 'string' || value.length < 1 || value.length > 240) return false;
  if (value.startsWith('/') || value.includes('\0')) return false;
  const parts = value.split('/');
  if (parts.some(part => !part || part === '.' || part === '..')) return false;
  return parts.every(part => /^[A-Za-z0-9._-]+$/.test(part));
}

function forbiddenTarget(relativePath) {
  const leaf = relativePath.split('/').at(-1).toLowerCase();
  if (leaf === '.env' || leaf.startsWith('.env.') || leaf === '.htpasswd') return true;
  return /\.(pem|key|p12|pfx|kdb|jks|bak|backup|old|orig|save|sql|sqlite|db|log)$/i.test(leaf);
}

function contentLooksSecret(content) {
  return /(-----BEGIN [A-Z ]*PRIVATE KEY-----|authorization\s*:\s*bearer\s+\S+|(?:password|secret|api[_-]?key|token|cookie|session)\s*[=:]\s*\S+)/i.test(content);
}

function stagePaths(stageId) {
  const root = `${OPERATOR_ROOT}/stages/${stageId}`;
  return { root, candidate: `${root}/candidate`, metadata: `${root}/metadata`, approved: `${root}/approved`, backup: `${root}/backup`, audit: `${OPERATOR_ROOT}/audit.jsonl` };
}

function validStageId(stageId) {
  return /^[a-f0-9-]{36}$/.test(stageId);
}

function auditShell(event, stageId, relativePath = '') {
  const safeEvent = String(event).replace(/[^a-z0-9._-]/gi, '_');
  const safePath = String(relativePath).replace(/[^A-Za-z0-9._\/-]/g, '_');
  return `mkdir -p ${shellQuote(OPERATOR_ROOT)}; chmod 700 ${shellQuote(OPERATOR_ROOT)}; printf '%s\\t%s\\t%s\\t%s\\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" ${shellQuote(safeEvent)} ${shellQuote(stageId)} ${shellQuote(safePath)} >> ${shellQuote(`${OPERATOR_ROOT}/audit.jsonl`)}`;
}

const INSPECTIONS = {
  overview: `printf 'time_utc='; date -u +%Y-%m-%dT%H:%M:%SZ; printf 'hostname='; hostname -f; printf 'principal='; id -un; printf 'home='; printf '%s\\n' "$HOME"; uptime`,
  resources: `df -Pk "$HOME" ${shellQuote(PUBLIC_ROOT)} 2>/dev/null || df -Pk "$HOME"; df -Pi "$HOME" 2>/dev/null || true; if command -v quota >/dev/null 2>&1; then quota -s 2>/dev/null || true; fi`,
  php: `if command -v php >/dev/null 2>&1; then php -r 'echo "version=".PHP_VERSION."\\nsapi=".PHP_SAPI."\\n"; echo "ini=".(php_ini_loaded_file() ?: "none")."\\n";'; else echo 'php=unavailable'; exit 3; fi`,
  web: `url=${shellQuote(`https://${PUBLIC_HOST}/`)}; if command -v curl >/dev/null 2>&1; then curl -fsSIL --max-time 12 --connect-timeout 5 "$url" | sed -n '1,20p'; else echo 'curl=unavailable'; exit 3; fi`,
  domain: `printf 'public_host=%s\\n' ${shellQuote(PUBLIC_HOST)}; if command -v getent >/dev/null 2>&1; then getent ahosts ${shellQuote(PUBLIC_HOST)} | awk '{print $1}' | sort -u | sed -n '1,8p'; fi`,
  tls: `if command -v openssl >/dev/null 2>&1; then printf '' | openssl s_client -servername ${shellQuote(PUBLIC_HOST)} -connect ${shellQuote(`${PUBLIC_HOST}:443`)} 2>/dev/null | openssl x509 -noout -subject -issuer -dates -fingerprint -sha256; else echo 'openssl=unavailable'; exit 3; fi`,
  cron: `if command -v crontab >/dev/null 2>&1; then crontab -l 2>&1 | sed -n '1,120p'; else echo 'crontab=unavailable'; exit 3; fi`,
  git: `git -C ${shellQuote(APP_ROOT)} rev-parse --show-toplevel; git -C ${shellQuote(APP_ROOT)} status --short --branch; printf 'head='; git -C ${shellQuote(APP_ROOT)} rev-parse HEAD; printf 'origin='; git -C ${shellQuote(APP_ROOT)} config --get remote.origin.url || true`,
  mail: `printf 'sendmail='; command -v sendmail 2>/dev/null || true; if command -v php >/dev/null 2>&1; then php -r 'echo "php_mail_function=".(function_exists("mail") ? "available" : "unavailable")."\\n"; echo "sendmail_path=".(ini_get("sendmail_path") ?: "none")."\\n";'; fi`,
  deployment: `[ -r ${shellQuote(`${SHARED_ROOT}/config.env`)} ] && echo 'config=present' || echo 'config=missing'; [ -r ${shellQuote(`${SHARED_ROOT}/deployments.log`)} ] && tail -n 10 ${shellQuote(`${SHARED_ROOT}/deployments.log`)} || echo 'deployments_log=missing'; [ -L ${shellQuote(`${SHARED_ROOT}/current`)} ] && printf 'current=' && readlink ${shellQuote(`${SHARED_ROOT}/current`)} || echo 'current=missing'`,
  bridge: `snapshot=${shellQuote(BRIDGE_SNAPSHOT)}; if [ -f "$snapshot" ]; then stat -c 'path=%n\\nsize=%s\\nmtime_unix=%Y\\nmode=%a' "$snapshot"; if [ -f "$snapshot.sha256" ]; then echo 'checksum_sidecar=present'; (cd "$(dirname "$snapshot")" && sha256sum -c "$(basename "$snapshot").sha256") 2>/dev/null && echo 'checksum=verified' || echo 'checksum=failed'; else echo 'checksum_sidecar=missing'; fi; else echo 'snapshot=missing'; exit 4; fi`,
  logs: `for f in "$HOME/access-logs/${PUBLIC_HOST}" "$HOME/access-logs/${PUBLIC_HOST}-ssl_log" "$HOME/logs/${PUBLIC_HOST}.php.error.log" "$HOME/logs/${PUBLIC_HOST}.error.log"; do if [ -f "$f" ]; then printf '%s\\n' "--- $f"; stat -c 'size=%s mtime_unix=%Y mode=%a' "$f"; tail -n 25 "$f"; fi; done`,
  config: `for f in ${shellQuote(`${SHARED_ROOT}/config.env`)} ${shellQuote(`${APP_ROOT}/scripts/deploy-business159.sh`)} ${shellQuote(`${APP_ROOT}/scripts/validate.sh`)} ${shellQuote(`${PUBLIC_ROOT}/.htaccess`)}; do if [ -f "$f" ]; then printf '%s ' "$f"; sha256sum "$f" | awk '{print $1}'; else printf '%s missing\\n' "$f"; fi; done`
};

function createServer() {
  const server = new McpServer(
    { name: 'business159-live-shell', version: '0.1.0' },
    { instructions: 'Business159 is a cPanel/shared-host account. Verify host and principal on every call. Prefer named read-only tools and business159_inspect. Deployment and staged filesystem writes are disabled unless explicitly enabled. Never request or expose credentials.' }
  );

  server.registerTool('business159.identity', { description: 'Return verified shared-host identity for Business159.', inputSchema: z.object({}) }, async () => fixedRead('business159.identity', INSPECTIONS.overview));

  server.registerTool('business159.resources', { description: 'Return bounded account filesystem/quota resource state.', inputSchema: z.object({}) }, async () => fixedRead('business159.resources', INSPECTIONS.resources));
  server.registerTool('business159.php_status', { description: 'Return bounded PHP CLI version/SAPI/config-path state without phpinfo or secrets.', inputSchema: z.object({}) }, async () => fixedRead('business159.php_status', INSPECTIONS.php));
  server.registerTool('business159.web_status', { description: 'Check the fixed WW.CX HTTPS endpoint from Business159.', inputSchema: z.object({}) }, async () => fixedRead('business159.web_status', INSPECTIONS.web));
  server.registerTool('business159.domain_state', { description: 'Return bounded resolver state for the configured WW.CX public hostname.', inputSchema: z.object({}) }, async () => fixedRead('business159.domain_state', INSPECTIONS.domain));
  server.registerTool('business159.tls_status', { description: 'Return certificate metadata for the fixed WW.CX public hostname.', inputSchema: z.object({}) }, async () => fixedRead('business159.tls_status', INSPECTIONS.tls));
  server.registerTool('business159.cron_state', { description: 'Return the account crontab with connector redaction and output limits.', inputSchema: z.object({}) }, async () => fixedRead('business159.cron_state', INSPECTIONS.cron));
  server.registerTool('business159.git_state', { description: 'Return repository branch/dirty/head/origin state without fetching or changing it.', inputSchema: z.object({}) }, async () => fixedRead('business159.git_state', INSPECTIONS.git));
  server.registerTool('business159.mail_state', { description: 'Return bounded mail capability/config-path state without queue contents or credentials.', inputSchema: z.object({}) }, async () => fixedRead('business159.mail_state', INSPECTIONS.mail));
  server.registerTool('business159.deployment_status', { description: 'Return bounded deployment workspace/current-release metadata.', inputSchema: z.object({}) }, async () => fixedRead('business159.deployment_status', INSPECTIONS.deployment));
  server.registerTool('business159.edge1_bridge_status', { description: 'Return freshness/integrity metadata for the Edge1 operations snapshot received on Business159.', inputSchema: z.object({}) }, async () => fixedRead('business159.edge1_bridge_status', INSPECTIONS.bridge));
  server.registerTool('business159.config_digest', { description: 'Return SHA-256 digests for selected Business159 deployment/operator files without file contents.', inputSchema: z.object({}) }, async () => fixedRead('business159.config_digest', INSPECTIONS.config));
  server.registerTool('business159.logs_summary', { description: 'Return bounded tails/metadata from fixed account-level WW.CX logs with redaction.', inputSchema: z.object({}) }, async () => fixedRead('business159.logs_summary', INSPECTIONS.logs));

  server.registerTool('business159.inventory', { description: 'Collect a deterministic bounded Business159 account inventory.', inputSchema: z.object({}) }, async () => {
    const command = [INSPECTIONS.overview, INSPECTIONS.resources, INSPECTIONS.php, INSPECTIONS.git, INSPECTIONS.deployment].map((item, i) => `echo '===${i + 1}==='; (${item}) || true`).join('; ');
    return fixedRead('business159.inventory', command);
  });

  server.registerTool('business159.snapshot', { description: 'Collect a broad read-only Business159 snapshot using fixed account/web/deployment checks.', inputSchema: z.object({}) }, async () => {
    const keys = ['overview', 'resources', 'php', 'web', 'git', 'deployment', 'bridge'];
    const command = keys.map(key => `echo ${shellQuote(`===${key}===`)}; (${INSPECTIONS[key]}) || true`).join('; ');
    return fixedRead('business159.snapshot', command);
  });

  server.registerTool('business159.health', { description: 'Return a bounded composite health check for Business159 without arbitrary shell.', inputSchema: z.object({}) }, async () => {
    const command = `failed=0; printf 'identity='; hostname -f; test -d ${shellQuote(PUBLIC_ROOT)} || { echo 'public_root=missing'; failed=1; }; command -v php >/dev/null 2>&1 || { echo 'php=missing'; failed=1; }; git -C ${shellQuote(APP_ROOT)} rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo 'git=unavailable'; failed=1; }; if command -v curl >/dev/null 2>&1; then curl -fsSI --max-time 12 ${shellQuote(`https://${PUBLIC_HOST}/`)} >/dev/null || { echo 'https=failed'; failed=1; }; else echo 'curl=missing'; failed=1; fi; [ -f ${shellQuote(BRIDGE_SNAPSHOT)} ] && echo 'bridge=present' || echo 'bridge=missing'; if [ "$failed" -eq 0 ]; then echo 'health=healthy'; else echo 'health=degraded'; fi; exit "$failed"`;
    const result = await runSsh(guard(command));
    return payload('business159.health', result, { readOnly: true, health: result.ok ? 'healthy' : 'degraded' });
  });

  server.registerTool('business159_connection_test', { description: 'Verify authenticated SSH connectivity, hostname and account principal.', inputSchema: z.object({}) }, async () => fixedRead('business159_connection_test', INSPECTIONS.overview));

  server.registerTool('business159_inspect', {
    description: 'Perform one bounded read-only Business159 inspection. Prefer this over raw shell.',
    inputSchema: z.object({ kind: z.enum(['overview', 'resources', 'php', 'web', 'domain', 'tls', 'cron', 'git', 'mail', 'deployment', 'bridge', 'logs', 'config']) })
  }, async ({ kind }) => fixedRead('business159_inspect', INSPECTIONS[kind], { kind }));

  server.registerTool('business159_deploy', {
    description: 'Run the existing Business159 deployer. Dry-run is always allowed; apply requires BUSINESS159_ALLOW_DEPLOY=1, a clean dedicated deploy checkout, and expected source commit verification.',
    inputSchema: z.object({ dryRun: z.boolean().default(true), expectedCommit: z.string().regex(/^[a-f0-9]{40}$/).optional() })
  }, async ({ dryRun, expectedCommit }) => {
    if (!dryRun && !ALLOW_DEPLOY) return { content: [{ type: 'text', text: 'Business159 deployment apply is disabled by policy (BUSINESS159_ALLOW_DEPLOY=0).' }], isError: true };
    if (!dryRun && !expectedCommit) return { content: [{ type: 'text', text: 'expectedCommit is required for an apply deployment.' }], isError: true };
    const deployer = `${APP_ROOT}/scripts/deploy-business159.sh`;
    const mode = dryRun ? '--dry-run' : '';
    const expectedCheck = expectedCommit ? `test "$(git -C ${shellQuote(APP_ROOT)} rev-parse origin/main)" = ${shellQuote(expectedCommit)}` : ':';
    const command = `test -x ${shellQuote(deployer)}; test -z "$(git -C ${shellQuote(APP_ROOT)} status --porcelain)" || { echo 'deploy_checkout_dirty' >&2; exit 73; }; git -C ${shellQuote(APP_ROOT)} fetch --prune origin; ${expectedCheck}; sh ${shellQuote(deployer)} ${mode}; ${dryRun ? ':' : `curl -fsSI --max-time 15 ${shellQuote(`https://${PUBLIC_HOST}/`)} >/dev/null; echo 'post_deploy_http=ok'`}`;
    const result = await runSsh(guard(command));
    return payload('business159_deploy', result, { mutation: !dryRun, dryRun, expectedCommit: expectedCommit || null });
  });

  server.registerTool('business159_fs_stage', {
    description: 'Stage one small non-secret file candidate for a relative path under the verified Business159 public root. Does not apply it.',
    inputSchema: z.object({ relativePath: z.string().min(1).max(240), content: z.string().max(MAX_STAGE_BYTES), reason: z.string().min(1).max(240) })
  }, async ({ relativePath, content, reason }) => {
    if (!ALLOW_FILESYSTEM) return { content: [{ type: 'text', text: 'Business159 staged filesystem operations are disabled by policy (BUSINESS159_ALLOW_FILESYSTEM=0).' }], isError: true };
    if (!validRelativePath(relativePath) || forbiddenTarget(relativePath)) return { content: [{ type: 'text', text: 'Target path is outside the approved relative-path/file policy.' }], isError: true };
    if (Buffer.byteLength(content, 'utf8') > MAX_STAGE_BYTES) return { content: [{ type: 'text', text: 'Candidate exceeds the configured stage size limit.' }], isError: true };
    if (contentLooksSecret(content)) return { content: [{ type: 'text', text: 'Candidate rejected because it appears to contain secret material.' }], isError: true };
    const stageId = randomUUID();
    const paths = stagePaths(stageId);
    const encoded = Buffer.from(content, 'utf8').toString('base64');
    const target = `${PUBLIC_ROOT}/${relativePath}`;
    const command = `umask 077; mkdir -p ${shellQuote(paths.root)}; printf '%s' ${shellQuote(encoded)} | base64 -d > ${shellQuote(paths.candidate)}; printf 'relative_path=%s\\ntarget=%s\\nreason=%s\\nsha256=%s\\n' ${shellQuote(relativePath)} ${shellQuote(target)} ${shellQuote(reason)} "$(sha256sum ${shellQuote(paths.candidate)} | awk '{print $1}')" > ${shellQuote(paths.metadata)}; ${auditShell('stage', stageId, relativePath)}; sha256sum ${shellQuote(paths.candidate)}; cat ${shellQuote(paths.metadata)}`;
    const result = await runSsh(guard(command));
    return payload('business159_fs_stage', result, { mutation: true, stageId, relativePath, target });
  });

  server.registerTool('business159_fs_status', {
    description: 'Inspect staged filesystem metadata and lifecycle markers for one stage.',
    inputSchema: z.object({ stageId: z.string() })
  }, async ({ stageId }) => {
    if (!validStageId(stageId)) return { content: [{ type: 'text', text: 'Invalid stage ID.' }], isError: true };
    const p = stagePaths(stageId);
    const command = `test -r ${shellQuote(p.metadata)}; cat ${shellQuote(p.metadata)}; [ -f ${shellQuote(p.approved)} ] && echo 'approved=yes' || echo 'approved=no'; [ -f ${shellQuote(p.backup)} ] && echo 'backup=yes' || echo 'backup=no'`;
    return fixedRead('business159_fs_status', command, { stageId });
  });

  server.registerTool('business159_fs_diff', {
    description: 'Show a bounded unified diff between the current public-root target and staged candidate.',
    inputSchema: z.object({ stageId: z.string() })
  }, async ({ stageId }) => {
    if (!validStageId(stageId)) return { content: [{ type: 'text', text: 'Invalid stage ID.' }], isError: true };
    const p = stagePaths(stageId);
    const command = `test -r ${shellQuote(p.metadata)}; relative=$(sed -n 's/^relative_path=//p' ${shellQuote(p.metadata)}); test -n "$relative"; target=${shellQuote(`${PUBLIC_ROOT}/`)}"$relative"; if [ -f "$target" ]; then diff -u -- "$target" ${shellQuote(p.candidate)} || test "$?" -eq 1; else diff -u -- /dev/null ${shellQuote(p.candidate)} || test "$?" -eq 1; fi`;
    return fixedRead('business159_fs_diff', command, { stageId });
  });

  server.registerTool('business159_fs_approve', {
    description: 'Approve an already-inspected stage. Approval records actor/reason; it does not apply the candidate.',
    inputSchema: z.object({ stageId: z.string(), actor: z.string().regex(/^[A-Za-z0-9._@-]{1,80}$/), reason: z.string().min(1).max(240) })
  }, async ({ stageId, actor, reason }) => {
    if (!ALLOW_FILESYSTEM) return { content: [{ type: 'text', text: 'Business159 staged filesystem operations are disabled by policy.' }], isError: true };
    if (!validStageId(stageId)) return { content: [{ type: 'text', text: 'Invalid stage ID.' }], isError: true };
    const p = stagePaths(stageId);
    const command = `test -r ${shellQuote(p.metadata)}; printf 'actor=%s\\nreason=%s\\napproved_utc=%s\\n' ${shellQuote(actor)} ${shellQuote(reason)} "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > ${shellQuote(p.approved)}; ${auditShell('approve', stageId)}; cat ${shellQuote(p.approved)}`;
    const result = await runSsh(guard(command));
    return payload('business159_fs_approve', result, { mutation: true, stageId, actor });
  });

  server.registerTool('business159_fs_apply', {
    description: 'Apply an approved stage atomically at the file level under public_html, after backup, then verify SHA-256 and permissions.',
    inputSchema: z.object({ stageId: z.string() })
  }, async ({ stageId }) => {
    if (!ALLOW_FILESYSTEM) return { content: [{ type: 'text', text: 'Business159 staged filesystem operations are disabled by policy.' }], isError: true };
    if (!validStageId(stageId)) return { content: [{ type: 'text', text: 'Invalid stage ID.' }], isError: true };
    const p = stagePaths(stageId);
    const command = `test -r ${shellQuote(p.metadata)}; test -r ${shellQuote(p.approved)}; relative=$(sed -n 's/^relative_path=//p' ${shellQuote(p.metadata)}); expected=$(sed -n 's/^sha256=//p' ${shellQuote(p.metadata)}); test -n "$relative"; case "$relative" in /*|*../*|../*|*/..|..) exit 74;; esac; target=${shellQuote(`${PUBLIC_ROOT}/`)}"$relative"; parent=$(dirname "$target"); test -d "$parent"; mode=644; if [ -f "$target" ]; then cp -p -- "$target" ${shellQuote(p.backup)}; mode=$(stat -c '%a' "$target"); else : > ${shellQuote(`${p.root}/created-new`)}; fi; tmp="$parent/.wwcx-stage-${stageId}"; cp -- ${shellQuote(p.candidate)} "$tmp"; chmod "$mode" "$tmp"; mv -f -- "$tmp" "$target"; actual=$(sha256sum "$target" | awk '{print $1}'); test "$actual" = "$expected"; ${auditShell('apply', stageId)}; printf 'target=%s\\nsha256=%s\\nmode=%s\\n' "$target" "$actual" "$(stat -c '%a' "$target")"`;
    const result = await runSsh(guard(command));
    return payload('business159_fs_apply', result, { mutation: true, stageId });
  });

  server.registerTool('business159_fs_rollback', {
    description: 'Roll back one applied stage using its stage-local backup, or remove only the file created by that stage, then record audit evidence.',
    inputSchema: z.object({ stageId: z.string() })
  }, async ({ stageId }) => {
    if (!ALLOW_FILESYSTEM) return { content: [{ type: 'text', text: 'Business159 staged filesystem operations are disabled by policy.' }], isError: true };
    if (!validStageId(stageId)) return { content: [{ type: 'text', text: 'Invalid stage ID.' }], isError: true };
    const p = stagePaths(stageId);
    const command = `test -r ${shellQuote(p.metadata)}; relative=$(sed -n 's/^relative_path=//p' ${shellQuote(p.metadata)}); test -n "$relative"; case "$relative" in /*|*../*|../*|*/..|..) exit 74;; esac; target=${shellQuote(`${PUBLIC_ROOT}/`)}"$relative"; parent=$(dirname "$target"); if [ -f ${shellQuote(p.backup)} ]; then tmp="$parent/.wwcx-rollback-${stageId}"; cp -p -- ${shellQuote(p.backup)} "$tmp"; mv -f -- "$tmp" "$target"; echo 'rollback=restored'; elif [ -f ${shellQuote(`${p.root}/created-new`)} ]; then rm -f -- "$target"; echo 'rollback=removed_stage_created_file'; else echo 'rollback_backup_missing' >&2; exit 75; fi; ${auditShell('rollback', stageId)}; [ -e "$target" ] && stat -c 'target=%n mode=%a size=%s' "$target" || echo 'target=absent'`;
    const result = await runSsh(guard(command));
    return payload('business159_fs_rollback', result, { mutation: true, stageId });
  });

  server.registerTool('business159_exec', {
    description: 'Run an attended caller-supplied account-level command on Business159. Disabled unless BUSINESS159_ENABLE_RAW_SHELL=1; use only when narrower tools cannot perform the explicitly authorized task.',
    inputSchema: z.object({ command: z.string().min(1).max(4000) })
  }, async ({ command }) => {
    if (!ENABLE_RAW_SHELL) return { content: [{ type: 'text', text: 'Raw Business159 shell is disabled by policy (BUSINESS159_ENABLE_RAW_SHELL=0).' }], isError: true };
    const result = await runSsh(guard(command));
    return payload('business159_exec', result, { mutation: true, attendedRawShell: true });
  });

  return server;
}

void serveStdio(createServer);
console.error('business159-live-shell MCP server running on stdio');
