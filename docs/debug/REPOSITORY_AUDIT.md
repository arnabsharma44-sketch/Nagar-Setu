# ROADGUARD AI — Repository Audit Report

**Date:** 2026-11-18
**Branch:** fix/full-system-debug-audit (from main)
**Commit:** 36cd719 (HEAD)

---

## 1. Repository Structure Overview

```
Nagar-Setu/
├── ai-engine/                    # AI/ML pipeline
│   ├── ai_engine/
│   │   ├── detection/           # Object detection (YOLO + synthetic)
│   │   ├── events/              # Event detection rules
│   │   ├── investigation/       # Root-cause analysis
│   │   ├── tracking/            # Multi-object tracking
│   │   ├── video/               # Video decoding, evidence, RTSP
│   │   └── workers/             # Celery + polling workers
│   └── requirements.txt
├── apps/
│   ├── api/                     # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/         # REST endpoints
│   │   │   ├── core/           # Config, security, errors
│   │   │   ├── db/             # Database session, base
│   │   │   ├── middleware/     # HTTP middleware
│   │   │   ├── models/         # SQLAlchemy models
---

## 3. Code Quality Baseline

### Backend (Python)
- **Ruff**: All checks pass
- **Pytest**: 61 tests pass (38 unit + 23 integration)
- **Type hints**: Comprehensive throughout
- **Dependencies**: Pinned in requirements.txt
- **Alembic**: 3 migrations applied, head at `837c7ef69730`

### Frontend (TypeScript/Next.js)
- **TypeScript**: Clean compile (`tsc --noEmit`)
- **Next.js Build**: Success (21 routes)
- **Dependencies**: Locked in package-lock.json

### Linting Issues Fixed (Recent)
- Import sorting (I001)
- Optional type syntax (UP045, UP035)
- Exception chaining (B904)
---

## 4. Database Schema

### Migrations Applied
1. `a0f8b507499d` - Initial schema (25 tables)
2. `b1c2d3e4f5a6` - Security layer (RLS, audit triggers, job claim function)
3. `837c7ef69730` - Coordinate columns for map serialization

### Tables (25 total)
| Table | Tenant-Scoped | Key Features |
|-------|--------------|--------------|
| organizations | No (root) | slug unique, is_demo |
| users | Yes | composite FK to departments, RLS |
| departments | Yes | normalized_name unique |
| contractors | Yes | registration_number unique |
| assets | Yes | PostGIS geography, asset_code unique |
| contracts | Yes | date ranges, warranty |
| contract_assets | Yes | many-to-many |
| cameras | Yes | secret_reference, source_type |
| videos | Yes | storage_key, checksum |
| ai_jobs | Yes | idempotency_key, lease mechanism |
| detections | Yes | frame-level detail |
| evidence | Yes | polymorphic associations |
| incidents | Yes | review_status, source_kind |
| accident_records | Yes | separate from incidents |
| investigations | Yes | facts/hypotheses JSONB |
| recommendations | Yes | approval workflow |
| work_orders | Yes | status transitions enforced |
| work_order_status_history | Yes | audit trail |
| verifications | Yes | separation of duties |
| audit_logs | Yes | append-only, RLS |
| hotspot_analyses | Yes | methodology stored |
| live_stream_sessions | Yes | simulated vs real |
| refresh_sessions | Yes | token hashes only |

### RLS Policies
- All tenant tables have `tenant_isolation` policy
- Uses `app.current_organization_id` transaction-local setting
- `organizations` table also protected
- `audit_logs` append-only via trigger + revoked UPDATE/DELETE
- Quote removal from forward refs (UP037)
│   │   │   ├── schemas/        # Pydantic schemas
│   │   │   └── services/       # Business logic
│   │   ├── alembic/            # Migrations
│   │   └── requirements.txt
│   └── web/                     # Next.js frontend
│       ├── app/                # App Router pages
│       ├── components/         # Shared components
│       └── lib/                # API client, utilities
---

## 5. API Surface

### Endpoints (68 documented paths under `/api/v1`)
| Module | Endpoints |
|--------|-----------|
| auth | login, refresh, logout, me, csrf, change-password |
| cameras | CRUD, enable/disable, health, live/simulate |
| videos | upload-url, complete-upload, process, playback-url |
| jobs | list, get, retry |
| incidents | list, get, review, manual, evidence, analytics |
| accident_records | list, get, import CSV |
| investigations | CRUD, analyze, assign, recommendations |
| work_orders | CRUD, completion, evidence, verification |
| hotspots | analyze, list, geojson |
| registry | departments, contractors, assets, contracts, responsibility |
| audit | audit-logs, users |
| realtime | ticket, WebSocket |
| health | live, ready, bootstrap, permissions |

### Response Format
- Consistent envelope: `{ data: T, meta: { request_id, pagination } }`
- Error envelope: `{ error: { code, message, details }, meta: { request_id } }`
- Pagination: cursor/offset with limit (max 100)

---

## 6. Authentication & Authorization

### Authentication Flow
- Argon2id password hashing
- JWT access tokens (15 min) in HttpOnly cookie
- Rotating refresh tokens (7 days) stored as SHA-256 hashes
- CSRF double-submit cookie pattern
- Login rate limiting (sliding window)

### Roles & Permissions
| Role | Key Permissions |
|------|----------------|
| platform_admin | All permissions including system:admin |
| org_admin | Organization admin, user management |
| police_admin | Camera/video/incident management |
| reviewer | incident:review, work_order:verify |
| department_engineer | work_order:complete, asset management |
| auditor | audit:read, incident:read (read-only) |

### Authorization Enforcement
- Every endpoint checks `ctx.require(permission)`
- Tenant context from JWT `org` claim
---

## 7. Video Processing Pipeline

### Upload Flow
1. POST `/videos/upload-url` → signed URL
2. Client PUT to MinIO
3. POST `/videos/{id}/complete-upload` → verify
4. POST `/videos/{id}/process` → enqueue job

### Processing (Celery + Polling)
- Worker claims job via `claim_ai_job()` SQL function (SECURITY DEFINER)
- Decode → Sample → Detect → Track → Event Rules → Evidence
- Job status: queued → running → succeeded/failed
- Progress updates via WebSocket events

### Detection Backends
- **synthetic_scene** (default): Color marker detection for demo clips
- **yolo**: Ultralytics YOLO (optional, requires weights)

### Tracking
- IoU-based tracker (deterministic, class-consistent)
- ByteTrack adapter (optional)

### Event Rules (6)
1. near_miss_v1
2. collision_v1
3. pedestrian_conflict_v1
4. rapid_motion_v1
5. wrong_way_v1
6. signal_violation_v1

---

## 8. Frontend Routes (21)

### Command Center (Dark)
- `/command` - Overview dashboard
- `/command/cameras` - Camera registry
- `/command/monitoring` - Live/simulated feed
- `/command/videos` - Upload & jobs
- `/command/incidents` - Event review queue
- `/command/incidents/[id]` - Incident detail + evidence
- `/command/hotspots` - Map + clustering
- `/command/investigations` - Case list
- `/command/investigations/[id]` - Investigation detail

### Admin Portal (Light)
- `/admin` - Overview
- `/admin/departments` - Department registry
- `/admin/contractors` - Contractor registry
- `/admin/assets` - Asset registry
- `/admin/contracts` - Contract registry
- `/admin/investigations` - Case review
- `/admin/investigations/[id]` - Case detail
- `/admin/work-orders` - Work order list
- `/admin/work-orders/[id]` - Work order detail + verification
- `/admin/analytics` - Hotspot map + stats
- `/admin/audit-logs` - Audit trail
- `/admin/users` - User management

### Shared Components
- AppShell with sidebar navigation
- DataTable, MetricCard, StatusBadge, MapPanel
- EvidenceGrid for frame/video evidence
- Form components with validation
- Loading, Empty, Error, Permission states

---

## 9. Test Coverage

### Unit Tests (38 tests, 8 files)
| File | Tests | Coverage |
|------|-------|----------|
| test_event_rules.py | 5 | Event rules, registry |
| test_media_validation.py | 8 | Upload validation |
| test_permissions_and_transitions.py | 12 | RBAC, state machine |
| test_rate_limit.py | 3 | Sliding window |
| test_tracker.py | 10 | IoU tracker |

### Integration Tests (23 tests, 2 files)
| File | Tests | Coverage |
|------|-------|----------|
| test_api_security.py | 19 | Auth, RBAC, CSRF, tenant isolation |
| test_audit_immutability.py | 3 | DB-level audit protection |

### Test Commands
```bash
pytest tests/unit -v
pytest tests/integration -v
pytest tests/ -v
```

---

## 10. Known Issues / Technical Debt

### Critical (P0/P1)
1. **No production deployment configs** - Docker Compose only, no K8s/ECS
---

## 11. Security Findings (Preliminary)

### Strengths
- ✅ Argon2id password hashing
- ✅ JWT in HttpOnly cookies
- ✅ CSRF double-submit protection
- ✅ JWT rotation + refresh token hashing
- ✅ RLS on all tenant tables
- ✅ Composite FKs for tenant isolation
- ✅ Audit trail append-only (DB enforced)
- ✅ Secret references (no raw RTSP creds)
- ✅ Signed URLs for object access
- ✅ Rate limiting on login

### Areas for Review
- ⚠️ In-process rate limiter (single-instance only)
- ⚠️ No WAF/rate limiting on API endpoints
- ⚠️ No CSP headers configured
- ⚠️ No security headers middleware visible
- ⚠️ No secret scanning in CI
- ⚠️ No dependency vulnerability scanning

---

## 12. Action Items for Deep Audit

### Phase 0 Complete ✅
- [x] Repository structure documented
- [x] Baseline tests passing (61/61)
- [x] Linting clean
- [x] TypeScript clean
- [x] Next.js build success
- [x] Debug branch created

### Next Phases (To Execute)
- [ ] Phase 1: Frontend Bug Audit
- [ ] Phase 2: Backend/API Bug Audit
- [ ] Phase 3: Database/Data Integrity Audit
- [ ] Phase 4: Auth/Security Audit
- [ ] Phase 5: Video/Processing Audit
- [ ] Phase 6: AI/CV Audit
- [ ] Phase 7: GIS/Hotspot Audit
- [ ] Phase 8: Investigation/Responsibility Audit
- [ ] Phase 9: Work Orders/Verification Audit
- [ ] Phase 10: WebSocket/Realtime Audit
- [ ] Phase 11: Docker/Infrastructure Audit
- [ ] Phase 12: Performance/Reliability Audit
- [ ] Phase 13: Full E2E Regression Testing

---

## 13. Commands Executed (Baseline)

```bash
# Git
git status
git log --oneline -5
git checkout -b fix/full-system-debug-audit

