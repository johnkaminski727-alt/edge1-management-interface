import { spawn } from 'node:child_process';
import { McpServer } from '@modelcontextprotocol/server';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';

const SSH_ALIAS = process.env.EDGE1_SSH_ALIAS || 'edge1';
const TIMEOUT_MS = Math.min(Number(process.env.EDGE1_TIMEOUT_MS || 30000), 120000);
const MAX_OUTPUT_BYTES = Math.min(Number(process.env.EDGE1_MAX_OUTPUT_BYTES || 24000), 262144);
const MAX_FILE_BYTES = Math.min(Number(process.env.EDGE1_MAX_FILE_BYTES || 1048576), 8 * 1024 * 1024);
const ALLOW_RESTARTS = process.env.EDGE1_ALLOW_RESTARTS === '1';
const ENABLE_RAW_SHELL = process.env.EDGE1_ENABLE_RAW_SHELL === '1';
const ENABLE_FILE_MUTATIONS = process.env.EDGE1_ENABLE_FILE_MUTATIONS === '1';
const ALLOW_SUDO_SHELL = process.env.EDGE1_ALLOW_SUDO_SHELL === '1';
const ALLOW_COOKIE_MONSTER = process.env.EDGE1_ALLOW_COOKIE_MONSTER === '1';
const COOKIE_MONSTER_TARGET_SHA = process.env.EDGE1_COOKIE_MONSTER_TARGET_SHA || '';
const ALLOW_RELEASES = process.env.EDGE1_ALLOW_RELEASES === '1';
const RELEASE_TARGET_SHA = process.env.EDGE1_RELEASE_TARGET_SHA || '';
const ALLOWED_SERVICES = new Set((process.env.EDGE1_ALLOWED_SERVICES || 'bigbird-ai-gateway').split(',').map(v => v.trim()).filter(Boolean));
const REPOSITORIES = parseRepositories(process.env.EDGE1_REPOSITORIES || 'edge1-interface=/opt/edge1-management-interface;bigbird-gateway=/opt/bigbird-ai-gateway');

function parseRepositories(value) {
  const map = new Map();
  for (const item of value.split(';')) {
    const i = item.indexOf('=');
    if (i <= 0) continue;
    const alias = item.slice(0, i).trim();
    const path = item.slice(i + 1).trim();
    if (/^[a-zA-Z0-9._-]+$/.test(alias) && path.startsWith('/')) map.set(alias, path);
  }
  return map;
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

function redact(text) {
  return String(text)
    .replace(/(authorization:\s*bearer\s+)[^\s]+/gi, '$1[REDACTED]')
    .replace(/((?:token|password|secret|api[_-]?key)\s*[=:]\s*)[^\s]+/gi, '$1[REDACTED]')
    .replace(/(-----BEGIN [A-Z ]*PRIVATE KEY-----)[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----)/g, '$1\n[REDACTED]\n$2');
}

function runSsh(remoteCommand, stdinText = '') {
  return new Promise((resolve) => {
    const started = new Date().toISOString();
    const child = spawn('ssh', [
      '-o', 'BatchMode=yes',
      '-o', 'StrictHostKeyChecking=yes',
      '-o', `ConnectTimeout=${Math.max(1, Math.ceil(TIMEOUT_MS / 1000))}`,
      SSH_ALIAS,
      remoteCommand
    ], { stdio: ['pipe', 'pipe', 'pipe'] });

    let stdout = Buffer.alloc(0);
    let stderr = Buffer.alloc(0);
    let killedForOutput = false;
    let timedOut = false;
    let settled = false;

    const append = (current, chunk) => {
      const next = Buffer.concat([current, chunk]);
      if (next.length > MAX_OUTPUT_BYTES) {
        killedForOutput = true;
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
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: false, exitCode: null, started, ended: new Date().toISOString(), stdout: '', stderr: redact(error.message), timedOut, outputLimited: killedForOutput });
    });
    child.on('close', code => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: code === 0 && !timedOut && !killedForOutput, exitCode: code, started, ended: new Date().toISOString(), stdout: redact(stdout.toString('utf8')), stderr: redact(stderr.toString('utf8')), timedOut, outputLimited: killedForOutput });
    });

    child.stdin.on('error', () => {});
    child.stdin.end(stdinText);
  });
}

