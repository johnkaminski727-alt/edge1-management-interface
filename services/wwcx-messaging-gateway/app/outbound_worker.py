from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping

from .models import Channel
from .outbound_policy import OutboundPolicy, PostgresSendRateLimiter, SendRateLimiter
from .persistence import PostgresEventStore
from .providers import MessagingProvider, build_provider_registry


def parse_provider_allowlist(value: str | None) -> set[str]:
    raw = value if value is not None else "simulator"
    return {item.strip() for item in raw.split(",") if item.strip()}


def run_once(
    store: PostgresEventStore,
    providers: Mapping[str, MessagingProvider],
    allowed_providers: set[str],
    policy: OutboundPolicy,
    rate_limiter: SendRateLimiter,
    *,
    retry_delay_seconds: int = 60,
    max_attempts: int = 5,
) -> dict[str, object]:
    if store.get_control_state().get("paused"):
        return {"status": "paused"}

    job = store.claim_outbound_job()
    if job is None:
        return {"status": "idle"}

    provider_name = job.message.provider
    if provider_name not in allowed_providers:
        store.block_outbound_job(job.job_id, "provider is not in outbound worker allowlist")
        return {"status": "blocked", "reason": "provider_not_allowlisted", "job_id": str(job.job_id)}

    provider = providers.get(provider_name)
    if provider is None:
        store.block_outbound_job(job.job_id, "provider adapter is not registered")
        return {"status": "blocked", "reason": "provider_not_registered", "job_id": str(job.job_id)}

    policy_reason = policy.evaluate(job.message)
    if policy_reason is not None:
        store.block_outbound_job(job.job_id, f"outbound authorization policy: {policy_reason}")
        return {"status": "blocked", "reason": policy_reason, "job_id": str(job.job_id)}

    suppressed = store.suppressed_recipients(job.message.recipients)
    if suppressed:
        store.block_outbound_job(job.job_id, "one or more recipients are suppressed", status="suppressed")
        return {
            "status": "suppressed",
            "job_id": str(job.job_id),
            "suppressed_recipient_count": len(suppressed),
        }

    if job.message.channel == Channel.MMS and job.message.media:
        store.block_outbound_job(
            job.job_id,
            "MMS media release is not authorized by the outbound worker",
            status="quarantined",
        )
        return {"status": "quarantined", "reason": "mms_media_release_not_authorized", "job_id": str(job.job_id)}

    rate_reason = rate_limiter.reserve(
        job.job_id,
        job.message,
        hourly_limit=policy.hourly_message_limit,
        daily_limit=policy.daily_message_limit,
    )
    if rate_reason is not None:
        store.block_outbound_job(job.job_id, f"outbound rate policy: {rate_reason}", status="rate_limited")
        return {"status": "rate_limited", "reason": rate_reason, "job_id": str(job.job_id)}

    try:
        result = provider.send(job.message)
    except Exception as exc:  # provider adapters are an external boundary
        state = store.retry_outbound_job(
            job.job_id,
            f"provider send raised {type(exc).__name__}",
            delay_seconds=retry_delay_seconds,
            max_attempts=max_attempts,
        )
        return {"status": state, "reason": "provider_error", "job_id": str(job.job_id)}

    if not result.accepted:
        state = store.retry_outbound_job(
            job.job_id,
            "provider did not accept outbound message",
            delay_seconds=retry_delay_seconds,
            max_attempts=max_attempts,
        )
        return {"status": state, "reason": "provider_not_accepted", "job_id": str(job.job_id)}

    store.complete_outbound_job(job.job_id, result.provider_message_id)
    return {
        "status": "sent",
        "job_id": str(job.job_id),
        "provider": provider_name,
        "provider_message_id": result.provider_message_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded WW.CX outbound queue worker iteration")
    parser.add_argument("--once", action="store_true", help="required safety gate; process at most one job")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required; continuous outbound sending is not enabled")

    if os.getenv("WWCX_OUTBOUND_WORKER_ENABLED", "false").lower() != "true":
        print(json.dumps({"status": "disabled"}))
        return 2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "error", "reason": "DATABASE_URL is required"}))
        return 2

    allowed_providers = parse_provider_allowlist(os.getenv("WWCX_OUTBOUND_PROVIDER_ALLOWLIST"))
    if not allowed_providers:
        print(json.dumps({"status": "error", "reason": "outbound provider allowlist is empty"}))
        return 2

    policy = OutboundPolicy.from_values(
        enabled=os.getenv("WWCX_OUTBOUND_POLICY_ENABLED", "false").lower() == "true",
        authorized_senders=os.getenv("WWCX_OUTBOUND_AUTHORIZED_SENDERS"),
        destination_prefixes=os.getenv("WWCX_OUTBOUND_DESTINATION_PREFIX_ALLOWLIST"),
        max_recipients=int(os.getenv("WWCX_OUTBOUND_MAX_RECIPIENTS", "1")),
        max_text_chars=int(os.getenv("WWCX_OUTBOUND_MAX_TEXT_CHARS", "1600")),
        hourly_message_limit=int(os.getenv("WWCX_OUTBOUND_HOURLY_MESSAGE_LIMIT", "10")),
        daily_message_limit=int(os.getenv("WWCX_OUTBOUND_DAILY_MESSAGE_LIMIT", "25")),
    )
    retry_delay_seconds = int(os.getenv("WWCX_OUTBOUND_RETRY_DELAY_SECONDS", "60"))
    max_attempts = int(os.getenv("WWCX_OUTBOUND_MAX_ATTEMPTS", "5"))
    simulator_token = lambda: os.getenv("WWCX_SIMULATOR_TOKEN", "development-only")
    result = run_once(
        PostgresEventStore(database_url),
        build_provider_registry(simulator_token),
        allowed_providers,
        policy,
        PostgresSendRateLimiter(database_url),
        retry_delay_seconds=retry_delay_seconds,
        max_attempts=max_attempts,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
