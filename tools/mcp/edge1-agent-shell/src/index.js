import { createHash, randomUUID, timingSafeEqual } from 'node:crypto';
import { createReadStream, appendFileSync, mkdirSync, statSync } from 'node:fs';
import { promises as fs } from 'node:fs';
import { createServer as createHttpServer } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { McpServer, createMcpHandler } from '@modelcontextprotocol/server';
import { toNodeHandler } from '@modelcontextprotocol/node';
import * as z from 'zod/v4';

const MODE = process.env.EDGE1_AGENT_SHELL_MODE || 'full';
if (!['full', 'read-only'].includes(MODE)) throw new Error('EDGE1_AGENT_SHELL_MODE must be full or read-only');

const READ_ONLY = MODE === 'read-only';
const HOST = process.env.EDGE1_AGENT_SHELL_HOST || '127.0.0.1';
const PORT = Number(process.env.EDGE1_AGENT_SHELL_PORT || 8114);
const MCP_PATH = process.env.EDGE1_AGENT_SHELL_PATH || '/mcp';
const TOKEN_FILE = process.env.EDGE1_AGENT_SHELL_TOKEN_FILE || '/etc/edge1-operator/mcp-token';
const AUDIT_LOG = process.env.EDGE1_AGENT_SHELL_AUDIT_LOG || '/var/log/wwcx-edge1-agent-shell/audit.jsonl';
const DEFAULT_TIMEOUT_MS = Math.min(Number(process.env.EDGE1_AGENT_SHELL_TIMEOUT_MS || 120000), 900000);
const DEFAULT_OUTPUT_BYTES = Math.min(Number(process.env.EDGE1_AGENT_SHELL_MAX_OUTPUT_BYTES || 131072), 1048576);
const MAX_FILE_BYTES = Math.min(Number(process.env.EDGE1_AGENT_SHELL_MAX_FILE_BYTES || 4194304), 16777216);
const ALLOWED_ORIGINS = new Set((process.env.EDGE1_AGENT_SHELL_ALLOWED_ORIGINS || '').split(',').map(v => v.trim()).filter(Boolean));

function assertLoopback(host) {
  if (!['127.0.0.1', '::1', 'localhost'].includes(host)) throw new Error('Edge1 Agent Shell must bind to loopback only');
  if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error('invalid EDGE1_AGENT_SHELL_PORT');
}

function redact(text) {
  return String(text)
    .replace(/(authorization:\s*bearer\s+)[^\s]+/gi, '$1[REDACTED]')
    .replace(/((?:token|password|passwd|secret|api[_-]?key|cookie|session)\s*[=:]\s*)[^\s]+/gi, '$1[REDACTED]')
    .replace(/([a-z][a-z0-9+.-]*:\/\/)[^\s/@]+:[^\s/@]+@/gi, '$1[REDACTED]@')
    .replace(/(-----BEGIN [A-Z ]*PRIVATE KEY-----)[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----)/g, '$1\n[REDACTED]\n$2');
}

function loadToken() {
  const st = statSync(TOKEN_FILE);
  if (!st.isFile()) throw new Error('Agent Shell bearer token path must be a regular file');
  if ((st.mode & 0o007) !== 0) throw new Error('Agent Shell bearer token must not be world-accessible');
  return fs.readFile(TOKEN_FILE, 'utf8').then(value => {
    const token = value.trim();
    if (token.length < 32 || /\s/.test(token)) throw new Error('Agent Shell bearer token is invalid');
    return token;
  });
}

