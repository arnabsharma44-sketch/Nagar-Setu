-- ROADGUARD AI — hosted Supabase bootstrap (SQL Editor path).
--
-- Run this in the Supabase SQL Editor (as the project owner) when you are NOT
-- using `python scripts/supabase_setup.py --bootstrap`.
--
-- 1. Replace CHANGE_ME_STRONG_PASSWORD below with a generated password.
-- 2. Run this file, then infrastructure/supabase/schema.sql if you are not running
--    Alembic. If you ARE running Alembic, run bootstrap then `alembic upgrade head`
--    over the direct (5432) connection instead of loading schema.sql.
-- 3. Verify with infrastructure/supabase/verify.sql.
--
-- This file does not touch Supabase's `anon` / `authenticated` / `service_role`.
-- They keep their Supabase defaults; the application never connects as them. The
-- runtime role below is deliberately separate and RLS-bound.

create extension if not exists pgcrypto with schema extensions;
create extension if not exists postgis with schema extensions;

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'roadguard_app') then
        create role roadguard_app login password 'CHANGE_ME_STRONG_PASSWORD'
            nosuperuser nobypassrls nocreatedb nocreaterole noinherit;
    else
        alter role roadguard_app with login password 'CHANGE_ME_STRONG_PASSWORD'
            nosuperuser nobypassrls nocreatedb nocreaterole noinherit;
    end if;
end
$$;

grant connect on database postgres to roadguard_app;
grant usage on schema public to roadguard_app;
grant usage on schema extensions to roadguard_app;

alter role roadguard_app in database postgres
    set search_path to "$user", public, extensions;

-- Current objects (safe to run before migrations: it simply affects nothing).
grant select, insert, update, delete on all tables in schema public to roadguard_app;
grant usage, select on all sequences in schema public to roadguard_app;
grant execute on all functions in schema public to roadguard_app;

-- Future objects created by the migration role (`postgres`).
alter default privileges in schema public
    grant select, insert, update, delete on tables to roadguard_app;
alter default privileges in schema public
    grant usage, select on sequences to roadguard_app;
alter default privileges in schema public
    grant execute on functions to roadguard_app;

-- Append-only audit trail: SELECT/INSERT only, now and after every re-run.
revoke update, delete, truncate on audit_logs from roadguard_app;
grant select, insert on audit_logs to roadguard_app;