function resultPayload(operation, result, extra = {}) {
  const payload = { operation, sshAlias: SSH_ALIAS, ...extra, ...result };
  return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload, isError: !result.ok };
}

function policyError(message) {
  return { content: [{ type: 'text', text: message }], structuredContent: { ok: false, error: message }, isError: true };
}

function validService(service) {
  return /^[A-Za-z0-9@_.-]+$/.test(service) && ALLOWED_SERVICES.has(service);
}

function validCookieMonsterTarget() {
  return /^[0-9a-f]{40}$/.test(COOKIE_MONSTER_TARGET_SHA);
}

function validReleaseTarget() {
  return /^[0-9a-f]{40}$/.test(RELEASE_TARGET_SHA);
}

function edge1Repository() {
  return REPOSITORIES.get('edge1-interface') || null;
}

function cookieMonsterCommand(action) {
  const repo = edge1Repository();
  if (!repo) return null;
  const qRepo = shellQuote(repo);
  const script = shellQuote(`${repo}/deploy/cookie_monster_edge1_activate.py`);
  const target = shellQuote(COOKIE_MONSTER_TARGET_SHA);
  if (action === 'preflight') return `sudo -n /usr/bin/python3 ${script} --repo ${qRepo}`;
  if (action === 'sync_sources') {
    return `set -eu; repo=${qRepo}; target=${target}; test "$(git -C "$repo" symbolic-ref --short HEAD)" = main; test -z "$(git -C "$repo" status --porcelain)"; before=$(git -C "$repo" rev-parse HEAD); git -C "$repo" fetch --prune origin; git -C "$repo" cat-file -e "$target^{commit}"; git -C "$repo" merge-base --is-ancestor "$target" origin/main; git -C "$repo" merge --ff-only "$target"; after=$(git -C "$repo" rev-parse HEAD); test "$after" = "$target"; printf 'before=%s\\nafter=%s\\nbranch=' "$before" "$after"; git -C "$repo" symbolic-ref --short HEAD; printf 'status='; git -C "$repo" status --short --branch`;
  }
  if (action === 'activate') return `set -eu; repo=${qRepo}; target=${target}; test "$(git -C "$repo" rev-parse HEAD)" = "$target"; sudo -n /usr/bin/python3 ${script} --repo ${qRepo} --apply`;
  if (action === 'rollback_last') return `sudo -n /usr/bin/python3 ${script} --repo ${qRepo} --rollback-last`;
  return null;
}

function releaseCommand(action) {
  const repo = edge1Repository();
  if (!repo) return null;
  const qRepo = shellQuote(repo);
  const target = shellQuote(RELEASE_TARGET_SHA);
  const controller = '/usr/local/libexec/edge1-release-controller';
  if (action === 'status') {
    return `if test -x ${shellQuote(controller)}; then sudo -n ${shellQuote(controller)} status --write-status --publish-status; else printf '%s\\n' '{"schema":"wwcx.edge1-release-status.v1","healthy":false,"action_required":true,"controller_installed":false,"automatic_promotion":false}'; fi`;
  }
  if (action === 'rollback_last') return `sudo -n ${shellQuote(controller)} rollback-last && sudo -n ${shellQuote(controller)} status --write-status --publish-status`;
  if (action === 'reconcile') {
    return `set -eu; repo=${qRepo}; target=${target}; tmp="/tmp/edge1-release-bootstrap-$$"; cleanup(){ git -C "$repo" worktree remove --force "$tmp" >/dev/null 2>&1 || true; rm -rf "$tmp" >/dev/null 2>&1 || true; }; trap cleanup EXIT HUP INT TERM; git -C "$repo" fetch --prune origin; git -C "$repo" cat-file -e "$target^{commit}"; git -C "$repo" merge-base --is-ancestor "$target" origin/main; git -C "$repo" worktree add --detach "$tmp" "$target"; sudo -n /usr/bin/python3 "$tmp/deploy/install_edge1_release_controller.py" --repo "$tmp" --apply; test -x ${shellQuote(controller)}; source=/opt/edge1-management-source; test "$(git -C "$source" symbolic-ref --short HEAD)" = main; test -z "$(git -C "$source" status --porcelain)"; git -C "$source" fetch --prune origin; git -C "$source" cat-file -e "$target^{commit}"; git -C "$source" merge-base --is-ancestor "$target" origin/main; sudo -n ${shellQuote(controller)} prepare "$target"; sudo -n ${shellQuote(controller)} promote "$target"; sudo -n ${shellQuote(controller)} status --write-status --publish-status`;
  }
  return null;
}

