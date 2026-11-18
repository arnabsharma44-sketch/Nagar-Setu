"""Infrastructure and camera registry models."""

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
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models._types import enum_column
from app.models.enums import (
    AssetType,
    CameraConnectionStatus,
    CameraSourceType,
    ConditionStatus,
    LocationQuality,
)


class Contractor(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "contractors"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_contractors_id_organization_id"),
        UniqueConstraint(
            "organization_id", "registration_number", name="uq_contractors_org_registration_number"
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    source_reference: Mapped[str | None] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Asset(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_assets_id_organization_id"),
        UniqueConstraint("organization_id", "asset_code", name="uq_assets_org_asset_code"),
        ForeignKeyConstraint(
            ["department_id", "organization_id"],
            ["departments.id", "departments.organization_id"],
            name="fk_assets_department_tenant",
        ),
        Index("ix_assets_location_gist", "location", postgresql_using="gist"),
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="longitude_range"
        ),
    )

    department_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    asset_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(enum_column(AssetType), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_quality: Mapped[LocationQuality] = mapped_column(
        enum_column(LocationQuality), nullable=False, default=LocationQuality.UNKNOWN
    )
    condition_status: Mapped[ConditionStatus] = mapped_column(
        enum_column(ConditionStatus), nullable=False, default=ConditionStatus.UNKNOWN
    )
    source_reference: Mapped[str | None] = mapped_column(String(255))
    last_inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Contract(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_contracts_id_organization_id"),
        UniqueConstraint("organization_id", "contract_number", name="uq_contracts_org_contract_number"),
        ForeignKeyConstraint(
            ["contractor_id", "organization_id"],
            ["contractors.id", "contractors.organization_id"],
            name="fk_contracts_contractor_tenant",
        ),
        ForeignKeyConstraint(
            ["department_id", "organization_id"],
            ["departments.id", "departments.organization_id"],
            name="fk_contracts_department_tenant",
        ),
    )

    contractor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    department_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    contract_number: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_description: Mapped[str] = mapped_column(String(2000), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    warranty_end_date: Mapped[date | None] = mapped_column(Date)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ContractAsset(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Join table: a contract may cover many assets (and vice versa)."""

    __tablename__ = "contract_assets"
    __table_args__ = (
        UniqueConstraint("contract_id", "asset_id", name="uq_contract_assets_contract_id_asset_id"),
        ForeignKeyConstraint(
            ["contract_id", "organization_id"],
            ["contracts.id", "contracts.organization_id"],
            name="fk_contract_assets_contract_tenant",
        ),
        ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["assets.id", "assets.organization_id"],
            name="fk_contract_assets_asset_tenant",
        ),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    scope_notes: Mapped[str | None] = mapped_column(String(1000))


class Camera(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_cameras_id_organization_id"),
        UniqueConstraint("organization_id", "camera_code", name="uq_cameras_org_camera_code"),
        Index("ix_cameras_location_gist", "location", postgresql_using="gist"),
        CheckConstraint("latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)", name="longitude_range"
        ),
    )

    camera_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[object | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_quality: Mapped[LocationQuality] = mapped_column(
        enum_column(LocationQuality), nullable=False, default=LocationQuality.UNKNOWN
    )
    source_type: Mapped[CameraSourceType] = mapped_column(
        enum_column(CameraSourceType), nullable=False
    )
    # Reference into the server-side secret store. The RTSP URL and credentials
    # are never persisted in a user-readable column and never returned by the API.
    secret_reference: Mapped[str | None] = mapped_column(String(255))
    connection_status: Mapped[CameraConnectionStatus] = mapped_column(
        enum_column(CameraConnectionStatus), nullable=False, default=CameraConnectionStatus.UNKNOWN
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
