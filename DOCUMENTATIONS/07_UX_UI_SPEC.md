# UX/UI Specification

**Version:** 1.0  
**Product surfaces:** Command Center (dark) and Administrative Portal (light)

## 1. UX principles

1. **Evidence before conclusions:** show source footage, timestamps and provenance before AI-generated interpretation.
2. **Clear distinction of certainty:** use “AI candidate”, “human reviewed”, “record match” and “verified” labels accurately.
3. **Operational clarity:** show status, owner, next action and last update on every workflow item.
4. **Progressive disclosure:** command center prioritizes monitoring; admin portal prioritizes management and workflow.
5. **Responsive and accessible:** desktop-first for control-room views, usable at laptop/tablet widths; keyboard navigation, focus states and sufficient contrast.
6. **Honest live-state labels:** distinguish connected live feed, disconnected feed, uploaded recording and simulated live replay.

## 2. Visual direction

### Command Center

- Dark charcoal/navy surfaces with restrained accent colours.
- Dense but readable status panels.
- Map and event feed as primary areas.
- Camera tiles with clear LIVE / RECORDING / SIMULATED / OFFLINE labels.
- Avoid flashing alarms and decorative gauges that imply unsupported precision.

### Administrative Portal

- Light neutral background, white/neutral cards and clear typography.
- Consistent tables, filters, forms, timelines and detail pages.
- Status badges use both colour and text; never rely on colour alone.
- Emphasize assignment, evidence, due date, history and next step.

## 3. Global navigation

### Command Center routes

| Route | Page content |
|---|---|
| `/command` | Operational overview, counters, map, event feed and job status |
| `/command/cameras` | Camera registry and connection health |
| `/command/cameras/[id]` | Camera detail, source mode, recent videos/events |
| `/command/monitoring` | Authorized live/simulated feeds and recent processing |
| `/command/videos` | Uploads, job status, playback and processing history |
| `/command/incidents` | Candidate/reviewed event queue |
| `/command/incidents/[id]` | Evidence player, event details and review decision |
| `/command/hotspots` | Geographic event/accident layers and methodology |
| `/command/investigations` | Case queue and case details |

### Admin routes

| Route | Page content |
|---|---|
| `/admin` | Work summary and unresolved actions |
| `/admin/departments` | Department directory and scope |
| `/admin/contractors` | Contractor registry |
| `/admin/assets` | Infrastructure asset register and map |
| `/admin/contracts` | Contract terms, dates and asset coverage |
| `/admin/investigations` | Assigned cases and findings |
| `/admin/work-orders` | Assignment, progress and due dates |
| `/admin/work-orders/[id]` | Status timeline, completion and verification |
| `/admin/analytics` | Department and resolution analytics |
| `/admin/audit-logs` | Filterable read-only activity trail |
| `/admin/users` | User/role administration (authorized admins only) |

## 4. Key screens and required components

### 4.1 Sign in

- Organization-aware sign-in context where applicable.
- Email and password fields.
- Loading, invalid credential, locked/rate-limited and network error states.
- No role selection by user as a way to elevate access.
- Password reset only if a secure reset flow is actually implemented; otherwise do not show a dead control.

### 4.2 Command overview

Widgets:

- Cameras: online/offline/unknown counts.
- Videos/jobs: queued/running/failed counts.
- Potential events by review state and type.
- Verified historical accident record count (separate from AI candidates).
- Hotspot/event concentration map with layer toggles.
- Recent event feed with timestamp, source, review status and evidence link.
- Worker/processing health.

Every card must use live API data or be explicitly labelled “demo sample”. No hardcoded numbers presented as actual city statistics.

### 4.3 Camera page

- Camera name/code and registered location.
- Source type: RTSP, upload association or demo replay.
- Connection health and last-seen time.
- Enable/disable action if authorized.
- Do not display secret URL/password.
- If replaying a file, display a persistent “SIMULATED LIVE” label.

### 4.4 Video upload and processing page

