import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models import MediaItem
from app.quarantine_storage import PrivateQuarantineStore
from app.telnyx_provider import TelnyxMediaAcquisitionError, TelnyxProvider


class StreamResponse:
    def __init__(self, body: bytes, *, status_code: int = 200, content_type: str = "image/png") -> None:
        self.body = body
        self.status_code = status_code
        self.headers = {"content-length": str(len(body)), "content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def iter_bytes(self):
        midpoint = max(1, len(self.body) // 2)
        yield self.body[:midpoint]
        yield self.body[midpoint:]


class MediaClient:
    def __init__(self, response: StreamResponse) -> None:
        self.response = response
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, *, headers):
        self.request = {"method": method, "url": url, "headers": headers}
        return self.response


def provider(client: MediaClient) -> TelnyxProvider:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return TelnyxProvider(
        lambda: public_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: client,
    )


def media_item(body: bytes, *, url: str = "https://media.telnyx.com/example/image.png") -> MediaItem:
    return MediaItem(
        url=url,
        content_type="image/png",
        sha256=hashlib.sha256(body).hexdigest(),
    )


def test_acquire_media_streams_authenticated_blob_into_private_quarantine(tmp_path) -> None:
    body = b"safe image test bytes"
    client = MediaClient(StreamResponse(body))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    result = provider(client).acquire_media(media_item(body), store)

    assert result["sha256"] == hashlib.sha256(body).hexdigest()
    assert result["state"] == "quarantined_pending_scan"
    assert result["release_authorized"] is False
    assert result["provider_reference_exposed"] is False
    assert result["web_served"] is False
    assert client.request["method"] == "GET"
    assert client.request["url"].startswith("https://media.telnyx.com/")
    assert client.request["headers"]["Authorization"] == "Bearer test-only-api-key"


def test_acquire_media_rejects_non_telnyx_origin_before_network_access(tmp_path) -> None:
    body = b"x"
    client = MediaClient(StreamResponse(body))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = media_item(body, url="https://attacker.invalid/media.png")

    with pytest.raises(TelnyxMediaAcquisitionError, match="allowlisted"):
        provider(client).acquire_media(item, store)
    assert client.request is None


def test_acquire_media_requires_provider_digest(tmp_path) -> None:
    client = MediaClient(StreamResponse(b"x"))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = MediaItem(url="https://media.telnyx.com/example/x", content_type="image/png", sha256=None)

    with pytest.raises(TelnyxMediaAcquisitionError, match="SHA-256"):
        provider(client).acquire_media(item, store)
    assert client.request is None


def test_acquire_media_rejects_content_type_substitution(tmp_path) -> None:
    body = b"document bytes"
    client = MediaClient(StreamResponse(body, content_type="application/pdf"))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)

    with pytest.raises(TelnyxMediaAcquisitionError, match="content type"):
        provider(client).acquire_media(media_item(body), store)


def test_acquire_media_fails_closed_on_digest_mismatch(tmp_path) -> None:
    body = b"observed bytes"
    client = MediaClient(StreamResponse(body))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=1024)
    item = MediaItem(
        url="https://media.telnyx.com/example/image.png",
        content_type="image/png",
        sha256=hashlib.sha256(b"different bytes").hexdigest(),
    )

    with pytest.raises(TelnyxMediaAcquisitionError, match="failed closed"):
        provider(client).acquire_media(item, store)


def test_acquire_media_rejects_declared_oversize_before_streaming(tmp_path) -> None:
    body = b"x" * 32
    client = MediaClient(StreamResponse(body))
    store = PrivateQuarantineStore(tmp_path / "quarantine", max_bytes=16)

    with pytest.raises(TelnyxMediaAcquisitionError, match="size limit"):
        provider(client).acquire_media(media_item(body), store)
