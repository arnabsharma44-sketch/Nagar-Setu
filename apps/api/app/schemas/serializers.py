"""ORM → response-model serializers.

Keeping serialization in one place means the API contract, the OpenAPI document
and the typed frontend client cannot drift apart.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.models import (
    WORK_ORDER_TRANSITIONS,
    AccidentRecord,
    Asset,
    AuditLog,
    Camera,
    Contract,
    Contractor,
    Department,
    Evidence,
    Incident,
    Investigation,
    Organization,
    Recommendation,
    User,
    Verification,
    Video,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.models.media import AIJob
from app.schemas.domain import (
    AccidentRecordOut,
    AssetOut,
    AuditLogOut,
    CameraOut,
    ContractorOut,
    ContractOut,
    CurrentUser,
    DepartmentOut,
    EvidenceOut,
    IncidentOut,
    InvestigationOut,
    JobOut,
    LocationOut,
    OrganizationSummary,
    RecommendationOut,
    StatusHistoryOut,
    UserOut,
    VerificationOut,
    VideoOut,
    WorkOrderDetail,
    WorkOrderOut,
)
from app.services.geo import point_payload


def location_out(instance: Any) -> LocationOut | None:
    payload = point_payload(instance)
    if payload is None:
        return None
    return LocationOut(
        latitude=payload["latitude"], longitude=payload["longitude"], quality=payload["quality"]
    )


def organization_summary(organization: Organization) -> OrganizationSummary:
    return OrganizationSummary(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        organization_type=organization.organization_type.value
        if hasattr(organization.organization_type, "value")
        else str(organization.organization_type),
        city=organization.city,
        state=organization.state,
        is_demo=organization.is_demo,
    )


def current_user(user: User, organization: Organization, permissions: list[str], csrf_token: str | None = None) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        permissions=permissions,
        organization=organization_summary(organization),
        csrf_token=csrf_token,
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        is_demo=user.is_demo,
    )


def department_out(department: Department) -> DepartmentOut:
    return DepartmentOut(
        id=department.id,
        name=department.name,
        department_type=department.department_type,
        contact_email=department.contact_email,
        description=department.description,
        source_reference=department.source_reference,
        is_demo=department.is_demo,
        created_at=department.created_at,
    )


def contractor_out(contractor: Contractor) -> ContractorOut:
    return ContractorOut(
        id=contractor.id,
        name=contractor.name,
        registration_number=contractor.registration_number,
        contact_email=contractor.contact_email,
        contact_phone=contractor.contact_phone,
        source_reference=contractor.source_reference,
        is_demo=contractor.is_demo,
        created_at=contractor.created_at,
    )


def asset_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        asset_type=asset.asset_type,
        address=asset.address,
        department_id=asset.department_id,
        location=location_out(asset),
        condition_status=asset.condition_status,
        source_reference=asset.source_reference,
        last_inspected_at=asset.last_inspected_at,
        is_demo=asset.is_demo,
        created_at=asset.created_at,
    )


def contract_out(
    contract: Contract,
    *,
    contractor_name: str | None = None,
    department_name: str | None = None,
    asset_ids: list[uuid.UUID] | None = None,
) -> ContractOut:
    return ContractOut(
        id=contract.id,
        contract_number=contract.contract_number,
        contract_type=contract.contract_type,
        contractor_id=contract.contractor_id,
        contractor_name=contractor_name,
        department_id=contract.department_id,
        department_name=department_name,
        scope_description=contract.scope_description,
        start_date=contract.start_date,
        end_date=contract.end_date,
        warranty_end_date=contract.warranty_end_date,
        asset_ids=asset_ids or [],
        source_reference=contract.source_reference,
        is_demo=contract.is_demo,
    )


def camera_out(camera: Camera) -> CameraOut:
    return CameraOut(
        id=camera.id,
        camera_code=camera.camera_code,
        name=camera.name,
        description=camera.description,
        source_type=camera.source_type,
        location=location_out(camera),
        connection_status=camera.connection_status,
        is_enabled=camera.is_enabled,
        is_demo=camera.is_demo,
        has_secret_reference=bool(camera.secret_reference),
        last_seen_at=camera.last_seen_at,
        created_at=camera.created_at,
    )


def video_out(video: Video) -> VideoOut:
    return VideoOut(
        id=video.id,
        camera_id=video.camera_id,
        original_filename=video.original_filename,
        content_type=video.content_type,
        file_size_bytes=video.file_size_bytes,
        checksum_sha256=video.checksum_sha256,
        source_type=video.source_type,
        status=video.status,
        recorded_at=video.recorded_at,
        duration_seconds=video.duration_seconds,
        width=video.width,
        height=video.height,
        frame_rate=video.frame_rate,
        validation_error=video.validation_error,
        uploaded_by=video.uploaded_by,
        created_at=video.created_at,
        is_demo=video.is_demo,
    )


def job_out(job: AIJob) -> JobOut:
    from app.core.config import settings

    return JobOut(
        id=job.id,
        video_id=job.video_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        attempts=job.attempts,
        model_name=job.model_name,
        model_version=job.model_version,
        event_rules_version=job.event_rules_version,
        result_summary=job.result_summary or {},
        error_code=job.error_code,
        error_message_safe=job.error_message_safe,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        can_retry=(
            job.status.value in {"failed", "cancelled"} and job.attempts < settings.job_max_attempts
        ),
    )


def incident_out(incident: Incident, *, camera_code: str | None = None) -> IncidentOut:
    return IncidentOut(
        id=incident.id,
        incident_type=incident.incident_type,
        source_kind=incident.source_kind,
        severity=incident.severity,
        model_score=incident.model_score,
        event_time=incident.event_time,
        start_offset_seconds=incident.start_offset_seconds,
        end_offset_seconds=incident.end_offset_seconds,
        location=location_out(incident),
        description=incident.description,
        review_status=incident.review_status,
        reviewed_by=incident.reviewed_by,
        reviewed_at=incident.reviewed_at,
        review_notes=incident.review_notes,
        camera_id=incident.camera_id,
        camera_code=camera_code,
        video_id=incident.video_id,
        ai_job_id=incident.ai_job_id,
        model_name=incident.model_name,
        model_version=incident.model_version,
        rule_name=incident.rule_name,
        rule_version=incident.rule_version,
        track_ids=list(incident.track_ids or []),
        features=dict(incident.features or {}),
        reason_codes=list(incident.reason_codes or []),
        limitations=list(incident.limitations or []),
        is_demo=incident.is_demo,
        created_at=incident.created_at,
    )


def evidence_out(evidence: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=evidence.id,
        evidence_type=evidence.evidence_type,
        label=evidence.label,
        content_type=evidence.content_type,
        original_filename=evidence.original_filename,
        file_size_bytes=evidence.file_size_bytes,
        checksum_sha256=evidence.checksum_sha256,
        timestamp_in_video=evidence.timestamp_in_video,
        incident_id=evidence.incident_id,
        investigation_id=evidence.investigation_id,
        work_order_id=evidence.work_order_id,
        created_at=evidence.created_at,
        is_demo=evidence.is_demo,
    )


def accident_out(record: AccidentRecord) -> AccidentRecordOut:
    return AccidentRecordOut(
        id=record.id,
        external_reference=record.external_reference,
        location=location_out(record),
        accident_time=record.accident_time,
        accident_date=record.accident_date,
        accident_type=record.accident_type,
        severity=record.severity,
        road_name=record.road_name,
        source_name=record.source_name,
        source_reference=record.source_reference,
        verification_status=record.verification_status,
        import_batch_id=record.import_batch_id,
        is_demo=record.is_demo,
    )


def investigation_out(investigation: Investigation) -> InvestigationOut:
    return InvestigationOut(
        id=investigation.id,
        case_number=investigation.case_number,
        title=investigation.title,
        summary=investigation.summary,
        incident_id=investigation.incident_id,
        asset_id=investigation.asset_id,
        assigned_department_id=investigation.assigned_department_id,
        assigned_to=investigation.assigned_to,
        status=investigation.status,
        responsibility_status=investigation.responsibility_status,
        observed_facts=list(investigation.observed_facts or []),
        hypotheses=list(investigation.hypotheses or []),
        missing_information=list(investigation.missing_information or []),
        analysis_source=investigation.analysis_source,
        analysis_model=investigation.analysis_model,
        analysis_generated_at=investigation.analysis_generated_at,
        opened_by=investigation.opened_by,
        closed_at=investigation.closed_at,
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        is_demo=investigation.is_demo,
    )


def recommendation_out(recommendation: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=recommendation.id,
        investigation_id=recommendation.investigation_id,
        recommendation_text=recommendation.recommendation_text,
        rationale=recommendation.rationale,
        priority=recommendation.priority,
        status=recommendation.status,
        model_name=recommendation.model_name,
        model_version=recommendation.model_version,
        limitations=list(recommendation.limitations or []),
        created_by=recommendation.created_by,
        reviewed_by=recommendation.reviewed_by,
        reviewed_at=recommendation.reviewed_at,
        review_notes=recommendation.review_notes,
        created_at=recommendation.created_at,
        is_demo=recommendation.is_demo,
    )


def work_order_out(order: WorkOrder, *, department_name: str | None = None) -> WorkOrderOut:
    return WorkOrderOut(
        id=order.id,
        work_order_number=order.work_order_number,
        investigation_id=order.investigation_id,
        recommendation_id=order.recommendation_id,
        assigned_department_id=order.assigned_department_id,
        department_name=department_name,
        assigned_to=order.assigned_to,
        title=order.title,
        description=order.description,
        status=order.status,
        priority=order.priority,
        due_date=order.due_date,
        completed_at=order.completed_at,
        completion_notes=order.completion_notes,
        completed_by=order.completed_by,
        verified_at=order.verified_at,
        verified_by=order.verified_by,
        created_at=order.created_at,
        updated_at=order.updated_at,
        is_demo=order.is_demo,
        allowed_transitions=sorted(WORK_ORDER_TRANSITIONS.get(order.status, set()), key=lambda v: v.value),
    )


def status_history_out(row: WorkOrderStatusHistory) -> StatusHistoryOut:
    return StatusHistoryOut(
        id=row.id,
        from_status=row.from_status,
        to_status=row.to_status,
        changed_by=row.changed_by,
        note=row.note,
        created_at=row.created_at,
    )


def verification_out(verification: Verification) -> VerificationOut:
    return VerificationOut(
        id=verification.id,
        verified_by=verification.verified_by,
        verification_status=verification.verification_status,
        notes=verification.notes,
        verified_at=verification.verified_at,
        created_at=verification.created_at,
    )


def work_order_detail(
    order: WorkOrder,
    *,
    department_name: str | None,
    history: list[WorkOrderStatusHistory],
    verifications: list[Verification],
    evidence: list[Evidence],
    allowed_transitions: list[Any],
    can_submit_completion: bool,
    can_verify: bool,
) -> WorkOrderDetail:
    base = work_order_out(order, department_name=department_name)
    return WorkOrderDetail(
        **base.model_dump(),
        history=[status_history_out(row) for row in history],
        verifications=[verification_out(row) for row in verifications],
        evidence=[evidence_out(row) for row in evidence],
        separation_of_duties=True,
        can_submit_completion=can_submit_completion,
        can_verify=can_verify,
    )


def audit_out(entry: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        id=entry.id,
        actor_id=entry.actor_id,
        actor_label=entry.actor_label,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        request_id=entry.request_id,
        summary=entry.summary,
        metadata=dict(entry.metadata_json or {}),
        created_at=entry.created_at,
    )
