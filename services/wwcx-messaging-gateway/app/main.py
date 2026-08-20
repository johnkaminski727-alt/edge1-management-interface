import os
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from .delivery_router import build_delivery_router
from .delivery_status import InMemoryDeliveryStatusStore, PostgresDeliveryStatusStore
from .media_quarantine import quarantine_summary
from .models import Direction, NormalizedMessage
from .persistence import PostgresEventStore
from .providers import ProviderWebhookRequest, build_provider_registry
from .store import InMemoryEventStore
from .telegraph_office import build_router
from .webhook_audit import InMemoryWebhookBoundaryCounters, PostgresWebhookBoundaryCounters
from .webhook_collision import duplicate_body_matches_previous
from .webhook_receipts import InMemoryWebhookReceiptLedger, PostgresWebhookReceiptLedger

app = FastAPI(title="WW.CX Messaging Gateway", version="0.4.7")

database_url = os.getenv("DATABASE_URL")
store = PostgresEventStore(database_url) if database_url else InMemoryEventStore()
webhook_receipts = (
    PostgresWebhookReceiptLedger(database_url) if database_url else InMemoryWebhookReceiptLedger()
)
webhook_audit = (
    PostgresWebhookBoundaryCounters(database_url) if database_url else InMemoryWebhookBoundaryCounters()
)
delivery_store = (
    PostgresDeliveryStatusStore(database_url) if database_url else InMemoryDeliveryStatusStore()
)


def simulator_token() -> str:
    return os.getenv("WWCX_SIMULATOR_TOKEN", "development-only")


def management_read_token() -> str:
    return os.getenv("WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")


providers = build_provider_registry(simulator_token)

app.include_router(build_router(store, simulator_token))
app.include_router(build_delivery_router(providers, delivery_store, management_read_token))


class ControlRequest(BaseModel):
    action: Literal["pause", "resume"]
    actor: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


def require_token(provided: str | None, environment_name: str, default: str) -> None:
    expected = os.getenv(environment_name, default)
    if provided != expected:
        raise HTTPException(status_code=401, detail="invalid management token")


def sanitized_message(message: NormalizedMessage) -> dict[str, object]:
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
        "media_quarantine": quarantine_summary(message),
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
    capabilities = [
        "messages.status.read",
        "messages.conversation.read",
        "messages.webhooks.receipts.read",
        "messages.webhooks.audit.read",
        "messages.delivery.status.read",
    ]
    if callable(getattr(store, "outbound_queue_status", None)):
        capabilities.append("messages.outbound.queue.read")
    if callable(getattr(store, "compliance_status", None)):
        capabilities.append("messages.compliance.read")
    return {
        "service": "wwcx-messaging-gateway",
        "version": app.version,
        "storage": "postgres" if database_url else "memory",
        "event_count": store.count(),
        "capabilities": capabilities,
        "providers": sorted(providers),
        "webhook_receipts": {
            "durable": bool(database_url),
            "records_verified_callbacks_only": True,
            "unverified_request_persistence": "bounded_aggregate_counters_only",
            "payload_collision_detection": True,
        },
        "delivery_status": {
            "durable": bool(database_url),
            "asynchronous_provider_callbacks": True,
            "final_statuses": ["delivered", "failed", "undelivered"],
            "real_carrier_adapter_registered": False,
        },
        "outbound_worker": {
            "enabled": os.getenv("WWCX_OUTBOUND_WORKER_ENABLED", "false").lower() == "true",
            "continuous_mode": False,
            "default_provider_allowlist": "simulator",
        },
        "keyword_compliance": {
            "inbound_sms_keywords_enabled": True,
            "actions": ["stop", "start", "help"],
            "auto_reply_enabled": False,
            "regulatory_compliance_claimed": False,
        },
        "mms_media_quarantine": {
            "state": "foundation_ready_fail_closed",
            "default": "quarantined_pending_scan",
            "release_authorized": False,
        },
        "mutation_authorized": False,
        **control,
    }


