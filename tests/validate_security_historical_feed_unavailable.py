#!/usr/bin/env python3
"""Regression fixture: an undeployed historical feed is not polled as live security."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src/web/security/index.html"

NODE = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const page = fs.readFileSync(process.argv[1], "utf8");
const candidates = [...page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]).filter(s => s.includes('const ENDPOINT="/edge1-status/security-operations.json"'));
assert.equal(candidates.length, 1);
const elements = new Map();
const callbacks = new Map();
let requests = 0;
const element = id => {
  if (!elements.has(id)) elements.set(id, {
    textContent: "", innerHTML: "", className: "",
    disabled: false, value: "all",
    addEventListener(name, fn) { callbacks.set(id + ":" + name, fn); }
  });
  return elements.get(id);
};
let poll;
const context = vm.createContext({
  document: {
    getElementById: element,
    addEventListener() {},
    visibilityState: "visible"
  },
  fetch: async () => { requests++; return {ok: false, status: 404}; },
  AbortController: class { abort() {} get signal() { return {}; } },
  setTimeout() { return 1; },
  clearTimeout() {},
  setInterval(fn, ms) { if (ms === 60_000) poll = fn; },
  console
});
vm.runInContext(candidates[0], context);
assert.equal(requests, 0, "Absent historical feed must not be auto-fetched");
assert.match(element("connection-status").textContent, /not deployed/i);
assert.match(element("error-banner").textContent, /CrowdSec observations above remain independent|CrowdSec monitoring is separate/i);
assert.equal(element("download-button").disabled, true);
assert.equal(typeof poll, "function");
poll();
assert.equal(requests, 0, "Uninstalled feed must not be polled on timer");
callbacks.get("refresh-button:click")();
setImmediate(() => {
  assert.equal(requests, 1, "Manual historical feed check expected");
  assert.match(element("connection-status").textContent, /not deployed/i);
  assert.match(element("overview").innerHTML, /not deployed/i);
  poll();
  assert.equal(requests, 1, "HTTP 404 must not enable background polling");
  console.log("PASS: absent historical Suricata feed is safely disabled; manual check is available");
});
"""

def main():
    text = PAGE.read_text(encoding="utf-8")
    for token in ("historicalPollingEnabled=false",
                  'response.status===404',
                  'setConnectionStatus("Historical feed not deployed"',
                  "if(historicalPollingEnabled)loadTelemetry()",
                  '<script src="./crowdsec-dashboard.js" defer>'):
        if token not in text:
            raise AssertionError("Missing historical telemetry boundary: " + token)
    subprocess.run(["node", "-e", NODE, str(PAGE)], check=True)
    print("PASS: Security Operations historical feed fixture; no live access")

if __name__ == "__main__":
    main()
