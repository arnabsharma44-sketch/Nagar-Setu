"""Video ingestion, processing jobs and evidence access."""

from __future__ import annotations

import uuid

from app.api.deps import CurrentContext, RequestContext
from app.core.config import settings
from app.core.errors import NotFound
from app.models import AIJob, Evidence, Video
from app.schemas.common import Envelope, ok, paginate
from app.schemas.domain import (
    EvidenceOut,
    EvidenceUrlOut,
    JobOut,
    PlaybackUrlOut,
    ProcessVideoRequest,
    UploadUrlRequest,
    UploadUrlResponse,
    VideoOut,
)
from app.schemas.serializers import evidence_out, job_out, video_out
from app.services import videos as video_service
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

router = APIRouter(tags=["videos"])


@router.post("/videos/upload-url", response_model=Envelope[UploadUrlResponse], status_code=201)
def create_upload_url(
    payload: UploadUrlRequest, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[UploadUrlResponse]:
    video, upload_url, expires_at = video_service.create_upload_session(ctx, payload)
    return ok(
        UploadUrlResponse(
            video_id=video.id,
            upload_url=upload_url,
            expires_at=expires_at,
            max_bytes=settings.max_upload_bytes,
        ),
        request,
    )


@router.post("/videos/{video_id}/complete-upload", response_model=Envelope[VideoOut])
def complete_upload(
    video_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[VideoOut]:
    video = video_service.complete_upload(ctx, video_id)
    return ok(video_out(video), request)


@router.get("/videos", response_model=Envelope[list[VideoOut]])
def list_videos(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    camera_id: uuid.UUID | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[VideoOut]]:
    ctx.require("video:read")
    statement = select(Video)
    count_statement = select(func.count()).select_from(Video)
    if camera_id:
        statement = statement.where(Video.camera_id == camera_id)
        count_statement = count_statement.where(Video.camera_id == camera_id)
    total = int(ctx.session.execute(count_statement).scalar_one())
    rows = ctx.session.execute(
        statement.order_by(Video.created_at.desc()).limit(limit).offset(offset)
    ).scalars()
    return ok([video_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.get("/videos/{video_id}", response_model=Envelope[VideoOut])
def get_video(
    video_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[VideoOut]:
    ctx.require("video:read")
    video = ctx.session.get(Video, video_id)
    if video is None:
        raise NotFound("Video not found.")
    return ok(video_out(video), request)


@router.post("/videos/{video_id}/process", response_model=Envelope[JobOut])
def process_video(
    video_id: uuid.UUID,
    payload: ProcessVideoRequest,
    request: Request,
    ctx: RequestContext = CurrentContext,
) -> Envelope[JobOut]:
    job = video_service.process_video(ctx, video_id, force=payload.force_reprocess)
    return ok(job_out(job), request)


@router.get("/videos/{video_id}/playback-url", response_model=Envelope[PlaybackUrlOut])
def playback_url(
    video_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[PlaybackUrlOut]:
    url = video_service.playback_url(ctx, video_id)
    return ok(
        PlaybackUrlOut(
            video_id=video_id, url=url, expires_in=settings.signed_url_ttl_seconds
        ),
        request,
    )


@router.get("/jobs", response_model=Envelope[list[JobOut]])
def list_jobs(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    video_id: uuid.UUID | None = Query(default=None),
    ctx: RequestContext = CurrentContext,
) -> Envelope[list[JobOut]]:
    ctx.require("video:read")
    statement = select(AIJob)
    count_statement = select(func.count()).select_from(AIJob)
    if video_id:
        statement = statement.where(AIJob.video_id == video_id)
        count_statement = count_statement.where(AIJob.video_id == video_id)
    total = int(ctx.session.execute(count_statement).scalar_one())
    rows = ctx.session.execute(
        statement.order_by(AIJob.created_at.desc()).limit(limit).offset(offset)
    ).scalars()
    return ok([job_out(row) for row in rows], request, pagination=paginate(limit, offset, total))


@router.get("/jobs/{job_id}", response_model=Envelope[JobOut])
def get_job(
    job_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[JobOut]:
    ctx.require("video:read")
    job = ctx.session.get(AIJob, job_id)
    if job is None:
        raise NotFound("Job not found.")
    return ok(job_out(job), request)


@router.post("/jobs/{job_id}/retry", response_model=Envelope[JobOut])
def retry_job(
    job_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[JobOut]:
    job = video_service.retry_job(ctx, job_id)
    return ok(job_out(job), request)


@router.get("/evidence/{evidence_id}", response_model=Envelope[EvidenceOut])
def get_evidence(
    evidence_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[EvidenceOut]:
    ctx.require("evidence:read")
    evidence = ctx.session.get(Evidence, evidence_id)
    if evidence is None:
        raise NotFound("Evidence not found.")
    return ok(evidence_out(evidence), request)


@router.get("/evidence/{evidence_id}/url", response_model=Envelope[EvidenceUrlOut])
def evidence_url(
    evidence_id: uuid.UUID, request: Request, ctx: RequestContext = CurrentContext
) -> Envelope[EvidenceUrlOut]:
    url, evidence = video_service.evidence_url(ctx, evidence_id)
    return ok(
        EvidenceUrlOut(
            evidence_id=evidence.id,
            url=url,
            expires_in=settings.signed_url_ttl_seconds,
            content_type=evidence.content_type,
        ),
        request,
    )
