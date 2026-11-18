"""Controlled vocabularies used across the API, database and AI worker."""

from __future__ import annotations

from enum import StrEnum


class OrganizationType(StrEnum):
    MUNICIPALITY = "municipality"
    POLICE = "police"
    ROAD_AUTHORITY = "road_authority"
    DEMO = "demo"


class CameraSourceType(StrEnum):
    UPLOAD_ASSOCIATION = "upload_association"
    RTSP = "rtsp"
    DEMO_REPLAY = "demo_replay"


class CameraConnectionStatus(StrEnum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    SIMULATED = "simulated"


class VideoSourceType(StrEnum):
    UPLOAD = "upload"
    RTSP_RECORDING = "rtsp_recording"
    DEMO_REPLAY = "demo_replay"


class VideoStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    VALIDATION_FAILED = "validation_failed"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(StrEnum):
    QUEUED = "queued"
    VALIDATING = "validating"
    DECODING = "decoding"
    DETECTING = "detecting"
    TRACKING = "tracking"
    CLASSIFYING = "classifying"
    EVIDENCE = "evidence"
    PERSISTING = "persisting"
    COMPLETED = "completed"


class IncidentSourceKind(StrEnum):
    AI_CANDIDATE = "ai_candidate"
    MANUAL_OBSERVATION = "manual_observation"
    IMPORTED = "imported"


class IncidentType(StrEnum):
    NEAR_MISS_CANDIDATE = "near_miss_candidate"
    COLLISION_CANDIDATE = "collision_candidate"
    WRONG_WAY_CANDIDATE = "wrong_way_candidate"
    RAPID_MOTION_CHANGE_CANDIDATE = "rapid_motion_change_candidate"
    PEDESTRIAN_VEHICLE_CONFLICT_CANDIDATE = "pedestrian_vehicle_conflict_candidate"
    SIGNAL_LINE_CROSSING_CANDIDATE = "signal_line_crossing_candidate"
    MANUAL_ROAD_HAZARD = "manual_road_hazard"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED_FALSE_POSITIVE = "rejected_false_positive"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class ReviewDecision(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED_FALSE_POSITIVE = "rejected_false_positive"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceType(StrEnum):
    ANNOTATED_FRAME = "annotated_frame"
    EVENT_CLIP = "event_clip"
    SOURCE_VIDEO = "source_video"
    COMPLETION_PHOTO = "completion_photo"
    COMPLETION_DOCUMENT = "completion_document"
    OTHER = "other"


class AssetType(StrEnum):
    ROAD_SEGMENT = "road_segment"
    INTERSECTION = "intersection"
    TRAFFIC_SIGNAL = "traffic_signal"
    STREET_LIGHT = "street_light"
    PEDESTRIAN_CROSSING = "pedestrian_crossing"
    ROAD_SIGN = "road_sign"
    DRAINAGE = "drainage"
    OTHER = "other"


class ConditionStatus(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class InvestigationStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    PENDING_FIELD_VERIFICATION = "pending_field_verification"
    CLOSED = "closed"


class RecommendationStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorkOrderStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED_PENDING_VERIFICATION = "completed_pending_verification"
    VERIFIED = "verified"
    REOPENED = "reopened"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class VerificationStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class AccidentVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"


class ResponsibilityStatus(StrEnum):
    MATCHED_RECORDS = "matched_records"
    AMBIGUOUS_MATCH = "ambiguous_match"
    NO_ASSET_MATCH = "no_asset_match"
    MISSING_CONTRACT_DATA = "missing_contract_data"
    REQUIRES_FIELD_VERIFICATION = "requires_field_verification"


class LocationQuality(StrEnum):
    SURVEYED = "surveyed"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class LiveSessionStatus(StrEnum):
    STOPPED = "stopped"
    SIMULATED = "simulated"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BLOCKED = "blocked"


WORK_ORDER_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.DRAFT: {WorkOrderStatus.PENDING, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.PENDING: {WorkOrderStatus.ASSIGNED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.ASSIGNED: {
        WorkOrderStatus.IN_PROGRESS,
        WorkOrderStatus.CANCELLED,
        WorkOrderStatus.REOPENED,
    },
    WorkOrderStatus.IN_PROGRESS: {
        WorkOrderStatus.COMPLETED_PENDING_VERIFICATION,
        WorkOrderStatus.CANCELLED,
    },
    WorkOrderStatus.COMPLETED_PENDING_VERIFICATION: {
        WorkOrderStatus.VERIFIED,
        WorkOrderStatus.REOPENED,
        WorkOrderStatus.REJECTED,
    },
    WorkOrderStatus.REOPENED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.VERIFIED: set(),
    WorkOrderStatus.REJECTED: {WorkOrderStatus.REOPENED},
    WorkOrderStatus.CANCELLED: set(),
}
