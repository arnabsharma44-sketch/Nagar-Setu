# ROADGUARD AI

AI-assisted road-safety review and government corrective-action tracking prototype.

Two interfaces, one application:

- **Command Center** (dark) — cameras, footage, processing jobs, tracking evidence, candidate
  events and human review, hotspot map, investigations.
- **Administrative Portal** (light) — departments, contractors, assets, contracts, case register,
  corrective work orders, verification, analytics, audit trail, users and roles.

The demonstrable end-to-end flow is:

```
sign in → upload footage → background AI processing → tracking → candidate event
→ human review → hotspot → investigation → asset/department/contract lookup
→ recommendation (independent approval) → work order → completion evidence
→ independent verification → audit history
```

> **Responsible-AI notice.** AI output is a *candidate observation*. Nothing in this prototype
> declares an accident, fault, negligence or liability. Physical speed is never derived from
> uncalibrated pixels. Historical accident records are kept separate from AI events. All seeded
> data is synthetic and labelled `DEMO`.

Full status and evidence: [`docs/IMPLEMENTATION_STATE.md`](docs/IMPLEMENTATION_STATE.md),
limitations: [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).
Product specifications live in [`DOCUMENTATIONS/`](DOCUMENTATIONS).

---

## Stack

| Layer | Technology |
| --- | --- |
| Web | Next.js 16 (App Router) + TypeScript + Tailwind CSS 4 + Leaflet |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic |
| Database | PostgreSQL 16 + PostGIS 3.4 (two roles: owner + RLS-constrained app role) |
| Jobs | Celery + Redis, plus an in-repo polling worker for environments without a broker |
| Media | OpenCV + FFmpeg, private object storage (local backend or S3/MinIO) |
| AI | Detector adapter (`synthetic_scene` default, YOLO adapter present), IoU tracker (ByteTrack adapter present), versioned event rules |
| Infra | Docker Compose |

## Quickstart (verified on Windows 11, Python 3.13, Node 26)

```bash
# 1. Python environment
python -m venv .venv
.venv/Scripts/pip install -r apps/api/requirements.txt -r ai-engine/requirements.txt -r requirements-dev.txt

# 2. Configuration
cp .env.example .env      # then set SECRET_KEY, POSTGRES_*, S3_* if using MinIO
#    A development .env is already present in this workspace.

# 3. Data services
docker compose up -d postgres redis minio minio-init

# 4. Schema + demo data (two organizations, one isolation tenant)
.venv/Scripts/python -m alembic -c apps/api/alembic.ini upgrade head
.venv/Scripts/python scripts/seed_database.py

# 5. Demo footage (synthetic clip, generated locally — no external download)
.venv/Scripts/python scripts/generate_demo_clip.py

# 6. API  (http://127.0.0.1:8000/docs)
cd apps/api && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 7. Worker (separate terminal) — claims jobs from PostgreSQL
.venv/Scripts/python -m ai_engine.workers.polling_worker --loop
#    or, with Redis running: JOB_RUNNER=celery python -m ai_engine.workers.celery_app worker --pool=solo

# 8. Web  (http://localhost:3000)
cd apps/web && npm install && npm run dev
```

Sign in at `http://localhost:3000/login`.

### Demo accounts

Password is `DEMO_SEED_PASSWORD` (default `RoadguardDemo#2026`).

| Email | Role | Useful for |
| --- | --- | --- |
| `ops@demo.roadguard.ai` | police_admin | upload, process, review, analyze, investigate |
| `reviewer@demo.roadguard.ai` | reviewer | independent approval and verification |
| `engineer@demo.roadguard.ai` | department_engineer | accepting and completing a work order |
| `admin@demo.roadguard.ai` | org_admin | user and registry administration |
| `auditor@demo.roadguard.ai` | auditor | read-only audit trail |
| `ops@isolation.roadguard.ai` | police_admin | second tenant, used by isolation tests |

## Demo script

1. Sign in as `ops@…` → **Command Center**.
2. **Videos & Jobs** → upload `datasets/sample_videos/demo_intersection_synthetic.mp4` →
   the API returns a signed upload URL, the browser PUTs straight to private storage, a job is
   queued (never processed inside the request).
3. Worker claims the job, validates media, tracks road users and writes a candidate
   `near_miss_candidate` with an annotated frame and an event clip.
4. **Events** → open the candidate → review the evidence → **Confirm observation**.
5. **Hotspots** → run an analysis (DBSCAN over located records) → map + cluster table.
6. **Investigations** → open a case from the event → see asset, department and contract match
   with each contract's validity period → **Draft analysis** (deterministic engine).
7. Draft a **recommendation**; approve it as `reviewer@…` (self-approval is rejected).
8. Create a **work order** for the owning department → `engineer@…` accepts → completes with
   evidence → `reviewer@…` verifies (the completing user cannot verify).
9. **Audit trail** shows every consequential action; `auditor@…` can read but not write.

## Verification commands

```bash
.venv/Scripts/python -m pytest                       # 61 tests
.venv/Scripts/python -m ruff check apps/api ai-engine scripts tests
.venv/Scripts/python scripts/demo_smoke.py           # 12-step HTTP workflow
cd apps/web && npx tsc --noEmit && npm run build
```

## Repository layout

```
apps/api/          FastAPI app, models, services, routers, Alembic migrations
apps/web/          Next.js Command Center + Administrative Portal
ai-engine/         detector, tracker, event rules, video/evidence, pipeline, workers
infrastructure/    Dockerfiles, Postgres init script
shared/schemas/    Cross-service contracts (realtime event envelope)
scripts/           demo clip generator, idempotent seed, HTTP workflow smoke test
tests/             unit + integration suites (pytest)
DOCUMENTATIONS/    product, technical, security and acceptance specifications
docs/              implementation state, changelog, limitations, decisions
datasets/          generated sample footage and the DEMO accident CSV
```

## Security posture (summary)

- Cookie sessions: short-lived JWT access cookie + rotating refresh cookie (hash stored server-side),
  double-submit CSRF header for state-changing requests.
- Every query is scoped to the authenticated organization; PostgreSQL RLS is enabled for the
  unprivileged application role, with composite tenant foreign keys.
- Object storage is private; the browser only receives short-lived signed URLs.
- Audit log is append-only: `UPDATE`/`DELETE` are revoked from the app role and blocked by trigger.
- Cross-tenant reads by direct UUID return `404` (see `tests/integration/test_api_security.py`).

Details and residual risks: [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).
