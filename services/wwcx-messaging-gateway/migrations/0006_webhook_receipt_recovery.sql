BEGIN;

ALTER TABLE messaging_webhook_receipts
    ADD COLUMN normalized_payload jsonb,
    ADD COLUMN attempt_count integer NOT NULL DEFAULT 0,
    ADD COLUMN available_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN locked_at timestamptz,
    ADD COLUMN last_error text;

ALTER TABLE messaging_webhook_receipts
    DROP CONSTRAINT messaging_webhook_receipts_processing_status_check;

ALTER TABLE messaging_webhook_receipts
    ADD CONSTRAINT messaging_webhook_receipts_processing_status_check
    CHECK (processing_status IN ('verified', 'processing', 'accepted', 'duplicate', 'failed'));

CREATE INDEX messaging_webhook_receipts_ready_idx
    ON messaging_webhook_receipts (available_at, received_at, id)
    WHERE processing_status = 'verified' AND normalized_payload IS NOT NULL;

COMMIT;