const FILE_HELPER = String.raw`
import base64, hashlib, json, os, shutil, stat, sys, tempfile, time
req=json.load(sys.stdin)
a=req.get('action')
p=req.get('path')
max_bytes=int(req.get('maxBytes') or 1048576)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b)
    return h.hexdigest()
def meta(path):
    st=os.lstat(path)
    out={'path':path,'mode':oct(stat.S_IMODE(st.st_mode)),'size':st.st_size,'mtimeNs':st.st_mtime_ns,'isFile':stat.S_ISREG(st.st_mode),'isDir':stat.S_ISDIR(st.st_mode),'isSymlink':stat.S_ISLNK(st.st_mode)}
    if stat.S_ISREG(st.st_mode) and st.st_size <= max_bytes: out['sha256']=sha(path)
    if stat.S_ISLNK(st.st_mode): out['linkTarget']=os.readlink(path)
    return out
def check_expected(path, expected):
    if expected is None: return
    actual=sha(path) if os.path.isfile(path) else None
    if actual != expected: raise RuntimeError('expectedSha256 mismatch')
def decode_content():
    c=req.get('content','')
    return base64.b64decode(c) if req.get('encoding')=='base64' else c.encode('utf-8')
def backup(path):
    if not req.get('backup', True) or not os.path.lexists(path): return None
    stamp=time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    dst=path+'.agent-backup-'+stamp
    i=0
    while os.path.lexists(dst):
        i+=1; dst=path+'.agent-backup-'+stamp+'-'+str(i)
    if os.path.isdir(path) and not os.path.islink(path): shutil.copytree(path,dst,symlinks=True)
    else: shutil.copy2(path,dst,follow_symlinks=False)
    return dst
out={'ok':True,'action':a}
if a=='stat': out['entry']=meta(p)
elif a=='list':
    entries=[]
    for name in sorted(os.listdir(p))[:int(req.get('limit') or 1000)]:
        q=os.path.join(p,name)
        try: entries.append(meta(q))
        except OSError as e: entries.append({'path':q,'error':str(e)})
    out['entries']=entries
elif a=='read':
    st=os.stat(p)
    if st.st_size > max_bytes: raise RuntimeError('file exceeds maxBytes')
    data=open(p,'rb').read()
    out['sha256']=hashlib.sha256(data).hexdigest(); out['size']=len(data)
    if req.get('encoding')=='base64': out['encoding']='base64'; out['content']=base64.b64encode(data).decode('ascii')
    else: out['encoding']='utf8'; out['content']=data.decode('utf-8')
elif a in ('write','append'):
    parent=os.path.dirname(p) or '.'
    if req.get('createParents'): os.makedirs(parent,exist_ok=True)
    check_expected(p, req.get('expectedSha256')) if os.path.exists(p) else None
    data=decode_content(); out['backupPath']=backup(p) if a=='write' else None
    if a=='append':
        with open(p,'ab') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    else:
        fd,tmp=tempfile.mkstemp(prefix='.agent-write-',dir=parent)
        try:
            with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
            if os.path.exists(p): os.chmod(tmp,stat.S_IMODE(os.stat(p).st_mode))
            elif req.get('mode') is not None: os.chmod(tmp,int(str(req['mode']),8))
            os.replace(tmp,p)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    out['entry']=meta(p)
elif a=='mkdir':
    os.makedirs(p,exist_ok=bool(req.get('existOk',True)))
    if req.get('mode') is not None: os.chmod(p,int(str(req['mode']),8))
    out['entry']=meta(p)
elif a in ('move','copy'):
    d=req.get('destination')
    if not d: raise RuntimeError('destination is required')
    if req.get('createParents'): os.makedirs(os.path.dirname(d) or '.',exist_ok=True)
    out['backupPath']=backup(d)
    if a=='move': shutil.move(p,d)
    elif os.path.isdir(p) and not os.path.islink(p): shutil.copytree(p,d,dirs_exist_ok=bool(req.get('overwrite')))
    else: shutil.copy2(p,d,follow_symlinks=False)
    out['destination']=meta(d)
elif a=='remove':
    out['before']=meta(p)
    if req.get('backup',True): out['backupPath']=backup(p)
    if os.path.isdir(p) and not os.path.islink(p):
        if not req.get('recursive'): os.rmdir(p)
        else: shutil.rmtree(p)
    else: os.unlink(p)
elif a=='chmod':
    os.chmod(p,int(str(req.get('mode')),8),follow_symlinks=False); out['entry']=meta(p)
else: raise RuntimeError('unsupported action')
print(json.dumps(out,separators=(',',':')))
`;

