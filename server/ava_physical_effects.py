#!/usr/bin/env python3
"""Bounded AVA physical-presentation effect policy.

This module does not access hardware.

It converts an already-sanitized AVA presentation effect into a fixed,
trusted physical-effect catalogue decision. Physical presentation remains
disabled unless an operator-controlled policy explicitly enables it.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


PHYSICAL_EFFECTS_ENABLED = False

ALLOWED_PRESENTATION_EFFECTS = frozenset({
    "blue_tit_easter_egg",
    "donkey_easter_egg",
    "cat_easter_egg",
    "moist_owlette_easter_egg",
})

# These are trusted catalogue identifiers, not hardware instructions.
PHYSICAL_EFFECT_CATALOGUE = {
    "blue_tit_easter_egg": "blue_tit_chirp",
    "donkey_easter_egg": "donkey_braying",
    "cat_easter_egg": "cat_meow",
    "moist_owlette_easter_egg": "moist_owlette_hoot",
}

_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class PhysicalEffectPolicyError(ValueError):
    """Raised when a physical presentation request fails closed."""


@dataclass(frozen=True)
class PhysicalEffectDecision:
    request_id: str
    presentation_effect: str
    catalogue_effect: str
    enabled: bool
    disposition: str

    def public(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "presentation_effect": self.presentation_effect,
            "catalogue_effect": self.catalogue_effect,
            "enabled": self.enabled,
            "disposition": self.disposition,
        }


def decide(
    request_id: str,
    presentation_effect: str,
    *,
    enabled: bool = PHYSICAL_EFFECTS_ENABLED,
) -> PhysicalEffectDecision:
    """Return a bounded physical-presentation decision.

    The caller must supply an effect that has already passed AVA's independent
    UI-effect sanitizer. This function repeats the allowlist check rather than
    trusting that upstream boundary.
    """

    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        raise PhysicalEffectPolicyError("invalid request_id")

    if (
        not isinstance(presentation_effect, str)
        or presentation_effect not in ALLOWED_PRESENTATION_EFFECTS
    ):
        raise PhysicalEffectPolicyError("presentation effect is not approved")

    catalogue_effect = PHYSICAL_EFFECT_CATALOGUE[presentation_effect]

    if enabled is not True:
        return PhysicalEffectDecision(
            request_id=request_id,
            presentation_effect=presentation_effect,
            catalogue_effect=catalogue_effect,
            enabled=False,
            disposition="disabled",
        )

    return PhysicalEffectDecision(
        request_id=request_id,
        presentation_effect=presentation_effect,
        catalogue_effect=catalogue_effect,
        enabled=True,
        disposition="approved",
    )
