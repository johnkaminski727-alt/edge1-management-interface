#!/usr/bin/env python3
"""
WW.CX Numbering Registry Source Definitions
"""

SOURCES = {
    "countries": {
        "standard": "ISO 3166-1",
        "fields": [
            "iso_alpha2",
            "iso_alpha3",
            "name",
            "calling_codes",
            "timezones",
            "currency",
        ],
    },

    "calling_codes": {
        "standard": "ITU E.164",
        "fields": [
            "country",
            "calling_code",
        ],
    },

    "timezones": {
        "standard": "IANA TZDB",
        "fields": [
            "iana_name",
            "country",
            "dst_supported",
        ],
    },

    "nanpa": {
        "standard": "NANPA",
        "fields": [
            "npa",
            "country",
            "region",
            "state",
            "timezone",
            "status",
        ],
    },
}


def list_sources():
    return SOURCES
