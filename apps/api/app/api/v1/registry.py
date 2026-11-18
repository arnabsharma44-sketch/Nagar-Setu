"""Departments, contractors, assets and contracts."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.api.deps import CurrentContext, RequestContext
from app.core.errors import NotFound
from app.models import Asset, Contract, Contractor, Department
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    AssetCreate,
    AssetOut,
    AssetUpdate,
    ContractCreate,
    ContractorCreate,
    ContractorOut,
    ContractOut,
    DepartmentCreate,
    DepartmentOut,
    NearbyAsset,
    ResponsibilityResponse,
)
from app.schemas.serializers import (
    asset_out,
    contract_out,
    contractor_out,
    department_out,
)
from app.services import registry as registry_service
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

router = APIRouter(tags=["registry"])


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #


@router.get("/departments", response_model=Envelope[list[DepartmentOut]])
def list_departments(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[DepartmentOut]]:
    ctx.require("department:read")
    total = int(ctx.session.execute(select(func.count()).select_from(Department)).scalar_one())
    rows = ctx.session.execute(
        select(Department).order_by(Department.name).limit(limit).offset(offset)
    ).scalars()
    return ok([department_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.post("/departments", response_model=Envelope[DepartmentOut], status_code=201)
def create_department(
    payload: DepartmentCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[DepartmentOut]:
    ctx.require("department:manage")
    department = registry_service.create_department(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        name=payload.name,
        department_type=payload.department_type,
        contact_email=payload.contact_email,
        description=payload.description,
        source_reference=payload.source_reference,
        request_id=ctx.request_id,
    )
    return ok(department_out(department), request)


@router.get("/departments/{department_id}", response_model=Envelope[DepartmentOut])
def get_department(
    department_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[DepartmentOut]:
    ctx.require("department:read")
    department = ctx.session.get(Department, department_id)
    if department is None:
        raise NotFound("Department not found.")
    return ok(department_out(department), request)


# --------------------------------------------------------------------------- #
# Contractors
# --------------------------------------------------------------------------- #


@router.get("/contractors", response_model=Envelope[list[ContractorOut]])
def list_contractors(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[ContractorOut]]:
    ctx.require("contractor:read")
    total = int(ctx.session.execute(select(func.count()).select_from(Contractor)).scalar_one())
    rows = ctx.session.execute(
        select(Contractor).order_by(Contractor.name).limit(limit).offset(offset)
    ).scalars()
    return ok([contractor_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.post("/contractors", response_model=Envelope[ContractorOut], status_code=201)
def create_contractor(
    payload: ContractorCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[ContractorOut]:
    ctx.require("contractor:manage")
    contractor = registry_service.create_contractor(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        name=payload.name,
        registration_number=payload.registration_number,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        source_reference=payload.source_reference,
        request_id=ctx.request_id,
    )
    return ok(contractor_out(contractor), request)


@router.get("/contractors/{contractor_id}", response_model=Envelope[ContractorOut])
def get_contractor(
    contractor_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[ContractorOut]:
    ctx.require("contractor:read")
    contractor = ctx.session.get(Contractor, contractor_id)
    if contractor is None:
        raise NotFound("Contractor not found.")
    return ok(contractor_out(contractor), request)


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


@router.get("/assets", response_model=Envelope[list[AssetOut]])
def list_assets(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[AssetOut]]:
    ctx.require("asset:read")
    total = int(ctx.session.execute(select(func.count()).select_from(Asset)).scalar_one())
    rows = ctx.session.execute(
        select(Asset).order_by(Asset.asset_code).limit(limit).offset(offset)
    ).scalars()
    return ok([asset_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.post("/assets", response_model=Envelope[AssetOut], status_code=201)
def create_asset(
    payload: AssetCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[AssetOut]:
    ctx.require("asset:manage")
    asset = registry_service.create_asset(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        payload=payload,
        request_id=ctx.request_id,
    )
    return ok(asset_out(asset), request)


@router.get("/assets/nearby", response_model=Envelope[list[NearbyAsset]])
def assets_nearby(
    request: Request,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_meters: float = Query(default=250, ge=10, le=5000),
    limit: int = Query(default=10, ge=1, le=50),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[NearbyAsset]]:
    ctx.require("asset:read")
    rows = registry_service.nearby_assets(
        ctx.session,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        limit=limit,
    )
    return ok(rows, request)


@router.get("/assets/{asset_id}", response_model=Envelope[AssetOut])
def get_asset(
    asset_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[AssetOut]:
    ctx.require("asset:read")
    asset = ctx.session.get(Asset, asset_id)
    if asset is None:
        raise NotFound("Asset not found.")
    return ok(asset_out(asset), request)


@router.patch("/assets/{asset_id}", response_model=Envelope[AssetOut])
def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[AssetOut]:
    ctx.require("asset:manage")
    asset = registry_service.update_asset(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        asset_id=asset_id,
        payload=payload,
        request_id=ctx.request_id,
    )
    return ok(asset_out(asset), request)


@router.get("/assets/{asset_id}/responsibility", response_model=Envelope[ResponsibilityResponse])
def asset_responsibility(
    asset_id: uuid.UUID,
    request: Request,
    event_date: datetime | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[ResponsibilityResponse]:
    ctx.require("asset:read")
    ctx.require("contract:read")
    payload = registry_service.responsibility_for_asset(
        ctx.session, asset_id, event_date.date() if event_date else None
    )
    return ok(payload, request)


# --------------------------------------------------------------------------- #
# Contracts
# --------------------------------------------------------------------------- #


@router.get("/contracts", response_model=Envelope[list[ContractOut]])
def list_contracts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[ContractOut]]:
    ctx.require("contract:read")
    total = int(ctx.session.execute(select(func.count()).select_from(Contract)).scalar_one())
    rows = list(
        ctx.session.execute(
            select(Contract).order_by(Contract.contract_number).limit(limit).offset(offset)
        ).scalars()
    )
    asset_map = registry_service.contract_asset_ids(ctx.session, [row.id for row in rows])
    contractor_ids = {row.contractor_id for row in rows}
    department_ids = {row.department_id for row in rows}
    contractors = {
        row.id: row.name
        for row in ctx.session.execute(
            select(Contractor).where(Contractor.id.in_(contractor_ids))
        ).scalars()
    }
    departments = {
        row.id: row.name
        for row in ctx.session.execute(
            select(Department).where(Department.id.in_(department_ids))
        ).scalars()
    }
    payload = [
        contract_out(
            row,
            contractor_name=contractors.get(row.contractor_id),
            department_name=departments.get(row.department_id),
            asset_ids=asset_map.get(row.id, []),
        )
        for row in rows
    ]
    return ok(payload, request, pagination=paginate(limit, offset, total))


@router.post("/contracts", response_model=Envelope[ContractOut], status_code=201)
def create_contract(
    payload: ContractCreate, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[ContractOut]:
    ctx.require("contract:manage")
    contract = registry_service.create_contract(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        payload=payload,
        request_id=ctx.request_id,
    )
    asset_map = registry_service.contract_asset_ids(ctx.session, [contract.id])
    return ok(contract_out(contract, asset_ids=asset_map.get(contract.id, [])), request)


@router.get("/contracts/{contract_id}", response_model=Envelope[ContractOut])
def get_contract(
    contract_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[ContractOut]:
    ctx.require("contract:read")
    contract = ctx.session.get(Contract, contract_id)
    if contract is None:
        raise NotFound("Contract not found.")
    asset_map = registry_service.contract_asset_ids(ctx.session, [contract.id])
    contractor = ctx.session.get(Contractor, contract.contractor_id)
    department = ctx.session.get(Department, contract.department_id)
    return ok(
        contract_out(
            contract,
            contractor_name=contractor.name if contractor else None,
            department_name=department.name if department else None,
            asset_ids=asset_map.get(contract.id, []),
        ),
        request,
    )
