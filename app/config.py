import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./distributor_os.db"
    GEMINI_API_KEY: str = ""

    # SMS Provider Configuration
    # SMS_GATEWAY_API_KEY must be supplied via environment in production; an empty
    # default makes an unconfigured gateway obvious instead of silently "working".
    SMS_PROVIDER: str = "MSG91"
    SMS_GATEWAY_API_KEY: str = ""

    # JWT signing secret. MUST be overridden via the environment in production —
    # the default below is for local development only and is not secret.
    SECRET_KEY: str = "super-secret-key-distributor-os-2026"

    # Firebase Authentication
    FIREBASE_CREDENTIALS_JSON: str | None = None


    # Allow configuration via environment variables or .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
