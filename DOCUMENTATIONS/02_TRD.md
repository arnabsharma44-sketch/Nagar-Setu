# Technical Requirements Document (TRD)

**Product:** ROADGUARD AI  
**Version:** 1.0  
**Status:** Prototype baseline  
**Date:** 18 November 2026

## 1. Technical objectives

Build a modular web application that separates user experience, business APIs, asynchronous video processing, data persistence and AI inference. The design must run locally with Docker Compose and support a future deployment to secured infrastructure without rewriting core business logic.

## 2. Reference stack

Use currently supported, mutually compatible stable releases and pin exact versions in package lockfiles, Python dependency lockfiles and container image tags. Do not blindly copy “latest” version numbers into the codebase.

| Layer | Technology | Responsibility |
|---|---|---|
| Web | Next.js App Router + TypeScript | Command Center and Admin Portal |
| UI | Tailwind CSS + shadcn/ui or equivalent accessible primitives | Design system and components |
| Maps | Leaflet + approved tile provider/OpenStreetMap-compatible tiles | Map and hotspot layers |
| API | Python FastAPI + Pydantic | REST, validation, auth and workflow |
| ORM | SQLAlchemy | Persistence and query layer |
| Migrations | Alembic | Version-controlled schema changes |
| Database | PostgreSQL + PostGIS | Relational and geospatial records |
| Queue | Celery + Redis | Asynchronous AI jobs |
| Object storage | MinIO locally; S3-compatible interface | Video, clips, images and reports |
| Video | FFmpeg + OpenCV | Decode, metadata and frame extraction |
| Detection | Ultralytics-compatible YOLO adapter | Road-user detection |
| Tracking | ByteTrack-compatible adapter | Track IDs across frames |
| Analytics | NumPy, Pandas, scikit-learn, GeoPandas as needed | Aggregation and clustering |
| Realtime | FastAPI WebSockets + Redis Pub/Sub | Organization-scoped updates |
| Testing | Pytest, HTTPX, Playwright, ESLint/TypeScript checks | Automated verification |
| Runtime | Docker Compose | Reproducible development environment |

Do not add Kafka, Kubernetes, microservice mesh, vector database or multiple LLM frameworks to the hackathon MVP unless a demonstrated requirement justifies it.

## 3. Repository layout

```text
roadguard-ai/
├── apps/
│   ├── web/                    # Next.js application
│   └── api/                    # FastAPI application
├── ai-engine/
│   ├── ingestion/              # video intake and metadata
│   ├── detection/              # model adapters
│   ├── tracking/               # tracker adapters
│   ├── events/                 # versioned event rules
│   ├── hotspot/                # spatial/temporal analysis
│   ├── investigation/          # rule engine and LLM adapter
│   └── workers/                # Celery tasks
├── shared/
│   ├── schemas/                # language-neutral JSON schemas
│   └── event-contracts/        # websocket/domain event definitions
├── infrastructure/
│   ├── docker/
│   └── postgres/
├── scripts/                    # seed/import/admin scripts
├── tests/
│   ├── integration/
│   └── e2e/
├── docs/                       # this documentation pack
├── docker-compose.yml
├── .env.example
└── README.md
```

## 4. Runtime services and boundaries

### 4.1 Web application

- Renders `/command/**` and `/admin/**` experiences.
- Calls FastAPI only; it must not connect directly to PostgreSQL, Redis or MinIO credentials.
- Uses a shared typed API client and server-side route protection as a usability layer.
- Backend remains the final authority for permissions.

### 4.2 API application

- Owns authentication, authorization, business validation and database transactions.
- Exposes versioned REST endpoints under `/api/v1`.
- Creates video records and processing jobs but does not run long video inference inside HTTP requests.
- Generates short-lived private object-storage upload/download URLs where appropriate.
- Publishes domain events after successful commits.

### 4.3 AI worker

- Pulls jobs from Celery/Redis.
- Reads source video from private object storage using a server-side credential.
- Executes FFmpeg/OpenCV, detection, tracking and event rules.
- Writes output via a controlled service/repository interface or a narrowly scoped database service identity.
- Stores annotated images and short evidence clips in private object storage.
- Updates processing progress and final state.
- Uses job idempotency and retry limits.

### 4.4 RTSP adapter

- Disabled by default unless `LIVE_CCTV_ENABLED=true` and an authorized camera has valid secret configuration.
- Runs server-side in a restricted network environment.
- Does not expose RTSP URLs, usernames or passwords to the browser.
- Uses an allowlist of approved camera hosts/network ranges; do not accept arbitrary client-provided URLs.
- Has connection timeout, reconnect policy, health status and resource limits.
- For the hackathon, a prerecorded clip may power a “simulated live” preview, clearly labelled as simulated.

### 4.5 Data stores

- PostgreSQL is the source of truth for application records.
- PostGIS stores geographic points and supports proximity queries.
- MinIO stores file objects; PostgreSQL stores metadata and opaque storage keys.
- Redis stores queue state, ephemeral cache and Pub/Sub messages. Do not treat Redis as the durable source of business records.

