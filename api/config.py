from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    ai_enabled: bool = os.getenv("AI_EXPLANATIONS_ENABLED", "true").lower() == "true"

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # API
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))
    result_ttl: int = int(os.getenv("RESULT_TTL", 3600))
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Paths
    project_root: Path = Path(__file__).parent.parent
    db_features_path: str = str(Path(__file__).parent.parent / "data" / "db_features.json")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def has_ai(self) -> bool:
        """True if AI explanations are enabled and a Gemini key is set."""
        return self.ai_enabled and bool(self.gemini_api_key)

    @property
    def use_celery(self) -> bool:
        """If Redis is not configured, fall back to synchronous processing."""
        return bool(self.redis_url)


settings = Settings()