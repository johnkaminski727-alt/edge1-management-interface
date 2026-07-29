#!/usr/bin/env python3
"""Inspect firewall and Fail2ban posture without changing controls or retaining sensitive lists."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

COMMAND_TIMEOUT_SECONDS = 15
MAX_JAILS = 100

Runner = Callable[[Sequence[str], int], tuple[int, str, str]]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_detail(value: Any, limit: int = 300) -> str:
    text = str(value or "").replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    return " ".join(text.split())[:limit]


def run_command(argv: Sequence[str], timeout: int = COMMAND_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run one fixed local read-only command without a shell."""
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", safe_detail(exc)
    return result.returncode, result.stdout, safe_detail(result.stderr)


def parse_systemctl_show(text: str) -> dict[str, str]:
    allowed = {"LoadState", "ActiveState", "SubState", "UnitFileState", "Result"}
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in allowed:
            values[key] = safe_detail(value, 80)
    return values


def service_status(unit: str, runner: Runner = run_command) -> dict[str, Any]:
    argv = (
        "systemctl",
        "show",
        unit,
        "--property=LoadState",
        "--property=ActiveState",
        "--property=SubState",
        "--property=UnitFileState",
        "--property=Result",
        "--no-pager",
    )
    code, stdout, error = runner(argv, COMMAND_TIMEOUT_SECONDS)
    values = parse_systemctl_show(stdout)
    return {
        "unit": unit,
        "available": code == 0 and values.get("LoadState") not in {"", "not-found"},
        "load_state": values.get("LoadState", "unknown"),
        "active_state": values.get("ActiveState", "unknown"),
        "sub_state": values.get("SubState", "unknown"),
        "unit_file_state": values.get("UnitFileState", "unknown"),
        "result": values.get("Result", "unknown"),
        "detail": "loaded" if code == 0 else (error or f"systemctl exited {code}"),
    }