## 5. Core technical requirements

### TR-01 — Configuration

- Read configuration from environment variables using a typed settings class.
- Validate required secrets at startup.
- Provide `.env.example` with placeholders only.
- Never commit `.env`, real credentials, CCTV URLs or tokens.

### TR-02 — API conventions

- Prefix endpoints with `/api/v1`.
- Use UUIDs for public record identifiers.
- Use ISO-8601 timestamps with timezone offsets; persist timestamps as `TIMESTAMPTZ` in UTC.
- Return consistent error objects.
- Paginate collection endpoints.
- Validate inputs and outputs with Pydantic schemas.
- Generate OpenAPI from FastAPI and keep it consistent with this document.

### TR-03 — Database

- Use SQLAlchemy models and Alembic migrations.
- Enable `pgcrypto` and `postgis` extensions.
- Add indexes for tenant filters, status/time queries and spatial queries.
- Add tenant-aware composite foreign keys or equivalent database constraints for organization-owned relationships.
- Use Row-Level Security (RLS) as defence in depth, with transaction-scoped organization context. Never rely on RLS alone if the connection pool context can leak between requests.

### TR-04 — Background jobs

- Job statuses: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
- Progress is integer 0–100 and is informational, not a promise of exact remaining time.
- Retry transient failures with bounded exponential backoff.
- Do not retry invalid input, unsupported codecs or authorization failures automatically.
- Store a sanitized error code/message for the user and detailed diagnostics in protected logs.
- Prevent duplicate processing using a unique idempotency key derived from video/version/config.

### TR-05 — Video processing

- Inspect media with FFprobe/FFmpeg before expensive processing.
- Enforce allowlisted extensions and verify file signatures/container parsing; extension alone is not validation.
- Enforce configured maximum upload bytes, duration, resolution and frame rate.
- Process frames at a configurable sampling rate; retain original timestamp offsets.
- Handle variable frame rate and missing metadata gracefully.
- Do not assume every codec is supported.
- Do not store full frames/detections indefinitely unless required by the retention policy.

### TR-06 — Detection and event rules

- Wrap model and tracker behind interfaces so a model can be changed without rewriting event logic.
- Record model name/version, weights identifier/hash, class map and confidence threshold for each job.
- Record event-rule version and parameters for every event.
- Event outputs must carry source video, time range, object track IDs where available, supporting measurements and known limitations.
- Treat model confidence as model-specific score, not calibrated probability of an actual accident.

### TR-07 — Geospatial processing

- Store longitude/latitude as WGS84 geography points (`SRID 4326`).
- Validate latitude and longitude ranges.
- Use PostGIS for proximity and spatial aggregation.
- Do not calculate physical speed or time-to-collision from raw pixel coordinates without camera calibration and road-plane mapping.
- Display approximate/unknown coordinates distinctly from surveyed coordinates.

### TR-08 — Realtime

- REST endpoints remain authoritative; WebSocket messages are hints for UI refresh.
- Authenticate WebSocket connections and derive organization identity from the session.
- Authorize subscriptions to organization-scoped channels only.
- Do not trust an organization ID sent in a WebSocket query parameter.
- Reconnect with backoff and refresh state using REST after reconnect.

### TR-09 — Observability

- Use structured logs with request ID, job ID and actor ID where appropriate.
- Never log passwords, tokens, signed URLs, RTSP credentials or raw sensitive video content.
- Capture API errors, job failures, worker restarts and stream disconnects.
- Provide a health endpoint that does not leak secret configuration.

## 6. Suggested local ports

| Service | Port |
|---|---:|
| Next.js | 3000 |
| FastAPI | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MinIO API | 9000 |
| MinIO Console | 9001 |

Ports may be mapped differently in developer environments. In container-to-container traffic use service DNS names, not `localhost`.

## 7. Performance targets for prototype

These are engineering targets to measure, not production SLAs:

- Dashboard API list endpoints: p95 under 1 second on seeded demo dataset, excluding external tile/network latency.
- Upload API: create upload session quickly; transfer large file directly to object storage rather than proxying through the API where supported.
- UI must remain responsive while processing runs.
- A worker must process the sample clip within the time demonstrated on the team's target hardware; publish measured throughput in the demo notes.
- Database list APIs must be paginated and tenant-filtered.

## 8. Dependency and licence management

- Pin dependencies and container image tags.
- Record model weights source, model licence and checksum.
- Review video datasets and sample footage usage rights.
- Avoid using scraped or unauthorized surveillance footage.
- Generate an SBOM or dependency inventory if time permits.

## 9. Build and run commands

The repository README must document the tested commands. Expected workflow:

```bash
cp .env.example .env
# Fill strong local-only secrets in .env

docker compose up --build -d
# Run migrations and seed data using documented service commands
# Open web UI at http://localhost:3000
# Open API docs at http://localhost:8000/docs
```

Do not claim commands work until they have been run and verified in the repository.
