BEGIN;

CREATE TABLE messaging_outbound_send_reservations (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL UNIQUE REFERENCES outbound_jobs(id) ON DELETE CASCADE,
    message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    provider text NOT NULL,
    sender text NOT NULL,
    recipient_count integer NOT NULL CHECK (recipient_count > 0),
    reserved_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messaging_outbound_send_reservations_sender_time_idx
    ON messaging_outbound_send_reservations (provider, sender, reserved_at DESC);

COMMIT;
