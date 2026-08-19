BEGIN;

CREATE TABLE messaging_webhook_receipts (
    id uuid PRIMARY KEY,
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    message_event_id uuid NOT NULL,
    body_sha256 text NOT NULL CHECK (body_sha256 ~ '^[0-9a-f]{64}$'),
    verification_status text NOT NULL CHECK (verification_status IN ('verified')),
    processing_status text NOT NULL CHECK (processing_status IN ('verified', 'accepted', 'duplicate')),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);

CREATE INDEX messaging_webhook_receipts_provider_event_idx
    ON messaging_webhook_receipts (provider, provider_event_id, received_at DESC);

CREATE INDEX messaging_webhook_receipts_processing_idx
    ON messaging_webhook_receipts (processing_status, received_at DESC);

COMMIT;
