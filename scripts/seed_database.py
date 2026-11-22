"""Idempotent seed script for DEMO data.

Everything created here is fictional and prefixed with ``DEMO``. Two organizations
are seeded so cross-tenant isolation can be demonstrated and tested. Re-running the
script updates the same rows instead of duplicating them (deterministic UUIDs).

Usage::

    python scripts/seed_database.py
    python scripts/seed_database.py --reset-demo-data   # deletes seed rows first

The demo password comes from ``DEMO_SEED_PASSWORD`` and defaults to a clearly
labelled local-only value. Never reuse it outside a local demonstration.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.core.security import hash_password, normalize_email  # noqa: E402
from app.db.session import get_privileged_engine, privileged_session  # noqa: E402
from app.models import (  # noqa: E402
    AccidentRecord,
    AccidentVerificationStatus,
    AIJob,
    Asset,
    AssetType,
    Camera,
    CameraConnectionStatus,
    CameraSourceType,
    ConditionStatus,
    Contract,
    ContractAsset,
    Contractor,
    Department,
    Evidence,
    EvidenceType,
    Incident,
    IncidentSourceKind,
    IncidentType,
    Investigation,
    InvestigationStatus,
    JobStage,
    JobStatus,
    LocationQuality,
    Organization,
    OrganizationType,
    Priority,
    ReviewStatus,
    Severity,
    User,
    Video,
    VideoSourceType,
    VideoStatus,
    WorkOrder,
    WorkOrderStatus,
)
from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import text  # noqa: E402

NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
DEMO_PASSWORD = os.environ.get("DEMO_SEED_PASSWORD", "RoadguardDemo#2026")
ACCIDENT_CSV = REPO_ROOT / "datasets" / "sample_accidents" / "demo_accidents.csv"


def stable_id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def point(latitude: float, longitude: float) -> WKTElement:
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def upsert(session, model, key: str, values: dict) -> object:  # noqa: ANN001
    identifier = stable_id(key)
    existing = session.get(model, identifier)
    if existing is None:
        instance = model(id=identifier, **values)
        session.add(instance)
        return instance
    for field, value in values.items():
        setattr(existing, field, value)
    return existing


def seed() -> None:
    now = datetime.now(UTC)
    password_hash = hash_password(DEMO_PASSWORD)

    with privileged_session() as session:
        org_main = upsert(
            session,
            Organization,
            "org:demo-city",
            {
                "name": "DEMO Bhubaneswar Road Safety Authority",
                "slug": "demo-city",
                "organization_type": OrganizationType.MUNICIPALITY,
                "city": "Bhubaneswar",
                "state": "Odisha",
                "is_demo": True,
            },
        )
        org_isolation = upsert(
            session,
            Organization,
            "org:demo-isolation",
            {
                "name": "DEMO Rourkela Isolation Tenant",
                "slug": "demo-isolation",
                "organization_type": OrganizationType.MUNICIPALITY,
                "city": "Rourkela",
                "state": "Odisha",
                "is_demo": True,
            },
        )
        session.flush()

        # ---------------- departments ----------------
        departments = {
            "roads": upsert(
                session,
                Department,
                "dept:roads",
                {
                    "organization_id": org_main.id,
                    "name": "DEMO Roads and Buildings",
                    "normalized_name": "demo roads and buildings",
                    "department_type": "roads",
                    "contact_email": "roads@demo.roadguard.ai",
                    "description": "Synthetic department record for demonstration only.",
                    "source_reference": "DEMO-DEPT-REG-001",
                    "is_demo": True,
                },
            ),
            "traffic": upsert(
                session,
                Department,
                "dept:traffic",
                {
                    "organization_id": org_main.id,
                    "name": "DEMO Traffic Engineering",
                    "normalized_name": "demo traffic engineering",
                    "department_type": "traffic_engineering",
                    "contact_email": "traffic@demo.roadguard.ai",
                    "description": "Synthetic department record for demonstration only.",
                    "source_reference": "DEMO-DEPT-REG-002",
                    "is_demo": True,
                },
            ),
            "police": upsert(
                session,
                Department,
                "dept:police",
                {
                    "organization_id": org_main.id,
                    "name": "DEMO Traffic Police",
                    "normalized_name": "demo traffic police",
                    "department_type": "police",
                    "contact_email": "police@demo.roadguard.ai",
                    "description": "Synthetic department record for demonstration only.",
                    "source_reference": "DEMO-DEPT-REG-003",
                    "is_demo": True,
                },
            ),
        }
        dept_isolation = upsert(
            session,
            Department,
            "dept:isolation-roads",
            {
                "organization_id": org_isolation.id,
                "name": "DEMO Isolation Roads",
                "normalized_name": "demo isolation roads",
                "department_type": "roads",
                "contact_email": "roads@isolation.roadguard.ai",
                "description": "Second-tenant department used by isolation tests.",
                "source_reference": "DEMO-DEPT-REG-ISO",
                "is_demo": True,
            },
        )
        session.flush()

        # ---------------- users ----------------
        users = [
            ("user:ops", "Demo Operations Administrator", "ops@demo.roadguard.ai", "police_admin", None, org_main),
            ("user:reviewer", "Demo Event Reviewer", "reviewer@demo.roadguard.ai", "reviewer", None, org_main),
            (
                "user:engineer",
                "Demo Department Engineer",
                "engineer@demo.roadguard.ai",
                "department_engineer",
                "roads",
                org_main,
            ),
            ("user:admin", "Demo Organization Administrator", "admin@demo.roadguard.ai", "org_admin", None, org_main),
            ("user:auditor", "Demo Auditor", "auditor@demo.roadguard.ai", "auditor", None, org_main),
            ("user:isolation", "Demo Isolation Operator", "ops@isolation.roadguard.ai", "police_admin", None, org_isolation),
        ]
        user_objs: dict[str, User] = {}
        for key, full_name, email, role, dept_key, organization in users:
            user_objs[key] = upsert(
                session,
                User,
                key,
                {
                    "organization_id": organization.id,
                    "department_id": departments[dept_key].id
                    if dept_key and organization is org_main
                    else (dept_isolation.id if dept_key else None),
                    "full_name": full_name,
                    "email": email,
                    "normalized_email": normalize_email(email),
                    "password_hash": password_hash,
                    "role": role,
                    "is_active": True,
                    "is_demo": True,
                },
            )
        session.flush()

        # ---------------- contractors and contracts ----------------
        contractor_a = upsert(
            session,
            Contractor,
            "contractor:a",
            {
                "organization_id": org_main.id,
                "name": "DEMO Sahyog Infra Pvt Ltd",
                "registration_number": "DEMO-REG-C-001",
                "contact_email": "contracts@sahyog.roadguard.ai",
                "contact_phone": "+91-00000-00001",
                "source_reference": "DEMO-CONTRACTOR-REG-001",
                "is_demo": True,
            },
        )
        contractor_b = upsert(
            session,
            Contractor,
            "contractor:b",
            {
                "organization_id": org_main.id,
                "name": "DEMO Kalinga Roadworks",
                "registration_number": "DEMO-REG-C-002",
                "contact_email": "contracts@kalinga.roadguard.ai",
                "contact_phone": "+91-00000-00002",
                "source_reference": "DEMO-CONTRACTOR-REG-002",
                "is_demo": True,
            },
        )
        session.flush()

        # ---------------- assets ----------------
        assets = {
            "junction": upsert(
                session,
                Asset,
                "asset:janpath-junction",
                {
                    "organization_id": org_main.id,
                    "department_id": departments["roads"].id,
                    "asset_code": "DEMO-AST-001",
                    "name": "DEMO Janpath Junction",
                    "asset_type": AssetType.INTERSECTION,
                    "address": "DEMO Janpath Road at Sector 1 crossing, Bhubaneswar",
                    "location": point(20.2961, 85.8245),
                    "latitude": 20.2961,
                    "longitude": 85.8245,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "condition_status": ConditionStatus.FAIR,
                    "source_reference": "DEMO-ASSET-REG-2025-001",
                    "last_inspected_at": now,
                    "is_demo": True,
                },
            ),
            "signal": upsert(
                session,
                Asset,
                "asset:janpath-signal",
                {
                    "organization_id": org_main.id,
                    "department_id": departments["traffic"].id,
                    "asset_code": "DEMO-AST-002",
                    "name": "DEMO Janpath Signal North",
                    "asset_type": AssetType.TRAFFIC_SIGNAL,
                    "address": "DEMO Janpath Road, north approach",
                    "location": point(20.2964, 85.8249),
                    "latitude": 20.2964,
                    "longitude": 85.8249,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "condition_status": ConditionStatus.GOOD,
                    "source_reference": "DEMO-ASSET-REG-2025-002",
                    "is_demo": True,
                },
            ),
            "crossing": upsert(
                session,
                Asset,
                "asset:janpath-crossing",
                {
                    "organization_id": org_main.id,
                    "department_id": departments["roads"].id,
                    "asset_code": "DEMO-AST-003",
                    "name": "DEMO Janpath Pedestrian Crossing",
                    "asset_type": AssetType.PEDESTRIAN_CROSSING,
                    "address": "DEMO Janpath Road, east crossing",
                    "location": point(20.2958, 85.8241),
                    "latitude": 20.2958,
                    "longitude": 85.8241,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "condition_status": ConditionStatus.POOR,
                    "source_reference": "DEMO-ASSET-REG-2025-003",
                    "is_demo": True,
                },
            ),
            "ring_road": upsert(
                session,
                Asset,
                "asset:ring-road-curve",
                {
                    "organization_id": org_main.id,
                    "department_id": departments["roads"].id,
                    "asset_code": "DEMO-AST-004",
                    "name": "DEMO Ring Road Sector 4 Curve",
                    "asset_type": AssetType.ROAD_SEGMENT,
                    "address": "DEMO Ring Road Sector 4",
                    "location": point(20.3011, 85.8302),
                    "latitude": 20.3011,
                    "longitude": 85.8302,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "condition_status": ConditionStatus.POOR,
                    "source_reference": "DEMO-ASSET-REG-2025-004",
                    "is_demo": True,
                },
            ),
            "unowned": upsert(
                session,
                Asset,
                "asset:unowned-light",
                {
                    "organization_id": org_main.id,
                    "department_id": None,
                    "asset_code": "DEMO-AST-005",
                    "name": "DEMO Bypass Curve Street Light (ownership unresolved)",
                    "asset_type": AssetType.STREET_LIGHT,
                    "address": "DEMO Bypass Curve",
                    "location": point(20.2839, 85.8412),
                    "latitude": 20.2839,
                    "longitude": 85.8412,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "condition_status": ConditionStatus.UNKNOWN,
                    "source_reference": "DEMO-ASSET-REG-2025-005",
                    "is_demo": True,
                },
            ),
            "unlocated": upsert(
                session,
                Asset,
                "asset:unlocated-drain",
                {
                    "organization_id": org_main.id,
                    "department_id": departments["roads"].id,
                    "asset_code": "DEMO-AST-006",
                    "name": "DEMO Drainage Asset (location unknown)",
                    "asset_type": AssetType.DRAINAGE,
                    "address": None,
                    "location": None,
                    "latitude": None,
                    "longitude": None,
                    "location_quality": LocationQuality.UNKNOWN,
                    "condition_status": ConditionStatus.UNKNOWN,
                    "source_reference": "DEMO-ASSET-REG-2025-006",
                    "is_demo": True,
                },
            ),
        }
        _isolation_asset = upsert(
            session,
            Asset,
            "asset:isolation-001",
            {
                "organization_id": org_isolation.id,
                "department_id": dept_isolation.id,
                "asset_code": "DEMO-AST-ISO-001",
                "name": "DEMO Isolation Asset",
                "asset_type": AssetType.ROAD_SEGMENT,
                "address": "DEMO Isolation Road",
                "location": point(22.2604, 84.8536),
                "latitude": 22.2604,
                "longitude": 84.8536,
                "location_quality": LocationQuality.APPROXIMATE,
                "condition_status": ConditionStatus.GOOD,
                "source_reference": "DEMO-ASSET-REG-ISO-001",
                "is_demo": True,
            },
        )
        session.flush()

        contract_active = upsert(
            session,
            Contract,
            "contract:active",
            {
                "organization_id": org_main.id,
                "contractor_id": contractor_a.id,
                "department_id": departments["roads"].id,
                "contract_number": "DEMO-CON-001",
                "contract_type": "maintenance",
                "scope_description": (
                    "DEMO road maintenance, surface repair and pedestrian crossing upkeep for "
                    "the Janpath corridor."
                ),
                "start_date": date(2024, 1, 1),
                "end_date": date(2027, 12, 31),
                "warranty_end_date": date(2028, 6, 30),
                "source_reference": "DEMO-CONTRACT-REG-001",
                "is_demo": True,
            },
        )
        contract_expired = upsert(
            session,
            Contract,
            "contract:expired",
            {
                "organization_id": org_main.id,
                "contractor_id": contractor_b.id,
                "department_id": departments["traffic"].id,
                "contract_number": "DEMO-CON-002",
                "contract_type": "signal_maintenance",
                "scope_description": "DEMO traffic signal maintenance for the north approach.",
                "start_date": date(2023, 1, 1),
                "end_date": date(2024, 12, 31),
                "warranty_end_date": None,
                "source_reference": "DEMO-CONTRACT-REG-002",
                "is_demo": True,
            },
        )
        session.flush()

        for key, contract, asset in (
            ("contract-asset:active-junction", contract_active, assets["junction"]),
            ("contract-asset:active-crossing", contract_active, assets["crossing"]),
            ("contract-asset:expired-signal", contract_expired, assets["signal"]),
        ):
            upsert(
                session,
                ContractAsset,
                key,
                {
                    "organization_id": org_main.id,
                    "contract_id": contract.id,
                    "asset_id": asset.id,
                    "scope_notes": "Synthetic association for demonstration.",
                },
            )
        session.flush()

        # ---------------- cameras ----------------
        _cameras = {
            "north": upsert(
                session,
                Camera,
                "camera:janpath-north",
                {
                    "organization_id": org_main.id,
                    "camera_code": "DEMO-CAM-001",
                    "name": "DEMO Janpath Junction North",
                    "description": "Synthetic demonstration camera associated with uploaded clips.",
                    "location": point(20.2961, 85.8245),
                    "latitude": 20.2961,
                    "longitude": 85.8245,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "source_type": CameraSourceType.UPLOAD_ASSOCIATION,
                    "connection_status": CameraConnectionStatus.UNKNOWN,
                    "is_enabled": True,
                    "is_demo": True,
                },
            ),
            "replay": upsert(
                session,
                Camera,
                "camera:janpath-replay",
                {
                    "organization_id": org_main.id,
                    "camera_code": "DEMO-CAM-002",
                    "name": "DEMO Janpath Simulated Live Replay",
                    "description": "Plays a stored demo clip; always labelled SIMULATED LIVE.",
                    "location": point(20.2963, 85.8242),
                    "latitude": 20.2963,
                    "longitude": 85.8242,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "source_type": CameraSourceType.DEMO_REPLAY,
                    "connection_status": CameraConnectionStatus.OFFLINE,
                    "is_enabled": True,
                    "is_demo": True,
                },
            ),
            "ring_road": upsert(
                session,
                Camera,
                "camera:ring-road",
                {
                    "organization_id": org_main.id,
                    "camera_code": "DEMO-CAM-003",
                    "name": "DEMO Ring Road Sector 4",
                    "description": "Second demonstration camera for map coverage.",
                    "location": point(20.3011, 85.8302),
                    "latitude": 20.3011,
                    "longitude": 85.8302,
                    "location_quality": LocationQuality.APPROXIMATE,
                    "source_type": CameraSourceType.UPLOAD_ASSOCIATION,
                    "connection_status": CameraConnectionStatus.UNKNOWN,
                    "is_enabled": True,
                    "is_demo": True,
                },
            ),
        }
        upsert(
            session,
            Camera,
            "camera:isolation-001",
            {
                "organization_id": org_isolation.id,
                "camera_code": "DEMO-CAM-ISO-001",
                "name": "DEMO Isolation Camera",
                "description": "Second-tenant camera used by isolation tests.",
                "location": point(22.2604, 84.8536),
                "latitude": 22.2604,
                "longitude": 84.8536,
                "location_quality": LocationQuality.APPROXIMATE,
                "source_type": CameraSourceType.UPLOAD_ASSOCIATION,
                "connection_status": CameraConnectionStatus.UNKNOWN,
                "is_enabled": True,
                "is_demo": True,
            },
        )
        session.flush()

        # ---------------- representative workflow graph ----------------
        # The tenant-isolation suite needs at least one row of each kind before it
        # can prove a second organisation cannot read it. Seeding one incident,
        # video, job, evidence artefact, investigation and work order keeps a cold
        # `seed -> pytest` run skip-free instead of silently proving nothing.
        demo_video = upsert(
            session,
            Video,
            "video:demo-near-miss",
            {
                "organization_id": org_main.id,
                "camera_id": _cameras["north"].id,
                "uploaded_by": user_objs["user:ops"].id,
                "storage_key": "demo/videos/demo-near-miss.mp4",
                "original_filename": "DEMO-near-miss.mp4",
                "content_type": "video/mp4",
                "file_size_bytes": 524288,
                "checksum_sha256": "0" * 64,
                "source_type": VideoSourceType.UPLOAD,
                "recorded_at": now,
                "duration_seconds": 12.0,
                "width": 1280,
                "height": 720,
                "frame_rate": 25.0,
                "status": VideoStatus.PROCESSED,
                "is_demo": True,
            },
        )
        # Flush each parent: these rows are linked by raw ids (no ORM relationship),
        # so SQLAlchemy cannot infer the insert order on its own.
        session.flush()
        demo_job = upsert(
            session,
            AIJob,
            "job:demo-near-miss",
            {
                "organization_id": org_main.id,
                "video_id": demo_video.id,
                "job_type": "video_analysis",
                "status": JobStatus.SUCCEEDED,
                "stage": JobStage.COMPLETED,
                "progress": 100,
                "idempotency_key": "demo-near-miss",
                "model_name": "synthetic-scene-colour-marker",
                "model_version": "1.0",
                "config_snapshot": {"source": "seed"},
                "result_summary": {"events": 1, "is_demo": True},
                "started_at": now,
                "completed_at": now,
                "created_by": user_objs["user:ops"].id,
            },
        )
        session.flush()
        demo_incident = upsert(
            session,
            Incident,
            "incident:demo-near-miss",
            {
                "organization_id": org_main.id,
                "camera_id": _cameras["north"].id,
                "video_id": demo_video.id,
                "ai_job_id": demo_job.id,
                "incident_type": IncidentType.NEAR_MISS_CANDIDATE,
                "source_kind": IncidentSourceKind.AI_CANDIDATE,
                "severity": Severity.MEDIUM,
                "model_score": 0.72,
                "event_time": now,
                "start_offset_seconds": 3.0,
                "end_offset_seconds": 9.0,
                "location": point(20.2961, 85.8245),
                "latitude": 20.2961,
                "longitude": 85.8245,
                "location_quality": LocationQuality.APPROXIMATE,
                "description": "DEMO synthetic near-miss used by isolation tests.",
                "review_status": ReviewStatus.CONFIRMED,
                "reviewed_by": user_objs["user:reviewer"].id,
                "reviewed_at": now,
                "model_name": "synthetic-scene-colour-marker",
                "model_version": "1.0",
                "rule_name": "demo_near_miss",
                "rule_version": "1.0",
                "is_demo": True,
            },
        )
        session.flush()
        upsert(
            session,
            Evidence,
            "evidence:demo-frame",
            {
                "organization_id": org_main.id,
                "incident_id": demo_incident.id,
                "storage_key": "demo/evidence/demo-frame.jpg",
                "evidence_type": EvidenceType.ANNOTATED_FRAME,
                "label": "DEMO annotated frame",
                "content_type": "image/jpeg",
                "original_filename": "DEMO-frame.jpg",
                "file_size_bytes": 32768,
                "checksum_sha256": "1" * 64,
                "timestamp_in_video": 4.5,
                "created_by": user_objs["user:ops"].id,
                "is_demo": True,
            },
        )
        demo_investigation = upsert(
            session,
            Investigation,
            "investigation:demo-case",
            {
                "organization_id": org_main.id,
                "case_number": "DEMO-INV-0001",
                "incident_id": demo_incident.id,
                "assigned_department_id": departments["roads"].id,
                "title": "DEMO investigation: Janpath near-miss",
                "summary": "Synthetic case seeded for isolation and UI coverage.",
                "observed_facts": ["DEMO: a near-miss candidate was reviewed and confirmed."],
                "hypotheses": [],
                "missing_information": ["DEMO: field verification not yet scheduled."],
                "status": InvestigationStatus.OPEN,
                "opened_by": user_objs["user:ops"].id,
                "is_demo": True,
            },
        )
        upsert(
            session,
            WorkOrder,
            "work-order:demo-case",
            {
                "organization_id": org_main.id,
                "work_order_number": "DEMO-WO-0001",
                "investigation_id": demo_investigation.id,
                "assigned_department_id": departments["roads"].id,
                "title": "DEMO work order: inspect Janpath crossing",
                "description": "Synthetic work order seeded for isolation and UI coverage.",
                "status": WorkOrderStatus.PENDING,
                "priority": Priority.HIGH,
                "due_date": now.date(),
                "created_by": user_objs["user:ops"].id,
                "is_demo": True,
            },
        )
        session.flush()

        # ---------------- historical accident records ----------------
        if ACCIDENT_CSV.exists():
            with ACCIDENT_CSV.open(encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    reference = (row.get("external_reference") or "").strip()
                    if not reference:
                        continue
                    values = {
                        "organization_id": org_main.id,
                        "external_reference": reference,
                        "source_name": row["source_name"].strip(),
                        "source_reference": row["source_reference"].strip(),
                        "accident_type": (row.get("accident_type") or "").strip() or None,
                        "severity": (row.get("severity") or "").strip() or None,
                        "road_name": (row.get("road_name") or "").strip() or None,
                        "verification_status": AccidentVerificationStatus(
                            (row.get("verification_status") or "unverified").strip().lower()
                        ),
                        "is_demo": True,
                    }
                    latitude = (row.get("latitude") or "").strip()
                    longitude = (row.get("longitude") or "").strip()
                    if latitude and longitude:
                        values["location"] = point(float(latitude), float(longitude))
                        values["latitude"] = float(latitude)
                        values["longitude"] = float(longitude)
                        values["location_quality"] = LocationQuality.APPROXIMATE
                    accident_time = (row.get("accident_time") or "").strip()
                    if accident_time:
                        parsed = datetime.fromisoformat(accident_time.replace("Z", "+00:00"))
                        values["accident_time"] = parsed
                        values["accident_date"] = parsed.date()
                    upsert(session, AccidentRecord, f"accident:{reference}", values)
        session.flush()

    print("Seed complete. DEMO organizations: demo-city, demo-isolation")
    printf_users()


def printf_users() -> None:
    print("\nDEMO sign-in accounts (password from DEMO_SEED_PASSWORD):")
    for email, role in (
        ("admin@demo.roadguard.ai", "org_admin"),
        ("ops@demo.roadguard.ai", "police_admin"),
        ("reviewer@demo.roadguard.ai", "reviewer"),
        ("engineer@demo.roadguard.ai", "department_engineer"),
        ("auditor@demo.roadguard.ai", "auditor"),
        ("ops@isolation.roadguard.ai", "police_admin (second tenant)"),
    ):
        print(f"  {email:<26} {role}")
    print("\nAll records are synthetic and labelled DEMO. Do not present them as real statistics.")


def reset_demo_data() -> None:
    """Remove seed rows only (privileged role). Leaves schema untouched."""

    engine = get_privileged_engine()
    tables_in_order = [
        "evidence",
        "verifications",
        "work_order_status_history",
        "work_orders",
        "recommendations",
        "investigations",
        "incidents",
        "detections",
        "ai_jobs",
        "videos",
        "live_stream_sessions",
        "contract_assets",
        "contracts",
        "assets",
        "cameras",
        "accident_records",
        "hotspot_analyses",
        "audit_logs",
        "refresh_sessions",
        "contractors",
        "users",
        "departments",
        "organizations",
    ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE "
                + ", ".join(tables_in_order)
                + " RESTART IDENTITY CASCADE"
            )
        )
    print("Demo data reset.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed ROADGUARD AI demo data")
    parser.add_argument("--reset-demo-data", action="store_true", help="truncate demo tables first")
    args = parser.parse_args()
    if args.reset_demo_data:
        reset_demo_data()
    seed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
