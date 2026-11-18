"""Candidate/confirmed incidents and imported historical accident records."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
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
    AccidentVerificationStatus,
    CameraSourceType,
    IncidentSourceKind,
    IncidentType,
    LocationQuality,
    ReviewStatus,
    Severity,
)


class Incident(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """A candidate or reviewed road-safety event.

    ``source_kind`` keeps AI candidates separate from manual observations. A
    reviewed incident is never promoted to a "historical accident record".
    """

    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_incidents_id_organization_id"),
        ForeignKeyConstraint(
            ["camera_id", "organization_id"],
            ["cameras.id", "cameras.organization_id"],
            name="fk_incidents_camera_tenant",
        ),
        ForeignKeyConstraint(
            ["video_id", "organization_id"],
            ["videos.id", "videos.organization_id"],
            name="fk_incidents_video_tenant",
        ),
        ForeignKeyConstraint(
            ["ai_job_id", "organization_id"],
            ["ai_jobs.id", "ai_jobs.organization_id"],
            name="fk_incidents_ai_job_tenant",
        ),
        ForeignKeyConstraint(
            ["reviewed_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_incidents_reviewed_by_tenant",
        ),
        Index("ix_incidents_org_event_time", "organization_id", text("event_time DESC")),
        Index("ix_incidents_org_review_status", "organization_id", "review_status"),
        Index("ix_incidents_location_gist", "location", postgresql_using="gist"),
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="longitude_range"
        ),
    )

    camera_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    video_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    incident_type: Mapped[IncidentType] = mapped_column(enum_column(IncidentType), nullable=False)
    source_kind: Mapped[IncidentSourceKind] = mapped_column(
        enum_column(IncidentSourceKind), nullable=False
    )
    severity: Mapped[Severity | None] = mapped_column(enum_column(Severity))
    model_score: Mapped[float | None] = mapped_column(Float)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_offset_seconds: Mapped[float | None] = mapped_column(Float)
    end_offset_seconds: Mapped[float | None] = mapped_column(Float)
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_quality: Mapped[LocationQuality] = mapped_column(
        enum_column(LocationQuality), nullable=False, default=LocationQuality.UNKNOWN
    )
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus), nullable=False, default=ReviewStatus.PENDING
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(String(2000))
    model_name: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str | None] = mapped_column(String(64))
    rule_name: Mapped[str | None] = mapped_column(String(80))
    rule_version: Mapped[str | None] = mapped_column(String(64))
    track_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    reason_codes: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    limitations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class AccidentRecord(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Imported historical accident record with provenance.

    Deliberately a separate table from ``incidents`` so that historical accident
    counts and AI candidate counts can never be silently merged.
    """

    __tablename__ = "accident_records"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_accident_records_id_organization_id"),
        Index("ix_accident_records_org_accident_time", "organization_id", "accident_time"),
        Index("ix_accident_records_location_gist", "location", postgresql_using="gist"),
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="longitude_range"
        ),
    )

    external_reference: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_quality: Mapped[LocationQuality] = mapped_column(
        enum_column(LocationQuality), nullable=False, default=LocationQuality.UNKNOWN
    )
    accident_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accident_date: Mapped[date | None] = mapped_column(Date)
    accident_type: Mapped[str | None] = mapped_column(String(80))
    severity: Mapped[str | None] = mapped_column(String(40))
    road_name: Mapped[str | None] = mapped_column(String(200))
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_status: Mapped[AccidentVerificationStatus] = mapped_column(
        enum_column(AccidentVerificationStatus),
        nullable=False,
        default=AccidentVerificationStatus.UNVERIFIED,
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    camera_source_type: Mapped[CameraSourceType | None] = mapped_column(
        enum_column(CameraSourceType)
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
