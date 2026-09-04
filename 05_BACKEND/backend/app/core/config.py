"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Configuration that is safe to keep in source control."""

    app_name: str
    environment: str


def get_settings() -> Settings:
    """Create settings using environment variables with safe defaults."""
    return Settings(
        app_name=os.getenv("APP_NAME", "RecoverAI API"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )
