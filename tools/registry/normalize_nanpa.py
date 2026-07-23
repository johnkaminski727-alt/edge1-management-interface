#!/usr/bin/env python3

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data/registry/sources/nanpa/raw/npa_report.csv"
NORMALIZED = ROOT / "data/registry/nanpa_npa.csv"
SOURCE_METADATA = ROOT / "data/registry/sources/nanpa/source.json"

COUNTRY_CODES = {
    "US": "US",
    "CANADA": "CA",
    "BAHAMAS": "BS",
    "BARBADOS": "BB",
    "ANGUILLA": "AI",
    "ANTIGUA/BARBUDA": "AG",
    "BRITISH VIRGIN ISLANDS": "VG",
    "CAYMAN ISLANDS": "KY",
    "BERMUDA": "BM",
    "DOMINICAN REPUBLIC": "DO",
    "GRENADA": "GD",
    "JAMAICA": "JM",
    "TURKS & CAICOS ISLANDS": "TC",
    "MONTSERRAT": "MS",
    "SINT MAARTEN": "SX",
    "ST.LUCIA": "LC",
    "ST. LUCIA": "LC",
    "DOMINICA": "DM",
    "ST. VINCENT & GRENADINES": "VC",
    "TRINIDAD & TOBAGO": "TT",
    "ST. KITTS & NEVIS": "KN",
    "PUERTO RICO": "PR",
    "US VIRGIN ISLANDS": "VI",
    "AMERICAN SAMOA": "AS",
    "GUAM": "GU",
    "NORTHERN MARIANA ISLANDS": "MP",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def yes(value: str) -> bool:
    return value.strip().upper() in {"Y", "YES", "TRUE", "1"}


def derive_status(row: dict[str, str]) -> str:
    if yes(row.get("IN_SERVICE", "")):
        return "active"

    if yes(row.get("ASSIGNED", "")):
        return "assigned"

    if yes(row.get("RESERVED", "")):
        return "reserved"

    if yes(row.get("ASSIGNABLE", "")):
        return "available"

    return "unavailable"


def normalize_country(row: dict[str, str]) -> str:
    country = row.get("COUNTRY", "").strip().upper()

    if country:
        try:
            return COUNTRY_CODES[country]
        except KeyError as exc:
            raise ValueError(
                f"Unknown NANPA country value for NPA "
                f"{row.get('NPA_ID')}: {country!r}"
            ) from exc

    # Non-geographic, reserved and unassigned NANPA codes use the
    # international pseudo-region code rather than a sovereign country.
    return "001"


def read_nanpa() -> tuple[str, list[dict[str, str]]]:
    with RAW.open(
        newline="",
        encoding="utf-8-sig",
        errors="strict",
    ) as handle:
        first_reader = csv.reader(handle)

        try:
            file_date_row = next(first_reader)
            header = next(first_reader)
        except StopIteration as exc:
            raise ValueError("NANPA source is missing its header") from exc

        if (
            len(file_date_row) < 2
            or file_date_row[0].strip() != "File Date"
        ):
            raise ValueError(
                f"Unexpected NANPA file-date row: {file_date_row!r}"
            )

        required = {
            "NPA_ID",
            "type_of_code",
            "ASSIGNABLE",
            "RESERVED",
            "ASSIGNED",
            "USE",
            "LOCATION",
            "COUNTRY",
            "IN_SERVICE",
            "STATUS",
            "OVERLAY_COMPLEX",
            "TIME_ZONE",
            "AREA_SERVED",
        }

        missing = required.difference(header)
        if missing:
            raise ValueError(
                f"NANPA source is missing columns: {sorted(missing)}"
            )

        reader = csv.DictReader(handle, fieldnames=header)
        rows = list(reader)

    return file_date_row[1].strip(), rows


def main() -> None:
    if not RAW.exists():
        raise SystemExit(f"Missing NANPA source: {RAW}")

    file_date, source_rows = read_nanpa()
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in source_rows:
        npa = row["NPA_ID"].strip()

        if not (len(npa) == 3 and npa.isdigit()):
            raise ValueError(f"Invalid NPA value: {npa!r}")

        if npa in seen:
            raise ValueError(f"Duplicate NPA in NANPA source: {npa}")

        seen.add(npa)

        location = row.get("LOCATION", "").strip()
        area_served = row.get("AREA_SERVED", "").strip()
        code_type = row.get("type_of_code", "").strip()
        overlay = row.get("OVERLAY_COMPLEX", "").strip()

        region_parts = [
            value
            for value in (
                area_served,
                code_type,
                f"Overlay {overlay}" if overlay else "",
            )
            if value
        ]

        normalized.append(
            {
                "npa": npa,
                "country": normalize_country(row),
                "region": " | ".join(region_parts),
                "state": location,
                # NANPA publishes broad timezone codes such as E, C,
                # M, P, EC and CM. Preserve the authoritative value;
                # do not misrepresent it as an exact IANA identifier.
                "timezone": row.get("TIME_ZONE", "").strip(),
                "status": derive_status(row),
            }
        )

    normalized.sort(key=lambda item: int(item["npa"]))

    NORMALIZED.parent.mkdir(parents=True, exist_ok=True)

    with NORMALIZED.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "npa",
                "country",
                "region",
                "state",
                "timezone",
                "status",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(normalized)

    statuses = Counter(item["status"] for item in normalized)
    countries = Counter(item["country"] for item in normalized)

    metadata = {
        "schema_version": "1.0",
        "source": "North American Numbering Plan Administrator",
        "dataset": "NPA Database",
        "file_date": file_date,
        "retrieved_at": now(),
        "source_file": "raw/npa_report.csv",
        "normalized_file": "../../nanpa_npa.csv",
        "records": len(normalized),
        "status_counts": dict(sorted(statuses.items())),
        "country_counts": dict(sorted(countries.items())),
        "timezone_semantics": (
            "Values are authoritative NANPA timezone codes and are not "
            "necessarily IANA timezone identifiers."
        ),
    }

    SOURCE_METADATA.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"NANPA normalized: {len(normalized)}")
    print(f"Source file date: {file_date}")
    print(f"Status counts: {dict(sorted(statuses.items()))}")
    print(f"Country counts: {dict(sorted(countries.items()))}")


if __name__ == "__main__":
    main()
