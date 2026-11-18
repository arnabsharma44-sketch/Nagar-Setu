"""Video, processing-job, detection, evidence and live-session models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._types import enum_column
from app.models.enums import (
    EvidenceType,
    JobStage,
    JobStatus,
    LiveSessionStatus,
    VideoSourceType,
    VideoStatus,
)


class Video(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_videos_id_organization_id"),
        ForeignKeyConstraint(
            ["camera_id", "organization_id"],
            ["cameras.id", "cameras.organization_id"],
            name="fk_videos_camera_tenant",
        ),
        ForeignKeyConstraint(
            ["uploaded_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_videos_uploaded_by_tenant",
        ),
        Index("ix_videos_org_created_at", "organization_id", text("created_at DESC")),
    )

    camera_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[VideoSourceType] = mapped_column(enum_column(VideoSourceType), nullable=False)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    frame_rate: Mapped[float | None] = mapped_column(Float)
    status: Mapped[VideoStatus] = mapped_column(
        enum_column(VideoStatus), nullable=False, default=VideoStatus.PENDING_UPLOAD
    )
    validation_error: Mapped[str | None] = mapped_column(String(500))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AIJob(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_ai_jobs_id_organization_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_ai_jobs_org_idempotency_key"),
        ForeignKeyConstraint(
            ["video_id", "organization_id"],
            ["videos.id", "videos.organization_id"],
            name="fk_ai_jobs_video_tenant",
        ),
        Index("ix_ai_jobs_org_status_created", "organization_id", "status", text("created_at DESC")),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, default="video_analysis")
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus), nullable=False, default=JobStatus.QUEUED
    )
    stage: Mapped[JobStage] = mapped_column(
        enum_column(JobStage), nullable=False, default=JobStage.QUEUED
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str | None] = mapped_column(String(64))
    weights_sha256: Mapped[str | None] = mapped_column(String(64))
    event_rules_version: Mapped[str | None] = mapped_column(String(64))
    config_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result_summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message_safe: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))


class Detection(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """Per-sampled-frame detection used for audit and evidence rendering."""

    __tablename__ = "detections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["ai_jobs.id", "ai_jobs.organization_id"],
            name="fk_detections_job_tenant",
        ),
        Index("ix_detections_job_id_frame_number", "job_id", "frame_number"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    class_label: Mapped[str] = mapped_column(String(40), nullable=False)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox: Mapped[list] = mapped_column(JSONB, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    track_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Evidence(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Evidence metadata. Bytes live in private object storage only."""

    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_evidence_id_organization_id"),
        ForeignKeyConstraint(
            ["incident_id", "organization_id"],
            ["incidents.id", "incidents.organization_id"],
            name="fk_evidence_incident_tenant",
        ),
        ForeignKeyConstraint(
            ["investigation_id", "organization_id"],
            ["investigations.id", "investigations.organization_id"],
            name="fk_evidence_investigation_tenant",
        ),
        ForeignKeyConstraint(
            ["work_order_id", "organization_id"],
            ["work_orders.id", "work_orders.organization_id"],
            name="fk_evidence_work_order_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_evidence_created_by_tenant",
        ),
    )

    incident_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(enum_column(EvidenceType), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp_in_video: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LiveStreamSession(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Server-side live/simulated live session state (never exposes stream secrets)."""

    __tablename__ = "live_stream_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["camera_id", "organization_id"],
            ["cameras.id", "cameras.organization_id"],
            name="fk_live_stream_sessions_camera_tenant",
        ),
        Index("ix_live_stream_sessions_camera_status", "camera_id", "status"),
    )

    camera_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[LiveSessionStatus] = mapped_column(
        enum_column(LiveSessionStatus), nullable=False, default=LiveSessionStatus.STOPPED
    )
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[str | None] = mapped_column(String(500))
