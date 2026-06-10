-- ============================================================
-- Merchant classification cache
-- Run this in the Supabase SQL Editor after create_transaction_tables.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS merchant_classification_cache (
    id                   SERIAL PRIMARY KEY,

    -- NULL = global/shared cache (reserved for future use).
    -- NOT NULL = user-specific cache (current behaviour).
    user_id              UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Normalised form of the raw merchant/description string.
    normalized_merchant  TEXT NOT NULL,

    -- "expense" or "income" — part of the key so a refund from a shop can be
    -- cached separately from a regular purchase.
    transaction_type     TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),

    -- Classification payload mirrors what the AI /classify endpoint returns.
    category_name        TEXT NOT NULL,
    normalized_category  TEXT NOT NULL,
    confidence           FLOAT NOT NULL DEFAULT 0.0,
    reason               TEXT NOT NULL DEFAULT '',

    -- "ai" = real AI result.  "fallback" is intentionally never inserted
    -- (the application layer filters these out), but the column exists for
    -- potential manual overrides or future admin tooling.
    source               TEXT NOT NULL DEFAULT 'ai',

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Unique indexes ────────────────────────────────────────────────────────────
-- Standard UNIQUE on (user_id, normalized_merchant, transaction_type) would
-- NOT deduplicate rows where user_id IS NULL because NULL != NULL in SQL.
-- Two partial indexes handle the two cases correctly.

-- User-scoped rows (the common case).
CREATE UNIQUE INDEX IF NOT EXISTS uq_mcc_user_merchant_type
ON merchant_classification_cache (user_id, normalized_merchant, transaction_type)
WHERE user_id IS NOT NULL;

-- Global rows (future cross-user cache).
CREATE UNIQUE INDEX IF NOT EXISTS uq_mcc_global_merchant_type
ON merchant_classification_cache (normalized_merchant, transaction_type)
WHERE user_id IS NULL;

-- ── Fast lookup index ─────────────────────────────────────────────────────────
-- The application always filters by user_id + normalized_merchant + transaction_type.
-- The partial unique indexes above are already usable for point lookups, but
-- this composite index covers partial merchant-only range scans (batch IN queries).
CREATE INDEX IF NOT EXISTS idx_mcc_lookup
ON merchant_classification_cache (user_id, normalized_merchant, transaction_type);

-- ── updated_at trigger ────────────────────────────────────────────────────────
-- Reuse the update_updated_at() function defined in create_tables.sql.
-- If that function doesn't exist in your environment, uncomment the block below.
--
-- CREATE OR REPLACE FUNCTION update_updated_at()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = NOW();
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS mcc_updated_at ON merchant_classification_cache;

CREATE TRIGGER mcc_updated_at
BEFORE UPDATE ON merchant_classification_cache
FOR EACH ROW EXECUTE PROCEDURE update_updated_at();
