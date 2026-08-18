import os
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .models import NormalizedMessage
from .persistence import PostgresEventStore
from .store import InMemoryEventStore
from .telegraph_office import build_router

app = FastAPI(title="WW.CX Messaging Gateway", version="0.4.1")

database_url = os.getenv("DATABASE_URL")
store = PostgresEventStore(database_url) if database_url else InMemoryEventStore()


def simulator_token() -> str:
    return os.getenv("WWCX_SIMULATOR_TOKEN", "development-only")


app.include_router(build_router(store, simulator_token))


class ControlRequest(BaseModel):
    action: Literal["pause", "resume"]
    actor: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


def require_token(provided: str | None, environment_name: str, default: str) -> None:
    expected = os.getenv(environment_name, default)
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid management token")


def sanitized_message(message: NormalizedMessage) -> dict[str, object]:
    """Bounded read projection for operator/Private-AI context.

    Media URLs and verification internals are deliberately excluded. Message text is
    bounded and remains untrusted data; this projection carries no mutation authority.
    """
    media = [
        {"content_type": item.content_type, "sha256": item.sha256}
        for item in message.media[:16]
    ]
    return {
        "event_id": str(message.event_id),
        "provider": message.provider[:128],
        "provider_event_id": message.provider_event_id[:256],
        "direction": message.direction.value,
        "channel": message.channel.value,
        "sender": message.sender[:256],
        "recipients": [recipient[:256] for recipient in message.recipients[:32]],
        "text_summary": message.text[:1000],
        "text_truncated": len(message.text) > 1000,
        "media": media,
        "occurred_at": message.occurred_at.isoformat(),
        "untrusted_content": True,
        "mutation_authorized": False,
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    ping = getattr(store, "ping", None)
    if callable(ping) and not ping():
        raise HTTPException(status_code=503, detail="storage unavailable")
    return {"status": "ready", "storage": "postgres" if database_url else "memory"}


@app.get("/v1/management/status")
def management_status(
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    control = store.get_control_state()
    return {
        "service": "wwcx-messaging-gateway",
        "version": app.version,
        "storage": "postgres" if database_url else "memory",
        "event_count": store.count(),
        "capabilities": ["messages.status.read", "messages.conversation.read"],
        "mutation_authorized": False,
        **control,
    }


@app.get("/v1/management/messages/recent")
def management_recent_messages(
    limit: int = 25,
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    bounded_limit = min(max(limit, 1), 100)
    events = [sanitized_message(item) for item in store.list_recent(bounded_limit)]
    return {
        "contract": "wwcx.messages-conversation-read.v1",
        "events": events,
        "count": len(events),
        "limit": bounded_limit,
        "content_is_untrusted": True,
        "mutation_authorized": False,
    }


@app.get("/v1/management/messages/{event_id}")
def management_message(
    event_id: str,
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    message = store.get_event(event_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message event not found")
    return {
        "contract": "wwcx.messages-conversation-read.v1",
        "event": sanitized_message(message),
        "content_is_untrusted": True,
        "mutation_authorized": False,
    }


@app.post("/v1/management/control")
def management_control(
    request: ControlRequest,
    x_wwcx_control_token: str | None = Header(default=None),
) -> dict[str, object]:
    if os.getenv("WWCX_MANAGEMENT_CONTROL_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="management controls are disabled")
    require_token(x_wwcx_control_token, "WWCX_MANAGEMENT_CONTROL_TOKEN", "development-control-only")
    return store.set_paused(paused=request.action == "pause", actor=request.actor, reason=request.reason)


@app.post("/v1/simulator/messages", status_code=status.HTTP_202_ACCEPTED)
def receive_simulated_message(
    message: NormalizedMessage,
    x_wwcx_simulator_token: str | None = Header(default=None),
) -> dict[str, object]:
    if x_wwcx_simulator_token != simulator_token():
        raise HTTPException(status_code=401, detail="invalid simulator token")
    if store.get_control_state()["paused"]:
        raise HTTPException(status_code=503, detail="messaging intake is paused")
    accepted = store.put_if_absent(message)
    return {"accepted": accepted, "duplicate": not accepted, "event_id": str(message.event_id)}


@app.get("/v1/simulator/events/count")
def simulator_event_count() -> dict[str, int]:
    return {"count": store.count()}
