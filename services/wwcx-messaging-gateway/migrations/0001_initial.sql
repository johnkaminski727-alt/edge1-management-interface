BEGIN;

CREATE TABLE messaging_events (
    id uuid PRIMARY KEY,
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    event_type text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    UNIQUE (provider, provider_event_id)
);

CREATE TABLE messages (
    id uuid PRIMARY KEY,
    provider text NOT NULL,
    provider_message_id text,
    direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel text NOT NULL CHECK (channel IN ('sms', 'mms')),
    sender text NOT NULL,
    recipients jsonb NOT NULL,
    body text NOT NULL DEFAULT '',
    status text NOT NULL,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE message_media (
    id uuid PRIMARY KEY,
    message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    source_url text NOT NULL,
    object_key text,
    content_type text,
    byte_size bigint,
    scan_status text NOT NULL DEFAULT 'pending'
);

CREATE TABLE suppressions (
    address text PRIMARY KEY,
    reason text NOT NULL,
    suppressed_at timestamptz NOT NULL DEFAULT now(),
    source_message_id uuid REFERENCES messages(id)
);

CREATE TABLE outbound_jobs (
    id uuid PRIMARY KEY,
    message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    state text NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    locked_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX outbound_jobs_ready_idx
    ON outbound_jobs (available_at)
    WHERE state = 'pending';

COMMIT;