function tokenMatches(header, token) {
  const expected = `Bearer ${token}`;
  const a = Buffer.from(String(header || ''));
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function mutationDenied(tool) {
  return {
    content: [{ type: 'text', text: JSON.stringify({ tool, ok: false, error: 'Agent Shell is running in read-only mode.' }) }],
    isError: true
  };
}

function audit(tool, requestId, metadata = {}) {
  try {
    mkdirSync(path.dirname(AUDIT_LOG), { recursive: true, mode: 0o700 });
    appendFileSync(AUDIT_LOG, JSON.stringify({
      schema: 'wwcx.edge1-agent-shell.audit.v1',
      timestamp: new Date().toISOString(),
      request_id: requestId,
      tool,
      mode: MODE,
      ...metadata
    }) + '\n', { encoding: 'utf8', mode: 0o600 });
  } catch {
    // The operational tool result must not be replaced by an audit-path failure.
  }
}

function shellResult(tool, requestId, result, extra = {}) {
  audit(tool, requestId, {
    ok: result.ok,
    exit_code: result.exitCode,
    timed_out: result.timedOut,
    output_limited: result.outputLimited,
    ...extra.audit
  });
  const payload = {
    tool,
    request_id: requestId,
    mode: MODE,
    ...extra.public,
    ...result
  };
  return {
    content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
    structuredContent: payload,
    isError: !result.ok
  };
}

function runShell({ command, cwd, stdin, environment, timeoutMs, maxOutputBytes, redactOutput = true }) {
  return new Promise((resolve) => {
    const started = new Date().toISOString();
    const timeout = Math.max(1000, Math.min(Number(timeoutMs || DEFAULT_TIMEOUT_MS), 900000));
    const outputLimit = Math.max(4096, Math.min(Number(maxOutputBytes || DEFAULT_OUTPUT_BYTES), 1048576));
    const env = { ...process.env };
    for (const [key, value] of Object.entries(environment || {})) {
      if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) env[key] = String(value);
    }

    const child = spawn('/bin/sh', ['-lc', command], {
      cwd: cwd || '/',
      env,
      detached: true,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = Buffer.alloc(0);
    let stderr = Buffer.alloc(0);
    let outputLimited = false;
    let timedOut = false;

    const stop = (signal) => {
      try { process.kill(-child.pid, signal); } catch { try { child.kill(signal); } catch {} }
    };

    const append = (current, chunk) => {
      const next = Buffer.concat([current, chunk]);
      if (next.length > outputLimit) {
        outputLimited = true;
        stop('SIGTERM');
        return next.subarray(0, outputLimit);
      }
      return next;
    };

    child.stdout.on('data', chunk => { stdout = append(stdout, chunk); });
    child.stderr.on('data', chunk => { stderr = append(stderr, chunk); });
    child.stdin.on('error', () => {});
    if (stdin) child.stdin.end(Buffer.from(stdin, 'base64'));
    else child.stdin.end();

    const timer = setTimeout(() => {
      timedOut = true;
      stop('SIGTERM');
      setTimeout(() => stop('SIGKILL'), 1000).unref();
    }, timeout);

    child.on('error', error => {
      clearTimeout(timer);
      const errorText = redactOutput ? redact(error.message) : error.message;
      resolve({ ok: false, exitCode: null, started, ended: new Date().toISOString(), stdout: '', stderr: errorText, timedOut, outputLimited });
    });
    child.on('close', code => {
      clearTimeout(timer);
      const out = stdout.toString('utf8');
      const err = stderr.toString('utf8');
      resolve({
        ok: code === 0 && !timedOut && !outputLimited,
        exitCode: code,
        started,
        ended: new Date().toISOString(),
        stdout: redactOutput ? redact(out) : out,
        stderr: redactOutput ? redact(err) : err,
        timedOut,
        outputLimited
      });
    });
  });
}

async function sha256File(filePath) {
  const hash = createHash('sha256');
  await new Promise((resolve, reject) => {
    const stream = createReadStream(filePath);
    stream.on('data', chunk => hash.update(chunk));
    stream.on('end', resolve);
    stream.on('error', reject);
  });
  return hash.digest('hex');
}

async function fileMetadata(filePath) {
  const st = await fs.lstat(filePath);
  return {
    path: filePath,
    size: st.size,
    mode: (st.mode & 0o7777).toString(8).padStart(4, '0'),
    uid: st.uid,
    gid: st.gid,
    mtime: st.mtime.toISOString(),
    type: st.isFile() ? 'file' : st.isDirectory() ? 'directory' : st.isSymbolicLink() ? 'symlink' : 'other'
  };
}

async function ensureExpectedHash(filePath, expectedSha256) {
  if (!expectedSha256) return null;
  if (!/^[0-9a-f]{64}$/.test(expectedSha256)) throw new Error('expected_sha256 must be a lowercase 64-character SHA-256');
  const actual = await sha256File(filePath);
  if (actual !== expectedSha256) throw new Error(`SHA-256 precondition failed: expected ${expectedSha256}, found ${actual}`);
  return actual;
}

async function atomicReplace(filePath, data, permissions) {
  const parent = path.dirname(filePath);
  const temp = path.join(parent, `.${path.basename(filePath)}.agent-shell-${randomUUID()}.tmp`);
  try {
    await fs.writeFile(temp, data, { mode: permissions ? Number.parseInt(permissions, 8) : 0o600, flag: 'wx' });
    const handle = await fs.open(temp, 'r');
    await handle.sync();
    await handle.close();
    if (permissions) await fs.chmod(temp, Number.parseInt(permissions, 8));
    await fs.rename(temp, filePath);
  } finally {
    await fs.rm(temp, { force: true }).catch(() => {});
  }
}

function buildServer() {
  const server = new McpServer(
    { name: 'wwcx-edge1-agent-shell', version: '0.1.0' },
    { instructions: 'Authenticated WW.CX Edge1 administration over the private MCP tunnel. This surface is intentionally capable of read, write, update, service control, and arbitrary shell execution when mode=full. Inspect before changing and record/verify consequential work.' }
  );

  server.registerTool('edge1_agent_identity', {
    description: 'Return the Agent Shell process and Edge1 host identity.',
    inputSchema: z.object({}),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  }, async () => {
    const requestId = randomUUID();
    const payload = {
      tool: 'edge1_agent_identity', request_id: requestId, ok: true, mode: MODE,
      hostname: os.hostname(), platform: os.platform(), release: os.release(), arch: os.arch(),
      uid: process.getuid?.() ?? null, gid: process.getgid?.() ?? null, pid: process.pid
    };
    audit('edge1_agent_identity', requestId, { ok: true });
    return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
  });

  server.registerTool('edge1_agent_capabilities', {
    description: 'Describe the active Agent Shell capability mode and transport limits.',
    inputSchema: z.object({}),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  }, async () => {
    const requestId = randomUUID();
    const payload = {
      tool: 'edge1_agent_capabilities', request_id: requestId, ok: true, mode: MODE,
      arbitrary_shell: !READ_ONLY,
      file_read: true,
      file_write: !READ_ONLY,
      file_patch: !READ_ONLY,
      file_manage: !READ_ONLY,
      service_control: !READ_ONLY,
      max_command_timeout_ms: 900000,
      max_output_bytes: 1048576,
      max_file_payload_bytes: MAX_FILE_BYTES,
      bind: `${HOST}:${PORT}`,
      endpoint: MCP_PATH,
      audit_log: AUDIT_LOG
    };
    audit('edge1_agent_capabilities', requestId, { ok: true });
    return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
  });

  server.registerTool('edge1_agent_exec', {
    description: 'Run an arbitrary shell command on Edge1. In full mode this is an intentionally unrestricted administrative escape hatch, constrained only by the Agent Shell process operating-system privileges.',
    inputSchema: z.object({
      command: z.string().min(1).max(65536),
      cwd: z.string().min(1).max(4096).optional(),
      stdin_base64: z.string().max(8388608).optional(),
      environment: z.record(z.string(), z.string()).optional(),
      timeout_ms: z.number().int().min(1000).max(900000).optional(),
      max_output_bytes: z.number().int().min(4096).max(1048576).optional(),
      redact_output: z.boolean().default(true)
    }),
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true }
  }, async ({ command, cwd, stdin_base64, environment, timeout_ms, max_output_bytes, redact_output }) => {
    if (READ_ONLY) return mutationDenied('edge1_agent_exec');
    const requestId = randomUUID();
    const commandSha256 = createHash('sha256').update(command).digest('hex');
    const result = await runShell({ command, cwd, stdin: stdin_base64, environment, timeoutMs: timeout_ms, maxOutputBytes: max_output_bytes, redactOutput: redact_output });
    return shellResult('edge1_agent_exec', requestId, result, {
      public: { cwd: cwd || '/', command_sha256: commandSha256 },
      audit: { command_sha256: commandSha256, cwd: cwd || '/' }
    });
  });

  server.registerTool('edge1_agent_file_stat', {
    description: 'Return metadata and, for regular files, SHA-256 for any filesystem path visible to the Agent Shell process.',
    inputSchema: z.object({ path: z.string().min(1).max(4096) }),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  }, async ({ path: filePath }) => {
    const requestId = randomUUID();
    try {
      const meta = await fileMetadata(filePath);
      if (meta.type === 'file') meta.sha256 = await sha256File(filePath);
      audit('edge1_agent_file_stat', requestId, { ok: true, path: filePath });
      const payload = { tool: 'edge1_agent_file_stat', request_id: requestId, ok: true, ...meta };
      return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
    } catch (error) {
      audit('edge1_agent_file_stat', requestId, { ok: false, path: filePath });
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_file_stat', request_id: requestId, ok: false, error: redact(error.message) }) }], isError: true };
    }
  });

  server.registerTool('edge1_agent_file_read', {
    description: 'Read any file visible to the Agent Shell process in bounded chunks as UTF-8 text or base64.',
    inputSchema: z.object({
      path: z.string().min(1).max(4096),
      offset: z.number().int().min(0).default(0),
      length: z.number().int().min(1).max(MAX_FILE_BYTES).default(Math.min(MAX_FILE_BYTES, 1048576)),
      encoding: z.enum(['utf8', 'base64']).default('utf8'),
      redact_output: z.boolean().default(true)
    }),
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false }
  }, async ({ path: filePath, offset, length, encoding, redact_output }) => {
    const requestId = randomUUID();
    try {
      const handle = await fs.open(filePath, 'r');
      const st = await handle.stat();
      const available = Math.max(0, st.size - offset);
      const count = Math.min(length, available);
      const buffer = Buffer.alloc(count);
      if (count > 0) await handle.read(buffer, 0, count, offset);
      await handle.close();
      let data = encoding === 'base64' ? buffer.toString('base64') : buffer.toString('utf8');
      if (encoding === 'utf8' && redact_output) data = redact(data);
      const payload = {
        tool: 'edge1_agent_file_read', request_id: requestId, ok: true,
        path: filePath, offset, bytes_read: count, size: st.size,
        eof: offset + count >= st.size, encoding, data
      };
      audit('edge1_agent_file_read', requestId, { ok: true, path: filePath, offset, bytes_read: count });
      return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
    } catch (error) {
      audit('edge1_agent_file_read', requestId, { ok: false, path: filePath });
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_file_read', request_id: requestId, ok: false, error: redact(error.message) }) }], isError: true };
    }
  });

  server.registerTool('edge1_agent_file_write', {
    description: 'Create, atomically replace, append to, or write at an offset in any file. Optional SHA-256 preconditions provide optimistic concurrency for updates.',
    inputSchema: z.object({
      path: z.string().min(1).max(4096),
      data: z.string().max(Math.ceil(MAX_FILE_BYTES * 4 / 3) + 16),
      encoding: z.enum(['utf8', 'base64']).default('utf8'),
      action: z.enum(['create', 'replace', 'append', 'write_at']).default('replace'),
      offset: z.number().int().min(0).optional(),
      expected_sha256: z.string().optional(),
      permissions: z.string().regex(/^[0-7]{3,4}$/).optional(),
      create_parents: z.boolean().default(false)
    }),
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }
  }, async ({ path: filePath, data, encoding, action, offset, expected_sha256, permissions, create_parents }) => {
    if (READ_ONLY) return mutationDenied('edge1_agent_file_write');
    const requestId = randomUUID();
    try {
      const buffer = encoding === 'base64' ? Buffer.from(data, 'base64') : Buffer.from(data, 'utf8');
      if (buffer.length > MAX_FILE_BYTES) throw new Error(`payload exceeds ${MAX_FILE_BYTES} bytes`);
      if (create_parents) await fs.mkdir(path.dirname(filePath), { recursive: true });
      const exists = await fs.access(filePath).then(() => true).catch(() => false);
      if (expected_sha256) {
        if (!exists) throw new Error('SHA-256 precondition supplied but target does not exist');
        await ensureExpectedHash(filePath, expected_sha256);
      }
      if (action === 'create') {
        if (exists) throw new Error('create refused because target already exists');
        await atomicReplace(filePath, buffer, permissions);
      } else if (action === 'replace') {
        await atomicReplace(filePath, buffer, permissions);
      } else if (action === 'append') {
        await fs.appendFile(filePath, buffer, { mode: permissions ? Number.parseInt(permissions, 8) : 0o600 });
        if (permissions) await fs.chmod(filePath, Number.parseInt(permissions, 8));
      } else if (action === 'write_at') {
        const handle = await fs.open(filePath, exists ? 'r+' : 'w+', permissions ? Number.parseInt(permissions, 8) : 0o600);
        await handle.write(buffer, 0, buffer.length, offset || 0);
        await handle.sync();
        await handle.close();
        if (permissions) await fs.chmod(filePath, Number.parseInt(permissions, 8));
      }
      const meta = await fileMetadata(filePath);
      meta.sha256 = await sha256File(filePath);
      audit('edge1_agent_file_write', requestId, { ok: true, path: filePath, action, bytes: buffer.length, sha256: meta.sha256 });
      const payload = { tool: 'edge1_agent_file_write', request_id: requestId, ok: true, action, bytes_written: buffer.length, ...meta };
      return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
    } catch (error) {
      audit('edge1_agent_file_write', requestId, { ok: false, path: filePath, action });
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_file_write', request_id: requestId, ok: false, error: redact(error.message) }) }], isError: true };
    }
  });

  server.registerTool('edge1_agent_file_patch', {
    description: 'Perform exact text replacement in a file with optional SHA-256 precondition, writing the result atomically.',
    inputSchema: z.object({
      path: z.string().min(1).max(4096),
      search: z.string().min(1).max(MAX_FILE_BYTES),
      replace: z.string().max(MAX_FILE_BYTES),
      occurrence: z.enum(['first', 'all']).default('first'),
      expected_sha256: z.string().optional()
    }),
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }
  }, async ({ path: filePath, search, replace, occurrence, expected_sha256 }) => {
    if (READ_ONLY) return mutationDenied('edge1_agent_file_patch');
    const requestId = randomUUID();
    try {
      await ensureExpectedHash(filePath, expected_sha256);
      const st = await fs.stat(filePath);
      if (st.size > MAX_FILE_BYTES) throw new Error(`file exceeds patch limit of ${MAX_FILE_BYTES} bytes; use edge1_agent_exec or chunked file_write`);
      const original = await fs.readFile(filePath, 'utf8');
      const matches = original.split(search).length - 1;
      if (matches === 0) throw new Error('search text not found');
      const updated = occurrence === 'all' ? original.split(search).join(replace) : original.replace(search, replace);
      await atomicReplace(filePath, Buffer.from(updated, 'utf8'), (st.mode & 0o7777).toString(8));
      const sha256 = await sha256File(filePath);
      const replacements = occurrence === 'all' ? matches : 1;
      audit('edge1_agent_file_patch', requestId, { ok: true, path: filePath, replacements, sha256 });
      const payload = { tool: 'edge1_agent_file_patch', request_id: requestId, ok: true, path: filePath, replacements, sha256 };
      return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
    } catch (error) {
      audit('edge1_agent_file_patch', requestId, { ok: false, path: filePath });
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_file_patch', request_id: requestId, ok: false, error: redact(error.message) }) }], isError: true };
    }
  });

  server.registerTool('edge1_agent_file_manage', {
    description: 'Manage filesystem objects without path allowlists: mkdir, remove, move, copy, chmod, chown, symlink, or hardlink.',
    inputSchema: z.object({
      action: z.enum(['mkdir', 'remove', 'move', 'copy', 'chmod', 'chown', 'symlink', 'hardlink']),
      path: z.string().min(1).max(4096),
      destination: z.string().max(4096).optional(),
      recursive: z.boolean().default(false),
      force: z.boolean().default(false),
      permissions: z.string().regex(/^[0-7]{3,4}$/).optional(),
      uid: z.number().int().min(0).optional(),
      gid: z.number().int().min(0).optional()
    }),
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }
  }, async ({ action, path: source, destination, recursive, force, permissions, uid, gid }) => {
    if (READ_ONLY) return mutationDenied('edge1_agent_file_manage');
    const requestId = randomUUID();
    try {
      if (['move', 'copy', 'symlink', 'hardlink'].includes(action) && !destination) throw new Error(`${action} requires destination`);
      if (action === 'mkdir') await fs.mkdir(source, { recursive, mode: permissions ? Number.parseInt(permissions, 8) : 0o755 });
      if (action === 'remove') await fs.rm(source, { recursive, force });
      if (action === 'move') await fs.rename(source, destination);
      if (action === 'copy') await fs.cp(source, destination, { recursive, force });
      if (action === 'chmod') {
        if (!permissions) throw new Error('chmod requires permissions');
        await fs.chmod(source, Number.parseInt(permissions, 8));
      }
      if (action === 'chown') {
        if (uid === undefined || gid === undefined) throw new Error('chown requires uid and gid');
        await fs.chown(source, uid, gid);
      }
      if (action === 'symlink') await fs.symlink(source, destination);
      if (action === 'hardlink') await fs.link(source, destination);
      audit('edge1_agent_file_manage', requestId, { ok: true, action, path: source, destination: destination || null });
      const payload = { tool: 'edge1_agent_file_manage', request_id: requestId, ok: true, action, path: source, destination: destination || null };
      return { content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }], structuredContent: payload };
    } catch (error) {
      audit('edge1_agent_file_manage', requestId, { ok: false, action, path: source, destination: destination || null });
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_file_manage', request_id: requestId, ok: false, error: redact(error.message) }) }], isError: true };
    }
  });

  server.registerTool('edge1_agent_service', {
    description: 'Control any systemd service by name: status, start, stop, restart, reload, enable, disable, or daemon-reload.',
    inputSchema: z.object({
      action: z.enum(['status', 'start', 'stop', 'restart', 'reload', 'enable', 'disable', 'daemon-reload']),
      service: z.string().max(256).optional(),
      timeout_ms: z.number().int().min(1000).max(300000).optional()
    }),
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }
  }, async ({ action, service, timeout_ms }) => {
    if (action !== 'status' && READ_ONLY) return mutationDenied('edge1_agent_service');
    const requestId = randomUUID();
    if (action !== 'daemon-reload' && (!service || !/^[A-Za-z0-9@_.:-]+$/.test(service))) {
      return { content: [{ type: 'text', text: JSON.stringify({ tool: 'edge1_agent_service', request_id: requestId, ok: false, error: 'valid service name required' }) }], isError: true };
    }
    let command;
    if (action === 'status') command = `systemctl is-enabled '${service}' 2>&1 || true; systemctl is-active '${service}' 2>&1 || true; systemctl --no-pager --full status '${service}' 2>&1`;
    else if (action === 'daemon-reload') command = 'systemctl daemon-reload';
    else command = `systemctl ${action} '${service}' && systemctl is-active '${service}' 2>&1 || true`;
    const result = await runShell({ command, cwd: '/', timeoutMs: timeout_ms, maxOutputBytes: DEFAULT_OUTPUT_BYTES, redactOutput: true });
    return shellResult('edge1_agent_service', requestId, result, {
      public: { action, service: service || null },
      audit: { action, service: service || null }
    });
  });

  return server;
}

