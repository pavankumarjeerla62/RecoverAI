"""Explicit database schema initialization for local development."""

from app.db import models
from app.db.base import Base
from app.db.session import engine


def create_schema() -> None:
    """Create all registered RecoverAI tables in the configured database."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_schema()
