from __future__ import annotations

from app.provider_readiness import sanitized_provider_readiness
from app.providers import build_provider_registry


def _by_name(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        item["provider"]: item
        for item in payload["providers"]  # type: ignore[index]
    }


def test_empty_environment_is_secret_free_and_unready() -> None:
    payload = sanitized_provider_readiness({}, registered_providers={"simulator"})
    providers = _by_name(payload)
    assert set(providers) == {"telnyx", "bandwidth"}
    assert payload["secret_values_output"] is False
    assert payload["provider_contact_performed"] is False
    assert payload["live_traffic_authorized"] is False
    for provider in providers.values():
        assert provider["implemented"] is True
        assert provider["registered"] is False
        assert provider["inbound_auth_configured"] is False
        assert provider["outbound_configured"] is False
        assert provider["public_webhook_ready"] is False
        assert provider["sender_bound"] is False
        assert provider["live_traffic_authorized"] is False


def test_configuration_presence_never_outputs_secret_values() -> None:
    secrets = {
        "WWCX_TELNYX_WEBHOOK_PUBLIC_KEY": "TELNYX-PUBLIC-KEY-SENTINEL",
        "WWCX_TELNYX_API_KEY": "TELNYX-API-SECRET-SENTINEL",
        "WWCX_BANDWIDTH_WEBHOOK_USERNAME": "BW-WEBHOOK-USER-SENTINEL",
        "WWCX_BANDWIDTH_WEBHOOK_PASSWORD": "BW-WEBHOOK-SECRET-SENTINEL",
        "WWCX_BANDWIDTH_ACCOUNT_ID": "BW-ACCOUNT-SENTINEL",
        "WWCX_BANDWIDTH_API_USERNAME": "BW-API-USER-SENTINEL",
        "WWCX_BANDWIDTH_API_PASSWORD": "BW-API-SECRET-SENTINEL",
        "WWCX_BANDWIDTH_APPLICATION_ID": "BW-APP-SENTINEL",
    }
    payload = sanitized_provider_readiness(secrets, registered_providers={"simulator"})
    providers = _by_name(payload)
    assert providers["telnyx"]["inbound_auth_configured"] is True
    assert providers["telnyx"]["outbound_configured"] is True
    assert providers["telnyx"]["mms_acquisition_configured"] is True
    assert providers["bandwidth"]["inbound_auth_configured"] is True
    assert providers["bandwidth"]["outbound_configured"] is True
    assert providers["bandwidth"]["mms_acquisition_configured"] is False
    assert providers["bandwidth"]["missing_mms_fields"] == (
        "BANDWIDTH_MMS_ACQUISITION_NOT_IMPLEMENTED",
    )
    rendered = repr(payload)
    for value in secrets.values():
        assert value not in rendered


def test_real_carriers_remain_unregistered_even_when_configuration_is_present() -> None:
    active = build_provider_registry(lambda: "simulator-test-token")
    assert set(active) == {"simulator"}
    payload = sanitized_provider_readiness(
        {
            "WWCX_TELNYX_WEBHOOK_PUBLIC_KEY": "configured",
            "WWCX_TELNYX_API_KEY": "configured",
            "WWCX_BANDWIDTH_WEBHOOK_USERNAME": "configured",
            "WWCX_BANDWIDTH_WEBHOOK_PASSWORD": "configured",
            "WWCX_BANDWIDTH_ACCOUNT_ID": "configured",
            "WWCX_BANDWIDTH_API_USERNAME": "configured",
            "WWCX_BANDWIDTH_API_PASSWORD": "configured",
            "WWCX_BANDWIDTH_APPLICATION_ID": "configured",
        },
        registered_providers=set(active),
    )
    for provider in _by_name(payload).values():
        assert provider["registered"] is False
        assert provider["live_traffic_authorized"] is False
