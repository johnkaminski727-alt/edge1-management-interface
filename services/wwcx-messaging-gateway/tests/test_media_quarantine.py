from app.media_quarantine import assess_media_item, quarantine_summary
from app.models import MediaItem, NormalizedMessage


def mms_message(*, sha256: str | None = "a" * 64) -> NormalizedMessage:
    return NormalizedMessage.model_validate(
        {
            "provider": "simulator",
            "provider_event_id": "media-001",
            "direction": "inbound",
            "channel": "mms",
            "from": "+15555550100",
            "to": ["+15555550101"],
            "text": "image attached",
            "media": [
                {
                    "url": "https://provider.invalid/private/object/1",
                    "content_type": "image/jpeg",
                    "sha256": sha256,
                }
            ],
        }
    )


def test_default_mms_media_is_quarantined_pending_scan() -> None:
    result = quarantine_summary(mms_message())
    assert result["applicable"] is True
    assert result["state"] == "quarantined_pending_scan"
    assert result["release_authorized"] is False
    item = result["items"][0]
    assert item["state"] == "quarantined_pending_scan"
    assert item["provider_reference_exposed"] is False
    assert "url" not in item


def test_missing_digest_fails_closed() -> None:
    result = quarantine_summary(mms_message(sha256=None))
    assert result["state"] == "quarantined"
    assert result["items"][0]["state"] == "quarantined_missing_digest"


def test_clean_scan_is_still_held_and_not_released() -> None:
    result = quarantine_summary(mms_message(), scanner=lambda item: "clean")
    assert result["state"] == "scanned_clean_held"
    assert result["release_authorized"] is False
    assert result["items"][0]["release_authorized"] is False


def test_malicious_and_scanner_error_remain_quarantined() -> None:
    malicious = quarantine_summary(mms_message(), scanner=lambda item: "malicious")
    assert malicious["state"] == "quarantined"
    assert malicious["items"][0]["state"] == "quarantined_malicious"

    def broken_scanner(item):
        raise RuntimeError("scanner unavailable")

    failed = quarantine_summary(mms_message(), scanner=broken_scanner)
    assert failed["state"] == "quarantined"
    assert failed["items"][0]["state"] == "quarantined_scan_error"


def test_sms_without_media_is_not_given_false_malware_semantics() -> None:
    sms = NormalizedMessage.model_validate(
        {
            "provider": "simulator",
            "provider_event_id": "sms-001",
            "direction": "inbound",
            "channel": "sms",
            "from": "+15555550100",
            "to": ["+15555550101"],
            "text": "plain SMS",
            "media": [],
        }
    )
    result = quarantine_summary(sms)
    assert result == {
        "applicable": False,
        "state": "not_applicable",
        "items": [],
        "release_authorized": False,
    }


def test_assessment_never_exposes_provider_reference() -> None:
    item = MediaItem(url="https://provider.invalid/private/object/2", content_type="image/png", sha256="b" * 64)
    record = assess_media_item(item).to_dict()
    assert "provider.invalid" not in str(record)
    assert record["provider_reference_exposed"] is False
