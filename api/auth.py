"""
Authentication and authorization for AEO Orchestrator.

Provides:
- Password hashing with bcrypt
- JWT token creation and validation
- API key creation and validation
- FastAPI dependencies for protected endpoints
"""

import secrets
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from config import get_settings
from db.models import APIKey, Organization, User

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class TokenData(BaseModel):
    """Data encoded in JWT token."""

    user_id: str
    organization_id: str
    email: str
    role: str


class TokenResponse(BaseModel):
    """Response containing access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthContext(BaseModel):
    """Authentication context for requests."""

    user_id: UUID | None = None
    organization_id: UUID
    email: str | None = None
    role: str = "api_key"
    auth_method: str  # "jwt" or "api_key"

    class Config:
        arbitrary_types_allowed = True


# =============================================================================
# PASSWORD UTILITIES
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT UTILITIES
# =============================================================================


def create_access_token(
    user_id: UUID,
    organization_id: UUID,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    settings = get_settings()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "sub": str(user_id),
        "org": str(organization_id),
        "email": email,
        "role": role,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token."""
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenData:
    """Decode and validate a JWT token."""
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")
        organization_id = payload.get("org")
        email = payload.get("email")
        role = payload.get("role")

        if not user_id or not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        return TokenData(
            user_id=user_id,
            organization_id=organization_id,
            email=email or "",
            role=role or "member",
        )

    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# =============================================================================
# API KEY UTILITIES
# =============================================================================


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete key to give to the user (only shown once)
        - key_prefix: First 8 chars to identify the key
        - key_hash: Hash to store in database
    """
    # Generate a secure random key
    full_key = f"aeo_{secrets.token_urlsafe(32)}"
    key_prefix = full_key[:12]
    key_hash = pwd_context.hash(full_key)

    return full_key, key_prefix, key_hash


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """Verify an API key against its hash."""
    return pwd_context.verify(api_key, key_hash)


# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================


async def get_auth_context(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    api_key: Annotated[str | None, Depends(api_key_header)],
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    """
    Get authentication context from request.

    Supports both JWT Bearer tokens and API keys.
    """
    # Try JWT token first
    if bearer and bearer.credentials:
        token_data = decode_token(bearer.credentials)

        return AuthContext(
            user_id=UUID(token_data.user_id),
            organization_id=UUID(token_data.organization_id),
            email=token_data.email,
            role=token_data.role,
            auth_method="jwt",
        )

    # Try API key
    if api_key:
        # Find the API key by prefix
        key_prefix = api_key[:12]

        result = await session.execute(
            select(APIKey)
            .where(APIKey.key_prefix == key_prefix)
            .where(APIKey.is_active == True)
        )
        db_key = result.scalar_one_or_none()

        if db_key and verify_api_key(api_key, db_key.key_hash):
            # Check expiration
            if db_key.expires_at and db_key.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                )

            # Update last used
            db_key.last_used_at = datetime.utcnow()
            await session.commit()

            return AuthContext(
                user_id=None,
                organization_id=db_key.organization_id,
                email=None,
                role="api_key",
                auth_method="api_key",
            )

    # No valid auth found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Get the current authenticated user.

    Only works with JWT auth, not API keys.
    """
    if auth.auth_method != "jwt" or not auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This endpoint requires user authentication (not API key)",
        )

    result = await session.execute(
        select(User).where(User.id == auth.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_organization(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    session: AsyncSession = Depends(get_session),
) -> Organization:
    """Get the current organization from auth context."""
    result = await session.execute(
        select(Organization).where(Organization.id == auth.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization not found",
        )

    if org.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Organization is {org.status}",
        )

    return org


def require_role(required_roles: list[str]):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.post("/admin-only", dependencies=[Depends(require_role(["admin", "owner"]))])
    """

    async def role_checker(
        auth: Annotated[AuthContext, Depends(get_auth_context)],
    ):
        if auth.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_roles}",
            )
        return auth

    return role_checker


# =============================================================================
# TYPE ALIASES FOR CLEANER CODE
# =============================================================================

# Use these in endpoint signatures:
# async def my_endpoint(auth: Auth, org: CurrentOrg, session: Session):

Auth = Annotated[AuthContext, Depends(get_auth_context)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentOrg = Annotated[Organization, Depends(get_current_organization)]
