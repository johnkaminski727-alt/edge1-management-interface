#!/usr/bin/env python3
"""Inventory navigable PHP pages without inventing routes.

This read-only tool scans a supplied CX Admin document root, extracts
conservative metadata, and emits JSON for human review before a canonical
navigation registry is built.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

TITLE_PATTERNS = (
    re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\$page_title\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE),
    re.compile(r"\$title\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE),
)
HREF_PATTERN = re.compile(r"href\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
AUTH_PATTERN = re.compile(r"(?:require_role|require_permission|has_permission|can_access|is_admin)\s*\(([^)]*)\)", re.IGNORECASE)
EXCLUDED_NAMES = {
    "api.php",
    "autoload.php",
    "bootstrap.php",
    "callback.php",
    "config.php",
    "functions.php",
    "helpers.php",
    "login.php",
    "logout.php",
    "renderer.php",
    "renderers.php",
    "webhook.php",
}
EXCLUDED_PARTS = {
    "_private",
    "actions",
    "api",
    "callbacks",
    "include",
    "includes",
    "payload",
    "private",
    "src",
    "vendor",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value)).strip()


def relative_route(root: Path, path: Path, url_prefix: str) -> str:
    return "{}/{}".format(url_prefix.rstrip("/"), path.relative_to(root).as_posix())


def classify(path: Path, source: str) -> Tuple[bool, List[str]]:
    reasons = []  # type: List[str]
    lower_parts = {part.lower() for part in path.parts}
    if path.name.lower() in EXCLUDED_NAMES:
        reasons.append("excluded implementation filename")
    if lower_parts & EXCLUDED_PARTS:
        reasons.append("excluded implementation directory")
    if re.search(r"\b(?:header\s*\(\s*['\"]Location:|http_response_code\s*\(\s*(?:30[12378]|204))", source, re.I):
        reasons.append("redirect or non-page response")
    if not re.search(r"<(?:html|body|main|section|div|h1|h2)\b", source, re.I):
        reasons.append("no recognizable page markup")
    return (not reasons, reasons)


def inspect_page(root: Path, path: Path, url_prefix: str) -> Dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    title = None
    for pattern in TITLE_PATTERNS:
        match = pattern.search(source)
        if match:
            title = clean_text(match.group(1))
            if title:
                break
    hrefs = sorted({href.strip() for href in HREF_PATTERN.findall(source) if href.strip() and not href.startswith(("#", "javascript:", "mailto:", "tel:"))})
    auth_hints = sorted({clean_text(match) for match in AUTH_PATTERN.findall(source) if clean_text(match)})
    navigable, exclusion_reasons = classify(path.relative_to(root), source)
    return {
        "path": path.relative_to(root).as_posix(),
        "route": relative_route(root, path, url_prefix),
        "title": title,
        "navigable_candidate": navigable,
        "exclusion_reasons": exclusion_reasons,
        "authorization_hints": auth_hints,
        "outbound_links": hrefs,
        "sha256": hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document_root", type=Path)
    parser.add_argument("--url-prefix", default="/admin")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.document_root.resolve()
    if not root.is_dir():
        parser.error("document root is not a directory: {}".format(root))
    pages = [inspect_page(root, path, args.url_prefix) for path in sorted(root.rglob("*.php"))]
    payload = {
        "schema_version": 2,
        "document_root": str(root),
        "url_prefix": args.url_prefix,
        "known_required_routes": ["/admin/bigbird-operations-console.php"],
        "page_count": len(pages),
        "navigable_candidate_count": sum(1 for page in pages if page["navigable_candidate"]),
        "pages": pages,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
