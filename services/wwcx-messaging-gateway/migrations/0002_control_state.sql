BEGIN;

CREATE TABLE messaging_control_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    paused boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL DEFAULT 'system',
    reason text NOT NULL DEFAULT 'initial state'
);

INSERT INTO messaging_control_state (singleton)
VALUES (true)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE messaging_control_audit (
    id bigserial PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('pause', 'resume')),
    actor text NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
