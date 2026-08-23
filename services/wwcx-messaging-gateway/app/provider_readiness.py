from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderReadiness:
    provider: str
    implemented: bool
    registered: bool
    inbound_auth_configured: bool
    outbound_configured: bool
    mms_acquisition_configured: bool
    public_webhook_ready: bool
    sender_bound: bool
    live_traffic_authorized: bool
    missing_inbound_fields: tuple[str, ...]
    missing_outbound_fields: tuple[str, ...]
    missing_mms_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderConfigurationContract:
    provider: str
    inbound_fields: tuple[str, ...]
    outbound_fields: tuple[str, ...]
    mms_fields: tuple[str, ...]


CONTRACTS = {
    "telnyx": ProviderConfigurationContract(
        provider="telnyx",
        inbound_fields=("WWCX_TELNYX_WEBHOOK_PUBLIC_KEY",),
        outbound_fields=("WWCX_TELNYX_API_KEY",),
        mms_fields=("WWCX_TELNYX_API_KEY",),
    ),
    "bandwidth": ProviderConfigurationContract(
        provider="bandwidth",
        inbound_fields=(
            "WWCX_BANDWIDTH_WEBHOOK_USERNAME",
            "WWCX_BANDWIDTH_WEBHOOK_PASSWORD",
        ),
        outbound_fields=(
            "WWCX_BANDWIDTH_ACCOUNT_ID",
            "WWCX_BANDWIDTH_API_USERNAME",
            "WWCX_BANDWIDTH_API_PASSWORD",
            "WWCX_BANDWIDTH_APPLICATION_ID",
        ),
        # The current Bandwidth adapter validates provider media references but has
        # no authenticated media-acquisition implementation. Configuration alone
        # therefore cannot make Bandwidth MMS acquisition ready.
        mms_fields=(),
    ),
}


def _present(environ: Mapping[str, str], name: str) -> bool:
    value = environ.get(name)
    return isinstance(value, str) and bool(value.strip())


def _missing(environ: Mapping[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in fields if not _present(environ, name))


def provider_readiness(
    environ: Mapping[str, str],
    *,
    registered_providers: set[str] | frozenset[str] | tuple[str, ...] = (),
) -> list[ProviderReadiness]:
    """Return secret-free provider configuration presence and activation gates.

    This function deliberately does not instantiate providers, read secret values,
    contact a carrier, infer a DID/sender assignment, or authorize a public webhook
    or live traffic. Environment variable *names* may be reported as missing; values,
    lengths and hashes are never returned.
    """
    registered = set(registered_providers)
    result: list[ProviderReadiness] = []
    for name in ("telnyx", "bandwidth"):
        contract = CONTRACTS[name]
        missing_inbound = _missing(environ, contract.inbound_fields)
        missing_outbound = _missing(environ, contract.outbound_fields)
        if name == "bandwidth":
            # No acquisition adapter exists yet, regardless of credential presence.
            missing_mms = ("BANDWIDTH_MMS_ACQUISITION_NOT_IMPLEMENTED",)
            mms_ready = False
        else:
            missing_mms = _missing(environ, contract.mms_fields)
            mms_ready = not missing_mms
        result.append(
            ProviderReadiness(
                provider=name,
                implemented=True,
                registered=name in registered,
                inbound_auth_configured=not missing_inbound,
                outbound_configured=not missing_outbound,
                mms_acquisition_configured=mms_ready,
                public_webhook_ready=False,
                sender_bound=False,
                live_traffic_authorized=False,
                missing_inbound_fields=missing_inbound,
                missing_outbound_fields=missing_outbound,
                missing_mms_fields=missing_mms,
            )
        )
    return result


def sanitized_provider_readiness(
    environ: Mapping[str, str],
    *,
    registered_providers: set[str] | frozenset[str] | tuple[str, ...] = (),
) -> dict[str, object]:
    providers = provider_readiness(environ, registered_providers=registered_providers)
    return {
        "contract": "wwcx.messaging-provider-readiness.v1",
        "providers": [item.to_dict() for item in providers],
        "secret_values_output": False,
        "provider_contact_performed": False,
        "public_webhook_ready": False,
        "sender_binding_verified": False,
        "live_traffic_authorized": False,
    }
