import os

from fastapi import FastAPI, Header, HTTPException, status

from .models import NormalizedMessage
from .store import InMemoryEventStore

app = FastAPI(title="WW.CX Messaging Gateway", version="0.1.0")
store = InMemoryEventStore()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


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
