"""Domain request and response schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from app.models.enums import (
    AccidentVerificationStatus,
    AssetType,
    CameraConnectionStatus,
    CameraSourceType,
    ConditionStatus,
    EvidenceType,
    IncidentSourceKind,
    IncidentType,
    InvestigationStatus,
    JobStage,
    JobStatus,
    LocationQuality,
    Priority,
    RecommendationStatus,
    ResponsibilityStatus,
    ReviewDecision,
    ReviewStatus,
    Severity,
    VerificationStatus,
    VideoSourceType,
    VideoStatus,
    WorkOrderStatus,
)
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# --------------------------------------------------------------------------- #
# Shared value objects
# --------------------------------------------------------------------------- #


class GeoPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    quality: LocationQuality = LocationQuality.APPROXIMATE


class LocationOut(BaseModel):
    latitude: float
    longitude: float
    quality: LocationQuality


class DemoFlag(BaseModel):
    is_demo: bool = True


# --------------------------------------------------------------------------- #
# Auth and identity
# --------------------------------------------------------------------------- #


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    organization_slug: str | None = Field(default=None, max_length=80)


class OrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    organization_type: str
    city: str | None = None
    state: str | None = None
    is_demo: bool


class CurrentUser(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: str
    department_id: uuid.UUID | None = None
    permissions: list[str]
    organization: OrganizationSummary
    csrf_token: str | None = None


class SessionResponse(BaseModel):
    user: CurrentUser
    expires_in: int


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    role: str
    department_id: uuid.UUID | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    is_demo: bool


class UserCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    role: str
    department_id: uuid.UUID | None = None
    password: str = Field(min_length=12, max_length=256)


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: str | None = None
    department_id: uuid.UUID | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Departments, contractors, assets and contracts
# --------------------------------------------------------------------------- #


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    department_type: str = Field(min_length=2, max_length=80)
    contact_email: EmailStr | None = None
    description: str | None = Field(default=None, max_length=1000)
    source_reference: str | None = Field(default=None, max_length=255)


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    department_type: str
    contact_email: str | None
    description: str | None
    source_reference: str | None
    is_demo: bool
    created_at: datetime


class ContractorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    registration_number: str = Field(min_length=2, max_length=80)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    source_reference: str | None = Field(default=None, max_length=255)


class ContractorOut(BaseModel):
    id: uuid.UUID
    name: str
    registration_number: str
    contact_email: str | None
    contact_phone: str | None
    source_reference: str | None
    is_demo: bool
    created_at: datetime


class AssetCreate(BaseModel):
    asset_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    asset_type: AssetType
    address: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    location: GeoPoint | None = None
    condition_status: ConditionStatus = ConditionStatus.UNKNOWN
    source_reference: str | None = Field(default=None, max_length=255)


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    asset_type: AssetType | None = None
    address: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    location: GeoPoint | None = None
    condition_status: ConditionStatus | None = None
    source_reference: str | None = Field(default=None, max_length=255)


class AssetOut(BaseModel):
    id: uuid.UUID
    asset_code: str
    name: str
    asset_type: AssetType
    address: str | None
    department_id: uuid.UUID | None
    location: LocationOut | None
    condition_status: ConditionStatus
    source_reference: str | None
    last_inspected_at: datetime | None
    is_demo: bool
    created_at: datetime


class ContractCreate(BaseModel):
    contractor_id: uuid.UUID
    department_id: uuid.UUID
    contract_number: str = Field(min_length=2, max_length=80)
    contract_type: str = Field(min_length=2, max_length=80)
    scope_description: str = Field(min_length=2, max_length=2000)
    start_date: date
    end_date: date
    warranty_end_date: date | None = None
    asset_ids: list[uuid.UUID] = Field(default_factory=list)
    source_reference: str | None = Field(default=None, max_length=255)

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, value: date, info: Any) -> date:
        start = info.data.get("start_date")
        if start and value < start:
            raise ValueError("end_date must be on or after start_date")
        return value


class ContractOut(BaseModel):
    id: uuid.UUID
    contract_number: str
    contract_type: str
    contractor_id: uuid.UUID
    contractor_name: str | None = None
    department_id: uuid.UUID
    department_name: str | None = None
    scope_description: str
    start_date: date
    end_date: date
    warranty_end_date: date | None
    asset_ids: list[uuid.UUID] = Field(default_factory=list)
    source_reference: str | None
    is_demo: bool


class ContractMatch(BaseModel):
    contract_id: uuid.UUID
    contract_number: str
    contract_type: str
    contractor_id: uuid.UUID
    contractor_name: str
    scope_description: str
    start_date: date
    end_date: date
    is_active_on_event_date: bool
    date_note: str
    scope_notes: str | None = None
    source_reference: str | None = None


class ResponsibilityResponse(BaseModel):
    """Record match only. Never a legal or contractual finding."""

    status: ResponsibilityStatus
    asset_id: uuid.UUID | None
    asset_code: str | None = None
    asset_name: str | None = None
    match_method: str
    distance_meters: float | None = None
    owning_department_id: uuid.UUID | None = None
    owning_department_name: str | None = None
    contracts: list[ContractMatch] = Field(default_factory=list)
    missing_records: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    verification_required: bool = True
    disclaimer: str


class NearbyAsset(BaseModel):
    asset_id: uuid.UUID
    asset_code: str
    name: str
    asset_type: AssetType
    distance_meters: float
    department_id: uuid.UUID | None
    location: LocationOut | None


# --------------------------------------------------------------------------- #
# Cameras
# --------------------------------------------------------------------------- #


class CameraCreate(BaseModel):
    camera_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    source_type: CameraSourceType = CameraSourceType.UPLOAD_ASSOCIATION
    location: GeoPoint | None = None
    description: str | None = Field(default=None, max_length=1000)
    is_enabled: bool = True
    # A secret *reference* only. Raw stream URLs are never accepted from clients.
    secret_reference: str | None = Field(default=None, max_length=255)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    location: GeoPoint | None = None
    is_enabled: bool | None = None


class CameraOut(BaseModel):
    id: uuid.UUID
    camera_code: str
    name: str
    description: str | None
    source_type: CameraSourceType
    location: LocationOut | None
    connection_status: CameraConnectionStatus
    is_enabled: bool
    is_demo: bool
    has_secret_reference: bool
    last_seen_at: datetime | None
    created_at: datetime


class CameraHealthOut(BaseModel):
    camera_id: uuid.UUID
    connection_status: CameraConnectionStatus
    is_simulated: bool
    last_seen_at: datetime | None
    detail: str | None = None
    live_enabled: bool


# --------------------------------------------------------------------------- #
# Videos, jobs and evidence
# --------------------------------------------------------------------------- #


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    file_size_bytes: int = Field(gt=0)
    camera_id: uuid.UUID | None = None
    recorded_at: datetime | None = None
    source_type: VideoSourceType = VideoSourceType.UPLOAD


class UploadUrlResponse(BaseModel):
    video_id: uuid.UUID
    upload_url: str
    upload_method: Literal["PUT"] = "PUT"
    expires_at: datetime
    max_bytes: int


class VideoOut(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID | None
    original_filename: str
    content_type: str
    file_size_bytes: int
    checksum_sha256: str | None
    source_type: VideoSourceType
    status: VideoStatus
    recorded_at: datetime | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    frame_rate: float | None
    validation_error: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    is_demo: bool


class JobOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    status: JobStatus
    stage: JobStage
    progress: int
    attempts: int
    model_name: str | None
    model_version: str | None
    event_rules_version: str | None
    result_summary: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None
    error_message_safe: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    can_retry: bool = False


class ProcessVideoRequest(BaseModel):
    force_reprocess: bool = False


class StepUpRequest(BaseModel):
    """Explicit acknowledgement required for live camera operations."""

    confirm: bool = False


# --------------------------------------------------------------------------- #
# Incidents and evidence
# --------------------------------------------------------------------------- #


class IncidentOut(BaseModel):
    id: uuid.UUID
    incident_type: IncidentType
    source_kind: IncidentSourceKind
    severity: Severity | None
    model_score: float | None
    event_time: datetime
    start_offset_seconds: float | None
    end_offset_seconds: float | None
    location: LocationOut | None
    description: str
    review_status: ReviewStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    camera_id: uuid.UUID | None
    camera_code: str | None = None
    video_id: uuid.UUID | None
    ai_job_id: uuid.UUID | None
    model_name: str | None
    model_version: str | None
    rule_name: str | None
    rule_version: str | None
    track_ids: list[Any] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[Any] = Field(default_factory=list)
    limitations: list[Any] = Field(default_factory=list)
    is_demo: bool
    created_at: datetime


class IncidentReviewRequest(BaseModel):
    decision: ReviewDecision
    notes: str | None = Field(default=None, max_length=2000)


class ManualIncidentRequest(BaseModel):
    incident_type: IncidentType = IncidentType.MANUAL_ROAD_HAZARD
    description: str = Field(min_length=5, max_length=2000)
    event_time: datetime
    severity: Severity | None = None
    camera_id: uuid.UUID | None = None
    location: GeoPoint | None = None


class EvidenceOut(BaseModel):
    id: uuid.UUID
    evidence_type: EvidenceType
    label: str | None
    content_type: str
    original_filename: str | None
    file_size_bytes: int
    checksum_sha256: str
    timestamp_in_video: float | None
    incident_id: uuid.UUID | None
    investigation_id: uuid.UUID | None
    work_order_id: uuid.UUID | None
    created_at: datetime
    is_demo: bool


class EvidenceUrlOut(BaseModel):
    evidence_id: uuid.UUID
    url: str
    expires_in: int
    content_type: str


class PlaybackUrlOut(BaseModel):
    video_id: uuid.UUID
    url: str
    expires_in: int


# --------------------------------------------------------------------------- #
# Historical accidents and hotspots
# --------------------------------------------------------------------------- #


class AccidentRecordOut(BaseModel):
    id: uuid.UUID
    external_reference: str | None
    location: LocationOut | None
    accident_time: datetime | None
    accident_date: date | None
    accident_type: str | None
    severity: str | None
    road_name: str | None
    source_name: str
    source_reference: str
    verification_status: AccidentVerificationStatus
    import_batch_id: uuid.UUID | None
    is_demo: bool


class AccidentImportResult(BaseModel):
    import_batch_id: uuid.UUID
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    is_demo: bool


class HotspotAnalyzeRequest(BaseModel):
    radius_meters: float = Field(default=250, ge=25, le=5000)
    min_size: int = Field(default=2, ge=2, le=50)
    window_from: datetime | None = None
    window_to: datetime | None = None


class HotspotCluster(BaseModel):
    cluster_key: str
    latitude: float
    longitude: float
    radius_meters: float
    counts: dict[str, int]
    total_records: int
    source_mix: list[str]
    categories: dict[str, int]
    first_seen: datetime | None
    last_seen: datetime | None
    record_ids: list[uuid.UUID]
    label: str


class HotspotAnalysisOut(BaseModel):
    id: uuid.UUID
    method: str
    radius_meters: float
    min_size: int
    window_from: datetime | None
    window_to: datetime | None
    generated_at: datetime
    methodology_note: str
    data_sources: list[str]
    clusters: list[HotspotCluster]
    unlocated_count: int
    is_demo: bool


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
    properties: dict[str, Any]


# --------------------------------------------------------------------------- #
# Incidents analytics
# --------------------------------------------------------------------------- #


class IncidentAnalytics(BaseModel):
    window_from: datetime | None
    window_to: datetime | None
    total: int
    by_review_status: dict[str, int]
    by_type: dict[str, int]
    by_source_kind: dict[str, int]
    confirmed_observations: int
    pending_candidates: int
    historical_accidents_in_window: int
    data_note: str


# --------------------------------------------------------------------------- #
# Investigations and recommendations
# --------------------------------------------------------------------------- #


class InvestigationCreate(BaseModel):
    incident_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    title: str = Field(min_length=4, max_length=250)
    summary: str | None = Field(default=None, max_length=2000)
    assigned_department_id: uuid.UUID | None = None
    observed_facts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=250)
    summary: str | None = Field(default=None, max_length=2000)
    status: InvestigationStatus | None = None
    observed_facts: list[str] | None = None
    missing_information: list[str] | None = None


class InvestigationAssign(BaseModel):
    department_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=1000)


class Hypothesis(BaseModel):
    hypothesis: str
    supporting_record_ids: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    confidence_label: Literal["low", "medium", "high"]


class InvestigationAnalysis(BaseModel):
    investigation_id: uuid.UUID
    analysis_source: Literal["deterministic", "llm"]
    model_name: str | None
    generated_at: datetime
    observed_facts: list[str]
    potential_root_causes: list[Hypothesis]
    missing_information: list[str]
    potentially_relevant_authorities: list[str]
    recommended_actions: list[dict[str, Any]]
    limitations: list[str]
    human_verification_required: bool = True


class RecommendationCreate(BaseModel):
    recommendation_text: str = Field(min_length=5, max_length=2000)
    rationale: str = Field(min_length=5, max_length=2000)
    priority: Priority = Priority.MEDIUM
    limitations: list[str] = Field(default_factory=list)


class RecommendationReview(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: str | None = Field(default=None, max_length=2000)


class RecommendationOut(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    recommendation_text: str
    rationale: str
    priority: Priority
    status: RecommendationStatus
    model_name: str | None
    model_version: str | None
    limitations: list[Any] = Field(default_factory=list)
    created_by: uuid.UUID
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    is_demo: bool


class InvestigationOut(BaseModel):
    id: uuid.UUID
    case_number: str
    title: str
    summary: str | None
    incident_id: uuid.UUID | None
    asset_id: uuid.UUID | None
    assigned_department_id: uuid.UUID | None
    assigned_to: uuid.UUID | None
    status: InvestigationStatus
    responsibility_status: ResponsibilityStatus | None
    observed_facts: list[Any]
    hypotheses: list[Any]
    missing_information: list[Any]
    analysis_source: str | None
    analysis_model: str | None
    analysis_generated_at: datetime | None
    opened_by: uuid.UUID
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_demo: bool


# --------------------------------------------------------------------------- #
# Work orders
# --------------------------------------------------------------------------- #


class WorkOrderCreate(BaseModel):
    investigation_id: uuid.UUID
    recommendation_id: uuid.UUID | None = None
    assigned_department_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    title: str = Field(min_length=4, max_length=250)
    description: str = Field(min_length=5, max_length=4000)
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None


class WorkOrderUpdate(BaseModel):
    status: WorkOrderStatus | None = None
    assigned_to: uuid.UUID | None = None
    priority: Priority | None = None
    due_date: date | None = None
    title: str | None = Field(default=None, min_length=4, max_length=250)
    description: str | None = Field(default=None, min_length=5, max_length=4000)
    note: str | None = Field(default=None, max_length=2000)


class CompletionSubmit(BaseModel):
    completion_notes: str = Field(min_length=5, max_length=4000)
    evidence_ids: list[uuid.UUID] = Field(default_factory=list)


class VerificationSubmit(BaseModel):
    verification_status: VerificationStatus
    notes: str = Field(min_length=5, max_length=2000)


class StatusHistoryOut(BaseModel):
    id: uuid.UUID
    from_status: WorkOrderStatus | None
    to_status: WorkOrderStatus
    changed_by: uuid.UUID
    note: str | None
    created_at: datetime


class VerificationOut(BaseModel):
    id: uuid.UUID
    verified_by: uuid.UUID
    verification_status: VerificationStatus
    notes: str
    verified_at: datetime
    created_at: datetime


class WorkOrderOut(BaseModel):
    id: uuid.UUID
    work_order_number: str
    investigation_id: uuid.UUID
    recommendation_id: uuid.UUID | None
    assigned_department_id: uuid.UUID
    department_name: str | None = None
    assigned_to: uuid.UUID | None
    title: str
    description: str
    status: WorkOrderStatus
    priority: Priority
    due_date: date | None
    completed_at: datetime | None
    completion_notes: str | None
    completed_by: uuid.UUID | None
    verified_at: datetime | None
    verified_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    is_demo: bool
    allowed_transitions: list[WorkOrderStatus] = Field(default_factory=list)


class WorkOrderDetail(WorkOrderOut):
    history: list[StatusHistoryOut] = Field(default_factory=list)
    verifications: list[VerificationOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    separation_of_duties: bool = True
    can_submit_completion: bool = False
    can_verify: bool = False


# --------------------------------------------------------------------------- #
# Audit and meta
# --------------------------------------------------------------------------- #


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_label: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    request_id: str | None
    summary: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BootstrapMeta(BaseModel):
    environment: str
    demo_mode: bool
    permissions: list[str]
    roles: list[str]
    max_upload_bytes: int
    max_video_duration_seconds: int
    supported_content_types: list[str]
    live_cctv_enabled: bool
    llm_enabled: bool
    detector_backend: str
