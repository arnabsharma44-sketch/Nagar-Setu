"""Departments, contractors, assets, contracts and deterministic responsibility matching.

Responsibility matching is rule-based. It returns the recorded relationships that
*indicate a potentially relevant authority*; it never concludes fault, breach or
legal liability.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.core.audit import record_audit
from app.core.errors import Conflict, NotFound
from app.models import (
    Asset,
    Contract,
    ContractAsset,
    Contractor,
    Department,
    ResponsibilityStatus,
)
from app.schemas.domain import (
    ContractMatch,
    NearbyAsset,
    ResponsibilityResponse,
)
from app.services.geo import set_point
from geoalchemy2 import Geography
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DISCLAIMER = (
    "These are recorded asset, department and contract relationships only. "
    "They indicate a potentially relevant authority and must be verified against "
    "scope and dates by an authorized person. No liability is determined."
)


def _normalized(name: str) -> str:
    return " ".join(name.strip().lower().split())


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #


def create_department(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    name: str,
    department_type: str,
    contact_email: str | None,
    description: str | None,
    source_reference: str | None,
    request_id: str | None,
) -> Department:
    existing = session.execute(
        select(Department).where(
            Department.organization_id == organization_id,
            Department.normalized_name == _normalized(name),
        )
    ).scalar_one_or_none()
    if existing:
        raise Conflict("A department with this name already exists.", code="DUPLICATE_DEPARTMENT")
    department = Department(
        organization_id=organization_id,
        name=name.strip(),
        normalized_name=_normalized(name),
        department_type=department_type,
        contact_email=contact_email,
        description=description,
        source_reference=source_reference,
    )
    session.add(department)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="department.created",
        entity_type="department",
        entity_id=department.id,
        request_id=request_id,
        summary=f"Department {department.name} created.",
    )
    return department


# --------------------------------------------------------------------------- #
# Contractors
# --------------------------------------------------------------------------- #


def create_contractor(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    name: str,
    registration_number: str,
    contact_email: str | None,
    contact_phone: str | None,
    source_reference: str | None,
    request_id: str | None,
) -> Contractor:
    existing = session.execute(
        select(Contractor).where(
            Contractor.organization_id == organization_id,
            Contractor.registration_number == registration_number,
        )
    ).scalar_one_or_none()
    if existing:
        raise Conflict("A contractor with this registration number exists.", code="DUPLICATE_CONTRACTOR")
    contractor = Contractor(
        organization_id=organization_id,
        name=name.strip(),
        registration_number=registration_number,
        contact_email=contact_email,
        contact_phone=contact_phone,
        source_reference=source_reference,
    )
    session.add(contractor)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="contractor.created",
        entity_type="contractor",
        entity_id=contractor.id,
        request_id=request_id,
        summary=f"Contractor {contractor.name} created.",
    )
    return contractor


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


def create_asset(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    payload: object,
    request_id: str | None,
) -> Asset:
    data = payload  # typed as AssetCreate by callers
    existing = session.execute(
        select(Asset).where(
            Asset.organization_id == organization_id, Asset.asset_code == data.asset_code
        )
    ).scalar_one_or_none()
    if existing:
        raise Conflict("An asset with this code already exists.", code="DUPLICATE_ASSET_CODE")
    if data.department_id is not None:
        _require_department(session, organization_id, data.department_id)

    asset = Asset(
        organization_id=organization_id,
        asset_code=data.asset_code.strip(),
        name=data.name.strip(),
        asset_type=data.asset_type,
        address=data.address,
        department_id=data.department_id,
        condition_status=data.condition_status,
        source_reference=data.source_reference,
    )
    if data.location is not None:
        set_point(asset, data.location.latitude, data.location.longitude, data.location.quality)
    session.add(asset)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="asset.created",
        entity_type="asset",
        entity_id=asset.id,
        request_id=request_id,
        summary=f"Asset {asset.asset_code} created.",
    )
    return asset


def update_asset(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    asset_id: uuid.UUID,
    payload: object,
    request_id: str | None,
) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise NotFound("Asset not found.")
    data = payload
    if data.department_id is not None:
        _require_department(session, organization_id, data.department_id)
    for field in ("name", "asset_type", "address", "condition_status", "source_reference"):
        value = getattr(data, field, None)
        if value is not None:
            setattr(asset, field, value)
    if data.department_id is not None:
        asset.department_id = data.department_id
    if data.location is not None:
        set_point(asset, data.location.latitude, data.location.longitude, data.location.quality)
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="asset.updated",
        entity_type="asset",
        entity_id=asset.id,
        request_id=request_id,
        summary=f"Asset {asset.asset_code} updated.",
    )
    return asset


def _require_department(session: Session, organization_id: uuid.UUID, department_id: uuid.UUID) -> Department:
    department = session.get(Department, department_id)
    if department is None or department.organization_id != organization_id:
        raise NotFound("Department not found.")
    return department


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


def create_contract(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_label: str,
    payload: object,
    request_id: str | None,
) -> Contract:
    data = payload
    contractor = session.get(Contractor, data.contractor_id)
    if contractor is None:
        raise NotFound("Contractor not found.")
    _require_department(session, organization_id, data.department_id)
    duplicate = session.execute(
        select(Contract).where(
            Contract.organization_id == organization_id,
            Contract.contract_number == data.contract_number,
        )
    ).scalar_one_or_none()
    if duplicate:
        raise Conflict("A contract with this number already exists.", code="DUPLICATE_CONTRACT")

    contract = Contract(
        organization_id=organization_id,
        contractor_id=data.contractor_id,
        department_id=data.department_id,
        contract_number=data.contract_number.strip(),
        contract_type=data.contract_type,
        scope_description=data.scope_description,
        start_date=data.start_date,
        end_date=data.end_date,
        warranty_end_date=data.warranty_end_date,
        source_reference=data.source_reference,
    )
    session.add(contract)
    session.flush()

    for asset_id in data.asset_ids:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise NotFound("One of the selected assets was not found.")
        session.add(
            ContractAsset(
                organization_id=organization_id,
                contract_id=contract.id,
                asset_id=asset.id,
                scope_notes=None,
            )
        )
    session.flush()
    record_audit(
        session,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action="contract.created",
        entity_type="contract",
        entity_id=contract.id,
        request_id=request_id,
        summary=f"Contract {contract.contract_number} created.",
    )
    return contract


def contract_asset_ids(session: Session, contract_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
    if not contract_ids:
        return {}
    rows = session.execute(
        select(ContractAsset.contract_id, ContractAsset.asset_id).where(
            ContractAsset.contract_id.in_(contract_ids)
        )
    ).all()
    grouped: dict[uuid.UUID, list[uuid.UUID]] = {cid: [] for cid in contract_ids}
    for contract_id, asset_id in rows:
        grouped.setdefault(contract_id, []).append(asset_id)
    return grouped


# --------------------------------------------------------------------------- #
# Spatial lookup
# --------------------------------------------------------------------------- #


def nearby_assets(
    session: Session, *, latitude: float, longitude: float, radius_meters: float, limit: int = 10
) -> list[NearbyAsset]:
    """Assets within a radius, ordered by geodesic distance in metres."""
    point = func.cast(
        func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography
    )
    distance = func.ST_Distance(Asset.location, point)
    stmt = (
        select(Asset, distance.label("distance_m"))
        .where(Asset.location.is_not(None))
        .where(func.ST_DWithin(Asset.location, point, radius_meters))
        .order_by(distance)
        .limit(limit)
    )
    results: list[NearbyAsset] = []
    for asset, distance_m in session.execute(stmt).all():
        results.append(
            NearbyAsset(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                name=asset.name,
                asset_type=asset.asset_type,
                distance_meters=float(distance_m or 0.0),
                department_id=asset.department_id,
                location=(
                    {
                        "latitude": asset.latitude,
                        "longitude": asset.longitude,
                        "quality": asset.location_quality,
                    }
                    if asset.latitude is not None and asset.longitude is not None
                    else None
                ),
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Responsibility matching
# --------------------------------------------------------------------------- #


def build_responsibility(
    session: Session,
    *,
    asset: Asset | None,
    event_date: date | None,
    distance_meters: float | None = None,
    match_method: str = "explicit_asset_selection",
) -> ResponsibilityResponse:
    if asset is None:
        return ResponsibilityResponse(
            status=ResponsibilityStatus.NO_ASSET_MATCH,
            asset_id=None,
            match_method=match_method,
            distance_meters=distance_meters,
            missing_records=["No infrastructure asset was matched to this location."],
            disclaimer=DISCLAIMER,
        )

    department = session.get(Department, asset.department_id) if asset.department_id else None
    contract_ids = [
        row[0]
        for row in session.execute(
            select(ContractAsset.contract_id).where(ContractAsset.asset_id == asset.id)
        ).all()
    ]
    contracts = (
        session.execute(select(Contract).where(Contract.id.in_(contract_ids))).scalars().all()
        if contract_ids
        else []
    )

    matches: list[ContractMatch] = []
    conflicts: list[str] = []
    missing: list[str] = []
    sources: list[str] = [asset.source_reference] if asset.source_reference else []

    for contract in contracts:
        contractor = session.get(Contractor, contract.contractor_id)
        active = bool(
            event_date and contract.start_date <= event_date <= contract.end_date
        )
        if event_date is None:
            date_note = "Event date unknown; contract validity cannot be confirmed."
        elif active:
            date_note = f"Contract records cover {contract.start_date} to {contract.end_date}."
        else:
            date_note = (
                f"Contract records cover {contract.start_date} to {contract.end_date}, "
                "which does not include the event date."
            )
        if contract.source_reference:
            sources.append(contract.source_reference)
        if department and contract.department_id != department.id:
            conflicts.append(
                f"Contract {contract.contract_number} is recorded to a different department "
                "than the asset's maintaining department."
            )
        matches.append(
            ContractMatch(
                contract_id=contract.id,
                contract_number=contract.contract_number,
                contract_type=contract.contract_type,
                contractor_id=contract.contractor_id,
                contractor_name=contractor.name if contractor else "Unknown contractor",
                scope_description=contract.scope_description,
                start_date=contract.start_date,
                end_date=contract.end_date,
                is_active_on_event_date=active,
                date_note=date_note,
                scope_notes=None,
                source_reference=contract.source_reference,
            )
        )

    if department is None:
        missing.append("The asset has no maintaining department recorded.")
    if not contracts:
        missing.append("No contract record is linked to this asset.")

    active_matches = [m for m in matches if m.is_active_on_event_date]
    if department is None:
        status = ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION
    elif not contracts:
        status = ResponsibilityStatus.MISSING_CONTRACT_DATA
    elif event_date is None or not active_matches:
        status = ResponsibilityStatus.REQUIRES_FIELD_VERIFICATION
    elif len(active_matches) > 1:
        status = ResponsibilityStatus.AMBIGUOUS_MATCH
    else:
        status = ResponsibilityStatus.MATCHED_RECORDS

    return ResponsibilityResponse(
        status=status,
        asset_id=asset.id,
        asset_code=asset.asset_code,
        asset_name=asset.name,
        match_method=match_method,
        distance_meters=distance_meters,
        owning_department_id=department.id if department else None,
        owning_department_name=department.name if department else None,
        contracts=matches,
        missing_records=missing,
        conflicts=conflicts,
        source_references=[s for s in sources if s],
        verification_required=True,
        disclaimer=DISCLAIMER,
    )


def responsibility_for_asset(
    session: Session, asset_id: uuid.UUID, event_date: date | None
) -> ResponsibilityResponse:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise NotFound("Asset not found.")
    return build_responsibility(session, asset=asset, event_date=event_date)


def now_utc() -> datetime:
    return datetime.now(UTC)
