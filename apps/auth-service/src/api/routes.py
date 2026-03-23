"""Auth API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_user_id
from src.api.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from src.application import auth_service
from src.application.bootstrap import get_session_factory
from src.domain.auth_errors import EmailAlreadyExists, InvalidCredentials, UserNotFound

router = APIRouter()


def _get_db():
    """Yield a DB session from the configured session factory."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@router.get("/healthz/live")
def liveness():
    return {"status": "live"}


@router.get("/healthz/ready")
def readiness():
    return {"status": "ready"}


@router.get("/healthz/info")
def deployment_info():
    import os
    info: dict = {"service": "auth-service"}
    if os.getenv("APP_ENV", "development") == "development":
        info["app_env"] = "development"
        info["deployment_profile"] = os.getenv("DEPLOYMENT_PROFILE", "local")
    return info


@router.post("/v1/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db=Depends(_get_db)):
    try:
        result = auth_service.register(db, body.email, body.display_name, body.password)
    except EmailAlreadyExists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return RegisterResponse(**result)


@router.post("/v1/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db=Depends(_get_db)):
    try:
        result = auth_service.login(db, body.email, body.password)
    except InvalidCredentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(**result)


@router.post("/v1/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db=Depends(_get_db)):
    try:
        result = auth_service.refresh(db, body.refresh_token)
    except (InvalidCredentials, UserNotFound):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return TokenResponse(**result)


@router.get("/v1/auth/me", response_model=UserResponse)
def me(user_id=Depends(get_current_user_id), db=Depends(_get_db)):
    try:
        return auth_service.get_me(db, user_id)
    except UserNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
