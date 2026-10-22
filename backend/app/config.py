"""Environment-based configuration for VSR AI."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VSR AI"
    environment: str = "development"

    # Database. SQLite is the zero-setup default; docker-compose sets PostgreSQL.
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'vsr_ai.db'}"

    # LangGraph checkpoint store (persists paused human-approval workflows)
    checkpoint_db_path: str = str(BASE_DIR / "data" / "checkpoints.sqlite")

    # Chroma vector store
    chroma_path: str = str(BASE_DIR / "data" / "chroma")
    chroma_collection: str = "vsr_ai_policies"
    policies_dir: str = str(BASE_DIR / "app" / "rag" / "policies")

    # Embeddings: "hashing" (offline, deterministic) or "openai"
    embedding_provider: str = "hashing"
    openai_embedding_model: str = "text-embedding-3-small"

    # LLM: "none" (deterministic agents), "openai", or "anthropic"
    llm_provider: str = "none"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    llm_timeout_seconds: float = 30.0

    # Auth
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Reliability
    rate_limit_per_minute: int = 300        # general API traffic, per client
    chat_rate_limit_per_minute: int = 30    # POST /api/chat (runs the agent graph)
    login_rate_limit_per_minute: int = 10   # POST /api/auth/login (brute-force guard)
    trust_proxy_headers: bool = False       # true only behind a known reverse proxy (docker-compose nginx)
    request_timeout_seconds: float = 45.0
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Business rules
    return_window_days: int = 30
    auto_refund_limit: float = 0.0  # every refund needs human approval

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
