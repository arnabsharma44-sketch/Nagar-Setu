"""Investigation, recommendation, work-order, verification, audit, hotspot models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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
    InvestigationStatus,
    Priority,
    RecommendationStatus,
    ResponsibilityStatus,
    VerificationStatus,
    WorkOrderStatus,
)


class Investigation(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "investigations"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_investigations_id_organization_id"),
        UniqueConstraint("organization_id", "case_number", name="uq_investigations_org_case_number"),
        ForeignKeyConstraint(
            ["incident_id", "organization_id"],
            ["incidents.id", "incidents.organization_id"],
            name="fk_investigations_incident_tenant",
        ),
        ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["assets.id", "assets.organization_id"],
            name="fk_investigations_asset_tenant",
        ),
        ForeignKeyConstraint(
            ["assigned_department_id", "organization_id"],
            ["departments.id", "departments.organization_id"],
            name="fk_investigations_department_tenant",
        ),
        ForeignKeyConstraint(
            ["assigned_to", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_investigations_assigned_to_tenant",
        ),
        ForeignKeyConstraint(
            ["opened_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_investigations_opened_by_tenant",
        ),
        Index("ix_investigations_org_status", "organization_id", "status"),
    )

    case_number: Mapped[str] = mapped_column(String(40), nullable=False)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    assigned_department_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(2000))
    # Observed facts, AI hypotheses and open questions are always separate fields.
    observed_facts: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    hypotheses: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    missing_information: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[InvestigationStatus] = mapped_column(
        enum_column(InvestigationStatus), nullable=False, default=InvestigationStatus.OPEN
    )
    responsibility_status: Mapped[ResponsibilityStatus | None] = mapped_column(
        enum_column(ResponsibilityStatus)
    )
    analysis_source: Mapped[str | None] = mapped_column(String(40))
    analysis_model: Mapped[str | None] = mapped_column(String(120))
    analysis_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Recommendation(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_recommendations_id_organization_id"),
        ForeignKeyConstraint(
            ["investigation_id", "organization_id"],
            ["investigations.id", "investigations.organization_id"],
            name="fk_recommendations_investigation_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_recommendations_created_by_tenant",
        ),
        ForeignKeyConstraint(
            ["reviewed_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_recommendations_reviewed_by_tenant",
        ),
        Index("ix_recommendations_org_status", "organization_id", "status"),
    )

    investigation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    recommendation_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    rationale: Mapped[str] = mapped_column(String(2000), nullable=False)
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        enum_column(RecommendationStatus), nullable=False, default=RecommendationStatus.DRAFT
    )
    model_name: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str | None] = mapped_column(String(64))
    input_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    limitations: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(String(2000))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkOrder(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_work_orders_id_organization_id"),
        UniqueConstraint("organization_id", "work_order_number", name="uq_work_orders_org_number"),
        ForeignKeyConstraint(
            ["investigation_id", "organization_id"],
            ["investigations.id", "investigations.organization_id"],
            name="fk_work_orders_investigation_tenant",
        ),
        ForeignKeyConstraint(
            ["recommendation_id", "organization_id"],
            ["recommendations.id", "recommendations.organization_id"],
            name="fk_work_orders_recommendation_tenant",
        ),
        ForeignKeyConstraint(
            ["assigned_department_id", "organization_id"],
            ["departments.id", "departments.organization_id"],
            name="fk_work_orders_department_tenant",
        ),
        ForeignKeyConstraint(
            ["assigned_to", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_work_orders_assigned_to_tenant",
        ),
        ForeignKeyConstraint(
            ["created_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_work_orders_created_by_tenant",
        ),
        Index("ix_work_orders_org_status_due", "organization_id", "status", "due_date"),
    )

    work_order_number: Mapped[str] = mapped_column(String(40), nullable=False)
    investigation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    assigned_department_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[WorkOrderStatus] = mapped_column(
        enum_column(WorkOrderStatus), nullable=False, default=WorkOrderStatus.PENDING
    )
    priority: Mapped[Priority] = mapped_column(enum_column(Priority), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(String(4000))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkOrderStatusHistory(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "work_order_status_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_order_id", "organization_id"],
            ["work_orders.id", "work_orders.organization_id"],
            name="fk_work_order_status_history_work_order_tenant",
        ),
        ForeignKeyConstraint(
            ["changed_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_work_order_status_history_changed_by_tenant",
        ),
        Index("ix_work_order_status_history_org_created", "organization_id", "created_at"),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    from_status: Mapped[WorkOrderStatus | None] = mapped_column(enum_column(WorkOrderStatus))
    to_status: Mapped[WorkOrderStatus] = mapped_column(enum_column(WorkOrderStatus), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Verification(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "verifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["work_order_id", "organization_id"],
            ["work_orders.id", "work_orders.organization_id"],
            name="fk_verifications_work_order_tenant",
        ),
        ForeignKeyConstraint(
            ["verified_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_verifications_verified_by_tenant",
        ),
        Index("ix_verifications_org_created", "organization_id", "created_at"),
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    verified_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus), nullable=False
    )
    notes: Mapped[str] = mapped_column(String(2000), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class AuditLog(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    """Append-only audit trail. UPDATE and DELETE are denied at the database."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_audit_logs_actor_tenant",
        ),
        Index("ix_audit_logs_org_created_at", "organization_id", text("created_at DESC")),
        Index("ix_audit_logs_org_entity", "organization_id", "entity_type", "entity_id"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    actor_label: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    request_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class HotspotAnalysis(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Stored hotspot calculation with its methodology and parameters."""

    __tablename__ = "hotspot_analyses"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_hotspot_analyses_id_organization_id"),
        Index("ix_hotspot_analyses_org_created", "organization_id", text("created_at DESC")),
    )

    method: Mapped[str] = mapped_column(String(80), nullable=False)
    radius_meters: Mapped[float] = mapped_column(nullable=False)  # type: ignore[assignment]
    window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_size: Mapped[int] = mapped_column(nullable=False, default=2)  # type: ignore[assignment]
    parameters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    results: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
