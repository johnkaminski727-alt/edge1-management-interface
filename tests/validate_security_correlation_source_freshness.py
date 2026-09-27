#!/usr/bin/env python3
"""Exercise Security Correlation source age logic without connecting to Edge1."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "src/web/security/correlation.html"

NODE = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]).filter(x => x.includes("function sourcePresentation"));
assert.equal(scripts.length, 1);
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    textContent: "", className: "", innerHTML: "", value: "all",
    disabled: false, addEventListener() {}
  });
  return elements.get(id);
}
const context = vm.createContext({
  document: {
    getElementById: element,
    addEventListener() {},
    visibilityState: "visible"
  },
  fetch() { return new Promise(() => {}); },
  AbortController: class { abort() {} get signal() { return {}; } },
  setTimeout() { return 1; },
  clearTimeout() {},
  setInterval() {},
  console
});
vm.runInContext(scripts[0], context);
const e = code => vm.runInContext(code, context);
const generated = new Date(Date.now() - 20_000).toISOString();
e("snapshot={generated_at:" + JSON.stringify(generated) + ",source_status:{}}");
const fresh = new Date(Date.now() - 30_000).toISOString();
let card = e('sourcePresentation("crowdsec",{available:true,modified_at:' +
  JSON.stringify(fresh) + ',detail:"Current sanitized listing"})');
assert.match(card, /Observed/);
assert.match(card, /age 3[0-4]s/);
assert.match(card, /Event recency is separate/);
const old = new Date(Date.now() - 360_000).toISOString();
card = e('sourcePresentation("crowdsec",{available:true,modified_at:' +
  JSON.stringify(old) + ',detail:"Old listing"})');
assert.match(card, /Stale/);
card = e('sourcePresentation("crowdsec",{available:true,detail:"Missing timestamp"})');
assert.match(card, /Age unknown/);
card = e('sourcePresentation("crowdsec",{available:false,modified_at:' +
  JSON.stringify(fresh) + ',detail:"Unavailable"})');
assert.match(card, /Unavailable/);
e('snapshot.source_status={crowdsec:{available:true,modified_at:' +
  JSON.stringify(fresh) + ',detail:"Current sanitized listing"}}');
e("renderSources()");
assert.match(element("sources").innerHTML, /Observed/);
e("snapshot.generated_at=new Date(Date.now()-360000).toISOString();updateFreshness()");
assert.match(element("freshness").textContent, /stale/i);
assert.match(element("sources").innerHTML, /Stale/);
console.log("PASS: correlation listing age, stale parent, unknown and unavailable states");
"""

def main():
    html = PAGE.read_text(encoding="utf-8")
    for phrase in ("Source coverage", "Event recency is separate",
                   "function sourcePresentation", "function updateFreshness"):
        if phrase not in html:
            raise AssertionError("Missing source-freshness contract: " + phrase)
    subprocess.run(["node", "-e", NODE, str(PAGE)], check=True)
    print("PASS: Security Correlation freshness fixture; no live access")

if __name__ == "__main__":
    main()
