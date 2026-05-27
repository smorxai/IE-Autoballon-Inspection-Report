"""
Auth routes — login, change password, forgot password, /me.
Self-registration endpoints return 403 (admin creates accounts).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.database import get_db
from auth.dependencies import get_current_user
from auth.models import RoleEnum, User
from auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    SendOtpRequest,
    TokenResponse,
    UserResponse,
)
from auth.utils import (
    create_access_token,
    find_user_by_login,
    generate_temp_password,
    hash_password,
    send_temp_password_email,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _issue_token(user: User) -> TokenResponse:
    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        tenant_id=user.tenant_id,
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        requires_password_change=user.is_temp_password,
        user_id=str(user.id),
        email=user.email,
        role=user.role.value,
        tenant_id=user.tenant_id,
    )


@router.post("/send-otp")
def send_otp(body: SendOtpRequest, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Self-registration is disabled. Contact your administrator for an account.",
    )


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Self-registration is disabled. Contact your administrator for an account.",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email/username + password."""
    user = find_user_by_login(db, body.login)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email/username or password.")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email/username or password.")

    if user.role != RoleEnum.super_admin:
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Your account is not active. Contact your super admin to grant access.",
            )
        if not user.can_read:
            raise HTTPException(
                status_code=403,
                detail="You do not have access yet. Contact your super admin to enable your account.",
            )

    return _issue_token(user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    err = validate_password_strength(body.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)

    current_user.password_hash = hash_password(body.new_password)
    current_user.is_temp_password = False
    db.commit()

    return {"ok": True, "message": "Password updated successfully."}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if user:
        temp_pwd = generate_temp_password()
        user.password_hash = hash_password(temp_pwd)
        user.is_temp_password = True
        db.commit()
        send_temp_password_email(to_email=user.email, name=user.name, temp_password=temp_pwd)

    return {
        "ok": True,
        "message": "If an account with that email exists, a temporary password has been sent.",
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
