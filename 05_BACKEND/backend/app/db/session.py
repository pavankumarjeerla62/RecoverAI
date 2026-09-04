"""SQLAlchemy engine and session support for future database access."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL environment variable is required for database access.")


engine: Engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session for a future API request."""
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()
