-- ROADGUARD AI — full schema for the Supabase SQL Editor path.
--
-- Generated with `pg_dump --schema-only --no-owner` from a database migrated to
-- Alembic head 837c7ef69730 on the local Supabase-shaped instance (PostgreSQL 16.4,
-- PostGIS 3.4.3 in the `extensions` schema).
--
-- Use this INSTEAD of `alembic upgrade head` when you cannot run Python against the
-- project (SQL Editor only). Apply order:
--   1. infrastructure/supabase/hosted-bootstrap.sql   (extensions, role, grants)
--   2. infrastructure/supabase/schema.sql             (this file)
--   3. infrastructure/supabase/verify.sql
-- If you use Alembic, do NOT run this file; run the migration instead.
--
-- The trailing block pins the Alembic head so a later `alembic upgrade head`
-- recognises the schema as current, and re-applies the append-only audit grants.

--
-- PostgreSQL database dump
--

-- Dumped from database version 16.4 (Debian 16.4-1.pgdg110+2)
-- Dumped by pg_dump version 16.4 (Debian 16.4-1.pgdg110+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA extensions;


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;


--
-- Name: claim_ai_job(text, integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_ai_job(p_worker_id text, p_lease_seconds integer DEFAULT 900, p_max_attempts integer DEFAULT 3) RETURNS TABLE(out_job_id uuid, out_organization_id uuid)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
        DECLARE
            claimed ai_jobs;
        BEGIN
            SELECT j.* INTO claimed
            FROM ai_jobs j
            WHERE j.status = 'queued'
               OR (j.status = 'running' AND j.lease_expires_at IS NOT NULL AND j.lease_expires_at < now())
            ORDER BY j.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF claimed.id IS NULL THEN
                RETURN;
            END IF;

            UPDATE ai_jobs
               SET status = 'running',
                   stage = 'validating',
                   lease_owner = p_worker_id,
                   lease_expires_at = now() + make_interval(secs => p_lease_seconds),
                   started_at = COALESCE(started_at, now()),
                   attempts = attempts + 1,
                   updated_at = now()
             WHERE id = claimed.id;

            out_job_id := claimed.id;
            out_organization_id := claimed.organization_id;
            RETURN NEXT;
        END
        $$;


--
-- Name: prevent_audit_log_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_audit_log_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF current_user = 'postgres' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'audit_logs is append-only';
        END
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accident_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accident_records (
    external_reference character varying(120),
    location extensions.geography(Point,4326),
    location_quality character varying(64) NOT NULL,
    accident_time timestamp with time zone,
    accident_date date,
    accident_type character varying(80),
    severity character varying(40),
    road_name character varying(200),
    source_name character varying(200) NOT NULL,
    source_reference character varying(255) NOT NULL,
    verification_status character varying(64) NOT NULL,
    import_batch_id uuid,
    camera_source_type character varying(64),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    latitude double precision,
    longitude double precision
);


--
-- Name: ai_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_jobs (
    video_id uuid NOT NULL,
    job_type character varying(40) NOT NULL,
    status character varying(64) NOT NULL,
    stage character varying(64) NOT NULL,
    progress integer NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    model_name character varying(120),
    model_version character varying(64),
    weights_sha256 character varying(64),
    event_rules_version character varying(64),
    config_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    result_summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    attempts integer NOT NULL,
    lease_owner character varying(120),
    lease_expires_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    error_code character varying(80),
    error_message_safe character varying(500),
    created_by uuid,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assets (
    department_id uuid,
    asset_code character varying(80) NOT NULL,
    name character varying(200) NOT NULL,
    asset_type character varying(64) NOT NULL,
    address character varying(255),
    location extensions.geography(Point,4326),
    location_quality character varying(64) NOT NULL,
    condition_status character varying(64) NOT NULL,
    source_reference character varying(255),
    last_inspected_at timestamp with time zone,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    latitude double precision,
    longitude double precision
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    actor_id uuid,
    actor_label character varying(200),
    action character varying(80) NOT NULL,
    entity_type character varying(60) NOT NULL,
    entity_id uuid,
    request_id character varying(64),
    summary character varying(500),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: cameras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cameras (
    camera_code character varying(80) NOT NULL,
    name character varying(200) NOT NULL,
    location extensions.geography(Point,4326),
    location_quality character varying(64) NOT NULL,
    source_type character varying(64) NOT NULL,
    secret_reference character varying(255),
    connection_status character varying(64) NOT NULL,
    is_enabled boolean NOT NULL,
    is_demo boolean NOT NULL,
    description character varying(1000),
    last_seen_at timestamp with time zone,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    latitude double precision,
    longitude double precision
);


--
-- Name: contract_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contract_assets (
    contract_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    scope_notes character varying(1000),
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: contractors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contractors (
    name character varying(200) NOT NULL,
    registration_number character varying(80) NOT NULL,
    contact_email character varying(254),
    contact_phone character varying(40),
    source_reference character varying(255),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: contracts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contracts (
    contractor_id uuid NOT NULL,
    department_id uuid NOT NULL,
    contract_number character varying(80) NOT NULL,
    contract_type character varying(80) NOT NULL,
    scope_description character varying(2000) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    warranty_end_date date,
    source_reference character varying(255),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    organization_id uuid NOT NULL,
    name character varying(200) NOT NULL,
    normalized_name character varying(200) NOT NULL,
    department_type character varying(80) NOT NULL,
    contact_email character varying(254),
    description character varying(1000),
    source_reference character varying(255),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: detections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.detections (
    job_id uuid NOT NULL,
    frame_number integer NOT NULL,
    timestamp_offset_seconds double precision NOT NULL,
    class_label character varying(40) NOT NULL,
    class_id integer NOT NULL,
    bbox jsonb NOT NULL,
    score double precision NOT NULL,
    track_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence (
    incident_id uuid,
    investigation_id uuid,
    work_order_id uuid,
    storage_key character varying(512) NOT NULL,
    evidence_type character varying(64) NOT NULL,
    label character varying(200),
    content_type character varying(120) NOT NULL,
    original_filename character varying(255),
    file_size_bytes bigint NOT NULL,
    checksum_sha256 character varying(64) NOT NULL,
    timestamp_in_video double precision,
    created_by uuid NOT NULL,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hotspot_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hotspot_analyses (
    method character varying(80) NOT NULL,
    radius_meters double precision NOT NULL,
    window_from timestamp with time zone,
    window_to timestamp with time zone,
    min_size integer NOT NULL,
    parameters jsonb DEFAULT '{}'::jsonb NOT NULL,
    results jsonb DEFAULT '{}'::jsonb NOT NULL,
    generated_at timestamp with time zone NOT NULL,
    created_by uuid,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incidents (
    camera_id uuid,
    video_id uuid,
    ai_job_id uuid,
    incident_type character varying(64) NOT NULL,
    source_kind character varying(64) NOT NULL,
    severity character varying(64),
    model_score double precision,
    event_time timestamp with time zone NOT NULL,
    start_offset_seconds double precision,
    end_offset_seconds double precision,
    location extensions.geography(Point,4326),
    location_quality character varying(64) NOT NULL,
    description character varying(2000) NOT NULL,
    review_status character varying(64) NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_notes character varying(2000),
    model_name character varying(120),
    model_version character varying(64),
    rule_name character varying(80),
    rule_version character varying(64),
    track_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    features jsonb DEFAULT '{}'::jsonb NOT NULL,
    reason_codes jsonb DEFAULT '[]'::jsonb NOT NULL,
    limitations jsonb DEFAULT '[]'::jsonb NOT NULL,
    is_demo boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    latitude double precision,
    longitude double precision
);


--
-- Name: investigations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.investigations (
    case_number character varying(40) NOT NULL,
    incident_id uuid,
    asset_id uuid,
    assigned_department_id uuid,
    assigned_to uuid,
    title character varying(250) NOT NULL,
    summary character varying(2000),
    observed_facts jsonb DEFAULT '[]'::jsonb NOT NULL,
    hypotheses jsonb DEFAULT '[]'::jsonb NOT NULL,
    missing_information jsonb DEFAULT '[]'::jsonb NOT NULL,
    status character varying(64) NOT NULL,
    responsibility_status character varying(64),
    analysis_source character varying(40),
    analysis_model character varying(120),
    analysis_generated_at timestamp with time zone,
    opened_by uuid NOT NULL,
    closed_by uuid,
    closed_at timestamp with time zone,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: live_stream_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.live_stream_sessions (
    camera_id uuid NOT NULL,
    status character varying(64) NOT NULL,
    mode character varying(40) NOT NULL,
    is_simulated boolean NOT NULL,
    started_at timestamp with time zone,
    stopped_at timestamp with time zone,
    started_by uuid,
    last_frame_at timestamp with time zone,
    detail character varying(500),
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    name character varying(200) NOT NULL,
    slug character varying(80) NOT NULL,
    organization_type character varying(64) NOT NULL,
    city character varying(120),
    state character varying(120),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recommendations (
    investigation_id uuid NOT NULL,
    recommendation_text character varying(2000) NOT NULL,
    rationale character varying(2000) NOT NULL,
    priority character varying(64) NOT NULL,
    status character varying(64) NOT NULL,
    model_name character varying(120),
    model_version character varying(64),
    input_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    limitations jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_by uuid NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_notes character varying(2000),
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: refresh_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_sessions (
    organization_id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    replaced_by_id uuid,
    user_agent character varying(255),
    ip_address character varying(64),
    id uuid NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    organization_id uuid NOT NULL,
    department_id uuid,
    full_name character varying(200) NOT NULL,
    email character varying(254) NOT NULL,
    normalized_email character varying(254) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(64) NOT NULL,
    is_active boolean NOT NULL,
    last_login_at timestamp with time zone,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: verifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verifications (
    work_order_id uuid NOT NULL,
    verified_by uuid NOT NULL,
    verification_status character varying(64) NOT NULL,
    notes character varying(2000) NOT NULL,
    verified_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: videos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.videos (
    camera_id uuid,
    uploaded_by uuid NOT NULL,
    storage_key character varying(512) NOT NULL,
    original_filename character varying(255) NOT NULL,
    content_type character varying(120) NOT NULL,
    file_size_bytes bigint NOT NULL,
    checksum_sha256 character varying(64),
    source_type character varying(64) NOT NULL,
    recorded_at timestamp with time zone,
    duration_seconds double precision,
    width integer,
    height integer,
    frame_rate double precision,
    status character varying(64) NOT NULL,
    validation_error character varying(500),
    retention_expires_at timestamp with time zone,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: work_order_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_order_status_history (
    work_order_id uuid NOT NULL,
    from_status character varying(64),
    to_status character varying(64) NOT NULL,
    changed_by uuid NOT NULL,
    note character varying(2000),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL
);


--
-- Name: work_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.work_orders (
    work_order_number character varying(40) NOT NULL,
    investigation_id uuid NOT NULL,
    recommendation_id uuid,
    assigned_department_id uuid NOT NULL,
    assigned_to uuid,
    title character varying(250) NOT NULL,
    description character varying(4000) NOT NULL,
    status character varying(64) NOT NULL,
    priority character varying(64) NOT NULL,
    due_date date,
    completed_at timestamp with time zone,
    completion_notes character varying(4000),
    completed_by uuid,
    verified_at timestamp with time zone,
    verified_by uuid,
    created_by uuid NOT NULL,
    is_demo boolean NOT NULL,
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: accident_records pk_accident_records; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accident_records
    ADD CONSTRAINT pk_accident_records PRIMARY KEY (id);


--
-- Name: ai_jobs pk_ai_jobs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_jobs
    ADD CONSTRAINT pk_ai_jobs PRIMARY KEY (id);


--
-- Name: assets pk_assets; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT pk_assets PRIMARY KEY (id);


--
-- Name: audit_logs pk_audit_logs; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT pk_audit_logs PRIMARY KEY (id);


--
-- Name: cameras pk_cameras; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT pk_cameras PRIMARY KEY (id);


--
-- Name: contract_assets pk_contract_assets; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assets
    ADD CONSTRAINT pk_contract_assets PRIMARY KEY (id);


--
-- Name: contractors pk_contractors; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT pk_contractors PRIMARY KEY (id);


--
-- Name: contracts pk_contracts; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT pk_contracts PRIMARY KEY (id);


--
-- Name: departments pk_departments; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT pk_departments PRIMARY KEY (id);


--
-- Name: detections pk_detections; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detections
    ADD CONSTRAINT pk_detections PRIMARY KEY (id);


--
-- Name: evidence pk_evidence; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT pk_evidence PRIMARY KEY (id);


--
-- Name: hotspot_analyses pk_hotspot_analyses; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hotspot_analyses
    ADD CONSTRAINT pk_hotspot_analyses PRIMARY KEY (id);


--
-- Name: incidents pk_incidents; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT pk_incidents PRIMARY KEY (id);


--
-- Name: investigations pk_investigations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT pk_investigations PRIMARY KEY (id);


--
-- Name: live_stream_sessions pk_live_stream_sessions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_stream_sessions
    ADD CONSTRAINT pk_live_stream_sessions PRIMARY KEY (id);


--
-- Name: organizations pk_organizations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT pk_organizations PRIMARY KEY (id);


--
-- Name: recommendations pk_recommendations; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT pk_recommendations PRIMARY KEY (id);


--
-- Name: refresh_sessions pk_refresh_sessions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT pk_refresh_sessions PRIMARY KEY (id);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: verifications pk_verifications; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verifications
    ADD CONSTRAINT pk_verifications PRIMARY KEY (id);


--
-- Name: videos pk_videos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT pk_videos PRIMARY KEY (id);


--
-- Name: work_order_status_history pk_work_order_status_history; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_status_history
    ADD CONSTRAINT pk_work_order_status_history PRIMARY KEY (id);


--
-- Name: work_orders pk_work_orders; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT pk_work_orders PRIMARY KEY (id);


--
-- Name: accident_records uq_accident_records_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accident_records
    ADD CONSTRAINT uq_accident_records_id_organization_id UNIQUE (id, organization_id);


--
-- Name: ai_jobs uq_ai_jobs_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_jobs
    ADD CONSTRAINT uq_ai_jobs_id_organization_id UNIQUE (id, organization_id);


--
-- Name: ai_jobs uq_ai_jobs_org_idempotency_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_jobs
    ADD CONSTRAINT uq_ai_jobs_org_idempotency_key UNIQUE (organization_id, idempotency_key);


--
-- Name: assets uq_assets_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT uq_assets_id_organization_id UNIQUE (id, organization_id);


--
-- Name: assets uq_assets_org_asset_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT uq_assets_org_asset_code UNIQUE (organization_id, asset_code);


--
-- Name: cameras uq_cameras_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT uq_cameras_id_organization_id UNIQUE (id, organization_id);


--
-- Name: cameras uq_cameras_org_camera_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT uq_cameras_org_camera_code UNIQUE (organization_id, camera_code);


--
-- Name: contract_assets uq_contract_assets_contract_id_asset_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assets
    ADD CONSTRAINT uq_contract_assets_contract_id_asset_id UNIQUE (contract_id, asset_id);


--
-- Name: contractors uq_contractors_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT uq_contractors_id_organization_id UNIQUE (id, organization_id);


--
-- Name: contractors uq_contractors_org_registration_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT uq_contractors_org_registration_number UNIQUE (organization_id, registration_number);


--
-- Name: contracts uq_contracts_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT uq_contracts_id_organization_id UNIQUE (id, organization_id);


--
-- Name: contracts uq_contracts_org_contract_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT uq_contracts_org_contract_number UNIQUE (organization_id, contract_number);


--
-- Name: departments uq_departments_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT uq_departments_id_organization_id UNIQUE (id, organization_id);


--
-- Name: departments uq_departments_org_normalized_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT uq_departments_org_normalized_name UNIQUE (organization_id, normalized_name);


--
-- Name: evidence uq_evidence_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT uq_evidence_id_organization_id UNIQUE (id, organization_id);


--
-- Name: evidence uq_evidence_storage_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT uq_evidence_storage_key UNIQUE (storage_key);


--
-- Name: hotspot_analyses uq_hotspot_analyses_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hotspot_analyses
    ADD CONSTRAINT uq_hotspot_analyses_id_organization_id UNIQUE (id, organization_id);


--
-- Name: incidents uq_incidents_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT uq_incidents_id_organization_id UNIQUE (id, organization_id);


--
-- Name: investigations uq_investigations_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT uq_investigations_id_organization_id UNIQUE (id, organization_id);


--
-- Name: investigations uq_investigations_org_case_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT uq_investigations_org_case_number UNIQUE (organization_id, case_number);


--
-- Name: organizations uq_organizations_slug; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT uq_organizations_slug UNIQUE (slug);


--
-- Name: recommendations uq_recommendations_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT uq_recommendations_id_organization_id UNIQUE (id, organization_id);


--
-- Name: refresh_sessions uq_refresh_sessions_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT uq_refresh_sessions_id_organization_id UNIQUE (id, organization_id);


--
-- Name: refresh_sessions uq_refresh_sessions_token_hash; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT uq_refresh_sessions_token_hash UNIQUE (token_hash);


--
-- Name: users uq_users_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_id_organization_id UNIQUE (id, organization_id);


--
-- Name: users uq_users_org_normalized_email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_org_normalized_email UNIQUE (organization_id, normalized_email);


--
-- Name: videos uq_videos_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT uq_videos_id_organization_id UNIQUE (id, organization_id);


--
-- Name: videos uq_videos_storage_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT uq_videos_storage_key UNIQUE (storage_key);


--
-- Name: work_orders uq_work_orders_id_organization_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT uq_work_orders_id_organization_id UNIQUE (id, organization_id);


--
-- Name: work_orders uq_work_orders_org_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT uq_work_orders_org_number UNIQUE (organization_id, work_order_number);


--
-- Name: ix_accident_records_import_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accident_records_import_batch_id ON public.accident_records USING btree (import_batch_id);


--
-- Name: ix_accident_records_location_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accident_records_location_gist ON public.accident_records USING gist (location);


--
-- Name: ix_accident_records_org_accident_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accident_records_org_accident_time ON public.accident_records USING btree (organization_id, accident_time);


--
-- Name: ix_accident_records_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accident_records_organization_id ON public.accident_records USING btree (organization_id);


--
-- Name: ix_ai_jobs_org_status_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_jobs_org_status_created ON public.ai_jobs USING btree (organization_id, status, created_at DESC);


--
-- Name: ix_ai_jobs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_jobs_organization_id ON public.ai_jobs USING btree (organization_id);


--
-- Name: ix_ai_jobs_video_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_jobs_video_id ON public.ai_jobs USING btree (video_id);


--
-- Name: ix_assets_location_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assets_location_gist ON public.assets USING gist (location);


--
-- Name: ix_assets_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assets_organization_id ON public.assets USING btree (organization_id);


--
-- Name: ix_audit_logs_org_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_org_created_at ON public.audit_logs USING btree (organization_id, created_at DESC);


--
-- Name: ix_audit_logs_org_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_org_entity ON public.audit_logs USING btree (organization_id, entity_type, entity_id);


--
-- Name: ix_audit_logs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_organization_id ON public.audit_logs USING btree (organization_id);


--
-- Name: ix_cameras_location_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cameras_location_gist ON public.cameras USING gist (location);


--
-- Name: ix_cameras_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cameras_organization_id ON public.cameras USING btree (organization_id);


--
-- Name: ix_contract_assets_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contract_assets_asset_id ON public.contract_assets USING btree (asset_id);


--
-- Name: ix_contract_assets_contract_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contract_assets_contract_id ON public.contract_assets USING btree (contract_id);


--
-- Name: ix_contract_assets_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contract_assets_organization_id ON public.contract_assets USING btree (organization_id);


--
-- Name: ix_contractors_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contractors_organization_id ON public.contractors USING btree (organization_id);


--
-- Name: ix_contracts_contractor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_contractor_id ON public.contracts USING btree (contractor_id);


--
-- Name: ix_contracts_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_department_id ON public.contracts USING btree (department_id);


--
-- Name: ix_contracts_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contracts_organization_id ON public.contracts USING btree (organization_id);


--
-- Name: ix_departments_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_departments_organization_id ON public.departments USING btree (organization_id);


--
-- Name: ix_detections_job_id_frame_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_detections_job_id_frame_number ON public.detections USING btree (job_id, frame_number);


--
-- Name: ix_detections_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_detections_organization_id ON public.detections USING btree (organization_id);


--
-- Name: ix_evidence_incident_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_incident_id ON public.evidence USING btree (incident_id);


--
-- Name: ix_evidence_investigation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_investigation_id ON public.evidence USING btree (investigation_id);


--
-- Name: ix_evidence_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_organization_id ON public.evidence USING btree (organization_id);


--
-- Name: ix_evidence_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evidence_work_order_id ON public.evidence USING btree (work_order_id);


--
-- Name: ix_hotspot_analyses_org_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hotspot_analyses_org_created ON public.hotspot_analyses USING btree (organization_id, created_at DESC);


--
-- Name: ix_hotspot_analyses_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hotspot_analyses_organization_id ON public.hotspot_analyses USING btree (organization_id);


--
-- Name: ix_incidents_ai_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_ai_job_id ON public.incidents USING btree (ai_job_id);


--
-- Name: ix_incidents_camera_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_camera_id ON public.incidents USING btree (camera_id);


--
-- Name: ix_incidents_location_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_location_gist ON public.incidents USING gist (location);


--
-- Name: ix_incidents_org_event_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_org_event_time ON public.incidents USING btree (organization_id, event_time DESC);


--
-- Name: ix_incidents_org_review_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_org_review_status ON public.incidents USING btree (organization_id, review_status);


--
-- Name: ix_incidents_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_organization_id ON public.incidents USING btree (organization_id);


--
-- Name: ix_incidents_video_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_incidents_video_id ON public.incidents USING btree (video_id);


--
-- Name: ix_investigations_asset_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_investigations_asset_id ON public.investigations USING btree (asset_id);


--
-- Name: ix_investigations_assigned_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_investigations_assigned_department_id ON public.investigations USING btree (assigned_department_id);


--
-- Name: ix_investigations_incident_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_investigations_incident_id ON public.investigations USING btree (incident_id);


--
-- Name: ix_investigations_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_investigations_org_status ON public.investigations USING btree (organization_id, status);


--
-- Name: ix_investigations_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_investigations_organization_id ON public.investigations USING btree (organization_id);


--
-- Name: ix_live_stream_sessions_camera_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_live_stream_sessions_camera_status ON public.live_stream_sessions USING btree (camera_id, status);


--
-- Name: ix_live_stream_sessions_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_live_stream_sessions_organization_id ON public.live_stream_sessions USING btree (organization_id);


--
-- Name: ix_recommendations_investigation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recommendations_investigation_id ON public.recommendations USING btree (investigation_id);


--
-- Name: ix_recommendations_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recommendations_org_status ON public.recommendations USING btree (organization_id, status);


--
-- Name: ix_recommendations_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recommendations_organization_id ON public.recommendations USING btree (organization_id);


--
-- Name: ix_refresh_sessions_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_sessions_organization_id ON public.refresh_sessions USING btree (organization_id);


--
-- Name: ix_refresh_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_refresh_sessions_user_id ON public.refresh_sessions USING btree (user_id);


--
-- Name: ix_users_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_department_id ON public.users USING btree (department_id);


--
-- Name: ix_users_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_organization_id ON public.users USING btree (organization_id);


--
-- Name: ix_verifications_org_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_verifications_org_created ON public.verifications USING btree (organization_id, created_at);


--
-- Name: ix_verifications_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_verifications_organization_id ON public.verifications USING btree (organization_id);


--
-- Name: ix_verifications_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_verifications_work_order_id ON public.verifications USING btree (work_order_id);


--
-- Name: ix_videos_camera_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_videos_camera_id ON public.videos USING btree (camera_id);


--
-- Name: ix_videos_org_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_videos_org_created_at ON public.videos USING btree (organization_id, created_at DESC);


--
-- Name: ix_videos_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_videos_organization_id ON public.videos USING btree (organization_id);


--
-- Name: ix_work_order_status_history_org_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_status_history_org_created ON public.work_order_status_history USING btree (organization_id, created_at);


--
-- Name: ix_work_order_status_history_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_status_history_organization_id ON public.work_order_status_history USING btree (organization_id);


--
-- Name: ix_work_order_status_history_work_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_order_status_history_work_order_id ON public.work_order_status_history USING btree (work_order_id);


--
-- Name: ix_work_orders_assigned_department_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_assigned_department_id ON public.work_orders USING btree (assigned_department_id);


--
-- Name: ix_work_orders_investigation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_investigation_id ON public.work_orders USING btree (investigation_id);


--
-- Name: ix_work_orders_org_status_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_org_status_due ON public.work_orders USING btree (organization_id, status, due_date);


--
-- Name: ix_work_orders_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_organization_id ON public.work_orders USING btree (organization_id);


--
-- Name: ix_work_orders_recommendation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_work_orders_recommendation_id ON public.work_orders USING btree (recommendation_id);


--
-- Name: audit_logs trg_audit_logs_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_logs_append_only BEFORE DELETE OR UPDATE ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_log_mutation();


--
-- Name: accident_records fk_accident_records_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accident_records
    ADD CONSTRAINT fk_accident_records_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: ai_jobs fk_ai_jobs_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_jobs
    ADD CONSTRAINT fk_ai_jobs_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: ai_jobs fk_ai_jobs_video_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_jobs
    ADD CONSTRAINT fk_ai_jobs_video_tenant FOREIGN KEY (video_id, organization_id) REFERENCES public.videos(id, organization_id);


--
-- Name: assets fk_assets_department_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT fk_assets_department_tenant FOREIGN KEY (department_id, organization_id) REFERENCES public.departments(id, organization_id);


--
-- Name: assets fk_assets_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT fk_assets_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: audit_logs fk_audit_logs_actor_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_actor_tenant FOREIGN KEY (actor_id, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: audit_logs fk_audit_logs_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: cameras fk_cameras_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cameras
    ADD CONSTRAINT fk_cameras_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: contract_assets fk_contract_assets_asset_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assets
    ADD CONSTRAINT fk_contract_assets_asset_tenant FOREIGN KEY (asset_id, organization_id) REFERENCES public.assets(id, organization_id);


--
-- Name: contract_assets fk_contract_assets_contract_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assets
    ADD CONSTRAINT fk_contract_assets_contract_tenant FOREIGN KEY (contract_id, organization_id) REFERENCES public.contracts(id, organization_id);


--
-- Name: contract_assets fk_contract_assets_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contract_assets
    ADD CONSTRAINT fk_contract_assets_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: contractors fk_contractors_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contractors
    ADD CONSTRAINT fk_contractors_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: contracts fk_contracts_contractor_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_contractor_tenant FOREIGN KEY (contractor_id, organization_id) REFERENCES public.contractors(id, organization_id);


--
-- Name: contracts fk_contracts_department_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_department_tenant FOREIGN KEY (department_id, organization_id) REFERENCES public.departments(id, organization_id);


--
-- Name: contracts fk_contracts_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contracts
    ADD CONSTRAINT fk_contracts_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: departments fk_departments_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT fk_departments_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: detections fk_detections_job_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detections
    ADD CONSTRAINT fk_detections_job_tenant FOREIGN KEY (job_id, organization_id) REFERENCES public.ai_jobs(id, organization_id);


--
-- Name: detections fk_detections_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.detections
    ADD CONSTRAINT fk_detections_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: evidence fk_evidence_created_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT fk_evidence_created_by_tenant FOREIGN KEY (created_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: evidence fk_evidence_incident_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT fk_evidence_incident_tenant FOREIGN KEY (incident_id, organization_id) REFERENCES public.incidents(id, organization_id);


--
-- Name: evidence fk_evidence_investigation_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT fk_evidence_investigation_tenant FOREIGN KEY (investigation_id, organization_id) REFERENCES public.investigations(id, organization_id);


--
-- Name: evidence fk_evidence_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT fk_evidence_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: evidence fk_evidence_work_order_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT fk_evidence_work_order_tenant FOREIGN KEY (work_order_id, organization_id) REFERENCES public.work_orders(id, organization_id);


--
-- Name: hotspot_analyses fk_hotspot_analyses_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hotspot_analyses
    ADD CONSTRAINT fk_hotspot_analyses_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: incidents fk_incidents_ai_job_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT fk_incidents_ai_job_tenant FOREIGN KEY (ai_job_id, organization_id) REFERENCES public.ai_jobs(id, organization_id);


--
-- Name: incidents fk_incidents_camera_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT fk_incidents_camera_tenant FOREIGN KEY (camera_id, organization_id) REFERENCES public.cameras(id, organization_id);


--
-- Name: incidents fk_incidents_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT fk_incidents_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: incidents fk_incidents_reviewed_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT fk_incidents_reviewed_by_tenant FOREIGN KEY (reviewed_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: incidents fk_incidents_video_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT fk_incidents_video_tenant FOREIGN KEY (video_id, organization_id) REFERENCES public.videos(id, organization_id);


--
-- Name: investigations fk_investigations_asset_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_asset_tenant FOREIGN KEY (asset_id, organization_id) REFERENCES public.assets(id, organization_id);


--
-- Name: investigations fk_investigations_assigned_to_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_assigned_to_tenant FOREIGN KEY (assigned_to, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: investigations fk_investigations_department_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_department_tenant FOREIGN KEY (assigned_department_id, organization_id) REFERENCES public.departments(id, organization_id);


--
-- Name: investigations fk_investigations_incident_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_incident_tenant FOREIGN KEY (incident_id, organization_id) REFERENCES public.incidents(id, organization_id);


--
-- Name: investigations fk_investigations_opened_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_opened_by_tenant FOREIGN KEY (opened_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: investigations fk_investigations_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigations
    ADD CONSTRAINT fk_investigations_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: live_stream_sessions fk_live_stream_sessions_camera_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_stream_sessions
    ADD CONSTRAINT fk_live_stream_sessions_camera_tenant FOREIGN KEY (camera_id, organization_id) REFERENCES public.cameras(id, organization_id);


--
-- Name: live_stream_sessions fk_live_stream_sessions_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_stream_sessions
    ADD CONSTRAINT fk_live_stream_sessions_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: recommendations fk_recommendations_created_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT fk_recommendations_created_by_tenant FOREIGN KEY (created_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: recommendations fk_recommendations_investigation_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT fk_recommendations_investigation_tenant FOREIGN KEY (investigation_id, organization_id) REFERENCES public.investigations(id, organization_id);


--
-- Name: recommendations fk_recommendations_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT fk_recommendations_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: recommendations fk_recommendations_reviewed_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT fk_recommendations_reviewed_by_tenant FOREIGN KEY (reviewed_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: refresh_sessions fk_refresh_sessions_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT fk_refresh_sessions_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: refresh_sessions fk_refresh_sessions_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_sessions
    ADD CONSTRAINT fk_refresh_sessions_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users fk_users_department_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_department_tenant FOREIGN KEY (department_id, organization_id) REFERENCES public.departments(id, organization_id);


--
-- Name: users fk_users_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: verifications fk_verifications_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verifications
    ADD CONSTRAINT fk_verifications_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: verifications fk_verifications_verified_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verifications
    ADD CONSTRAINT fk_verifications_verified_by_tenant FOREIGN KEY (verified_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: verifications fk_verifications_work_order_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verifications
    ADD CONSTRAINT fk_verifications_work_order_tenant FOREIGN KEY (work_order_id, organization_id) REFERENCES public.work_orders(id, organization_id);


--
-- Name: videos fk_videos_camera_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT fk_videos_camera_tenant FOREIGN KEY (camera_id, organization_id) REFERENCES public.cameras(id, organization_id);


--
-- Name: videos fk_videos_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT fk_videos_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: videos fk_videos_uploaded_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT fk_videos_uploaded_by_tenant FOREIGN KEY (uploaded_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: work_order_status_history fk_work_order_status_history_changed_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_status_history
    ADD CONSTRAINT fk_work_order_status_history_changed_by_tenant FOREIGN KEY (changed_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: work_order_status_history fk_work_order_status_history_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_status_history
    ADD CONSTRAINT fk_work_order_status_history_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: work_order_status_history fk_work_order_status_history_work_order_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_order_status_history
    ADD CONSTRAINT fk_work_order_status_history_work_order_tenant FOREIGN KEY (work_order_id, organization_id) REFERENCES public.work_orders(id, organization_id);


--
-- Name: work_orders fk_work_orders_assigned_to_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_assigned_to_tenant FOREIGN KEY (assigned_to, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: work_orders fk_work_orders_created_by_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_created_by_tenant FOREIGN KEY (created_by, organization_id) REFERENCES public.users(id, organization_id);


--
-- Name: work_orders fk_work_orders_department_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_department_tenant FOREIGN KEY (assigned_department_id, organization_id) REFERENCES public.departments(id, organization_id);


--
-- Name: work_orders fk_work_orders_investigation_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_investigation_tenant FOREIGN KEY (investigation_id, organization_id) REFERENCES public.investigations(id, organization_id);


--
-- Name: work_orders fk_work_orders_organization_id_organizations; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_organization_id_organizations FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE RESTRICT;


--
-- Name: work_orders fk_work_orders_recommendation_tenant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.work_orders
    ADD CONSTRAINT fk_work_orders_recommendation_tenant FOREIGN KEY (recommendation_id, organization_id) REFERENCES public.recommendations(id, organization_id);


--
-- Name: accident_records; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.accident_records ENABLE ROW LEVEL SECURITY;

--
-- Name: ai_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ai_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: assets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_logs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

--
-- Name: cameras; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cameras ENABLE ROW LEVEL SECURITY;

--
-- Name: contract_assets; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contract_assets ENABLE ROW LEVEL SECURITY;

--
-- Name: contractors; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contractors ENABLE ROW LEVEL SECURITY;

--
-- Name: contracts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.contracts ENABLE ROW LEVEL SECURITY;

--
-- Name: departments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;

--
-- Name: detections; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.detections ENABLE ROW LEVEL SECURITY;

--
-- Name: evidence; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.evidence ENABLE ROW LEVEL SECURITY;

--
-- Name: hotspot_analyses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.hotspot_analyses ENABLE ROW LEVEL SECURITY;

--
-- Name: incidents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;

--
-- Name: investigations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.investigations ENABLE ROW LEVEL SECURITY;

--
-- Name: live_stream_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.live_stream_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: organizations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;

--
-- Name: recommendations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.refresh_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: accident_records tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.accident_records USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: ai_jobs tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.ai_jobs USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: assets tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.assets USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: audit_logs tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.audit_logs USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: cameras tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.cameras USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: contract_assets tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.contract_assets USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: contractors tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.contractors USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: contracts tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.contracts USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: departments tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.departments USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: detections tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.detections USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: evidence tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.evidence USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: hotspot_analyses tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.hotspot_analyses USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: incidents tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.incidents USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: investigations tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.investigations USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: live_stream_sessions tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.live_stream_sessions USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: organizations tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.organizations USING ((id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: recommendations tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.recommendations USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: refresh_sessions tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.refresh_sessions USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: users tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.users USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: verifications tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.verifications USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: videos tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.videos USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: work_order_status_history tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.work_order_status_history USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: work_orders tenant_isolation; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tenant_isolation ON public.work_orders USING ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid)) WITH CHECK ((organization_id = (NULLIF(current_setting('app.current_organization_id'::text, true), ''::text))::uuid));


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: verifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.verifications ENABLE ROW LEVEL SECURITY;

--
-- Name: videos; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;

--
-- Name: work_order_status_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_order_status_history ENABLE ROW LEVEL SECURITY;

--
-- Name: work_orders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.work_orders ENABLE ROW LEVEL SECURITY;

--
-- Name: SCHEMA extensions; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO roadguard_app;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: -
--

GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO roadguard_app;


--
-- Name: FUNCTION claim_ai_job(p_worker_id text, p_lease_seconds integer, p_max_attempts integer); Type: ACL; Schema: public; Owner: -
--

REVOKE ALL ON FUNCTION public.claim_ai_job(p_worker_id text, p_lease_seconds integer, p_max_attempts integer) FROM PUBLIC;
GRANT ALL ON FUNCTION public.claim_ai_job(p_worker_id text, p_lease_seconds integer, p_max_attempts integer) TO roadguard_app;


--
-- Name: FUNCTION prevent_audit_log_mutation(); Type: ACL; Schema: public; Owner: -
--

GRANT ALL ON FUNCTION public.prevent_audit_log_mutation() TO roadguard_app;


--
-- Name: TABLE accident_records; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.accident_records TO roadguard_app;


--
-- Name: TABLE ai_jobs; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.ai_jobs TO roadguard_app;


--
-- Name: TABLE alembic_version; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.alembic_version TO roadguard_app;


--
-- Name: TABLE assets; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.assets TO roadguard_app;


--
-- Name: TABLE audit_logs; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT ON TABLE public.audit_logs TO roadguard_app;


--
-- Name: TABLE cameras; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.cameras TO roadguard_app;


--
-- Name: TABLE contract_assets; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.contract_assets TO roadguard_app;


--
-- Name: TABLE contractors; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.contractors TO roadguard_app;


--
-- Name: TABLE contracts; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.contracts TO roadguard_app;


--
-- Name: TABLE departments; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.departments TO roadguard_app;


--
-- Name: TABLE detections; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.detections TO roadguard_app;


--
-- Name: TABLE evidence; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.evidence TO roadguard_app;


--
-- Name: TABLE hotspot_analyses; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.hotspot_analyses TO roadguard_app;


--
-- Name: TABLE incidents; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.incidents TO roadguard_app;


--
-- Name: TABLE investigations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.investigations TO roadguard_app;


--
-- Name: TABLE live_stream_sessions; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.live_stream_sessions TO roadguard_app;


--
-- Name: TABLE organizations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.organizations TO roadguard_app;


--
-- Name: TABLE recommendations; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.recommendations TO roadguard_app;


--
-- Name: TABLE refresh_sessions; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.refresh_sessions TO roadguard_app;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.users TO roadguard_app;


--
-- Name: TABLE verifications; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.verifications TO roadguard_app;


--
-- Name: TABLE videos; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.videos TO roadguard_app;


--
-- Name: TABLE work_order_status_history; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.work_order_status_history TO roadguard_app;


--
-- Name: TABLE work_orders; Type: ACL; Schema: public; Owner: -
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.work_orders TO roadguard_app;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,USAGE ON SEQUENCES TO roadguard_app;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO roadguard_app;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: -
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO roadguard_app;


--
-- PostgreSQL database dump complete
--


-- --- head marker + append-only hardening (idempotent) ---
INSERT INTO public.alembic_version (version_num) VALUES ('837c7ef69730')
    ON CONFLICT (version_num) DO NOTHING;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM roadguard_app;
GRANT SELECT, INSERT ON public.audit_logs TO roadguard_app;
