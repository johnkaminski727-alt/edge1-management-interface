#!/usr/bin/env python3
"""Exercise Network Defense source freshness using its actual browser script.

Node runs only the inline browser code with a stub DOM and a permanently pending
fetch. It does not connect to Edge1 or alter production services.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "src/web/network-defense/index.html"

NODE_TEST = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const page = fs.readFileSync(process.argv[1], "utf8");
const scripts = [...page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(m => m[1]).filter(x => x.includes("function sourcePresentation"));
assert.equal(scripts.length, 1, "Expected exactly one inline freshness script");

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {
    textContent: "", className: "", innerHTML: "", disabled: false,
    addEventListener() {}
  });
  return elements.get(id);
};
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
const evaluate = expression => vm.runInContext(expression, context);
const generated = new Date(Date.now() - 15_000).toISOString();
evaluate("snapshot={generated_at:" + JSON.stringify(generated) + ",sources:{}}");
const fresh = evaluate(
  'sourcePresentation("core_live", {available:true,age_seconds:2,stale_after_seconds:300,detail:"Current read-only observation"})'
);
assert.match(fresh, /Observed/);
assert.match(fresh, /observation age 1[5-9]s/);
const stale = evaluate(
  'sourcePresentation("core_live", {available:true,age_seconds:4,stale_after_seconds:10,detail:"Current read-only observation"})'
);
assert.match(stale, /Stale/);
const unknown = evaluate(
  'sourcePresentation("core_live", {available:true,age_seconds:null,detail:"No observation time"})'
);
assert.match(unknown, /Age unknown/);
const missing = evaluate(
  'sourcePresentation("network", {available:false,age_seconds:null,detail:"network source is missing"})'
);
assert.match(missing, /Unavailable/);
const staged = evaluate(
  'sourcePresentation("dns_policy", {available:false,age_seconds:null,detail:"dns policy status is not staged"})'
);
assert.match(staged, /Not staged/);

evaluate('snapshot.sources={core_live:{available:true,age_seconds:4,stale_after_seconds:10,detail:"Current read-only observation"}}');
evaluate("renderSources()");
assert.match(element("sources").innerHTML, /Stale/);
evaluate("snapshot.generated_at=new Date(Date.now()-360000).toISOString();updateFreshness()");
assert.match(element("freshness").textContent, /stale/i);
assert.match(element("sources").innerHTML, /Stale/);
console.log("PASS: source ages advance from snapshot time; stale, unknown, missing and unstaged states are distinct");
"""

def main():
    text = HTML.read_text(encoding="utf-8")
    for anchor in ("Source freshness", "observation age", "stale_after_seconds",
                   "Snapshot timestamp invalid", "not an end-to-end test"):
        if anchor not in text:
            raise AssertionError("Missing freshness contract: " + anchor)
    subprocess.run(["node", "-e", NODE_TEST, str(HTML)], check=True)
    print("PASS: Network Defense freshness validation complete; no live access")

if __name__ == "__main__":
    main()
