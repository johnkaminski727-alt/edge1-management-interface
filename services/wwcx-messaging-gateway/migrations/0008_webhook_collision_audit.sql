BEGIN;

ALTER TABLE messaging_webhook_receipts
    DROP CONSTRAINT messaging_webhook_receipts_processing_status_check;

ALTER TABLE messaging_webhook_receipts
    ADD CONSTRAINT messaging_webhook_receipts_processing_status_check
    CHECK (processing_status IN ('verified', 'processing', 'accepted', 'duplicate', 'conflict', 'failed'));

CREATE TABLE messaging_webhook_boundary_counters (
    provider_bucket text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN (
            'unknown_provider',
            'verification_failed',
            'invalid_payload',
            'paused',
            'accepted',
            'duplicate',
            'payload_conflict'
        )
    ),
    event_count bigint NOT NULL DEFAULT 0 CHECK (event_count >= 0),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider_bucket, outcome)
);

COMMIT;
