# api/auth.py
"""
JWT Authentication for Agens Multi-Agent System
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
from utils.feature_logs import get_feature_logger

router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
auth_log = get_feature_logger("auth")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: datetime


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token"""
    if request.username != ADMIN_USERNAME or request.password != ADMIN_PASSWORD:
        auth_log.warning(f"login_failed username={request.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": request.username,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    auth_log.info(
        f"login_success username={request.username} expire_hours={JWT_EXPIRE_HOURS}"
    )

    return LoginResponse(access_token=token)


@router.post("/logout")
async def logout():
    """Logout endpoint (client should discard token)"""
    auth_log.info("logout")
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
):
    """Get current authenticated user"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        auth_log.info(f"me_success username={payload.get('sub', '')}")
        return {"username": payload["sub"]}
    except JWTError:
        auth_log.warning("me_failed invalid_or_expired_token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