@app.get("/v1/management/outbound/queue")
def management_outbound_queue(
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    queue_status = getattr(store, "outbound_queue_status", None)
    if not callable(queue_status):
        raise HTTPException(status_code=503, detail="durable outbound queue unavailable")
    return {
        "contract": "wwcx.messages-outbound-queue-read.v1",
        **queue_status(),
        "mutation_authorized": False,
    }


@app.get("/v1/management/webhooks/receipts")
def management_webhook_receipts(
    limit: int = 25,
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    return {
        "contract": "wwcx.messages-webhook-receipts-read.v1",
        **webhook_receipts.status(limit),
        "raw_body_retained": False,
        "unverified_request_rows_persisted": False,
        "mutation_authorized": False,
    }


@app.get("/v1/management/webhooks/audit")
def management_webhook_audit(
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    return {
        "contract": "wwcx.messages-webhook-audit-read.v1",
        **webhook_audit.status(),
        "storage_model": "bounded_aggregate_counters",
        "raw_request_data_retained": False,
        "mutation_authorized": False,
    }


@app.get("/v1/management/compliance")
def management_compliance(
    limit: int = 25,
    x_wwcx_management_token: str | None = Header(default=None),
) -> dict[str, object]:
    require_token(x_wwcx_management_token, "WWCX_MANAGEMENT_READ_TOKEN", "development-read-only")
    compliance_status = getattr(store, "compliance_status", None)
    if not callable(compliance_status):
        raise HTTPException(status_code=503, detail="messaging compliance state unavailable")
    return {
        "contract": "wwcx.messages-compliance-read.v1",
        **compliance_status(limit),
        "auto_reply_enabled": False,
        "regulatory_compliance_claimed": False,
        "mutation_authorized": False,
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


@app.post("/v1/simulator/outbound", status_code=status.HTTP_202_ACCEPTED)
def queue_simulated_outbound(
    message: NormalizedMessage,
    x_wwcx_simulator_token: str | None = Header(default=None),
) -> dict[str, object]:
    if os.getenv("WWCX_SIMULATOR_OUTBOUND_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="simulator outbound queueing is disabled")
    if x_wwcx_simulator_token != simulator_token():
        raise HTTPException(status_code=401, detail="invalid simulator token")
    if message.direction != Direction.OUTBOUND:
        raise HTTPException(status_code=400, detail="outbound queue requires direction=outbound")
    if message.provider != "simulator":
        raise HTTPException(status_code=400, detail="simulator outbound route accepts provider=simulator only")
    if store.get_control_state()["paused"]:
        raise HTTPException(status_code=503, detail="messaging is paused")
    enqueue = getattr(store, "enqueue_outbound", None)
    if not callable(enqueue):
        raise HTTPException(status_code=503, detail="durable outbound queue unavailable")
    accepted = enqueue(message)
    return {
        "queued": accepted,
        "duplicate": not accepted,
        "event_id": str(message.event_id),
        "send_authorized": False,
        "worker_required": True,
    }


@app.get("/v1/simulator/events/count")
def simulator_event_count() -> dict[str, int]:
    return {"count": store.count()}


@app.post("/v1/webhooks/{provider_name}", status_code=status.HTTP_202_ACCEPTED)
async def receive_provider_webhook(provider_name: str, request: Request) -> dict[str, object]:
    provider = providers.get(provider_name)
    if provider is None:
        webhook_audit.record("__unknown__", "unknown_provider")
        raise HTTPException(status_code=404, detail="unknown provider")

    body = await request.body()
    webhook_request = ProviderWebhookRequest(body=body, headers=request.headers)

    if not provider.verify_webhook(webhook_request):
        webhook_audit.record(provider_name, "verification_failed")
        raise HTTPException(
            status_code=401,
            detail="webhook verification failed",
            headers=provider.webhook_auth_failure_headers() or None,
        )

    try:
        message = provider.normalize_webhook(webhook_request)
    except ValueError as exc:
        webhook_audit.record(provider_name, "invalid_payload")
        raise HTTPException(status_code=400, detail="invalid provider payload") from exc

    if store.get_control_state()["paused"]:
        webhook_audit.record(provider_name, "paused")
        raise HTTPException(status_code=503, detail="messaging intake is paused")

    receipt_id = webhook_receipts.record_verified(provider_name, message, body)
    accepted = store.put_if_absent(message)
    if accepted:
        webhook_receipts.mark_processed(receipt_id, "accepted")
        webhook_audit.record(provider_name, "accepted")
    else:
        body_matches = duplicate_body_matches_previous(webhook_receipts, receipt_id)
        if body_matches is False:
            webhook_receipts.mark_processed(receipt_id, "duplicate")
            webhook_audit.record(provider_name, "payload_conflict")
            raise HTTPException(
                status_code=409,
                detail="provider_event_id replay body does not match the prior processed webhook",
            )
        webhook_receipts.mark_processed(receipt_id, "duplicate")
        webhook_audit.record(provider_name, "duplicate")

    return {
        "accepted": accepted,
        "duplicate": not accepted,
        "event_id": str(message.event_id),
        "provider": provider_name,
        "receipt_id": str(receipt_id),
    }