def parse_nft_ruleset(document: Any) -> dict[str, int]:
    entries = document.get("nftables") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ValueError("nft JSON does not contain an nftables list")
    counts = {
        "table_count": 0,
        "chain_count": 0,
        "rule_count": 0,
        "set_count": 0,
        "map_count": 0,
        "flowtable_count": 0,
        "named_counter_count": 0,
    }
    key_map = {
        "table": "table_count",
        "chain": "chain_count",
        "rule": "rule_count",
        "set": "set_count",
        "map": "map_count",
        "flowtable": "flowtable_count",
        "counter": "named_counter_count",
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key, target in key_map.items():
            if isinstance(entry.get(key), dict):
                counts[target] += 1
    return counts


def inspect_firewall(runner: Runner = run_command) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    service = service_status("nftables.service", runner)
    nft_path = shutil.which("nft")
    result: dict[str, Any] = {
        "tool_available": bool(nft_path),
        "ruleset_readable": False,
        "service": service,
        "counts": {
            "table_count": 0,
            "chain_count": 0,
            "rule_count": 0,
            "set_count": 0,
            "map_count": 0,
            "flowtable_count": 0,
            "named_counter_count": 0,
        },
        "detail": "nft command is unavailable",
    }
    if not nft_path:
        warnings.append("nft command is unavailable")
        return result, warnings

    code, stdout, error = runner((nft_path, "-j", "list", "ruleset"), COMMAND_TIMEOUT_SECONDS)
    if code != 0:
        result["detail"] = error or f"nft exited {code}"
        warnings.append("nft ruleset could not be read")
        return result, warnings
    try:
        document = json.loads(stdout)
        result["counts"] = parse_nft_ruleset(document)
    except (json.JSONDecodeError, ValueError) as exc:
        result["detail"] = safe_detail(exc)
        warnings.append("nft returned invalid or unexpected JSON")
        return result, warnings

    result["ruleset_readable"] = True
    result["detail"] = "sanitized aggregate counts loaded"
    return result, warnings


def parse_fail2ban_jail_list(text: str) -> list[str]:
    match = re.search(r"^\s*`?-?\s*Jail list:\s*(.*?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return []
    names: list[str] = []
    for raw in match.group(1).split(","):
        name = raw.strip()
        if name and re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            names.append(name)
    return sorted(set(names))[:MAX_JAILS]


def parse_fail2ban_jail_status(text: str) -> dict[str, int]:
    labels = {
        "currently_failed": "Currently failed",
        "total_failed": "Total failed",
        "currently_banned": "Currently banned",
        "total_banned": "Total banned",
    }
    values: dict[str, int] = {key: 0 for key in labels}
    for key, label in labels.items():
        match = re.search(rf"{re.escape(label)}:\s*(\d+)", text, re.IGNORECASE)
        if match:
            values[key] = max(0, int(match.group(1)))
    return values


def inspect_fail2ban(runner: Runner = run_command) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    service = service_status("fail2ban.service", runner)
    client_path = shutil.which("fail2ban-client")
    result: dict[str, Any] = {
        "tool_available": bool(client_path),
        "status_readable": False,
        "service": service,
        "jail_count": 0,
        "totals": {
            "currently_failed": 0,
            "total_failed": 0,
            "currently_banned": 0,
            "total_banned": 0,
        },
        "jails": [],
        "detail": "fail2ban-client is unavailable",
    }
    if not client_path:
        warnings.append("fail2ban-client is unavailable")
        return result, warnings

    code, stdout, error = runner((client_path, "status"), COMMAND_TIMEOUT_SECONDS)
    if code != 0:
        result["detail"] = error or f"fail2ban-client exited {code}"
        warnings.append("Fail2ban status could not be read")
        return result, warnings

    jails = parse_fail2ban_jail_list(stdout)
    sanitized_jails: list[dict[str, Any]] = []
    totals = dict(result["totals"])
    for jail in jails:
        jail_code, jail_stdout, jail_error = runner(
            (client_path, "status", jail),
            COMMAND_TIMEOUT_SECONDS,
        )
        if jail_code != 0:
            sanitized_jails.append({"name": jail, "available": False, "detail": jail_error or f"exit {jail_code}"})
            warnings.append(f"Fail2ban jail status unavailable: {jail}")
            continue
        metrics = parse_fail2ban_jail_status(jail_stdout)
        for key, value in metrics.items():
            totals[key] += value
        sanitized_jails.append({"name": jail, "available": True, **metrics})

    result.update({
        "status_readable": True,
        "jail_count": len(jails),
        "totals": totals,
        "jails": sanitized_jails,
        "detail": "sanitized jail counters loaded",
    })
    return result, warnings


def build_snapshot(runner: Runner = run_command) -> dict[str, Any]:
    firewall, firewall_warnings = inspect_firewall(runner)
    fail2ban, fail2ban_warnings = inspect_fail2ban(runner)
    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "read_only": True,
        "traffic_controls_changed": False,
        "privacy": {
            "raw_rules_included": False,
            "addresses_included": False,
            "ports_included": False,
            "packet_payloads_included": False,
            "banned_ip_list_included": False,
            "raw_command_output_included": False,
        },
        "firewall": firewall,
        "fail2ban": fail2ban,
        "warnings": firewall_warnings + fail2ban_warnings,
        "limitations": [
            "Aggregate counts do not prove that traffic is blocked as intended.",
            "No rules, addresses, ports, packet payloads, or banned-IP lists are retained.",
            "A failed read is reported as unavailable and does not change service state.",
        ],
    }


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_snapshot()
    if args.output:
        write_snapshot(snapshot, args.output)
        print(json.dumps({
            "ok": True,
            "output": str(args.output),
            "firewall_readable": snapshot["firewall"]["ruleset_readable"],
            "fail2ban_readable": snapshot["fail2ban"]["status_readable"],
            "traffic_controls_changed": False,
        }))
    else:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
