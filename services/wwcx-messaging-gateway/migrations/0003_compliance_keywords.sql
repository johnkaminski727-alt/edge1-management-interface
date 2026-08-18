BEGIN;

CREATE TABLE messaging_consent_state (
    address text PRIMARY KEY,
    state text NOT NULL CHECK (state IN ('active', 'suppressed')),
    effective_at timestamptz NOT NULL,
    source_message_id uuid NOT NULL REFERENCES messages(id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE messaging_compliance_events (
    id bigserial PRIMARY KEY,
    message_id uuid NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    address text NOT NULL,
    action text NOT NULL CHECK (action IN ('stop', 'start', 'help')),
    keyword text NOT NULL,
    applied boolean NOT NULL,
    occurred_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messaging_compliance_events_address_idx
    ON messaging_compliance_events (address, occurred_at DESC, id DESC);

COMMIT;
