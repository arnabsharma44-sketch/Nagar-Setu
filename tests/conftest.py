"""Shared test fixtures.

Integration tests run against the running database used by the dev stack, but they
are read-only: nothing here mutates seeded demo data, so the suite can be executed
against a live environment without destroying evidence.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "apps" / "api", ROOT / "ai-engine", ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

os.environ.setdefault("ENVIRONMENT", "test")
# The suite signs in many times by design; the limiter's own behaviour is covered by
# a unit test against SlidingWindowLimiter, so the HTTP tests raise the ceiling.
os.environ.setdefault("LOGIN_RATE_LIMIT_PER_MINUTE", "500")

DEMO_PASSWORD = os.environ.get("DEMO_SEED_PASSWORD", "RoadguardDemo#2026")


@pytest.fixture(scope="session")
def db_engine():
    """Privileged engine for schema-level assertions (tables, RLS, PostGIS)."""
    from app.db.session import get_privileged_engine

    return get_privileged_engine()


@pytest.fixture(scope="session")
def client():
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def login_as(client) -> Callable[[str], dict]:
    """Sign in explicitly before each request.

    A TestClient keeps one cookie jar, so a cached session fixture would silently
    leak the previous test's identity. Logging in per test keeps identity honest.
    """

    def _login(email: str) -> dict:
        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        client.headers.update({"x-csrf-token": data["user"]["csrf_token"]})
        return data

    return _login


@pytest.fixture
def anonymous() -> Iterator[object]:
    """A client with no session, used to prove protected routes reject callers."""
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as fresh:
        yield fresh


def unique_suffix() -> str:
    return uuid.uuid4().hex[:8]