- Drag/drop and file picker.
- Allowed type/maximum size guidance from backend config.
- Optional camera association and recorded-at timestamp.
- Upload progress and processing progress as separate indicators.
- Job status, current stage and safe error message.
- Retry action only for retryable failed jobs.

### 4.5 Incident review page

- Evidence player or clip link with timestamp offsets.
- Annotated still frames.
- Event type and source (`AI candidate`, `manual observation`, `imported`).
- Model score (if relevant), not misleading “probability of accident”.
- Model/rule version and limitations.
- Supporting track IDs/features where relevant.
- Review actions: confirm, reject false positive, request more information.
- Reviewer identity/time and notes after decision.

### 4.6 Hotspot page

- Map with layer controls and legend.
- Separate layers for historical accident records, confirmed observations and pending AI candidates.
- Filters for date range, event category, review status and source.
- Cluster details include count, source mix, time window, method and generated timestamp.
- Unknown coordinates not silently plotted.
- Map is not a claim that location is legally an accident blackspot unless the underlying data/method qualifies.

### 4.7 Asset and responsibility page

- Asset code, type, map point, location quality and department.
- Contracts linked to asset, including contractor, scope and effective dates.
- Source/provenance for each record.
- Responsibility banner: “Records indicate a potentially relevant authority; verify scope and dates.”
- Conflict/missing-data warnings.

### 4.8 Investigation detail

Use explicit sections:

1. Observed facts
2. AI-generated hypotheses (unverified)
3. Historical records
4. Related asset/department/contract records
5. Missing information / inspection questions
6. Draft recommendations
7. Review/assignment history
8. Evidence and audit trail

### 4.9 Work order detail

- Action title, linked investigation and recommendation.
- Assigned department/user, priority and due date.
- Status timeline.
- Completion notes and evidence upload.
- Separate verifier action.
- Rejection/needs-more-evidence reason.

## 5. Common UI states

Every data-driven page must handle:

- Initial loading/skeleton.
- Empty state with a useful next action.
- Error state with retry.
- No permission state.
- Stale data/reconnecting state.
- Partial data/unknown location state.
- Demo data banner where applicable.

## 6. Design tokens and components

Define shared tokens for colour, spacing, typography, borders, radius, elevation and z-index. Use shared components:

- `AppShell`, `Sidebar`, `Topbar`, `PageHeader`
- `MetricCard`, `StatusBadge`, `DataTable`, `FilterBar`
- `MapPanel`, `CameraTile`, `VideoUploader`, `JobProgress`
- `EvidenceViewer`, `IncidentSummary`, `ReviewPanel`
- `InvestigationTimeline`, `RecommendationCard`
- `WorkOrderStatus`, `VerificationPanel`, `AuditTimeline`
- `ConfirmDialog`, `EmptyState`, `ErrorState`, `PermissionGuard`

Do not duplicate API logic or business rules in individual pages.

## 7. Interaction requirements

- Destructive actions require a confirmation dialog.
- Forms show validation messages near the relevant field.
- Save actions prevent duplicate submissions.
- Status transitions are driven by backend response, not optimistic assumptions for consequential actions.
- When WebSocket events arrive, update only the relevant item or invalidate/refetch the affected query.
- Every interactive control must perform a real action; do not ship inert buttons.

## 8. Accessibility and responsive behaviour

- Use semantic headings, labels, table headers and accessible names.
- Keyboard access for navigation, dialogs, map alternatives and forms.
- Visible focus ring.
- Charts must have text/summary alternatives.
- Avoid conveying status only through red/green colour.
- Provide a list/table equivalent for map-only information.
- On smaller screens, prioritize case details and list views over multi-camera grids.

## 9. Demo-data presentation

Show a global banner such as “DEMO ENVIRONMENT — synthetic records and sample footage”. Show local source badges on demo cameras, contracts, accident records and assets. Never imply seeded sample values are actual Bhubaneswar city statistics.
