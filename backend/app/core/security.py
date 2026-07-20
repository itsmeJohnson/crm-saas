from datetime import datetime, timedelta, timezone
from typing import Any, Union
import jwt
import uuid
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], token_version: int = 1, expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "jti": uuid.uuid4().hex,
        "tv": token_version,  # token_version for forced-logout support
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh", "jti": uuid.uuid4().hex}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.
    Raises HTTPException with specific detail on expiry vs invalid token,
    so the frontend can distinguish between the two and attempt a refresh.
    """
    from fastapi import HTTPException, status as http_status
    try:
        decoded_token = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="token_expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="token expired"'},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


import hashlib
import secrets

def generate_random_token() -> str:
    """Generate a secure, random token."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """Generate a SHA-256 hash of the token for secure DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_mfa_challenge_token(user_id: Any) -> str:
    """
    Create a short-lived (5 min) MFA challenge token.
    Type='mfa_challenge' — rejected by all normal auth guards.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    to_encode = {
        "exp": expire,
        "sub": str(user_id),
        "type": "mfa_challenge",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_mfa_challenge_token(token: str) -> str:
    """
    Decode an MFA challenge token. Returns user_id (sub).
    Raises HTTPException if expired or wrong type.
    """
    from fastapi import HTTPException, status as http_status
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="MFA session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA token.")

    if payload.get("type") != "mfa_challenge":
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid token type for MFA verification.")

    return payload["sub"]

