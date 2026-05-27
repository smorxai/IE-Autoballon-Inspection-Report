"""Portable SQLAlchemy column types (PostgreSQL + SQLite)."""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, String
from sqlalchemy.types import TypeDecorator

# JSON works on both PostgreSQL and SQLite (replaces JSONB for local dev).
JSONB = JSON


class UUIDStr(TypeDecorator):
    """Store UUIDs as 36-char strings; return uuid.UUID to Python."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
