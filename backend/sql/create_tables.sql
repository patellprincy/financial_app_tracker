create extension if not exists "pgcrypto";

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    first_name text not null,
    last_name text not null,
    email text unique not null,
    password_hash text not null,
    country text not null default 'Canada',
    default_currency text not null default 'CAD',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists users_updated_at on users;

create trigger users_updated_at
before update on users
for each row execute procedure update_updated_at();
