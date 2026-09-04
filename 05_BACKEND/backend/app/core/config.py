"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIRECTORY / ".env")


@dataclass(frozen=True)
class Settings:
    """Configuration that is safe to keep in source control."""

    app_name: str
    environment: str
    database_url: str | None


def get_settings() -> Settings:
    """Create settings using environment variables with safe defaults."""
    return Settings(
        app_name=os.getenv("APP_NAME", "RecoverAI API"),
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL"),
    )
