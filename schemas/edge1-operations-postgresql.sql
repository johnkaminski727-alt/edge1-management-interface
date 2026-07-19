-- Optional private-network backend. Do not expose PostgreSQL publicly for this service.
CREATE SCHEMA IF NOT EXISTS edge1_operations;

CREATE TABLE IF NOT EXISTS edge1_operations.operation_audit (
    id uuid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    action text NOT NULL,
    request_hash text NOT NULL,
    status text NOT NULL CHECK (status IN ('succeeded','failed','timed_out','denied','error')),
    exit_code integer,
    duration_ms integer,
    stdout text NOT NULL DEFAULT '',
    stderr text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS edge1_operations.request_nonces (
    nonce text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);

REVOKE ALL ON SCHEMA edge1_operations FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA edge1_operations FROM PUBLIC;
-- Grant only SELECT/INSERT/DELETE on these tables to a dedicated NOLOGIN-owner-managed
-- application role after the private connection and credential design is approved.
