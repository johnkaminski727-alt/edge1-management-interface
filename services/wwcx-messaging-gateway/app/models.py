from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Channel(StrEnum):
    SMS = "sms"
    MMS = "mms"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MediaItem(BaseModel):
    url: str
    content_type: str | None = None


class NormalizedMessage(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    provider: str
    provider_event_id: str
    direction: Direction
    channel: Channel
    sender: str = Field(alias="from")
    recipients: list[str] = Field(alias="to")
    text: str = ""
    media: list[MediaItem] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True}
