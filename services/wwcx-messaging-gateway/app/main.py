import os

from fastapi import FastAPI, Header, HTTPException, status

from .models import NormalizedMessage
from .persistence import PostgresEventStore
from .store import InMemoryEventStore

app = FastAPI(title="WW.CX Messaging Gateway", version="0.2.0")

database_url = os.getenv("DATABASE_URL")
store = PostgresEventStore(database_url) if database_url else InMemoryEventStore()


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


@app.post("/v1/simulator/messages", status_code=status.HTTP_202_ACCEPTED)
def receive_simulated_message(
    message: NormalizedMessage,
    x_wwcx_simulator_token: str | None = Header(default=None),
) -> dict[str, object]:
    expected = os.getenv("WWCX_SIMULATOR_TOKEN", "development-only")
    if x_wwcx_simulator_token != expected:
        raise HTTPException(status_code=401, detail="invalid simulator token")

    accepted = store.put_if_absent(message)
    return {
        "accepted": accepted,
        "duplicate": not accepted,
        "event_id": str(message.event_id),
    }


@app.get("/v1/simulator/events/count")
def simulator_event_count() -> dict[str, int]:
    return {"count": store.count()}
