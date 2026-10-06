"""Additive Unified Contacts OpenPGP public-key metadata schema.

Private key material is explicitly prohibited by the schema.
"""
SCHEMA_VERSION = "unified-contacts-openpgp-1"
DDL = r"""
CREATE TABLE IF NOT EXISTS contact_openpgp_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_point_id INTEGER NOT NULL REFERENCES contact_points(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    public_key_armored TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK(verification_status IN ('verified','document_sourced','unverified','revoked','expired','disputed')),
    source TEXT NOT NULL DEFAULT 'manual',
    expires_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(length(fingerprint) IN (40,64)),
    CHECK(instr(public_key_armored,'PRIVATE KEY') = 0),
    UNIQUE(contact_point_id,fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_contact_openpgp_keys_point
    ON contact_openpgp_keys(contact_point_id);
CREATE INDEX IF NOT EXISTS idx_contact_openpgp_keys_fingerprint
    ON contact_openpgp_keys(fingerprint);
CREATE TABLE IF NOT EXISTS contact_openpgp_policy (
    contact_point_id INTEGER PRIMARY KEY REFERENCES contact_points(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'encrypt_if_verified_key'
        CHECK(mode IN ('disabled','sign_only','encrypt_if_verified_key','require_encryption')),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
def apply_schema(connection):
    connection.executescript(DDL)
