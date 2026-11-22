"""Exercise every documented API operation, not just the interesting ones.

This suite is deliberately exhaustive. It walks the real lifecycle in dependency
order (registry -> camera -> upload -> job -> incident -> hotspots -> investigation
-> recommendation -> work order -> completion -> verification) and asserts that each
call returned its intended outcome. At the end it diffs the set of operations it
touched against ``app.openapi()`` and fails if any documented operation was never
called, so a newly added route cannot ship untested.

It also proves that no protected operation answers an unauthenticated caller.

The workflow creates its own uniquely named records; nothing seeded is mutated.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import cv2
import numpy as np
from fastapi.testclient import TestClient

DEMO_PASSWORD = os.environ.get("DEMO_SEED_PASSWORD", "RoadguardDemo#2026")

ADMIN = "admin@demo.roadguard.ai"
POLICE = "ops@demo.roadguard.ai"
REVIEWER = "reviewer@demo.roadguard.ai"
ENGINEER = "engineer@demo.roadguard.ai"
AUDITOR = "auditor@demo.roadguard.ai"

# Operations that are intentionally reachable without a session:
# * health probes for the orchestrator
# * the permission catalog (static, non-tenant reference data)
# * the CSRF bootstrap cookie the login form needs before it can POST
# * logout, which is an idempotent cookie clear and never touches data
PUBLIC_OPERATIONS = {
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("GET", "/api/v1/meta/permissions"),
    ("GET", "/api/v1/auth/csrf"),
    ("POST", "/api/v1/auth/logout"),
}


class EndpointCalls:
    """Thin recorder that keeps the exercised-operation set honest."""

    def __init__(self, client: TestClient, login_as) -> None:
        self.client = client
        self.login_as = login_as
        self.covered: set[tuple[str, str]] = set()

    def call(
        self,
        method: str,
        url: str,
        *,
        template: str | None = None,
        expect: tuple[int, ...] | int = (200,),
        role: str | None = None,
        **kwargs: Any,
    ):
        if role:
            self.login_as(role)
        response = self.client.request(method, url, **kwargs)
        self.covered.add((method.upper(), template or url))
        expected = (expect,) if isinstance(expect, int) else expect
        assert response.status_code in expected, (
            f"{method} {url} -> {response.status_code}, expected {expected}: "
            f"{response.text[:500]}"
        )
        return response


def _error_code(response) -> str:
    body = response.json()
    return str(body.get("error", {}).get("code") or body.get("code") or "")


def _tiny_clip(path) -> bytes:
    """A real, decodable MP4 so container validation is not bypassed."""
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (160, 120)
    )
    assert writer.isOpened(), "OpenCV could not open an MP4 writer"
    for index in range(10):
        frame = np.full((120, 160, 3), 40 + index * 8, dtype=np.uint8)
        cv2.rectangle(frame, (10 + index * 4, 40), (50 + index * 4, 80), (0, 200, 255), -1)
        writer.write(frame)
    writer.release()
    return path.read_bytes()


def _png_bytes() -> bytes:
    image = np.full((32, 32, 3), 210, dtype=np.uint8)
    cv2.rectangle(image, (4, 4), (28, 28), (20, 20, 20), 2)
    ok, buffer = cv2.imencode(".png", image)
    assert ok
    return buffer.tobytes()


def test_every_documented_operation_is_exercised(client, login_as, tmp_path) -> None:
    calls = EndpointCalls(client, login_as)
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)

    # --- health and metadata ------------------------------------------------
    calls.call("GET", "/api/v1/health/live")
    calls.call("GET", "/api/v1/health/ready")
    calls.call("GET", "/api/v1/meta/permissions")
    calls.call("GET", "/api/v1/meta/bootstrap", role=ADMIN)

    # --- authentication -----------------------------------------------------
    login = calls.call(
        "POST",
        "/api/v1/auth/login",
        json={"email": ADMIN, "password": DEMO_PASSWORD},
        expect=200,
    )
    assert login.json()["data"]["user"]["email"] == ADMIN
    calls.call("GET", "/api/v1/auth/me")
    calls.call("GET", "/api/v1/auth/csrf")

    # A throwaway account covers change-password, refresh and logout without
    # touching any seeded demo identity.
    temp_email = f"audit.temp.{suffix}@demo.roadguard.ai"
    temp_password = "AuditTempPassword#2026"
    temp_user = calls.call(
        "POST",
        "/api/v1/users",
        role=ADMIN,
        json={
            "full_name": "Audit Temp",
            "email": temp_email,
            "role": "auditor",
            "password": temp_password,
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call("GET", "/api/v1/users", role=ADMIN)
    calls.call(
        "PATCH",
        f"/api/v1/users/{temp_user['id']}",
        template="/api/v1/users/{user_id}",
        role=ADMIN,
        json={"full_name": "Audit Temp User"},
    )

    with TestClient(client.app) as temp_client:
        signed_in = temp_client.post(
            "/api/v1/auth/login", json={"email": temp_email, "password": temp_password}
        )
        assert signed_in.status_code == 200, signed_in.text
        temp_client.headers.update(
            {"x-csrf-token": signed_in.json()["data"]["user"]["csrf_token"]}
        )
        refreshed = temp_client.post("/api/v1/auth/refresh")
        assert refreshed.status_code == 200, refreshed.text
        temp_client.headers.update(
            {"x-csrf-token": refreshed.json()["data"]["user"]["csrf_token"]}
        )
        changed = temp_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temp_password,
                "new_password": "AuditTempPassword#2027",
            },
        )
        assert changed.status_code in {200, 204}, changed.text
        logged_out = temp_client.post("/api/v1/auth/logout")
        assert logged_out.status_code in {200, 204}, logged_out.text
        calls.covered.add(("POST", "/api/v1/auth/refresh"))
        calls.covered.add(("POST", "/api/v1/auth/change-password"))
        calls.covered.add(("POST", "/api/v1/auth/logout"))
        # The session must really be gone after logout.
        assert temp_client.get("/api/v1/auth/me").status_code == 401

    calls.call(
        "PATCH",
        f"/api/v1/users/{temp_user['id']}",
        template="/api/v1/users/{user_id}",
        role=ADMIN,
        json={"is_active": False},
    )

    # --- registry -----------------------------------------------------------
    calls.call("GET", "/api/v1/departments")
    department = calls.call(
        "POST",
        "/api/v1/departments",
        role=ADMIN,
        json={
            "name": f"Audit Public Works {suffix}",
            "department_type": "public_works",
            "contact_email": f"works.{suffix}@demo.roadguard.ai",
            "source_reference": "audit-endpoint-suite",
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call(
        "GET",
        f"/api/v1/departments/{department['id']}",
        template="/api/v1/departments/{department_id}",
    )

    calls.call("GET", "/api/v1/contractors")
    contractor = calls.call(
        "POST",
        "/api/v1/contractors",
        role=ADMIN,
        json={
            "name": f"Audit Contractor {suffix}",
            "registration_number": f"REG-{suffix}",
            "contact_phone": "+91-0000000000",
            "source_reference": "audit-endpoint-suite",
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call(
        "GET",
        f"/api/v1/contractors/{contractor['id']}",
        template="/api/v1/contractors/{contractor_id}",
    )

    latitude, longitude = 20.2961, 85.8245
    calls.call("GET", "/api/v1/assets")
    asset = calls.call(
        "POST",
        "/api/v1/assets",
        role=ADMIN,
        json={
            "asset_code": f"AST-{suffix}",
            "name": f"Audit Intersection {suffix}",
            "asset_type": "intersection",
            "department_id": department["id"],
            "condition_status": "fair",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "quality": "surveyed",
            },
            "source_reference": "audit-endpoint-suite",
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call("GET", f"/api/v1/assets/{asset['id']}", template="/api/v1/assets/{asset_id}")
    calls.call(
        "PATCH",
        f"/api/v1/assets/{asset['id']}",
        template="/api/v1/assets/{asset_id}",
        json={"condition_status": "poor", "source_reference": "audit-updated"},
    )
    calls.call(
        "GET",
        f"/api/v1/assets/{asset['id']}/responsibility",
        template="/api/v1/assets/{asset_id}/responsibility",
    )
    calls.call(
        "GET",
        "/api/v1/assets/nearby",
        params={"latitude": latitude, "longitude": longitude, "radius_meters": 500},
    )

    calls.call("GET", "/api/v1/contracts")
    contract = calls.call(
        "POST",
        "/api/v1/contracts",
        role=ADMIN,
        json={
            "contractor_id": contractor["id"],
            "department_id": department["id"],
            "contract_number": f"CT-{suffix}",
            "contract_type": "maintenance",
            "scope_description": "Audit coverage contract for surface maintenance.",
            "start_date": (now - timedelta(days=365)).date().isoformat(),
            "end_date": (now + timedelta(days=365)).date().isoformat(),
            "asset_ids": [asset["id"]],
            "source_reference": "audit-endpoint-suite",
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call(
        "GET", f"/api/v1/contracts/{contract['id']}", template="/api/v1/contracts/{contract_id}"
    )

    # --- cameras, live modes ------------------------------------------------
    calls.call("GET", "/api/v1/cameras")
    camera = calls.call(
        "POST",
        "/api/v1/cameras",
        role=ADMIN,
        json={
            "camera_code": f"CAM-{suffix}",
            "name": f"Audit Camera {suffix}",
            "source_type": "upload_association",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "quality": "approximate",
            },
            "description": "Created by the endpoint coverage suite.",
        },
        expect=(200, 201),
    ).json()["data"]
    camera_id = camera["id"]
    calls.call("GET", f"/api/v1/cameras/{camera_id}", template="/api/v1/cameras/{camera_id}")
    calls.call(
        "PATCH",
        f"/api/v1/cameras/{camera_id}",
        template="/api/v1/cameras/{camera_id}",
        json={"description": "Updated by the endpoint coverage suite."},
    )
    calls.call(
        "GET", f"/api/v1/cameras/{camera_id}/health", template="/api/v1/cameras/{camera_id}/health"
    )
    calls.call(
        "POST", f"/api/v1/cameras/{camera_id}/disable", template="/api/v1/cameras/{camera_id}/disable"
    )
    calls.call(
        "POST", f"/api/v1/cameras/{camera_id}/enable", template="/api/v1/cameras/{camera_id}/enable"
    )
    simulated = calls.call(
        "POST",
        f"/api/v1/cameras/{camera_id}/live/simulate",
        template="/api/v1/cameras/{camera_id}/live/simulate",
        json={"confirm": True},
    ).json()["data"]
    assert simulated["is_simulated"] is True
    calls.call(
        "POST",
        f"/api/v1/cameras/{camera_id}/live/stop",
        template="/api/v1/cameras/{camera_id}/live/stop",
    )
    # Real RTSP must fail closed (not configured here), never 5xx.
    rtsp = calls.call(
        "POST",
        f"/api/v1/cameras/{camera_id}/live/rtsp",
        template="/api/v1/cameras/{camera_id}/live/rtsp",
        json={"confirm": True},
        expect=(200, 400, 403, 409, 422, 503),
    )
    if rtsp.status_code == 200:
        detail = rtsp.json()["data"]
        assert detail["status"] in {"blocked", "disconnected", "stopped"}

    # --- upload, job queue --------------------------------------------------
    clip = _tiny_clip(tmp_path / "audit_clip.mp4")
    upload = calls.call(
        "POST",
        "/api/v1/videos/upload-url",
        json={
            "filename": f"audit_{suffix}.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": len(clip),
            "camera_id": camera_id,
        },
        expect=(200, 201),
    ).json()["data"]
    upload_url = upload["upload_url"]
    stored = client.put(
        upload_url,
        content=clip,
        headers={"content-type": "video/mp4"},
    )
    calls.covered.add(("PUT", "/api/v1/storage/upload/{token}"))
    assert stored.status_code == 204, stored.text

    video = calls.call(
        "POST",
        f"/api/v1/videos/{upload['video_id']}/complete-upload",
        template="/api/v1/videos/{video_id}/complete-upload",
        expect=(200, 201),
    ).json()["data"]
    calls.call("GET", "/api/v1/videos")
    calls.call("GET", f"/api/v1/videos/{video['id']}", template="/api/v1/videos/{video_id}")
    playback = calls.call(
        "GET",
        f"/api/v1/videos/{video['id']}/playback-url",
        template="/api/v1/videos/{video_id}/playback-url",
    ).json()["data"]["url"]
    if playback.startswith("/"):
        assert client.get(playback).status_code == 200

    job = calls.call(
        "POST",
        f"/api/v1/videos/{video['id']}/process",
        template="/api/v1/videos/{video_id}/process",
        json={"force_reprocess": False},
    ).json()["data"]
    calls.call("GET", "/api/v1/jobs")
    calls.call("GET", f"/api/v1/jobs/{job['id']}", template="/api/v1/jobs/{job_id}")
    # Retry is only legal for a failed/cancelled job; the guard must say so.
    retry = calls.call(
        "POST",
        f"/api/v1/jobs/{job['id']}/retry",
        template="/api/v1/jobs/{job_id}/retry",
        expect=409,
    )
    assert _error_code(retry) == "JOB_NOT_RETRYABLE"

    # --- incidents ----------------------------------------------------------
    calls.call("GET", "/api/v1/incidents/analytics")
    calls.call("GET", "/api/v1/incidents", params={"limit": 5})
    incident = calls.call(
        "POST",
        "/api/v1/incidents/manual",
        role=POLICE,
        json={
            "incident_type": "manual_road_hazard",
            "description": "Audit: standing water over the pedestrian crossing.",
            "event_time": (now - timedelta(hours=2)).isoformat(),
            "severity": "medium",
            "camera_id": camera_id,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "quality": "approximate",
            },
        },
        expect=(200, 201),
    ).json()["data"]
    calls.call(
        "GET",
        f"/api/v1/incidents/{incident['id']}",
        template="/api/v1/incidents/{incident_id}",
    )
    calls.call(
        "GET",
        f"/api/v1/incidents/{incident['id']}/evidence",
        template="/api/v1/incidents/{incident_id}/evidence",
    )
    reviewed = calls.call(
        "PATCH",
        f"/api/v1/incidents/{incident['id']}/review",
        template="/api/v1/incidents/{incident_id}/review",
        role=POLICE,
        json={"decision": "confirmed", "notes": "Confirmed during endpoint audit."},
    ).json()["data"]
    assert reviewed["review_status"] == "confirmed"

    # --- historical accidents ----------------------------------------------
    calls.call("GET", "/api/v1/accident-records", params={"limit": 5})
    csv_body = (
        "external_reference,source_name,source_reference,latitude,longitude,"
        "accident_time,accident_type,severity,road_name,verification_status\n"
        f"AUD-{suffix},Audit Fixture,audit://{suffix}/1,{latitude},{longitude},"
        f"{now.isoformat()},rear_end,low,Audit Road,unverified\n"
    ).encode()
    imported = calls.call(
        "POST",
        "/api/v1/accident-records/import",
        role=POLICE,
        files={"file": (f"audit_{suffix}.csv", csv_body, "text/csv")},
    ).json()["data"]
    assert imported["imported"] == 1, imported

    # --- hotspots -----------------------------------------------------------
    analysis = calls.call(
        "POST",
        "/api/v1/hotspots/analyze",
        role=POLICE,
        json={"radius_meters": 500, "min_size": 2},
    ).json()["data"]
    calls.call("GET", "/api/v1/hotspots")
    calls.call(
        "GET", "/api/v1/hotspots/geojson", params={"analysis_id": analysis["id"]}
    )
    calls.call(
        "GET",
        f"/api/v1/hotspots/{analysis['id']}",
        template="/api/v1/hotspots/{hotspot_id}",
    )

    # --- investigation, recommendation -------------------------------------
    calls.call("GET", "/api/v1/investigations")
    investigation = calls.call(
        "POST",
        "/api/v1/investigations",
        role=POLICE,
        json={
            "incident_id": incident["id"],
            "asset_id": asset["id"],
            "title": f"Audit investigation {suffix}",
            "summary": "Endpoint coverage investigation.",
            "assigned_department_id": department["id"],
            "observed_facts": ["Standing water recorded on the crossing."],
            "missing_information": ["Drain survey for the junction."],
        },
        expect=(200, 201),
    ).json()["data"]
    inv_id = investigation["id"]
    calls.call(
        "GET", f"/api/v1/investigations/{inv_id}", template="/api/v1/investigations/{investigation_id}"
    )
    calls.call(
        "PATCH",
        f"/api/v1/investigations/{inv_id}",
        template="/api/v1/investigations/{investigation_id}",
        role=POLICE,
        json={"status": "under_review", "title": f"Audit investigation {suffix} (review)"},
    )
    calls.call(
        "POST",
        f"/api/v1/investigations/{inv_id}/analyze",
        template="/api/v1/investigations/{investigation_id}/analyze",
        role=POLICE,
    )
    calls.call(
        "POST",
        f"/api/v1/investigations/{inv_id}/assign",
        template="/api/v1/investigations/{investigation_id}/assign",
        role=POLICE,
        json={"department_id": department["id"], "note": "Assigned by audit suite."},
    )
    calls.call(
        "GET",
        f"/api/v1/investigations/{inv_id}/recommendations",
        template="/api/v1/investigations/{investigation_id}/recommendations",
    )
    recommendation = calls.call(
        "POST",
        f"/api/v1/investigations/{inv_id}/recommendations",
        template="/api/v1/investigations/{investigation_id}/recommendations",
        role=POLICE,
        json={
            "recommendation_text": "Clear and re-grade the junction drainage before monsoon.",
            "rationale": "Standing water was observed on the crossing.",
            "priority": "medium",
            "limitations": ["Site survey not yet completed."],
        },
        expect=(200, 201),
    ).json()["data"]
    approved = calls.call(
        "PATCH",
        f"/api/v1/recommendations/{recommendation['id']}/review",
        template="/api/v1/recommendations/{recommendation_id}/review",
        role=REVIEWER,
        json={"decision": "approved", "notes": "Approved independently."},
    ).json()["data"]
    assert approved["status"] == "approved"

    # --- work order, completion, verification ------------------------------
    calls.call("GET", "/api/v1/work-orders")
    work_order = calls.call(
        "POST",
        "/api/v1/work-orders",
        role=POLICE,
        json={
            "investigation_id": inv_id,
            "recommendation_id": recommendation["id"],
            "assigned_department_id": department["id"],
            "title": f"Audit drainage repair {suffix}",
            "description": "Clear and re-grade the junction drainage.",
            "priority": "medium",
        },
        expect=(200, 201),
    ).json()["data"]
    wo_id = work_order["id"]
    calls.call(
        "GET", f"/api/v1/work-orders/{wo_id}", template="/api/v1/work-orders/{work_order_id}"
    )
    # A new order is PENDING; the state machine only allows PENDING -> ASSIGNED ->
    # IN_PROGRESS, so both transitions are exercised (and the first one is proven).
    assigned = calls.call(
        "PATCH",
        f"/api/v1/work-orders/{wo_id}",
        template="/api/v1/work-orders/{work_order_id}",
        role=POLICE,
        json={"status": "assigned", "note": "Assigned to the drainage crew."},
    ).json()["data"]
    assert assigned["status"] == "assigned"
    transitioned = calls.call(
        "PATCH",
        f"/api/v1/work-orders/{wo_id}",
        template="/api/v1/work-orders/{work_order_id}",
        role=POLICE,
        json={"status": "in_progress", "note": "Crew mobilised."},
    ).json()["data"]
    assert transitioned["status"] == "in_progress"

    evidence = calls.call(
        "POST",
        f"/api/v1/work-orders/{wo_id}/evidence",
        template="/api/v1/work-orders/{work_order_id}/evidence",
        role=ENGINEER,
        files={"file": ("completion.png", _png_bytes(), "image/png")},
        data={"label": "After repair"},
        expect=(200, 201),
    ).json()["data"]
    calls.call(
        "GET",
        f"/api/v1/evidence/{evidence['id']}",
        template="/api/v1/evidence/{evidence_id}",
    )
    evidence_url = calls.call(
        "GET",
        f"/api/v1/evidence/{evidence['id']}/url",
        template="/api/v1/evidence/{evidence_id}/url",
    ).json()["data"]["url"]
    if evidence_url.startswith("/"):
        fetched = client.get(evidence_url)
        assert fetched.status_code == 200
        calls.covered.add(("GET", "/api/v1/storage/download/{token}"))
        download_token = evidence_url.rsplit("/", 1)[-1]
        exists = calls.call(
            "GET",
            f"/api/v1/storage/local-object-exists/{download_token}",
            template="/api/v1/storage/local-object-exists/{token}",
        )
        assert exists.json()["exists"] is True
    else:
        # S3 backend: the storage routes are exercised through their token guard.
        calls.call("GET", "/api/v1/storage/download/not-a-token", expect=(400, 401, 403))
        calls.covered.add(("GET", "/api/v1/storage/download/{token}"))
        calls.call(
            "GET",
            "/api/v1/storage/local-object-exists/not-a-token",
            template="/api/v1/storage/local-object-exists/{token}",
            expect=(400, 401, 403),
        )

    completed = calls.call(
        "POST",
        f"/api/v1/work-orders/{wo_id}/completion",
        template="/api/v1/work-orders/{work_order_id}/completion",
        role=ENGINEER,
        json={
            "completion_notes": "Drain cleared and crossing re-graded.",
            "evidence_ids": [evidence["id"]],
        },
    ).json()["data"]
    assert completed["status"] == "completed_pending_verification"

    verified = calls.call(
        "POST",
        f"/api/v1/work-orders/{wo_id}/verifications",
        template="/api/v1/work-orders/{work_order_id}/verifications",
        role=REVIEWER,
        json={"verification_status": "accepted", "notes": "Inspected on site."},
    ).json()["data"]
    verified_status = verified.get("status") or verified.get("work_order", {}).get("status")
    assert verified_status == "verified"

    # --- audit trail --------------------------------------------------------
    audit = calls.call("GET", "/api/v1/audit-logs", role=AUDITOR, params={"limit": 20})
    assert audit.json()["data"], "the audit trail must not be empty after a full workflow"

    # --- realtime -----------------------------------------------------------
    ticket = calls.call("POST", "/api/v1/realtime/ticket", role=POLICE).json()["data"]["ticket"]
    assert ticket
    with client.websocket_connect(f"/api/v1/ws/command-center?ticket={ticket}") as socket:
        hello = socket.receive_json()
    assert hello, "the command-center socket must greet a ticketed client"

    # --- coverage gate ------------------------------------------------------
    expected = {
        (method.upper(), path)
        for path, operations in client.app.openapi()["paths"].items()
        for method in operations
    }
    missing = sorted(expected - calls.covered)
    unexpected = sorted(calls.covered - expected)
    assert not missing, f"documented operations never exercised: {missing}"
    assert not unexpected, f"calls recorded for unknown operations: {unexpected}"


def test_anonymous_callers_cannot_reach_protected_operations(anonymous) -> None:
    """Systematic auth sweep: no protected operation may answer 2xx without a session."""
    spec = anonymous.app.openapi()
    leaked: list[str] = []
    placeholder = "00000000-0000-4000-8000-000000000000"

    for path, operations in spec["paths"].items():
        concrete = path.replace("{token}", "invalid-token")
        for parameter in ("department_id", "contractor_id", "asset_id", "contract_id",
                          "camera_id", "video_id", "job_id", "evidence_id",
                          "incident_id", "hotspot_id", "investigation_id",
                          "recommendation_id", "work_order_id", "user_id"):
            concrete = concrete.replace("{" + parameter + "}", placeholder)
        for method in operations:
            key = (method.upper(), path)
            if key in PUBLIC_OPERATIONS:
                continue
            response = anonymous.request(method.upper(), concrete)
            if 200 <= response.status_code < 300:
                leaked.append(f"{key[0]} {path} -> {response.status_code}")

    assert not leaked, f"operations reachable without a session: {leaked}"
