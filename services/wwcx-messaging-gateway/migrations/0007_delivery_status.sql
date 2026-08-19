BEGIN;

CREATE TABLE messaging_delivery_events (
    id uuid PRIMARY KEY,
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    provider_message_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('delivered', 'failed', 'undelivered')),
    raw_status text,
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    applied boolean NOT NULL DEFAULT false,
    matched_message_id uuid REFERENCES messages(id),
    UNIQUE (provider, provider_event_id)
);

CREATE TABLE messaging_delivery_state (
    provider text NOT NULL,
    provider_message_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('delivered', 'failed', 'undelivered')),
    effective_at timestamptz NOT NULL,
    source_event_id text NOT NULL,
    matched_message_id uuid REFERENCES messages(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, provider_message_id)
);

CREATE INDEX messaging_delivery_events_message_idx
    ON messaging_delivery_events (provider, provider_message_id, occurred_at DESC);

CREATE INDEX messaging_delivery_events_unmatched_idx
    ON messaging_delivery_events (received_at, id)
    WHERE applied = true AND matched_message_id IS NULL;

COMMIT;
