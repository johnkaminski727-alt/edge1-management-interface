import os
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .models import NormalizedMessage
from .persistence import PostgresEventStore
from .store import InMemoryEventStore

app = FastAPI(title="WW.CX Messaging Gateway", version="0.3.0")

database_url = os.getenv("DATABASE_URL")
store = PostgresEventStore(database_url) if database_url else InMemoryEventStore()


class ControlRequest(BaseModel):
    action: Literal["pause", "resume"]
    actor: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


def require_token(provided: str | None, environment_name: str, default: str) -> None:
    expected = os.getenv(environment_name, default)
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid management token")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    ping = getattr(store, "ping", None)
    if callable(ping) and not ping():
        raise HTTPException(status_code=503, detail="storage unavailable")
    return {
        "status": "ready",
        "storage": "postgres" if database_url else "memory",
    }


@app.get("/v1/management/status")
def management_status(
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(
        x_wwcx_management_token,
        "WWCX_MANAGEMENT_READ_TOKEN",
        "development-read-only",
    )
    control = store.get_control_state()
    return {
        "service": "wwcx-messaging-gateway",
        "version": app.version,
        "storage": "postgres" if database_url else "memory",
        "event_count": store.count(),
        **control,
    }


@app.post("/v1/management/control")
def management_control(
    request: ControlRequest,
    x_wwcx_control_token: str | None = Header(default=None),
) -> dict[str, object]:
    if os.getenv("WWCX_MANAGEMENT_CONTROL_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="management controls are disabled")
    require_token(
        x_wwcx_control_token,
        "WWCX_MANAGEMENT_CONTROL_TOKEN",
        "development-control-only",
    )
    return store.set_paused(
        paused=request.action == "pause",
        actor=request.actor,
        reason=request.reason,
    )


@app.post("/v1/simulator/messages", status_code=status.HTTP_202_ACCEPTED)
def receive_simulated_message(
    message: NormalizedMessage,
    x_wwcx_simulator_token: str | None = Header(default=None),
) -> dict[str, object]:
    expected = os.getenv("WWCX_SIMULATOR_TOKEN", "development-only")
    if x_wwcx_simulator_token != expected:
        raise HTTPException(status_code=401, detail="invalid simulator token")

    if store.get_control_state()["paused"]:
        raise HTTPException(status_code=503, detail="messaging intake is paused")

    accepted = store.put_if_absent(message)
    return {
        "accepted": accepted,
        "duplicate": not accepted,
        "event_id": str(message.event_id),
    }


@app.get("/v1/simulator/events/count")
def simulator_event_count() -> dict[str, int]:
    return {"count": store.count()}
