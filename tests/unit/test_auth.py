"""Unit tests for authentication logic."""

from __future__ import annotations

import pytest
from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    hash_password,
    hash_token,
    needs_rehash,
    normalize_email,
    tokens_equal,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_different_hash_each_time(self) -> None:
        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    def test_verify_password_correct(self) -> None:
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_verify_password_incorrect(self) -> None:
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert not verify_password("WrongPassword123!", hashed)

    def test_needs_rehash_false_for_current_hash(self) -> None:
        password = "TestPassword123!"
        hashed = hash_password(password)
        assert not needs_rehash(hashed)

    def test_normalize_email_strips_and_lowers(self) -> None:
        assert normalize_email("  Test@Example.COM  ") == "test@example.com"
        assert normalize_email("USER@DOMAIN.COM") == "user@domain.com"

    def test_hash_token_is_deterministic(self) -> None:
        token = "test-token-123"
        hash1 = hash_token(token)
        hash2 = hash_token(token)
        assert hash1 == hash2
        assert len(hash1) == 64


class TestJWTTokens:
    def test_create_access_token(self) -> None:
        import uuid
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        token, expires_in = create_access_token(
            user_id=user_id, organization_id=org_id, role="police_admin"
        )
        assert isinstance(token, str)
        assert token.count(".") == 2
        assert expires_in > 0

    def test_create_refresh_token(self) -> None:
        import uuid
        from datetime import UTC, datetime
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        session_id = uuid.uuid4()
        token, expires_at = create_refresh_token(
            user_id=user_id, organization_id=org_id, session_id=session_id
        )
        assert isinstance(token, str)
        assert token.count(".") == 2
        assert expires_at > datetime.now(UTC)

    def test_decode_token_valid(self) -> None:
        import uuid
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        token, _ = create_access_token(
            user_id=user_id, organization_id=org_id, role="police_admin"
        )
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == str(user_id)
        assert payload["org"] == str(org_id)
        assert payload["role"] == "police_admin"
        assert payload["type"] == "access"

    def test_decode_token_expired_raises(self) -> None:
        import uuid
        from datetime import timedelta

        from app.core.security import _encode
        expired_token = _encode(
            {"type": "access", "sub": str(uuid.uuid4()), "org": str(uuid.uuid4())},
            timedelta(seconds=-1),
        )
        with pytest.raises(AuthenticationError, match="expired"):
            decode_token(expired_token, expected_type="access")

    def test_decode_token_wrong_type_raises(self) -> None:
        import uuid
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        access_token, _ = create_access_token(
            user_id=user_id, organization_id=org_id, role="police_admin"
        )
        with pytest.raises(AuthenticationError, match="not valid for this operation"):
            decode_token(access_token, expected_type="refresh")


class TestCSRF:
    def test_generate_csrf_token(self) -> None:
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        assert token1 != token2
        assert len(token1) > 20

    def test_tokens_equal_timing_safe(self) -> None:
        assert tokens_equal("abc123", "abc123")
        assert not tokens_equal("abc123", "abc124")
        assert not tokens_equal("abc", "abcd")


class TestConstantTimeVerification:
    def test_constant_time_dummy_verify_runs(self) -> None:
        from app.core.security import constant_time_dummy_verify
        constant_time_dummy_verify()