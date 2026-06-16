import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./distributor_os.db"
    GEMINI_API_KEY: str = ""

    # SMS Provider Configuration
    SMS_PROVIDER: str = "MSG91"
    SMS_GATEWAY_API_KEY: str = "MOCK_KEY"

    # Firebase Authentication
    FIREBASE_CREDENTIALS_JSON: str | None = None


    # Allow configuration via environment variables or .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
