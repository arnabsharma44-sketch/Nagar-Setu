"""Historical accident records, hotspot analysis and map layers."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from app.api.deps import CurrentContext, RequestContext
from app.core.audit import record_audit
from app.core.errors import NotFound, ValidationError
from app.models import AccidentRecord, AccidentVerificationStatus, HotspotAnalysis, LocationQuality
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    AccidentImportResult,
    AccidentRecordOut,
    FeatureCollection,
    HotspotAnalysisOut,
    HotspotAnalyzeRequest,
)
from app.schemas.serializers import accident_out
from app.services import analytics
from app.services.geo import set_point
from fastapi import APIRouter, File, Query, Request, UploadFile
from sqlalchemy import func, select

router = APIRouter(tags=["accidents"])


@router.get("/accident-records", response_model=Envelope[list[AccidentRecordOut]])
def list_accident_records(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[AccidentRecordOut]]:
    ctx.require("accident:read")
    total = int(ctx.session.execute(select(func.count()).select_from(AccidentRecord)).scalar_one())
    rows = ctx.session.execute(
        select(AccidentRecord)
        .order_by(AccidentRecord.accident_time.desc().nullslast())
        .limit(limit)
        .offset(offset)
    ).scalars()
    return ok([accident_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.post("/accident-records/import", response_model=Envelope[AccidentImportResult])
async def import_accident_records(
    request: Request,
    file: UploadFile = File(...),
    ctx: RequestContext = CurrentContext,
) -> Envelope[AccidentImportResult]:
    """Import historical records from CSV with provenance.

    Required columns: ``external_reference``, ``source_name``, ``source_reference``.
    Optional: ``latitude``, ``longitude``, ``accident_time``, ``accident_type``,
    ``severity``, ``road_name``, ``verification_status``.
    """
    ctx.require("accident:import")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise ValidationError("Upload a CSV file.", code="UNSUPPORTED_MEDIA_TYPE")

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationError("CSV import is limited to 5 MB.", code="FILE_TOO_LARGE")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV must be UTF-8 encoded.", code="INVALID_ENCODING") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {"external_reference", "source_name", "source_reference"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValidationError(
            "CSV is missing required columns.",
            code="MISSING_COLUMNS",
            details=[{"field": column, "reason": "required"} for column in sorted(missing)],
        )

    batch_id = uuid.uuid4()
    imported = 0
    skipped = 0
    errors: list[str] = []
    for line_number, row in enumerate(reader, start=2):
        try:
            source_name = (row.get("source_name") or "").strip()
            source_reference = (row.get("source_reference") or "").strip()
            external = (row.get("external_reference") or "").strip() or None
            if not source_name or not source_reference:
                skipped += 1
                errors.append(f"line {line_number}: source provenance required")
                continue
            existing = ctx.session.execute(
                select(AccidentRecord).where(
                    AccidentRecord.organization_id == ctx.organization_id,
                    AccidentRecord.source_reference == source_reference,
                    AccidentRecord.external_reference == external,
                )
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue

            record = AccidentRecord(
                organization_id=ctx.organization_id,
                external_reference=external,
                source_name=source_name,
                source_reference=source_reference,
                accident_type=(row.get("accident_type") or "").strip() or None,
                severity=(row.get("severity") or "").strip() or None,
                road_name=(row.get("road_name") or "").strip() or None,
                import_batch_id=batch_id,
                is_demo=True,
            )
            latitude = (row.get("latitude") or "").strip()
            longitude = (row.get("longitude") or "").strip()
            if latitude and longitude:
                set_point(record, float(latitude), float(longitude), LocationQuality.APPROXIMATE)
            accident_time = (row.get("accident_time") or "").strip()
            if accident_time:
                record.accident_time = datetime.fromisoformat(accident_time.replace("Z", "+00:00"))
                record.accident_date = record.accident_time.date()
            status_value = (row.get("verification_status") or "").strip().lower()
            if status_value in {item.value for item in AccidentVerificationStatus}:
                record.verification_status = AccidentVerificationStatus(status_value)
            ctx.session.add(record)
            imported += 1
        except (ValueError, TypeError) as exc:
            skipped += 1
            errors.append(f"line {line_number}: {type(exc).__name__}")

    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="accident_records.imported",
        entity_type="accident_import",
        entity_id=batch_id,
        request_id=ctx.request_id,
        summary=f"Imported {imported} historical accident records.",
        metadata={"skipped": skipped, "errors": errors[:10]},
    )
    return ok(
        AccidentImportResult(
            import_batch_id=batch_id,
            imported=imported,
            skipped=skipped,
            errors=errors[:20],
            is_demo=True,
        ),
        request,
    )


@router.post("/hotspots/analyze", response_model=Envelope[HotspotAnalysisOut])
def analyze_hotspots(
    payload: HotspotAnalyzeRequest, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[HotspotAnalysisOut]:
    ctx.require("hotspot:analyze")
    analysis = analytics.analyze(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        payload=payload,
        request_id=ctx.request_id,
    )
    return ok(analytics.to_schema(analysis), request)


@router.get("/hotspots", response_model=Envelope[list[HotspotAnalysisOut]])
def list_hotspot_analyses(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[HotspotAnalysisOut]]:
    ctx.require("analytics:read")
    rows = list(
        ctx.session.execute(
            select(HotspotAnalysis).order_by(HotspotAnalysis.generated_at.desc()).limit(limit)
        ).scalars()
    )
    return ok([analytics.to_schema(row) for row in rows], request)


@router.get("/hotspots/geojson", response_model=Envelope[FeatureCollection])
def hotspot_geojson(
    request: Request,
    analysis_id: uuid.UUID | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[FeatureCollection]:
    ctx.require("analytics:read")
    if analysis_id:
        analysis = ctx.session.get(HotspotAnalysis, analysis_id)
        if analysis is None:
            raise NotFound("Hotspot analysis not found.")
    else:
        analysis = ctx.session.execute(
            select(HotspotAnalysis).order_by(HotspotAnalysis.generated_at.desc()).limit(1)
        ).scalar_one_or_none()
        if analysis is None:
            return ok(
                FeatureCollection(
                    features=[],
                    properties={
                        "analysis_id": None,
                        "data_sources": analytics.DATA_SOURCES,
                        "methodology_note": analytics.METHODOLOGY_NOTE,
                        "count_interpretation": "No hotspot analysis has been generated yet.",
                        "generated_at": datetime.now(UTC).isoformat(),
                    },
                ),
                request,
            )
    return ok(analytics.to_feature_collection(analysis), request)


@router.get("/hotspots/{hotspot_id}", response_model=Envelope[HotspotAnalysisOut])
def get_hotspot(
    hotspot_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[HotspotAnalysisOut]:
    ctx.require("analytics:read")
    analysis = ctx.session.get(HotspotAnalysis, hotspot_id)
    if analysis is None:
        raise NotFound("Hotspot analysis not found.")
    return ok(analytics.to_schema(analysis), request)