async function main() {
  assertLoopback(HOST);
  const token = await loadToken();
  const handler = createMcpHandler(() => buildServer(), { responseMode: 'json' });
  const mcpNodeHandler = toNodeHandler(handler);

  const httpServer = createHttpServer((req, res) => {
    const url = new URL(req.url || '/', `http://${req.headers.host || `${HOST}:${PORT}`}`);
    if (url.pathname === '/healthz') {
      const body = Buffer.from(JSON.stringify({ status: 'ok', service: 'wwcx-edge1-agent-shell', mode: MODE, endpoint: MCP_PATH }));
      res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': String(body.length) });
      res.end(body);
      return;
    }
    if (url.pathname !== MCP_PATH) {
      res.writeHead(404, { 'Content-Length': '0' });
      res.end();
      return;
    }
    const origin = req.headers.origin;
    if (origin && (!ALLOWED_ORIGINS.size || !ALLOWED_ORIGINS.has(origin))) {
      res.writeHead(403, { 'Content-Length': '0' });
      res.end();
      return;
    }
    if (!tokenMatches(req.headers.authorization, token)) {
      res.writeHead(401, { 'WWW-Authenticate': 'Bearer', 'Content-Length': '0' });
      res.end();
      return;
    }
    mcpNodeHandler(req, res);
  });

  httpServer.listen(PORT, HOST, () => {
    console.error(`wwcx-edge1-agent-shell listening on http://${HOST}:${PORT}${MCP_PATH} mode=${MODE}`);
  });

  const shutdown = async () => {
    httpServer.close();
    await handler.close().catch(() => {});
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

main().catch(error => {
  console.error(redact(error.stack || error.message));
  process.exitCode = 1;
});
