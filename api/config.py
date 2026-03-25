from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    # AI — Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    ai_enabled: bool = os.getenv("AI_EXPLANATIONS_ENABLED", "true").lower() == "true"

    # Redis / Celery
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # API
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))
    result_ttl: int = int(os.getenv("RESULT_TTL", 3600))
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Clerk
    clerk_secret_key: str = os.getenv("CLERK_SECRET_KEY", "")
    clerk_publishable_key: str = os.getenv("CLERK_PUBLISHABLE_KEY", "")

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Paths
    project_root: Path = Path(__file__).parent.parent
    db_features_path: str = str(Path(__file__).parent.parent / "data" / "db_features.json")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def has_ai(self) -> bool:
        return self.ai_enabled and bool(self.gemini_api_key)

    @property
    def use_celery(self) -> bool:
        return bool(self.redis_url)

    @property
    def has_auth(self) -> bool:
        return bool(self.clerk_secret_key)

    @property
    def has_db(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)


settings = Settings()