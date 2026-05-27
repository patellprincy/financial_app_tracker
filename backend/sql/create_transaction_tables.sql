-- Run this in the Supabase SQL Editor after create_tables.sql

-- Global categories (shared across all users)
CREATE TABLE IF NOT EXISTS categories (
    id               SERIAL PRIMARY KEY,
    name             TEXT NOT NULL,
    normalized_name  TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (normalized_name, transaction_type)
);

CREATE INDEX IF NOT EXISTS idx_categories_normalized
ON categories(normalized_name, transaction_type);

-- User-specific transactions
CREATE TABLE IF NOT EXISTS transactions (
    id                 SERIAL PRIMARY KEY,
    user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    merchant           TEXT NOT NULL,
    amount             FLOAT NOT NULL,
    notes              TEXT NOT NULL DEFAULT '',
    transaction_type   TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
    category_id        INTEGER NOT NULL REFERENCES categories(id),
    category_name      TEXT NOT NULL,
    confidence         FLOAT NOT NULL DEFAULT 0.5,
    reason             TEXT NOT NULL DEFAULT '',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Latest ML anomaly detection result
    is_anomaly         BOOLEAN NOT NULL DEFAULT FALSE,
    anomaly_score      FLOAT,
    anomaly_reason     TEXT,
    anomaly_checked_at TIMESTAMPTZ,
    ml_model_version   TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_user_id
ON transactions(user_id);

CREATE INDEX IF NOT EXISTS idx_transactions_user_created
ON transactions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_user_anomaly
ON transactions(user_id, is_anomaly);

CREATE INDEX IF NOT EXISTS idx_transactions_anomaly_checked
ON transactions(anomaly_checked_at);