function fileCommand(useSudo) {
  const python = `/usr/bin/python3 -c ${shellQuote(FILE_HELPER)}`;
  return useSudo ? `sudo -n ${python}` : python;
}

function createServer() {
  const server = new McpServer(
    { name: 'edge1-live-shell', version: '0.4.0' },
    { instructions: 'Authenticated SSH/tunnel operator for Edge1. Verify identity first. Structured file read/write/update and caller-supplied shell execution are available when enabled by operator policy. Preserve evidence and backups for material changes. Never expose credentials or secret material in normal responses.' }
  );

  server.registerTool('edge1_capabilities', {
    description: 'Report the live-shell sidecar capability profile without touching Edge1.',
    inputSchema: z.object({})
  }, async () => {
    const payload = {
      ok: true,
      sshAlias: SSH_ALIAS,
      rawShell: ENABLE_RAW_SHELL,
      fileRead: true,
      fileMutations: ENABLE_FILE_MUTATIONS,
      sudoShell: ENABLE_RAW_SHELL && ALLOW_SUDO_SHELL,
      serviceRestarts: ALLOW_RESTARTS,
      cookieMonsterMutations: ALLOW_COOKIE_MONSTER,
      releaseMutations: ALLOW_RELEASES,
      maxOutputBytes: MAX_OUTPUT_BYTES,
      maxFileBytes: MAX_FILE_BYTES,
      repositories: [...REPOSITORIES.keys()],
      services: [...ALLOWED_SERVICES]
    };
    return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
  });

  server.registerTool('edge1_connection_test', {
    description: 'Verify authenticated SSH connectivity and return remote hostname, principal, UID, and kernel identity.',
    inputSchema: z.object({})
  }, async () => {
    const command = "printf 'hostname='; hostname -f; printf 'principal='; id -un; printf 'uid='; id -u; printf 'kernel='; uname -srm";
    return resultPayload('connection_test', await runSsh(command));
  });

  server.registerTool('edge1_inspect', {
    description: 'Perform a bounded Edge1 inspection: overview, resources, service status/logs, or allowlisted repository status.',
    inputSchema: z.object({
      kind: z.enum(['overview', 'resources', 'service_status', 'service_logs', 'repository_status']),
      service: z.string().optional(),
      repository: z.string().optional(),
      lines: z.number().int().min(10).max(300).default(100)
    })
  }, async ({ kind, service, repository, lines }) => {
    let command;
    if (kind === 'overview') command = "date -u +%Y-%m-%dT%H:%M:%SZ; hostname -f; id; uptime; systemctl --failed --no-pager || true; ss -lntup || true";
    if (kind === 'resources') command = "df -h /; df -i /; (command -v free >/dev/null && free -h || true); uptime";
    if (kind === 'service_status') {
      if (!service || !validService(service)) return policyError('Service is missing or not allowlisted.');
      command = `systemctl is-enabled ${shellQuote(service)} 2>&1 || true; systemctl is-active ${shellQuote(service)} 2>&1 || true; systemctl --no-pager --full status ${shellQuote(service)} 2>&1`;
    }
    if (kind === 'service_logs') {
      if (!service || !validService(service)) return policyError('Service is missing or not allowlisted.');
      command = `journalctl -u ${shellQuote(service)} -n ${Number(lines)} --no-pager --output=short-iso 2>&1`;
    }
    if (kind === 'repository_status') {
      const path = repository ? REPOSITORIES.get(repository) : null;
      if (!path) return policyError(`Repository alias is missing or not allowlisted. Allowed aliases: ${[...REPOSITORIES.keys()].join(', ')}`);
      command = `git -C ${shellQuote(path)} rev-parse --show-toplevel; git -C ${shellQuote(path)} status --short --branch; git -C ${shellQuote(path)} remote -v; git -C ${shellQuote(path)} log -1 --oneline --decorate`;
    }
    return resultPayload('inspect', await runSsh(command), { kind, service: service || null, repository: repository || null });
  });

  server.registerTool('edge1_fs', {
    description: 'Structured Edge1 filesystem access. Read/stat/list are always available. Write, append, mkdir, move, copy, remove and chmod require EDGE1_ENABLE_FILE_MUTATIONS=1. Existing-file writes are atomic and backup-first by default. Set sudo=true only when the sidecar is configured with EDGE1_ALLOW_SUDO_SHELL=1 and the remote sudo policy permits it.',
    inputSchema: z.object({
      action: z.enum(['stat', 'list', 'read', 'write', 'append', 'mkdir', 'move', 'copy', 'remove', 'chmod']),
      path: z.string().min(1).max(4096),
      destination: z.string().max(4096).optional(),
      content: z.string().max(8 * 1024 * 1024).optional(),
      encoding: z.enum(['utf8', 'base64']).default('utf8'),
      expectedSha256: z.string().regex(/^[0-9a-f]{64}$/).optional(),
      backup: z.boolean().default(true),
      createParents: z.boolean().default(false),
      overwrite: z.boolean().default(false),
      recursive: z.boolean().default(false),
      existOk: z.boolean().default(true),
      mode: z.string().regex(/^[0-7]{3,4}$/).optional(),
      sudo: z.boolean().default(false),
      limit: z.number().int().min(1).max(5000).default(1000),
      maxBytes: z.number().int().min(1).max(MAX_FILE_BYTES).default(MAX_FILE_BYTES)
    })
  }, async (args) => {
    const readOnly = new Set(['stat', 'list', 'read']);
    if (!readOnly.has(args.action) && !ENABLE_FILE_MUTATIONS) return policyError('Filesystem mutations are disabled by policy (EDGE1_ENABLE_FILE_MUTATIONS=0).');
    if (args.sudo && !ALLOW_SUDO_SHELL) return policyError('sudo filesystem access is disabled by policy (EDGE1_ALLOW_SUDO_SHELL=0).');
    if (args.action === 'write' || args.action === 'append') {
      if (args.content === undefined) return policyError('content is required for write/append.');
    }
    if ((args.action === 'move' || args.action === 'copy') && !args.destination) return policyError('destination is required for move/copy.');
    if (args.action === 'chmod' && !args.mode) return policyError('mode is required for chmod.');
    const request = { ...args, maxBytes: Math.min(args.maxBytes, MAX_FILE_BYTES) };
    const result = await runSsh(fileCommand(args.sudo), JSON.stringify(request));
    return resultPayload('fs', result, { action: args.action, path: args.path, destination: args.destination || null, sudo: args.sudo });
  });

  server.registerTool('edge1_restart_service', {
    description: 'Restart one allowlisted Edge1 systemd service through non-interactive sudo. Requires EDGE1_ALLOW_RESTARTS=1.',
    inputSchema: z.object({ service: z.string() })
  }, async ({ service }) => {
    if (!ALLOW_RESTARTS) return policyError('Service restarts are disabled by policy (EDGE1_ALLOW_RESTARTS=0).');
    if (!validService(service)) return policyError('Service is not allowlisted.');
    const command = `sudo -n systemctl restart ${shellQuote(service)} && systemctl is-active ${shellQuote(service)} && systemctl --no-pager --full status ${shellQuote(service)}`;
    return resultPayload('restart_service', await runSsh(command), { service });
  });

  server.registerTool('edge1_cookie_monster', {
    description: 'Run the fixed Cookie Monster Alpha staging lifecycle on Edge1. Preflight is read-only; source sync, activation and rollback require EDGE1_ALLOW_COOKIE_MONSTER=1.',
    inputSchema: z.object({ action: z.enum(['preflight', 'sync_sources', 'activate', 'rollback_last']) })
  }, async ({ action }) => {
    if (action !== 'preflight' && !ALLOW_COOKIE_MONSTER) return policyError('Cookie Monster mutation actions are disabled by policy (EDGE1_ALLOW_COOKIE_MONSTER=0).');
    if ((action === 'sync_sources' || action === 'activate') && !validCookieMonsterTarget()) return policyError('EDGE1_COOKIE_MONSTER_TARGET_SHA must be an exact 40-character Git commit SHA.');
    const command = cookieMonsterCommand(action);
    if (!command) return policyError('Cookie Monster repository alias is unavailable.');
    return resultPayload('cookie_monster', await runSsh(command), { action, targetSha: (action === 'sync_sources' || action === 'activate') ? COOKIE_MONSTER_TARGET_SHA : null });
  });

  server.registerTool('edge1_release', {
    description: 'Read or reconcile the persistent Edge1 runtime release controller. Reconcile is commit-pinned and rollback returns to the recorded previous release.',
    inputSchema: z.object({ action: z.enum(['status', 'reconcile', 'rollback_last']) })
  }, async ({ action }) => {
    if (action !== 'status' && !ALLOW_RELEASES) return policyError('Edge1 release mutations are disabled by policy (EDGE1_ALLOW_RELEASES=0).');
    if (action === 'reconcile' && !validReleaseTarget()) return policyError('EDGE1_RELEASE_TARGET_SHA must be an exact 40-character Git commit SHA.');
    const command = releaseCommand(action);
    if (!command) return policyError('Edge1 repository alias is unavailable.');
    return resultPayload('release', await runSsh(command), { action, targetSha: action === 'reconcile' ? RELEASE_TARGET_SHA : null });
  });

  server.registerTool('edge1_exec', {
    description: 'Run a caller-supplied POSIX shell command on Edge1 over authenticated SSH. Requires EDGE1_ENABLE_RAW_SHELL=1. Supports working directory, stdin, and optional sudo shell when EDGE1_ALLOW_SUDO_SHELL=1 and remote sudo policy permits it.',
    inputSchema: z.object({
      command: z.string().min(1).max(16000),
      cwd: z.string().min(1).max(4096).optional(),
      stdin: z.string().max(8 * 1024 * 1024).default(''),
      sudo: z.boolean().default(false)
    })
  }, async ({ command, cwd, stdin, sudo }) => {
    if (!ENABLE_RAW_SHELL) return policyError('Raw shell is disabled by policy (EDGE1_ENABLE_RAW_SHELL=0).');
    if (sudo && !ALLOW_SUDO_SHELL) return policyError('sudo shell is disabled by policy (EDGE1_ALLOW_SUDO_SHELL=0).');
    const script = `${cwd ? `cd -- ${shellQuote(cwd)} && ` : ''}${command}`;
    const remote = sudo ? `sudo -n /bin/sh -lc ${shellQuote(script)}` : `/bin/sh -lc ${shellQuote(script)}`;
    return resultPayload('exec', await runSsh(remote, stdin), { cwd: cwd || null, sudo });
  });

  return server;
}

void serveStdio(createServer);
console.error('edge1-live-shell MCP server running on stdio');
