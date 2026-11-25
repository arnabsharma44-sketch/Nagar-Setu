"""Job runner shared by the polling worker and the Celery task.

Persistence rules that this module enforces:

* The organization id always comes from the ``ai_jobs`` row, never from a task
  payload supplied by a client.
* Every write runs inside a tenant-scoped session, so Row-Level Security applies
  and the composite foreign keys reject any cross-tenant relationship.
* A failure never fabricates events; the job is marked failed with a safe message
  (and retried only for transient errors).
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (REPO_ROOT / "apps" / "api", REPO_ROOT / "ai-engine"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ai_engine.detection.detector import DetectorAdapter  # noqa: E402
from ai_engine.detection.yolo import DetectorUnavailable, build_detector  # noqa: E402
from ai_engine.events.base import RuleConfig  # noqa: E402
from ai_engine.pipeline import PipelineResult, analyze_video, annotations_at  # noqa: E402
from ai_engine.video.decoder import VideoValidationError  # noqa: E402
from ai_engine.video.evidence import build_event_clip, encode_png  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.errors import NotFound  # noqa: E402
from app.db.session import app_session_factory, apply_tenant_context, privileged_session, tenant_session  # noqa: E402
from app.models import (  # noqa: E402
    AIJob,
    Camera,
    Detection,
    Evidence,
    EvidenceType,
    Incident,
    IncidentSourceKind,
    JobStage,
    JobStatus,
    ReviewStatus,
    Video,
    VideoStatus,
)
from app.services.events import publish_event  # noqa: E402
from app.services.geo import set_point  # noqa: E402
from app.services.storage import build_storage_key, get_storage, sha256_of  # noqa: E402
from sqlalchemy import text  # noqa: E402

logger = logging.getLogger("roadguard.worker")


class JobContext:
    def __init__(self, job_id: uuid.UUID) -> None:
        self.job_id = job_id
        self.organization_id: uuid.UUID | None = None
        self.video_id: uuid.UUID | None = None
        self.camera_id: uuid.UUID | None = None
        self.storage_key: str | None = None
        self.config_snapshot: dict[str, Any] = {}
        self.attempts = 0


def load_job_context(job_id: uuid.UUID) -> JobContext:
    """Read the job with the privileged role, then work only inside its tenant."""
    context = JobContext(job_id)
    with privileged_session() as session:
        job = session.get(AIJob, job_id)
        if job is None:
            raise NotFound(f"Job {job_id} not found")
        video = session.get(Video, job.video_id)
        if video is None:
            raise NotFound(f"Video for job {job_id} not found")
        context.organization_id = job.organization_id
        context.video_id = video.id
        context.camera_id = video.camera_id
        context.storage_key = video.storage_key
        context.config_snapshot = dict(job.config_snapshot or {})
        context.attempts = job.attempts
    return context


def _build_detector(config: dict[str, Any]) -> DetectorAdapter:
    backend = str(config.get("detector_backend") or settings.detector_backend)
    return build_detector(
        backend=backend,
        weights=str(config.get("yolo_weights") or settings.yolo_weights),
        confidence=settings.yolo_confidence_threshold,
    )


def _rules(config: dict[str, Any]) -> RuleConfig:
    return RuleConfig(
        near_miss_proximity_ratio=float(
            config.get("near_miss_proximity_ratio", settings.near_miss_proximity_ratio)
        ),
        near_miss_convergence_window_seconds=float(
            config.get("near_miss_convergence_window_seconds", settings.near_miss_convergence_window_seconds)
        ),
        near_miss_min_track_frames=int(
            config.get("near_miss_min_track_frames", settings.near_miss_min_track_frames)
        ),
    )


# Module-level cached session factory for progress updates to avoid repeated factory creation
_progress_session_factory = None


def _get_progress_session_factory():
    global _progress_session_factory
    if _progress_session_factory is None:
        _progress_session_factory = app_session_factory()
    return _progress_session_factory


def _update_progress(job_id: uuid.UUID, organization_id: uuid.UUID, progress: int, stage: str) -> None:
    """Progress is informational; each update is its own short transaction.
    
    Lease is extended on every progress update to prevent expiration during long jobs.
    """
    factory = _get_progress_session_factory()
    session = factory()
    try:
        session.begin()
        apply_tenant_context(session, organization_id)
        job = session.get(AIJob, job_id)
        if job is not None and job.status == JobStatus.RUNNING:
            job.progress = progress
            job.stage = JobStage(stage) if stage in JobStage._value2member_map_ else job.stage
            # Extend lease on every progress update to prevent expiration during long jobs
            job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.job_lease_seconds)
        session.commit()
    except Exception:  # pragma: no cover - progress must never fail a job
        session.rollback()
    finally:
        session.close()


def _mark_running(job_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    with tenant_session(organization_id) as session:
        job = session.get(AIJob, job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING
        job.stage = JobStage.VALIDATING
        job.progress = max(1, job.progress)
        job.started_at = job.started_at or datetime.now(UTC)
        job.error_code = None
        job.error_message_safe = None


def _fail(job_id: uuid.UUID, organization_id: uuid.UUID, code: str, message: str, *, retryable: bool) -> None:
    with tenant_session(organization_id) as session:
        job = session.get(AIJob, job_id)
        if job is None:
            return
        job.error_code = code
        job.error_message_safe = message
        if retryable and job.attempts < settings.job_max_attempts:
            job.status = JobStatus.QUEUED
            job.stage = JobStage.QUEUED
            job.progress = 0
            job.lease_owner = None
            job.lease_expires_at = None
        else:
            job.status = JobStatus.FAILED
            job.stage = JobStage.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.lease_owner = None
            job.lease_expires_at = None
            video = session.get(Video, job.video_id)
            if video is not None:
                video.status = VideoStatus.FAILED
        publish_event(
            organization_id=organization_id,
            event_type="video.processing_completed",
            resource_type="ai_job",
            resource_id=job.id,
            data={
                "job_id": str(job.id),
                "video_id": str(job.video_id),
                "status": job.status.value,
                "error_code": code,
                "error_message": message,
            },
        )


def _persist_result(
    *,
    job_id: uuid.UUID,
    organization_id: uuid.UUID,
    context: JobContext,
    result: PipelineResult,
    detector: DetectorAdapter,
    video_recorded_at: datetime | None,
    camera_lat: float | None,
    camera_lon: float | None,
    camera_quality: Any,
    source_path: str,
) -> dict[str, Any]:
    incident_ids: list[uuid.UUID] = []
    with tenant_session(organization_id) as session:
        job = session.get(AIJob, job_id)
        if job is None:
            raise NotFound("Job disappeared while persisting results")
        video = session.get(Video, job.video_id)

        # Detections (job-local track ids, sampled frames only).
        session.bulk_save_objects(
            [
                Detection(
                    organization_id=organization_id,
                    job_id=job_id,
                    frame_number=detection.frame_number,
                    timestamp_offset_seconds=detection.timestamp_offset_seconds,
                    class_label=detection.class_label,
                    class_id=detection.class_id,
                    bbox=list(detection.bbox),
                    score=detection.score,
                    track_id=track_id,
                )
                for track_id, detection in result.detections
            ]
        )

        evidence_author = job.created_by or (video.uploaded_by if video else None)
        if evidence_author is None:
            raise RuntimeError("Job has no attributable author for evidence creation")
        event_base_time = video_recorded_at or video.created_at
        for event in result.events:
            event_time = event_base_time
            if video_recorded_at is not None:
                event_time = video_recorded_at + timedelta(seconds=event.start_offset_seconds)
            incident = Incident(
                organization_id=organization_id,
                camera_id=context.camera_id,
                video_id=video.id if video else None,
                ai_job_id=job_id,
                incident_type=event.event_type,
                source_kind=IncidentSourceKind.AI_CANDIDATE,
                severity=event.severity,
                model_score=event.score,
                event_time=event_time,
                start_offset_seconds=event.start_offset_seconds,
                end_offset_seconds=event.end_offset_seconds,
                description=(
                    f"Candidate {event.event_type.replace('_', ' ')} from rule "
                    f"{event.rule_name} v{event.rule_version}. Requires human review."
                ),
                review_status=ReviewStatus.PENDING,
                model_name=detector.name,
                model_version=detector.version,
                rule_name=event.rule_name,
                rule_version=event.rule_version,
                track_ids=event.track_ids,
                features=event.features,
                reason_codes=event.reason_codes,
                limitations=event.limitations,
                is_demo=settings.demo_mode,
            )
            if camera_lat is not None and camera_lon is not None:
                set_point(incident, camera_lat, camera_lon, camera_quality)
            session.add(incident)
            session.flush()
            incident_ids.append(incident.id)

            annotations = annotations_at(result, event.best_frame_number)
            from ai_engine.pipeline import read_annotated_source

            annotated = read_annotated_source(source_path, event.start_offset_seconds, annotations)
            if annotated is not None:
                frame_bytes = encode_png(annotated)
                key = build_storage_key(
                    str(organization_id), "evidence", str(incident.id), f"frame_{int(event.start_offset_seconds)}.png"
                )
                get_storage().put_bytes(key, frame_bytes, "image/png")
                session.add(
                    Evidence(
                        organization_id=organization_id,
                        incident_id=incident.id,
                        storage_key=key,
                        evidence_type=EvidenceType.ANNOTATED_FRAME,
                        label=f"Annotated frame at {event.start_offset_seconds:.1f}s",
                        content_type="image/png",
                        original_filename=f"frame_{int(event.start_offset_seconds)}.png",
                        file_size_bytes=len(frame_bytes),
                        checksum_sha256=sha256_of(frame_bytes),
                        timestamp_in_video=event.start_offset_seconds,
                        created_by=evidence_author,
                        is_demo=settings.demo_mode,
                    )
                )

            clip = build_event_clip(
                source_path,
                start_offset=max(0.0, event.start_offset_seconds - 1.0),
                end_offset=event.end_offset_seconds + 1.0,
                annotations_by_frame=result.annotations_by_frame,
                footer=f"ROADGUARD AI - {event.event_type} candidate - review required",
            )
            if clip:
                key = build_storage_key(
                    str(organization_id), "evidence", str(incident.id), "event_clip.mp4"
                )
                get_storage().put_bytes(key, clip, "video/mp4")
                session.add(
                    Evidence(
                        organization_id=organization_id,
                        incident_id=incident.id,
                        storage_key=key,
                        evidence_type=EvidenceType.EVENT_CLIP,
                        label="Annotated event clip",
                        content_type="video/mp4",
                        original_filename="event_clip.mp4",
                        file_size_bytes=len(clip),
                        checksum_sha256=sha256_of(clip),
                        timestamp_in_video=event.start_offset_seconds,
                        created_by=evidence_author,
                        is_demo=settings.demo_mode,
                    )
                )

        job.status = JobStatus.SUCCEEDED
        job.stage = JobStage.COMPLETED
        job.progress = 100
        job.completed_at = datetime.now(UTC)
        job.lease_owner = None
        job.lease_expires_at = None
        job.weights_sha256 = getattr(detector, "weights_sha256", lambda: None)()
        job.model_version = detector.version
        job.result_summary = {
            **result.summary(),
            "detector": detector.describe(),
            "incidents_created": len(incident_ids),
        }
        if video is not None:
            video.status = VideoStatus.PROCESSED
            video.duration_seconds = result.metadata.duration_seconds
            video.width = result.metadata.width
            video.height = result.metadata.height
            video.frame_rate = result.metadata.frame_rate

        publish_event(
            organization_id=organization_id,
            event_type="video.processing_completed",
            resource_type="ai_job",
            resource_id=job_id,
            data={
                "job_id": str(job_id),
                "video_id": str(context.video_id),
                "status": JobStatus.SUCCEEDED.value,
                "progress": 100,
                "events_created": len(incident_ids),
            },
        )
        for incident_id in incident_ids:
            publish_event(
                organization_id=organization_id,
                event_type="incident.detected",
                resource_type="incident",
                resource_id=incident_id,
                data={"incident_id": str(incident_id), "review_status": ReviewStatus.PENDING.value},
            )

    return {"incidents_created": len(incident_ids)}


def process_job(job_id: uuid.UUID | str) -> dict[str, Any]:
    job_uuid = uuid.UUID(str(job_id))
    context = load_job_context(job_uuid)
    if context.organization_id is None:
        raise RuntimeError("Job has no organization")
    organization_id = context.organization_id

    _mark_running(job_uuid, organization_id)
    _update_progress(job_uuid, organization_id, 3, "validating")

    storage = get_storage()
    temp_dir = tempfile.mkdtemp(prefix="roadguard-job-")
    source_path = os.path.join(temp_dir, "source.bin")
    try:
        if not context.storage_key:
            raise RuntimeError("Job has no storage key")
        try:
            data = storage.read_bytes(context.storage_key)
        except NotFound:
            _fail(job_uuid, organization_id, "SOURCE_MISSING", "The source video is no longer available in private storage.", retryable=False)
            return {"status": "failed", "error_code": "SOURCE_MISSING"}
        with open(source_path, "wb") as handle:
            handle.write(data)

        detector = _build_detector(context.config_snapshot)
        camera_lat = camera_lon = None
        camera_quality = None
        video_recorded_at = None
        with tenant_session(organization_id) as session:
            video = session.get(Video, context.video_id) if context.video_id else None
            if video is not None:
                video_recorded_at = video.recorded_at
            if context.camera_id:
                camera = session.get(Camera, context.camera_id)
                if camera is not None:
                    camera_lat, camera_lon = camera.latitude, camera.longitude
                    camera_quality = camera.location_quality

        result = analyze_video(
            source_path,
            detector=detector,
            sample_fps=float(context.config_snapshot.get("frame_sample_fps", settings.frame_sample_fps)),
            rules=_rules(context.config_snapshot),
            tracker_name=str(context.config_snapshot.get("tracker", settings.tracker)),
            scene_config=context.config_snapshot.get("scene_config"),
            max_duration_seconds=settings.max_video_duration_seconds,
            max_width=settings.max_video_width,
            max_height=settings.max_video_height,
            progress=lambda value, stage: _update_progress(job_uuid, organization_id, value, stage),
        )
        outcome = _persist_result(
            job_id=job_uuid,
            organization_id=organization_id,
            context=context,
            result=result,
            detector=detector,
            video_recorded_at=video_recorded_at,
            camera_lat=camera_lat,
            camera_lon=camera_lon,
            camera_quality=camera_quality,
            source_path=source_path,
        )
        logger.info(
            "job_succeeded job=%s events=%s detections=%s",
            job_uuid,
            outcome["incidents_created"],
            len(result.detections),
        )
        return {"status": "succeeded", **outcome}

    except VideoValidationError as exc:
        _fail(job_uuid, organization_id, "INVALID_MEDIA", str(exc)[:480], retryable=False)
        return {"status": "failed", "error_code": "INVALID_MEDIA", "message": str(exc)}
    except DetectorUnavailable as exc:
        _fail(job_uuid, organization_id, "DETECTOR_UNAVAILABLE", str(exc)[:480], retryable=False)
        return {"status": "failed", "error_code": "DETECTOR_UNAVAILABLE", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected failure path
        logger.exception("job_failed job=%s error=%s", job_uuid, type(exc).__name__)
        _fail(
            job_uuid,
            organization_id,
            "PROCESSING_ERROR",
            "Processing failed unexpectedly. The job can be retried.",
            retryable=True,
        )
        return {"status": "failed", "error_code": "PROCESSING_ERROR"}
    finally:
        for name in os.listdir(temp_dir):
            with contextlib.suppress(OSError):
                os.unlink(os.path.join(temp_dir, name))
        with contextlib.suppress(OSError):
            os.rmdir(temp_dir)


def claim_next_job(worker_id: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Atomically claim one queued job via the SECURITY DEFINER function.

    ``claim_ai_job`` is the only sanctioned cross-tenant read: it returns a job id
    and the organization recorded on that job row, and nothing else.
    """
    factory = app_session_factory()
    session = factory()
    try:
        session.begin()
        row = session.execute(
            text(
                "SELECT out_job_id, out_organization_id FROM claim_ai_job("
                "CAST(:worker AS text), CAST(:lease AS integer), CAST(:max_attempts AS integer))"
            ),
            {
                "worker": worker_id,
                "lease": settings.job_lease_seconds,
                "max_attempts": settings.job_max_attempts,
            },
        ).first()
        session.commit()
        if row is None:
            return None
        return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
