-- Supabase-shaped bootstrap for a LOCAL verification instance.
--
-- This file only runs when the container's data directory is empty. It recreates
-- the role and schema model a hosted Supabase project has, so the application can
-- be proven against that model instead of against a plain single-role Postgres.
--
-- Hosted Supabase already has these roles; do NOT run this file against a project.
-- The hosted equivalent is infrastructure/supabase/hosted-bootstrap.sql.

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS postgis SCHEMA extensions;

-- Supabase's client roles. They are NOLOGIN and have no privileges until granted:
-- RLS therefore fails closed for any client that somehow reaches them.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
        -- No password on purpose: nothing logs in as authenticator in this stack.
        CREATE ROLE authenticator LOGIN NOINHERIT;
    END IF;
END
$$;

-- The application's runtime role. It is the analogue of `authenticated`:
-- LOGIN, no superuser, no BYPASSRLS, no inheritance, so RLS applies to it.
-- Deliberately created WITHOUT a password: scripts/supabase_setup.py --bootstrap
-- sets one (generated, never committed) so no credential lives in tracked files.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'roadguard_app') THEN
        CREATE ROLE roadguard_app LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

-- Mapping, made explicit: the app runtime role is a member of `authenticated`,
-- and `authenticator` may switch to either client role (as on Supabase).
GRANT authenticated TO roadguard_app;
GRANT anon, authenticated TO authenticator;

-- Supabase puts PostGIS in `extensions`; every role must be able to resolve it.
ALTER DATABASE postgres SET search_path = "$user", public, extensions;

-- Mirrors Supabase's default: clients cannot create objects in public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public, extensions TO anon, authenticated, roadguard_app;
