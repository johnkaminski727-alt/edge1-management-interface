from __future__ import annotations

from collections.abc import Callable, Mapping

from fastapi import APIRouter, Header, HTTPException, Request, status

from .delivery_status import InMemoryDeliveryStatusStore, PostgresDeliveryStatusStore
from .providers import MessagingProvider, ProviderWebhookRequest


def build_delivery_router(
    providers: Mapping[str, MessagingProvider],
    delivery_store: InMemoryDeliveryStatusStore | PostgresDeliveryStatusStore,
    management_token_provider: Callable[[], str],
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/v1/webhooks/{provider_name}/delivery",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def receive_delivery_status(provider_name: str, request: Request) -> dict[str, object]:
        provider = providers.get(provider_name)
        if provider is None:
            raise HTTPException(status_code=404, detail="unknown provider")

        body = await request.body()
        webhook_request = ProviderWebhookRequest(body=body, headers=request.headers)
        if not provider.verify_webhook(webhook_request):
            raise HTTPException(status_code=401, detail="webhook verification failed")
        try:
            event = provider.normalize_delivery_webhook(webhook_request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid provider delivery payload") from exc

        result = delivery_store.put_if_absent(event)
        return {
            "accepted": result.accepted,
            "duplicate": not result.accepted,
            "applied": result.applied,
            "matched": result.matched,
            "event_id": str(event.event_id),
            "provider": provider_name,
            "provider_message_id": event.provider_message_id,
            "delivery_status": event.status.value,
            "send_authorized": False,
        }

    @router.get("/v1/management/delivery/status")
    def management_delivery_status(
        limit: int = 25,
        x_wwcx_management_token: str | None = Header(default=None),
    ) -> dict[str, object]:
        if x_wwcx_management_token != management_token_provider():
            raise HTTPException(status_code=401, detail="invalid management token")
        return {
            "contract": "wwcx.messages-delivery-status-read.v1",
            **delivery_store.status(limit),
            "mutation_authorized": False,
        }

    return router
