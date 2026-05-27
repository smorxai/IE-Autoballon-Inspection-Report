"""
Super-admin management routes.

Prefix: /admin
All routes require a valid JWT with role=super_admin.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.database import get_db
from auth.dependencies import require_super_admin
from auth.helpers import make_tenant_id
from auth.models import Organization, RoleEnum, User
from auth.schemas import (
    CreateEngineerRequest,
    CreateOrganizationRequest,
    EngineerCreatedResponse,
    OrganizationResponse,
    UpdateUserPermissionsRequest,
    UserResponse,
)
from auth.settings import trial_days
from auth.utils import generate_temp_password, hash_password, send_temp_password_email

router = APIRouter(prefix="/admin", tags=["Super Admin"])


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
@router.post("/organizations", response_model=OrganizationResponse)
def create_organization(
    body: CreateOrganizationRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Create a new organization (tenant).

    Automatically generates a unique tenant_id slug from the name.
    """
    # Prevent duplicate names (soft check — tenant_id uniqueness is the hard constraint)
    existing = db.query(Organization).filter(
        Organization.name.ilike(body.name)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An organization named '{body.name}' already exists (tenant_id: {existing.tenant_id}).",
        )

    tenant_id = make_tenant_id(body.name)
    now = datetime.now(timezone.utc)
    org = Organization(
        name=body.name,
        tenant_id=tenant_id,
        trial_start_date=now,
        trial_end_date=now + timedelta(days=trial_days()),
        subscription_status="trial",
        is_active=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        tenant_id=org.tenant_id,
        created_at=org.created_at,
        engineer_count=0,
        subscription_status=org.subscription_status,
        trial_end_date=org.trial_end_date,
        is_active=org.is_active,
    )


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """List all organizations with engineer counts."""
    orgs = db.query(Organization).order_by(Organization.created_at).all()
    results = []
    for org in orgs:
        count = db.query(User).filter_by(tenant_id=org.tenant_id).count()
        results.append(
            OrganizationResponse(
                id=org.id,
                name=org.name,
                tenant_id=org.tenant_id,
                created_at=org.created_at,
                engineer_count=count,
                subscription_status=org.subscription_status,
                trial_end_date=org.trial_end_date,
                is_active=org.is_active,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Engineers
# ---------------------------------------------------------------------------
@router.post("/engineers", response_model=EngineerCreatedResponse)
def create_engineer(
    body: CreateEngineerRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """
    Create an engineer account under an existing tenant.

    Flow:
      1. Validate tenant exists
      2. Check email uniqueness
      3. Generate temporary password
      4. Hash and store
      5. Send temp password via email (console mock by default)
      6. Return temp password in response (dev convenience — remove in production)
    """
    # 1. Validate tenant
    org = db.query(Organization).filter_by(tenant_id=body.tenant_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization with tenant_id '{body.tenant_id}' not found.",
        )

    # 2. Check email uniqueness
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{body.email}' already exists.",
        )

    # 3 & 4. Generate temp password and hash it
    temp_pwd = generate_temp_password()
    base_username = body.email.split("@")[0].lower().replace(".", "_")[:40]
    username = base_username
    n = 1
    while db.query(User).filter_by(username=username).first():
        username = f"{base_username}{n}"
        n += 1

    user = User(
        name=body.name,
        email=body.email,
        username=username,
        password_hash=hash_password(temp_pwd),
        role=RoleEnum.engineer,
        tenant_id=body.tenant_id,
        is_temp_password=True,
        email_verified=True,
        can_read=False,
        can_write=False,
        can_delete=False,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 5. Deliver via email (mock prints to console)
    send_temp_password_email(
        to_email=user.email,
        name=user.name,
        temp_password=temp_pwd,
    )

    return EngineerCreatedResponse(
        ok=True,
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        temp_password=temp_pwd,   # ← remove from response once real email is wired
        message=(
            f"Engineer '{user.name}' created under tenant '{org.name}'. "
            "Account is inactive until you grant access in User access control. "
            "Temporary password printed to server console (and returned here for dev)."
        ),
    )


@router.get("/engineers", response_model=List[UserResponse])
def list_all_engineers(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """List every engineer across all tenants."""
    users = (
        db.query(User)
        .filter_by(role=RoleEnum.engineer)
        .order_by(User.created_at)
        .all()
    )
    return users


@router.get("/engineers/{tenant_id}", response_model=List[UserResponse])
def list_engineers_by_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """List all engineers belonging to a specific tenant."""
    org = db.query(Organization).filter_by(tenant_id=tenant_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found.",
        )

    users = (
        db.query(User)
        .filter_by(tenant_id=tenant_id, role=RoleEnum.engineer)
        .order_by(User.created_at)
        .all()
    )
    return users


@router.delete("/engineers/{engineer_id}")
def delete_engineer(
    engineer_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """Remove an engineer account (cannot delete super_admin)."""
    user = db.query(User).filter_by(id=engineer_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role == RoleEnum.super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete super admin.",
        )
    db.delete(user)
    db.commit()
    return {"ok": True, "message": f"Engineer {user.email} deleted."}


@router.get("/users", response_model=List[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """List all users (engineers) with permissions for super admin control."""
    return (
        db.query(User)
        .filter(User.role == RoleEnum.engineer)
        .order_by(User.created_at)
        .all()
    )


@router.patch("/users/{user_id}/permissions", response_model=UserResponse)
def update_user_permissions(
    user_id: str,
    body: UpdateUserPermissionsRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
):
    """Super admin toggles read / write / delete / active for a user."""
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == RoleEnum.super_admin:
        raise HTTPException(status_code=403, detail="Cannot modify super admin permissions.")

    user.can_read = body.can_read
    user.can_write = body.can_write
    user.can_delete = body.can_delete
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user
