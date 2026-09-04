"""Shared SQLAlchemy declarative base for RecoverAI models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class inherited by every database model."""
