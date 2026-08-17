#!/usr/bin/env python3
"""Offline deterministic validation for the Private AI signed-chat harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "private_ai_signed_chat_e2e.py"

spec = importlib.util.spec_from_file_location("private_ai_signed_chat_e2e", HARNESS)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load harness: {HARNESS}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main() -> int:
    canonical = module.canonical_request(
        "POST",
        "/v1/chat",
        "1700000000",
        "abc123",
        "0123456789abcdef",
    )
    assert canonical == "POST\n/v1/chat\n1700000000\nabc123\n0123456789abcdef"
    assert module.sign_request("dummy-secret", canonical) == (
        "cf832167cf4c81921fe5f1dcff047380ff72e19e76a678bb375bcea75ca0845a"
    )

    common = {
        "request_id": "req-1",
        "user_id": "test-user",
        "role": None,
        "group": "usenet.comp.lang.python",
    }

    default = module.scenario_payload("default", **common)
    assert default["include_communications"] is False
    assert default["communications_groups"] == []
    assert default["user"]["role"] == "registered_user"
    assert default["user"]["scopes"] == ["chat:general"]

    missing = module.scenario_payload("missing-scope", **common)
    assert missing["include_communications"] is True
    assert missing["user"]["role"] == "internal_viewer"
    assert missing["user"]["scopes"] == ["chat:general"]
    assert "communications:read" not in missing["user"]["scopes"]

    authorized = module.scenario_payload("authorized", **common)
    assert authorized["include_communications"] is True
    assert authorized["communications_groups"] == ["usenet.comp.lang.python"]
    assert authorized["user"]["role"] == "internal_viewer"
    assert authorized["user"]["scopes"] == ["chat:general", "communications:read"]

    override = module.scenario_payload("default", **{**common, "role": "internal_viewer"})
    assert override["user"]["role"] == "internal_viewer"
    assert override["user"]["scopes"] == ["chat:general"]

    module.assert_scenario("default", 200, {"communications_sources": []})
    module.assert_scenario("missing-scope", 403, {"detail": "forbidden"})
    module.assert_scenario(
        "authorized",
        200,
        {"communications_sources": [{"source_name": "dummy", "thread_key": "thread-1"}]},
    )

    print("private AI signed chat harness offline validation passed")
    print("PASS canonical POST /v1/chat HMAC-SHA256 vector")
    print("PASS default registered_user + chat:general omission payload")
    print("PASS missing-scope internal_viewer + chat:general payload")
    print("PASS authorized internal_viewer + chat:general + communications:read payload")
    print("PASS explicit role override does not alter scenario scopes")
    print("PASS authorized communications provenance assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
