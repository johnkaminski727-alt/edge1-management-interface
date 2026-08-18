import { spawn } from 'node:child_process';
import { McpServer } from '@modelcontextprotocol/server';
import { serveStdio } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';

const SSH_ALIAS = process.env.EDGE1_SSH_ALIAS || 'edge1';
const TIMEOUT_MS = Math.min(Number(process.env.EDGE1_TIMEOUT_MS || 30000), 120000);
const MAX_OUTPUT_BYTES = Math.min(Number(process.env.EDGE1_MAX_OUTPUT_BYTES || 24000), 262144);
const ALLOW_RESTARTS = process.env.EDGE1_ALLOW_RESTARTS === '1';
const ENABLE_RAW_SHELL = process.env.EDGE1_ENABLE_RAW_SHELL === '1';
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
    let killedForOutput = false;
    let timedOut = false;

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
      clearTimeout(timer);
      resolve({ ok: false, exitCode: null, started, ended: new Date().toISOString(), stdout: '', stderr: redact(error.message), timedOut, outputLimited: killedForOutput });
    });
    child.on('close', code => {
      clearTimeout(timer);
      resolve({ ok: code === 0 && !timedOut && !killedForOutput, exitCode: code, started, ended: new Date().toISOString(), stdout: redact(stdout.toString('utf8')), stderr: redact(stderr.toString('utf8')), timedOut, outputLimited: killedForOutput });
    });
  });
}

function resultPayload(operation, result, extra = {}) {
  const payload = { operation, sshAlias: SSH_ALIAS, ...extra, ...result };
  return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], isError: !result.ok };
}

function validService(service) {
  return /^[A-Za-z0-9@_.-]+$/.test(service) && ALLOWED_SERVICES.has(service);
}

function createServer() {
  const server = new McpServer(
    { name: 'edge1-live-shell', version: '0.1.0' },
    { instructions: 'Read first. Verify Edge1 identity before mutation. Prefer edge1_inspect over edge1_exec. Never request or expose credentials. Restarts and raw shell are disabled unless explicitly enabled by the operator environment.' }
  );

  server.registerTool('edge1_connection_test', {
    description: 'Verify authenticated SSH connectivity and return the remote Edge1 hostname, principal, UID, and kernel identity. Run this before other Edge1 operations when connectivity is unknown.',
    inputSchema: z.object({})
  }, async () => {
    const command = "printf 'hostname='; hostname -f; printf 'principal='; id -un; printf 'uid='; id -u; printf 'kernel='; uname -srm";
    return resultPayload('connection_test', await runSsh(command));
  });

  server.registerTool('edge1_inspect', {
    description: 'Perform a bounded read-only Edge1 inspection: overview, resources, service status/logs, or allowlisted repository status.',
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
      if (!service || !validService(service)) return { content: [{ type: 'text', text: 'Service is missing or not allowlisted.' }], isError: true };
      command = `systemctl is-enabled ${shellQuote(service)} 2>&1 || true; systemctl is-active ${shellQuote(service)} 2>&1 || true; systemctl --no-pager --full status ${shellQuote(service)} 2>&1`;
    }
    if (kind === 'service_logs') {
      if (!service || !validService(service)) return { content: [{ type: 'text', text: 'Service is missing or not allowlisted.' }], isError: true };
      command = `journalctl -u ${shellQuote(service)} -n ${Number(lines)} --no-pager --output=short-iso 2>&1`;
    }
    if (kind === 'repository_status') {
      const path = repository ? REPOSITORIES.get(repository) : null;
      if (!path) return { content: [{ type: 'text', text: `Repository alias is missing or not allowlisted. Allowed aliases: ${[...REPOSITORIES.keys()].join(', ')}` }], isError: true };
      command = `git -C ${shellQuote(path)} rev-parse --show-toplevel; git -C ${shellQuote(path)} status --short --branch; git -C ${shellQuote(path)} remote -v; git -C ${shellQuote(path)} log -1 --oneline --decorate`;
    }
    return resultPayload('inspect', await runSsh(command), { kind, service: service || null, repository: repository || null });
  });

  server.registerTool('edge1_restart_service', {
    description: 'Restart one allowlisted Edge1 systemd service through non-interactive sudo. Disabled unless EDGE1_ALLOW_RESTARTS=1.',
    inputSchema: z.object({ service: z.string() })
  }, async ({ service }) => {
    if (!ALLOW_RESTARTS) return { content: [{ type: 'text', text: 'Service restarts are disabled by policy (EDGE1_ALLOW_RESTARTS=0).' }], isError: true };
    if (!validService(service)) return { content: [{ type: 'text', text: 'Service is not allowlisted.' }], isError: true };
    const command = `sudo -n systemctl restart ${shellQuote(service)} && systemctl is-active ${shellQuote(service)} && systemctl --no-pager --full status ${shellQuote(service)}`;
    return resultPayload('restart_service', await runSsh(command), { service });
  });

  server.registerTool('edge1_exec', {
    description: 'Run an attended caller-supplied command on Edge1. Disabled unless EDGE1_ENABLE_RAW_SHELL=1. Use only when narrower tools cannot perform the explicitly authorized task.',
    inputSchema: z.object({ command: z.string().min(1).max(4000) })
  }, async ({ command }) => {
    if (!ENABLE_RAW_SHELL) return { content: [{ type: 'text', text: 'Raw shell is disabled by policy (EDGE1_ENABLE_RAW_SHELL=0).' }], isError: true };
    return resultPayload('exec', await runSsh(command));
  });

  return server;
}

void serveStdio(createServer);
console.error('edge1-live-shell MCP server running on stdio');
