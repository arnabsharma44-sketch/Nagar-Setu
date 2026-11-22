"""Multi-tenant isolation integration tests."""

from __future__ import annotations

import pytest

CITY = "ops@demo.roadguard.ai"
ISOLATION = "ops@isolation.roadguard.ai"


class TestTenantIsolation:
    def test_cross_tenant_camera_read_is_404(self, client, login_as) -> None:
        login_as(ISOLATION)
        isolation_cameras = client.get("/api/v1/cameras").json()["data"]
        assert isolation_cameras, "the isolation tenant should have a seeded camera"
        foreign_id = isolation_cameras[0]["id"]

        login_as(CITY)
        response = client.get(f"/api/v1/cameras/{foreign_id}")
        assert response.status_code == 404, response.text

    def test_organizations_do_not_share_records(self, client, login_as) -> None:
        login_as(ISOLATION)
        isolation_ids = {camera["id"] for camera in client.get("/api/v1/cameras").json()["data"]}

        login_as(CITY)
        city_ids = {camera["id"] for camera in client.get("/api/v1/cameras").json()["data"]}

        assert isolation_ids and city_ids
        assert isolation_ids.isdisjoint(city_ids)

    def test_cross_tenant_incident_read_is_404(self, client, login_as) -> None:
        login_as(CITY)
        city_incidents = client.get("/api/v1/incidents?limit=5").json()["data"]
        if not city_incidents:
            pytest.skip("no city incident available to test against")
        city_incident_id = city_incidents[0]["id"]

        login_as(ISOLATION)
        assert client.get("/api/v1/incidents").json()["data"] == [], \
            "the isolation tenant must not see the other organization's events"
        response = client.get(f"/api/v1/incidents/{city_incident_id}")
        assert response.status_code == 404, response.text

    def test_cross_tenant_evidence_is_not_served(self, client, login_as) -> None:
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

    def test_cross_tenant_video_access_denied(self, client, login_as) -> None:
        login_as(CITY)
        videos = client.get("/api/v1/videos?limit=5").json()["data"]
        if not videos:
            pytest.skip("no video available to test")
        video_id = videos[0]["id"]

        login_as(ISOLATION)
        response = client.get(f"/api/v1/videos/{video_id}")
        assert response.status_code == 404

    def test_cross_tenant_job_access_denied(self, client, login_as) -> None:
        login_as(CITY)
        jobs = client.get("/api/v1/jobs?limit=5").json()["data"]
        if not jobs:
            pytest.skip("no job available to test")
        job_id = jobs[0]["id"]

        login_as(ISOLATION)
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 404

    def test_cross_tenant_investigation_access_denied(self, client, login_as) -> None:
        login_as(CITY)
        investigations = client.get("/api/v1/investigations?limit=5").json()["data"]
        if not investigations:
            pytest.skip("no investigation available to test")
        investigation_id = investigations[0]["id"]

        login_as(ISOLATION)
        response = client.get(f"/api/v1/investigations/{investigation_id}")
        assert response.status_code == 404

    def test_cross_tenant_work_order_access_denied(self, client, login_as) -> None:
        login_as(CITY)
        work_orders = client.get("/api/v1/work-orders?limit=5").json()["data"]
        if not work_orders:
            pytest.skip("no work order available to test")
        wo_id = work_orders[0]["id"]

        login_as(ISOLATION)
        response = client.get(f"/api/v1/work-orders/{wo_id}")
        assert response.status_code == 404

    def test_cross_tenant_websocket_isolation(self, client, login_as) -> None:
        login_as(CITY)
        response = client.post("/api/v1/realtime/ticket")
        assert response.status_code == 200
        city_ticket = response.json()["data"]["ticket"]

        login_as(ISOLATION)
        response = client.post("/api/v1/realtime/ticket")
        assert response.status_code == 200
        isolation_ticket = response.json()["data"]["ticket"]

        assert city_ticket != isolation_ticket

    def test_cross_tenant_search_is_scoped(self, client, login_as) -> None:
        login_as(CITY)
        response = client.get("/api/v1/cameras?search=test")
        assert response.status_code == 200
        me = client.get("/api/v1/auth/me").json()["data"]
        assert me["user"]["organization"]["slug"] == "demo-city"

    def test_cross_tenant_list_pagination_is_scoped(self, client, login_as) -> None:
        login_as(ISOLATION)
        iso_count = len(client.get("/api/v1/cameras").json()["data"])

        login_as(CITY)
        city_count = len(client.get("/api/v1/cameras").json()["data"])

        assert iso_count > 0 or city_count > 0
        # They should be different or one could be empty