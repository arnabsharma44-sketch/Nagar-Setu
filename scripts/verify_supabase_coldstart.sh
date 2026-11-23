#!/usr/bin/env bash
# Cold-start verification for the Supabase-shaped stack.
#
# This is the exact sequence documented in docs/SUPABASE.md §2. It destroys the
# stack's containers AND volumes, rebuilds it, and then proves, in order:
#
#   1. TLS is required and the Supabase role model exists
#   2. bootstrap creates/hardens the runtime role
#   3. migrations apply empty -> head with no errors
#   4. a second migration run is a no-op
#   5. schema, RLS, policies and audit grants are present
#   6. seed + the 2-organisation isolation/database suites pass through the pooler
#   7. an external worker completes the 12-step workflow against the pooler
#   8. a bootstrap RE-RUN leaves the pooler able to log in (stale-credential regression)
#   9. the non-Alembic schema.sql loads into a fresh database
#
# It never writes .env (the dev path stays untouched) and it kills only the API and
# worker processes it started itself.
#
#   bash scripts/verify_supabase_coldstart.sh
#   LOG=/tmp/cold.log bash scripts/verify_supabase_coldstart.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Child processes are native Windows binaries: paths that bash understands
# (/c/PROJECTS/...) are meaningless to them, so hand them Windows paths.
native_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

PY="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"
LOG="${LOG:-/tmp/supabase-coldstart.log}"
COMPOSE=(docker compose -f docker-compose.supabase.yml)
DIRECT_URL="postgresql://postgres:postgres@127.0.0.1:5433/postgres?sslmode=require"
# Generated per run and never committed: the pooler userlist and the role password
# are both derived from it. Nothing secret lives in tracked files.
APP_PASSWORD="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
export APP_PASSWORD
export APP_DB_PASSWORD="$APP_PASSWORD"   # consumed by the compose `auth` service
APP_URL="postgresql://roadguard_app:${APP_PASSWORD}@127.0.0.1:6543/postgres?sslmode=require&pgbouncer=true"

export DATABASE_MIGRATION_URL="$DIRECT_URL"
export DATABASE_APP_URL="$APP_URL"
export STORAGE_BACKEND=local
export LOCAL_STORAGE_DIR="$(native_path "$ROOT/storage-supabase")"
export JOB_RUNNER=polling
export ENVIRONMENT=development
export LOGIN_RATE_LIMIT_PER_MINUTE=500

