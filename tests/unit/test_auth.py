"""
Unit tests for authentication module.

Tests:
- Password hashing and verification
- JWT token creation and decoding
- API key generation and verification
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_api_key,
    TokenData,
)
from config import get_settings


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_hash(self):
        """hash_password returns a bcrypt hash."""
        password = "mysecretpassword"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_hash_is_unique(self):
        """Same password produces different hashes (due to salt)."""
        password = "samepassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """verify_password returns True for correct password."""
        password = "correctpassword"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password returns False for incorrect password."""
        hashed = hash_password("correctpassword")

        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password(self):
        """Can hash and verify empty password."""
        password = ""
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("notempty", hashed) is False


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token(self):
        """create_access_token creates a valid JWT."""
        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            organization_id=org_id,
            email="test@example.com",
            role="admin",
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token(self):
        """decode_token extracts data from JWT."""
        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            organization_id=org_id,
            email="test@example.com",
            role="admin",
        )

        data = decode_token(token)

        assert isinstance(data, TokenData)
        assert data.user_id == str(user_id)
        assert data.organization_id == str(org_id)
        assert data.email == "test@example.com"
        assert data.role == "admin"

    def test_token_with_custom_expiry(self):
        """Token respects custom expiry delta."""
        settings = get_settings()
        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            organization_id=org_id,
            email="test@example.com",
            role="member",
            expires_delta=timedelta(hours=2),
        )

        # Decode to check expiry
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        exp = datetime.utcfromtimestamp(payload["exp"])
        now = datetime.utcnow()

        # Should expire in ~2 hours
        diff = exp - now
        assert 7100 <= diff.total_seconds() <= 7300  # ~2 hours

    def test_expired_token_raises(self):
        """Expired token raises HTTPException."""
        from fastapi import HTTPException

        user_id = uuid4()
        org_id = uuid4()

        # Create token that expires immediately
        token = create_access_token(
            user_id=user_id,
            organization_id=org_id,
            email="test@example.com",
            role="member",
            expires_delta=timedelta(seconds=-10),  # Already expired
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)

        assert exc_info.value.status_code == 401

    def test_invalid_token_raises(self):
        """Invalid token raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")

        assert exc_info.value.status_code == 401

    def test_create_refresh_token(self):
        """create_refresh_token creates a valid refresh token."""
        user_id = uuid4()
        token = create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode to verify structure
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"


class TestAPIKeys:
    """Tests for API key functions."""

    def test_generate_api_key_format(self):
        """generate_api_key returns key, prefix, and hash."""
        full_key, prefix, key_hash = generate_api_key()

        assert full_key.startswith("aeo_")
        assert len(full_key) > 20
        assert prefix == full_key[:12]
        assert key_hash.startswith("$2b$")  # bcrypt hash

    def test_generate_api_key_unique(self):
        """Each generated API key is unique."""
        key1, _, _ = generate_api_key()
        key2, _, _ = generate_api_key()

        assert key1 != key2

    def test_verify_api_key_correct(self):
        """verify_api_key returns True for correct key."""
        full_key, _, key_hash = generate_api_key()

        assert verify_api_key(full_key, key_hash) is True

    def test_verify_api_key_incorrect(self):
        """verify_api_key returns False for incorrect key."""
        _, _, key_hash = generate_api_key()

        assert verify_api_key("aeo_wrongkey", key_hash) is False

    def test_api_key_prefix_consistent(self):
        """Key prefix matches the start of the full key."""
        full_key, prefix, _ = generate_api_key()

        assert full_key.startswith(prefix)
