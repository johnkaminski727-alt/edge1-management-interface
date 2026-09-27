#!/usr/bin/env python3
"""Validate that Core and CrowdSec cards lose current status as their snapshots age."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "src/web/operations-center/core-dashboard.js",
    "src/web/operations-center/crowdsec-dashboard.js",
    "src/web/security/crowdsec-dashboard.js",
)

NODE = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const files = process.argv.slice(1);
async function check(file) {
  let now = Date.now();
  const isCore = file.includes("core-dashboard");
  const ids = isCore
    ? ["core-cards", "core-freshness", "core-refresh"]
    : ["crowdsec-cards", "crowdsec-freshness", "crowdsec-refresh"];
  const elements = Object.fromEntries(ids.map(id => [id, {
    textContent: "", innerHTML: "", disabled: false, addEventListener() {}
  }]));
  const intervals = new Map();
  const Clock = class extends Date { static now() { return now; } };
  const snapshot = isCore ? {
    schema_version: "wwcx.core-observation.v1",
    generated_at: new Date(now - 20_000).toISOString(),
    read_only: true, traffic_controls_changed: false,
    services: {}, interfaces: {}, routing: {}
  } : {
    schema_version: "wwcx.crowdsec-observation.v1",
    generated_at: new Date(now - 20_000).toISOString(),
    input: {}, forward: {}, services: {}, blacklists: {}
  };
  const context = vm.createContext({
    Date: Clock,
    document: {
      getElementById(id) { return elements[id] || null; },
      addEventListener() {},
      visibilityState: "visible"
    },
    fetch: async () => ({ok: true, json: async () => snapshot}),
    setInterval(callback, milliseconds) { intervals.set(milliseconds, callback); },
    console
  });
  vm.runInContext(fs.readFileSync(file, "utf8"), context);
  await new Promise(resolve => setImmediate(resolve));
  const grid = elements[ids[0]];
  const badge = elements[ids[1]];
  assert.match(badge.textContent, /20 seconds/);
  assert.ok(!grid.innerHTML.includes("Cached observations have expired"));
  assert.ok(intervals.has(10_000), "Missing continuous age timer");
  now += 360_000;
  intervals.get(10_000)();
  assert.match(badge.textContent, /STALE/);
  assert.match(grid.innerHTML, /Not current/);
  assert.match(grid.innerHTML, /Cached observations have expired/);
  console.log("PASS:", file, "fresh->stale after elapsed observation age");
}
(async () => {
  for (const file of files) await check(file);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""

def main():
    for relative in SCRIPTS:
        if not (ROOT / relative).is_file():
            raise AssertionError("Missing script: " + relative)
    subprocess.run(["node", "-e", NODE, *[str(ROOT / p) for p in SCRIPTS]],
                   check=True)
    print("PASS: All three observation badges expire stale values without live access")

if __name__ == "__main__":
    main()