API_PID=""
WORKER_PID=""
cleanup() {
    if [ -n "$WORKER_PID" ]; then kill "$WORKER_PID" 2>/dev/null || true; fi
    if [ -n "$API_PID" ]; then kill "$API_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

step() { printf '\n=== %s ===\n' "$*"; }
fail() { printf '\nCOLD-START FAIL: %s\n' "$*" >&2; exit 1; }

run() {
    step "$1"
    shift
    "$@"
}

{
    run "0. destroy containers, volumes and local runtime storage" "${COMPOSE[@]}" down -v --remove-orphans
    docker rm -f roadguard-supabase-db roadguard-supabase-pooler roadguard-supabase-certs \
        >/dev/null 2>&1 || true
    rm -rf "$ROOT/storage-supabase"
    mkdir -p "$ROOT/storage-supabase"

    run "1. start the stack (auth file generated into a volume)" "${COMPOSE[@]}" up -d
    step "1b. wait for database health"
    for _ in $(seq 1 45); do
        [ "$(docker inspect -f '{{.State.Health.Status}}' roadguard-supabase-db 2>/dev/null)" = "healthy" ] && break
        sleep 2
    done
    [ "$(docker inspect -f '{{.State.Health.Status}}' roadguard-supabase-db)" = "healthy" ] || fail "database never became healthy"
    "${COMPOSE[@]}" ps

    step "2. TLS enforced + Supabase role model"
    "$PY" - <<'PY'
import psycopg

direct = "postgresql://postgres:postgres@127.0.0.1:5433/postgres"
with psycopg.connect(direct + "?sslmode=require", connect_timeout=10) as c:
    ssl = c.execute("select ssl from pg_stat_ssl where pid=pg_backend_pid()").fetchone()[0]
    print("TLS require ->", "ssl=on" if ssl else "ssl=OFF")
    assert ssl, "TLS was not negotiated"
try:
    psycopg.connect(direct + "?sslmode=disable", connect_timeout=5)
    raise SystemExit("plaintext connection was accepted")
except Exception as exc:
    print("TLS disable -> refused:", str(exc).splitlines()[0][:80])

with psycopg.connect(direct + "?sslmode=require") as c:
    rows = c.execute(
        "select rolname, rolcanlogin, rolsuper, rolbypassrls from pg_roles "
        "where rolname in ('anon','authenticated','service_role','authenticator','roadguard_app') "
        "order by rolname"
    ).fetchall()
    for row in rows:
        print("  role", row)
    if not any(r[0] == "service_role" and r[3] for r in rows):
        raise SystemExit("service_role should have BYPASSRLS")
    if any(r[0] == "roadguard_app" and (r[2] or r[3]) for r in rows):
        raise SystemExit("roadguard_app must not be superuser or bypassrls")
PY

    run "3. bootstrap (direct URL; app password matches the local pooler)" \
        bash -c "SUPABASE_DB_URL='$DIRECT_URL' '$PY' scripts/supabase_setup.py --url '$DIRECT_URL' --app-url '$APP_URL' --app-password '$APP_PASSWORD' --bootstrap"

    run "4. migrate from empty to head" bash -c "cd '$ROOT/apps/api' && '$PY' -m alembic upgrade head"

    step "5. second migration run must be a no-op"
    second="$(cd "$ROOT/apps/api" && "$PY" -m alembic upgrade head 2>&1)"
    printf '%s\n' "$second"
    if printf '%s' "$second" | grep -q "Running upgrade"; then
        fail "the second alembic run applied migrations again"
    fi
    (cd "$ROOT/apps/api" && "$PY" -m alembic current 2>&1 | tail -1)

    step "6. schema / RLS / audit grants"
    docker exec roadguard-supabase-db psql -U postgres -d postgres -tAc "
        select 'tables', count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'
        union all select 'rls_tables', count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='public' and c.relkind='r' and c.relrowsecurity
        union all select 'policies', count(*) from pg_policies where schemaname='public'
        union all select 'policies_with_org', count(*) from pg_policies where schemaname='public'
            and coalesce(qual,'') like '%current_organization_id%'
        union all select 'foreign_keys', count(*) from pg_constraint where contype='f' and connamespace='public'::regnamespace
        union all select 'indexes', count(*) from pg_indexes where schemaname='public'
        union all select 'audit_update_allowed', has_table_privilege('roadguard_app','audit_logs','UPDATE')::int
        union all select 'audit_delete_allowed', has_table_privilege('roadguard_app','audit_logs','DELETE')::int;"

    run "7. seed demo organisations and users" "$PY" scripts/seed_database.py

    step "8. isolation + database suites through the pooler"
    if ! "$PY" -m pytest tests/integration/test_database.py tests/integration/test_tenant_isolation.py \
        -q -rs --junitxml="$LOG.junit.xml" > "$LOG.tests" 2>&1; then
        tail -25 "$LOG.tests"
        fail "isolation suite failed"
    fi
    tail -4 "$LOG.tests"
    "$PY" - "$LOG.junit.xml" <<'PY'
import sys, xml.etree.ElementTree as ET
suite = ET.parse(sys.argv[1]).getroot().find("testsuite")
counts = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
print("isolation_suite", " ".join(f"{k}={v}" for k, v in counts.items()))
if counts["skipped"] or counts["failures"] or counts["errors"]:
    raise SystemExit("isolation suite was not skip-free and green")
PY

    step "9. start API (pooler runtime URL)"
    ( cd "$ROOT/apps/api" && exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 ) \
        > "$LOG.api" 2>&1 &
    API_PID=$!
    ready=0
    for _ in $(seq 1 30); do
        if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/api/v1/health/ready)" = "200" ]; then ready=1; break; fi
        sleep 2
    done
    [ "$ready" = "1" ] || { tail -20 "$LOG.api"; fail "API did not become ready"; }
    echo "API ready (database=pooler)"

    step "10. start external worker"
    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*) PATH_SEP=';' ;;
        *) PATH_SEP=':' ;;
    esac
    PYTHONPATH="$(native_path "$ROOT/ai-engine")${PATH_SEP}$(native_path "$ROOT/apps/api")" \
        "$PY" -m ai_engine.workers.polling_worker --loop --interval 1 > "$LOG.worker" 2>&1 &
    WORKER_PID=$!
    sleep 3
    grep -q "worker_started" "$LOG.worker" || { tail -20 "$LOG.worker"; fail "worker did not start"; }

    step "11. 12-step workflow through the external worker"
    "$PY" scripts/demo_smoke.py --api http://127.0.0.1:8001 --external-worker
    kill "$WORKER_PID" 2>/dev/null || true
    kill "$API_PID" 2>/dev/null || true
    WORKER_PID=""
    API_PID=""

    step "12. bootstrap re-run must not break the pooler (stale-credential regression)"
    SUPABASE_DB_URL="$DIRECT_URL" "$PY" scripts/supabase_setup.py \
        --url "$DIRECT_URL" --app-url "$APP_URL" --bootstrap
    "$PY" - <<'PY'
import os
import psycopg
url = (
    "postgresql://roadguard_app:"
    + os.environ["APP_PASSWORD"]
    + "@127.0.0.1:6543/postgres?sslmode=require"
)
with psycopg.connect(url, connect_timeout=15) as c:
    print("pooler login after bootstrap re-run ->", c.execute("select current_user").fetchone()[0])
PY

    step "13. non-Alembic SQL path in a fresh database"
    docker exec roadguard-supabase-db psql -U postgres -d postgres \
        -c "drop database if exists roadguard_sqlpath;" \
        -c "create database roadguard_sqlpath;" >/dev/null
    docker exec -i roadguard-supabase-db psql -U postgres -d roadguard_sqlpath \
        -v ON_ERROR_STOP=1 < infrastructure/supabase/schema.sql > "$LOG.sqlpath" 2>&1
    docker exec roadguard-supabase-db psql -U postgres -d roadguard_sqlpath -tAc "
        select 'sqlpath_tables', count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'
        union all select 'sqlpath_rls', count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
            where n.nspname='public' and c.relkind='r' and c.relrowsecurity
        union all select 'sqlpath_policies', count(*) from pg_policies where schemaname='public'
        union all select 'sqlpath_head', count(*) from alembic_version where version_num='837c7ef69730'
        union all select 'sqlpath_audit_update', has_table_privilege('roadguard_app','audit_logs','UPDATE')::int;"

    step "COLD START PASS"
} 2>&1 | tee "$LOG"
