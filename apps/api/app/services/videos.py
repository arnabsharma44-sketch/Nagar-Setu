"""Video ingestion and processing-job orchestration.

The API never runs inference inline. It validates metadata, stores the object
privately, creates an idempotent job row and hands the job to the worker (Celery
when configured, otherwise the in-repo claim/lease worker).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.api.deps import RequestContext
from app.core.audit import record_audit
from app.core.config import settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationError
from app.models import (
    AIJob,
    Camera,
    Evidence,
    EvidenceType,
    JobStage,
    JobStatus,
    Video,
    VideoStatus,
)
from app.schemas.domain import UploadUrlRequest
from app.services import media_validation
from app.services.events import publish_event
from app.services.storage import build_storage_key, get_storage
from sqlalchemy import func, select

logger = logging.getLogger("roadguard.videos")

DETECTOR_NAME = (
    "synthetic-scene-colour-marker" if settings.detector_backend == "synthetic_scene" else "ultralytics-yolo"
)
RULES_VERSION = "1.0.0"


def _job_idempotency_key(video_id: uuid.UUID) -> str:
    raw = (
        f"{video_id}|{settings.detector_backend}|{settings.yolo_weights}|"
        f"{RULES_VERSION}|{settings.frame_sample_fps}|{settings.tracker}|"
        f"{settings.near_miss_proximity_ratio}|{settings.near_miss_convergence_window_seconds}|"
        f"{settings.near_miss_min_track_frames}|{settings.yolo_confidence_threshold}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_upload_session(ctx: RequestContext, payload: UploadUrlRequest) -> tuple[Video, str, datetime]:
    ctx.require("video:upload")
    content_type = media_validation.check_content_type(payload.filename, payload.content_type)
    media_validation.check_size(payload.file_size_bytes)

    camera: Camera | None = None
    if payload.camera_id is not None:
        camera = ctx.session.get(Camera, payload.camera_id)
        if camera is None or camera.organization_id != ctx.organization_id:
            raise NotFound("Camera not found.")

    video_id = uuid.uuid4()
    filename = media_validation.sanitize_filename(payload.filename)
    extension = "." + filename.rsplit(".", 1)[-1].lower()
    storage_key = build_storage_key(
        str(ctx.organization_id), "videos", str(video_id), f"{uuid.uuid4().hex}{extension}"
    )

    video = Video(
        id=video_id,
        organization_id=ctx.organization_id,
        camera_id=camera.id if camera else None,
        uploaded_by=ctx.user_id,
        storage_key=storage_key,
        original_filename=filename,
        content_type=content_type,
        file_size_bytes=payload.file_size_bytes,
        source_type=payload.source_type,
        recorded_at=payload.recorded_at,
        status=VideoStatus.PENDING_UPLOAD,
        retention_expires_at=datetime.now(UTC) + timedelta(days=settings.video_retention_days),
        is_demo=settings.demo_mode,
    )
    ctx.session.add(video)
    ctx.session.flush()

    upload_url = get_storage().upload_url(
        key=storage_key, organization_id=ctx.organization_id, content_type=content_type
    )
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.signed_url_ttl_seconds)
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="video.upload_started",
        entity_type="video",
        entity_id=video.id,
        request_id=ctx.request_id,
        summary=f"Upload session created for {filename}.",
        metadata={"content_type": content_type, "file_size_bytes": payload.file_size_bytes},
    )
    return video, upload_url, expires_at


def complete_upload(ctx: RequestContext, video_id: uuid.UUID) -> Video:
    ctx.require("video:upload")
    # Use SELECT FOR UPDATE to prevent race conditions
    video = ctx.session.execute(
        select(Video).where(Video.id == video_id).with_for_update()
    ).scalar_one_or_none()
    if video is None:
        raise NotFound("Video not found.")
    if video.status != VideoStatus.PENDING_UPLOAD:
        raise Conflict("This upload has already been finalised.", code="UPLOAD_ALREADY_FINALISED")
    if video.uploaded_by != ctx.user_id and not ctx.principal.has("video:process"):
        raise PermissionDenied("Only the uploader can finalise this upload.")

    storage = get_storage()
    stat = storage.stat(video.storage_key)
    if not stat.exists:
        raise NotFound("The uploaded object was not found in private storage.")
    if stat.size_bytes > settings.max_upload_bytes:
        video.status = VideoStatus.VALIDATION_FAILED
        video.validation_error = "Uploaded file exceeds the configured maximum size."
        raise ValidationError("The uploaded file exceeds the configured limit.")
    if stat.size_bytes == 0:
        video.status = VideoStatus.VALIDATION_FAILED
        video.validation_error = "Uploaded file is empty."
        raise ValidationError("The uploaded file is empty.")

    stream = storage.open_stream(video.storage_key)
    try:
        head = stream.read(64)
        media_validation.verify_container(head)
        stream.seek(0)
        digest = hashlib.sha256()
        while chunk := stream.read(1024 * 256):
            digest.update(chunk)
    finally:
        stream.close()

    video.checksum_sha256 = digest.hexdigest()
    video.file_size_bytes = stat.size_bytes
    video.status = VideoStatus.UPLOADED
    video.validation_error = None
    ctx.session.flush()

    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="video.upload_completed",
        entity_type="video",
        entity_id=video.id,
        request_id=ctx.request_id,
        summary=f"Upload finalised for {video.original_filename}.",
        metadata={"checksum_sha256": video.checksum_sha256, "size": stat.size_bytes},
    )
    enqueue_job(ctx, video, force=False)
    return video


def enqueue_job(ctx: RequestContext, video: Video, *, force: bool) -> AIJob:
    key = _job_idempotency_key(video.id)
    existing = ctx.session.execute(
        select(AIJob).where(
            AIJob.organization_id == ctx.organization_id, AIJob.idempotency_key == key
        )
    ).scalar_one_or_none()
    if (
        existing
        and not force
        and existing.status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED}
    ):
        return existing

    job = AIJob(
        organization_id=ctx.organization_id,
        video_id=video.id,
        job_type="video_analysis",
        status=JobStatus.QUEUED,
        stage=JobStage.QUEUED,
        progress=0,
        idempotency_key=key if not force else f"{key}:{uuid.uuid4().hex[:8]}",
        model_name=DETECTOR_NAME,
        model_version="synthetic_scene_v1" if settings.detector_backend == "synthetic_scene" else "yolov8",
        event_rules_version=RULES_VERSION,
        config_snapshot={
            "detector_backend": settings.detector_backend,
            "yolo_weights": settings.yolo_weights,
            "frame_sample_fps": settings.frame_sample_fps,
            "tracker": settings.tracker,
            "near_miss_proximity_ratio": settings.near_miss_proximity_ratio,
            "near_miss_convergence_window_seconds": settings.near_miss_convergence_window_seconds,
            "near_miss_min_track_frames": settings.near_miss_min_track_frames,
        },
        created_by=ctx.user_id,
    )
    ctx.session.add(job)
    ctx.session.flush()

    video.status = VideoStatus.PROCESSING
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="video.processing_queued",
        entity_type="ai_job",
        entity_id=job.id,
        request_id=ctx.request_id,
        summary="Processing job queued.",
        metadata={"video_id": str(video.id)},
    )

    if settings.job_runner == "celery":
        try:
            from ai_engine.workers.celery_app import process_video_job

            process_video_job.delay(str(job.id))
        except Exception as exc:  # pragma: no cover - broker optional
            logger.warning("celery_dispatch_failed job=%s error=%s", job.id, type(exc).__name__)

    publish_event(
        organization_id=ctx.organization_id,
        event_type="video.processing_started",
        resource_type="ai_job",
        resource_id=job.id,
        data={
            "job_id": str(job.id),
            "video_id": str(video.id),
            "status": JobStatus.QUEUED.value,
            "progress": 0,
            "stage": JobStage.QUEUED.value,
        },
    )
    return job


def process_video(ctx: RequestContext, video_id: uuid.UUID, *, force: bool) -> AIJob:
    ctx.require("video:process")
    video = ctx.session.get(Video, video_id)
    if video is None:
        raise NotFound("Video not found.")
    if video.status == VideoStatus.PENDING_UPLOAD:
        raise Conflict("The upload has not been finalised yet.", code="UPLOAD_INCOMPLETE")
    return enqueue_job(ctx, video, force=force)


def retry_job(ctx: RequestContext, job_id: uuid.UUID) -> AIJob:
    ctx.require("video:process")
    job = ctx.session.get(AIJob, job_id)
    if job is None:
        raise NotFound("Job not found.")
    if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
        raise Conflict("Only a failed or cancelled job can be retried.", code="JOB_NOT_RETRYABLE")
    if job.attempts >= settings.job_max_attempts:
        raise Conflict(
            "This job has reached its retry limit. Upload a new file or reprocess explicitly.",
            code="JOB_RETRY_LIMIT",
        )
    job.status = JobStatus.QUEUED
    job.stage = JobStage.QUEUED
    job.progress = 0
    job.error_code = None
    job.error_message_safe = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.completed_at = None
    ctx.session.flush()
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="video.job_retried",
        entity_type="ai_job",
        entity_id=job.id,
        request_id=ctx.request_id,
        summary="Failed job re-queued by an operator.",
    )
    return job


def playback_url(ctx: RequestContext, video_id: uuid.UUID) -> str:
    ctx.require("video:read")
    video = ctx.session.get(Video, video_id)
    if video is None:
        raise NotFound("Video not found.")
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="video.playback_url_issued",
        entity_type="video",
        entity_id=video.id,
        request_id=ctx.request_id,
        summary="Short-lived playback URL issued.",
    )
    return get_storage().download_url(
        key=video.storage_key,
        organization_id=ctx.organization_id,
        filename=video.original_filename,
        content_type=video.content_type,
    )


def evidence_url(ctx: RequestContext, evidence_id: uuid.UUID) -> tuple[str, Evidence]:
    ctx.require("evidence:read")
    evidence = ctx.session.get(Evidence, evidence_id)
    if evidence is None:
        raise NotFound("Evidence not found.")
    record_audit(
        ctx.session,
        organization_id=ctx.organization_id,
        actor_id=ctx.user_id,
        actor_label=ctx.principal.email,
        action="evidence.download_url_issued",
        entity_type="evidence",
        entity_id=evidence.id,
        request_id=ctx.request_id,
        summary="Short-lived evidence URL issued.",
    )
    url = get_storage().download_url(
        key=evidence.storage_key,
        organization_id=ctx.organization_id,
        filename=evidence.original_filename,
        content_type=evidence.content_type,
    )
    return url, evidence


def create_completion_evidence(
    ctx: RequestContext,
    *,
    work_order_id: uuid.UUID,
    filename: str,
    content_type: str,
    data: bytes,
    label: str | None,
) -> Evidence:
    """Store completion evidence submitted with a work order."""
    from app.services.storage import sha256_of

    storage = get_storage()
    key = build_storage_key(
        str(ctx.organization_id), "work-orders", str(work_order_id), f"{uuid.uuid4().hex}_{media_validation.sanitize_filename(filename)}"
    )
    storage.put_bytes(key, data, content_type)
    evidence = Evidence(
        organization_id=ctx.organization_id,
        work_order_id=work_order_id,
        storage_key=key,
        evidence_type=EvidenceType.COMPLETION_PHOTO
        if content_type.startswith("image/")
        else EvidenceType.COMPLETION_DOCUMENT,
        label=label,
        content_type=content_type,
        original_filename=media_validation.sanitize_filename(filename),
        file_size_bytes=len(data),
        checksum_sha256=sha256_of(data),
        created_by=ctx.user_id,
        is_demo=settings.demo_mode,
    )
    ctx.session.add(evidence)
    ctx.session.flush()
    return evidence


def video_counts(ctx: RequestContext) -> dict[str, int]:
    rows = ctx.session.execute(
        select(Video.status, func.count()).group_by(Video.status)
    ).all()
    return {str(status): int(count) for status, count in rows}