# Backend Tests
python -m pytest tests/unit -v --tb=short      # 38 passed
python -m pytest tests/integration -v --tb=short # 23 passed
python -m pytest tests/ -v --tb=short           # 61 passed

# Linting
python -m ruff check apps/api ai-engine scripts tests --fix  # All clean

# Frontend
cd apps/web && npx tsc --noEmit                 # Clean
cd apps/web && npx next build                   # Success (21 routes)

# Docker
docker compose build                            # 3 images built
docker compose up -d                            # 7 services healthy
python scripts/demo_smoke.py --external-worker  # 12/12 PASSED
```
2. **No CI/CD pipeline** - Manual testing only
3. **RTSP adapter is stub** - No real camera integration
4. **YOLO adapter untested** - Requires GPU + weights
6. **LLM adapter optional** - Falls back to deterministic engine

### Medium (P2)
7. **No Playwright/E2E tests** - Only API integration tests
8. **No load testing** - Performance baselines unknown
9. **No dependency vulnerability scanning** - Not in CI
10. **Starlette deprecation warnings** - HTTP_422, HTTP_413
11. **In-process rate limiter** - Won't work multi-replica

### Low (P3)
12. **No structured logging aggregation** - Console only
13. **No distributed tracing** - Request IDs only
14. **In-process WebSocket hub** - Needs Redis Pub/Sub for scaling
14. **Turbopack filesystem settling notice** - Dev server cosmetic
15. **Missing API versioning strategy** - Only v1 prefix
- Database RLS as defense-in-depth
- No client-supplied org_id trusted
├── infrastructure/
│   ├── docker/                 # Dockerfiles
│   └── postgres/               # Postgres init
├── scripts/                    # Seed, demo, generate clip
├── shared/
│   └── schemas/               # Shared JSON schemas
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 2. Environment Configuration

### .env.example Analysis
- All required variables documented
- Clear placeholders for secrets
- Development defaults provided
- No actual secrets committed

### Docker Compose
- Services: postgres, redis, minio, minio-init, api, worker, web
- Health checks configured
- Proper dependency ordering
- Volume persistence for postgres and minio

### Missing Config
- No production docker-compose override
- No Kubernetes manifests
- No CI/CD pipeline configuration