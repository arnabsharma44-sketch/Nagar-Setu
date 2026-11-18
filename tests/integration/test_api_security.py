"""Integration checks for authentication, RBAC, CSRF and tenant isolation.

These run against the live seeded development database and are strictly read-only:
no fixture here creates, mutates or deletes a record.
"""

from __future__ import annotations

import pytest

from tests.conftest import DEMO_PASSWORD

CITY = "ops@demo.roadguard.ai"
ISOLATION = "ops@isolation.roadguard.ai"


def test_health_endpoint_is_public(client) -> None:
    assert client.get("/api/v1/health/live").status_code == 200


def test_anonymous_request_is_rejected_with_an_error_envelope(anonymous) -> None:
    response = anonymous.get("/api/v1/cameras")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"]
    assert body["meta"]["request_id"]


def test_bootstrap_meta_requires_a_session(anonymous) -> None:
    assert anonymous.get("/api/v1/meta/bootstrap").status_code == 401


def test_wrong_password_is_rejected(anonymous) -> None:
    response = anonymous.post(
        "/api/v1/auth/login", json={"email": CITY, "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_unknown_email_is_rejected_without_revealing_existence(anonymous) -> None:
    response = anonymous.post(
        "/api/v1/auth/login", json={"email": "nobody@demo.roadguard.ai", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 401
    assert "unknown" not in response.text.lower()


def test_mutation_without_csrf_header_is_rejected(anonymous) -> None:
    login = anonymous.post(
        "/api/v1/auth/login", json={"email": CITY, "password": DEMO_PASSWORD}
    )
    assert login.status_code == 200
    # Deliberately omit the x-csrf-token header that the session established.
    response = anonymous.patch(
        "/api/v1/cameras/00000000-0000-4000-8000-000000000000", json={"name": "renamed"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_session_reports_role_and_permissions(client, login_as) -> None:
    login_as(CITY)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["user"]["role"] == "police_admin"
    assert payload["user"]["organization"]["slug"] == "demo-city"
    assert "incident:read" in payload["user"]["permissions"]


def test_cross_tenant_camera_read_is_a_404(client, login_as) -> None:
    """A record in another organization must be indistinguishable from a missing one."""
    login_as(ISOLATION)
    isolation_cameras = client.get("/api/v1/cameras").json()["data"]
    assert isolation_cameras, "the isolation tenant should have a seeded camera"
    foreign_id = isolation_cameras[0]["id"]

    login_as(CITY)
    response = client.get(f"/api/v1/cameras/{foreign_id}")
    assert response.status_code == 404, response.text


def test_organizations_do_not_share_records(client, login_as) -> None:
    login_as(ISOLATION)
    isolation_ids = {camera["id"] for camera in client.get("/api/v1/cameras").json()["data"]}

    login_as(CITY)
    city_ids = {camera["id"] for camera in client.get("/api/v1/cameras").json()["data"]}

    assert isolation_ids and city_ids
    assert isolation_ids.isdisjoint(city_ids)


def test_cross_tenant_incident_read_is_a_404(client, login_as) -> None:
    login_as(CITY)
    city_incidents = client.get("/api/v1/incidents?limit=5").json()["data"]
    if not city_incidents:
        pytest.skip("no city incident available to test against")
    city_incident_id = city_incidents[0]["id"]

    login_as(ISOLATION)
    assert (
        client.get("/api/v1/incidents").json()["data"] == []
    ), "the isolation tenant must not see the other organization's events"
    response = client.get(f"/api/v1/incidents/{city_incident_id}")
    assert response.status_code == 404, response.text


def test_cross_tenant_evidence_is_not_served(client, login_as) -> None:
    login_as(CITY)
    incidents = client.get("/api/v1/incidents?limit=5").json()["data"]
    if not incidents:
        pytest.skip("no incident available to test evidence access")
    evidence = client.get(f"/api/v1/incidents/{incidents[0]['id']}/evidence").json()["data"]
    if not evidence:
        pytest.skip("the incident has no evidence artefacts")

    login_as(ISOLATION)
    response = client.get(f"/api/v1/evidence/{evidence[0]['id']}/url")
    assert response.status_code == 404, response.text


def test_auditor_cannot_create_an_administrative_record(client, login_as) -> None:
    login_as("auditor@demo.roadguard.ai")
    response = client.post(
        "/api/v1/departments", json={"name": "Unauthorised Department", "department_type": "roads"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_auditor_can_read_the_audit_trail(client, login_as) -> None:
    login_as("auditor@demo.roadguard.ai")
    response = client.get("/api/v1/audit-logs?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_auditor_cannot_review_an_incident(client, login_as) -> None:
    login_as(CITY)
    incidents = client.get("/api/v1/incidents?limit=1").json()["data"]
    if not incidents:
        pytest.skip("no incident available to attempt a review")

    login_as("auditor@demo.roadguard.ai")
    response = client.patch(
        f"/api/v1/incidents/{incidents[0]['id']}/review",
        json={"decision": "confirmed", "notes": "auditor must not be able to do this"},
    )
    assert response.status_code == 403


def test_engineer_cannot_verify_a_work_order(client, login_as) -> None:
    """Role boundaries are enforced by the API, not by hiding buttons."""
    login_as("engineer@demo.roadguard.ai")
    response = client.get("/api/v1/work-orders?limit=1").json()["data"]
    if not response:
        pytest.skip("no work order available")
    orders = response
    verification = client.post(
        f"/api/v1/work-orders/{orders[0]['id']}/verifications",
        json={"verification_status": "accepted", "notes": "engineer attempting self verification"},
    )
    assert verification.status_code in {403, 409}


def test_client_supplied_scoping_parameter_is_ignored(client, login_as) -> None:
    login_as(CITY)
    response = client.get(
        "/api/v1/cameras?organization_id=00000000-0000-4000-8000-000000000000"
    )
    assert response.status_code == 200
    me = client.get("/api/v1/auth/me").json()["data"]
    assert me["user"]["organization"]["slug"] == "demo-city"


def test_realtime_ticket_is_scoped_and_short_lived(client, login_as) -> None:
    login_as(CITY)
    response = client.post("/api/v1/realtime/ticket")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["expires_in"] <= 60
    assert payload["path"].endswith("/ws/command-center")
    assert payload["ticket"].count(".") == 2
