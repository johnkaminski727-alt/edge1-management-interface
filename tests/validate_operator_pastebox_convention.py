#!/usr/bin/env python3
"""Prevent regression of the WW.CX attended operator paste-box convention."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONVENTION = (ROOT / "docs" / "operator-pastebox-convention.md").read_text(encoding="utf-8")
EDGE1_PROMPT = (ROOT / "prompts" / "edge1-authenticated-operator.md").read_text(encoding="utf-8")
MULTIHOST = (ROOT / "docs" / "wwcx-multihost-operator.md").read_text(encoding="utf-8")
BUSINESS159_SKILL = (ROOT / "skills" / "business159-authenticated-operator" / "SKILL.md").read_text(encoding="utf-8")
CROSS_HOST_SKILL = (ROOT / "skills" / "wwcx-cross-host-operator" / "SKILL.md").read_text(encoding="utf-8")

required_convention = (
    "SERVER: <fqdn-or-hostname> — <short action>",
    "# SERVER: <fqdn-or-hostname>",
    "# USER:   <expected principal, when known>",
    "# ACTION: <plain-language action>",
    "# SCOPE:  <bounded effect or READ-ONLY>",
    "Use one host per paste box.",
    "Paste the complete terminal output directly back into this ChatGPT conversation.",
    "This convention is a human-factors safety control, not cosmetic formatting.",
)
for token in required_convention:
    if token not in CONVENTION:
        raise SystemExit(f"operator paste-box convention missing required rule: {token}")

required_references = {
    "Edge1 operator prompt": (EDGE1_PROMPT, "docs/operator-pastebox-convention.md"),
    "multi-host architecture": (MULTIHOST, "docs/operator-pastebox-convention.md"),
    "Business159 authenticated operator Skill": (BUSINESS159_SKILL, "docs/operator-pastebox-convention.md"),
    "WW.CX cross-host operator Skill": (CROSS_HOST_SKILL, "docs/operator-pastebox-convention.md"),
}
for label, (text, token) in required_references.items():
    if token not in text:
        raise SystemExit(f"{label} does not reference the attended paste-box convention")

for label, text in (
    ("Edge1 operator prompt", EDGE1_PROMPT),
    ("multi-host architecture", MULTIHOST),
    ("WW.CX cross-host operator Skill", CROSS_HOST_SKILL),
):
    if "one host per" not in text.lower() and "separate" not in text.lower():
        raise SystemExit(f"{label} does not preserve host separation for attended commands")

if "where the resulting output" not in EDGE1_PROMPT.lower():
    raise SystemExit("Edge1 operator prompt does not require an explicit result destination")
if "where" not in BUSINESS159_SKILL.lower() or "output" not in BUSINESS159_SKILL.lower():
    raise SystemExit("Business159 operator Skill does not require an explicit result destination")

print("operator paste-box convention validation passed")
