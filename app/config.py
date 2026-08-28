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

    # Deployment environment: "development" (default, safe for local work) or
    # "production". Used only to gate the SECRET_KEY safety check below —
    # does not otherwise change app behavior.
    ENVIRONMENT: str = "development"

    # Allow configuration via environment variables or .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Fix for AUTH-3: SECRET_KEY signs every JWT session/refresh token in the
# app (see app/utils/security.py). Its default value is a fixed, publicly
# visible string committed to source control -- if a production deployment
# is ever started with ENVIRONMENT=production but without overriding
# SECRET_KEY, anyone who reads this file could forge a valid session token
# for any user/tenant, a complete authentication bypass. Fail fast at
# startup rather than silently running with all this implies.
_INSECURE_DEFAULT_SECRET_KEY = "super-secret-key-distributor-os-2026"
if settings.ENVIRONMENT.lower() == "production" and settings.SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is still set to the insecure, publicly-known default value "
        "while ENVIRONMENT=production. Set a strong, unique SECRET_KEY via the "
        "environment before starting the app in production -- refusing to start "
        "with a forgeable JWT signing secret."
    )
