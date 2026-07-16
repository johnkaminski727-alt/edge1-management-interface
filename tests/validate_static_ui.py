#!/usr/bin/env python3
"""Validate the dependency-free Private Library Search static UI scaffold."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web"


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if "id" in attr_map and attr_map["id"]:
            self.ids.add(attr_map["id"])
        if tag == "script" and attr_map.get("src"):
            self.scripts.append(attr_map["src"] or "")
        if tag == "link" and attr_map.get("rel") == "stylesheet" and attr_map.get("href"):
            self.stylesheets.append(attr_map["href"] or "")


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_result_shape(result: dict[str, object]) -> None:
    required = {
        "source_id",
        "document_id",
        "collection",
        "title",
        "source_path",
        "classification",
        "chunk_index",
        "locator",
        "excerpt",
        "score",
    }
    missing = sorted(required.difference(result))
    if missing:
        raise AssertionError(f"fixture result missing keys: {missing}")


def main() -> None:
    fixture = load_json(WEB / "private-library-search.fixture.json")
    if not isinstance(fixture, dict):
        raise AssertionError("fixture must be a JSON object")
    results = fixture.get("results")
    if not isinstance(results, list) or not results:
        raise AssertionError("fixture must include at least one result")
    for result in results:
        if not isinstance(result, dict):
            raise AssertionError("each fixture result must be an object")
        assert_result_shape(result)

    parser = IdCollector()
    parser.feed((WEB / "index.html").read_text(encoding="utf-8"))

    required_ids = {
        "search-form",
        "query",
        "collection",
        "limit",
        "results",
        "result-count",
        "detail-title",
        "detail-source-path",
        "detail-classification",
        "detail-document-id",
        "detail-chunk",
        "detail-locator",
        "detail-excerpt",
        "copy-citation",
        "copy-source",
    }
    missing_ids = sorted(required_ids.difference(parser.ids))
    if missing_ids:
        raise AssertionError(f"index.html missing required ids: {missing_ids}")

    if "./app.js" not in parser.scripts:
        raise AssertionError("index.html must load ./app.js")
    if "./styles.css" not in parser.stylesheets:
        raise AssertionError("index.html must load ./styles.css")

    for filename in ("app.js", "styles.css"):
        if not (WEB / filename).exists():
            raise AssertionError(f"missing web asset: {filename}")

    print("static UI validation passed")


if __name__ == "__main__":
    main()
