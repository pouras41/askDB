from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.limiter import enforce_rate_limit
from app.models import RefreshToken, User
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    hash_token,
    new_refresh_token,
    refresh_expiry,
    validate_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _public(user: User) -> UserPublic:
    return UserPublic(id=user.id, name=user.name, email=user.email)


def _issue(db: Session, user: User) -> TokenResponse:
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=refresh_expiry(),
            revoked=False,
        )
    )
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=raw,
        user=_public(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    enforce_rate_limit(
        f"register:{_client_key(request)}",
        settings.register_rate_limit,
        settings.auth_rate_window_seconds,
    )
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    problem = validate_password(payload.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    user = User(
        name=name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc
    db.refresh(user)
    return _issue(db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    enforce_rate_limit(
        f"login:{_client_key(request)}",
        settings.login_rate_limit,
        settings.auth_rate_window_seconds,
    )
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    password_hash = user.password_hash if user else dummy_password_hash()
    password_ok = verify_password(payload.password, password_hash)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _issue(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    enforce_rate_limit(
        f"refresh:{_client_key(request)}",
        20,
        settings.auth_rate_window_seconds,
    )
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token)))
    if token is None or token.revoked or _expired(token.expires_at):
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired.")
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired.")
    token.revoked = True
    db.commit()
    return _issue(db, user)


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token)))
    if token is not None:
        token.revoked = True
        db.commit()


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _public(user)
