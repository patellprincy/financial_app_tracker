create extension if not exists "pgcrypto";

create table if not exists statement_uploads (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    file_name text not null,
    status text not null default 'uploaded',
    total_transactions integer,
    imported_transactions integer,
    failed_transactions integer,
    created_at timestamptz not null default now()
);

create index if not exists idx_statement_uploads_user_id on statement_uploads(user_id);
