"""Shared auth helpers."""
from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from auth.models import Organization


def make_tenant_id(org_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-")
    slug = slug[:40]
    suffix = uuid.uuid4().hex[:4]
    return f"{slug}-{suffix}"


def normalize_org_name(name: str) -> str:
    """Case-insensitive key for duplicate company detection."""
    return re.sub(r"\s+", " ", name.strip().lower())


def organization_name_taken(db: Session, organization_name: str) -> Organization | None:
    """
    Return existing Organization if this company name is already registered
    (blocks multiple free trials with different emails for the same org).
    """
    key = normalize_org_name(organization_name)
    if not key:
        return None
    for org in db.query(Organization).all():
        if normalize_org_name(org.name) == key:
            return org
    return None
