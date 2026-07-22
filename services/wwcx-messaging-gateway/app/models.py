from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class Channel(StrEnum):
    SMS = "sms"
    MMS = "mms"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CoordinateSource(StrEnum):
    BROWSER = "browser"
    DEVICE = "device"
    OPERATOR = "operator"
    PRESET = "preset"


class SecurityMode(StrEnum):
    PLAIN = "plain"
    SIGNED = "signed"
    ENCRYPTED = "encrypted"
    ENCRYPTED_AND_SIGNED = "encrypted_and_signed"


class MediaItem(BaseModel):
    url: str
    content_type: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class CoordinateAttestation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0)
    altitude_m: float | None = None
    altitude_accuracy_m: float | None = Field(default=None, gt=0)
    source: CoordinateSource
    observed_at: datetime
    consent: bool
    station_name: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def require_consent(self) -> "CoordinateAttestation":
        if not self.consent:
            raise ValueError("coordinate attestation requires explicit consent")
        return self


class TimeAttestation(BaseModel):
    server_observed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    client_observed_at_utc: datetime | None = None
    ntp_synchronized: bool | None = None
    ntp_source: str | None = Field(default=None, max_length=255)
    clock_offset_ms: float | None = None
    timezone: str = Field(default="UTC", max_length=64)


class SecurityAttestation(BaseModel):
    mode: SecurityMode = SecurityMode.PLAIN
    recipient_fingerprints: list[str] = Field(default_factory=list)
    signer_fingerprint: str | None = None
    signature_valid: bool | None = None
    plaintext_retained: bool = False


class VerificationEnvelope(BaseModel):
    content_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    media_sha256: list[str] = Field(default_factory=list)
    time: TimeAttestation = Field(default_factory=TimeAttestation)
    coordinates: CoordinateAttestation | None = None
    security: SecurityAttestation = Field(default_factory=SecurityAttestation)


class NormalizedMessage(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    provider: str
    provider_event_id: str
    direction: Direction
    channel: Channel
    sender: str = Field(alias="from")
    recipients: list[str] = Field(alias="to", min_length=1)
    text: str = ""
    media: list[MediaItem] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verification: VerificationEnvelope | None = None

    model_config = {"populate_by_name": True}
