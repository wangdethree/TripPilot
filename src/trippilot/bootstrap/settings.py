"""Environment-backed application configuration."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRIPPILOT_",
        env_file=".env",
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"
    model_provider: str = "fake"
    tool_provider: str = "fake"
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    extraction_model: str = "gpt-5.6-luna"
    planning_model: str = "gpt-5.6-terra"
    amap_api_key: SecretStr | None = None
    tool_timeout_seconds: float = Field(default=8.0, ge=1.0, le=20.0)
    tool_max_retries: int = Field(default=2, ge=0, le=2)
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg://trippilot:trippilot@localhost:5432/trippilot")
    )
    token_pepper: SecretStr = Field(default=SecretStr("local-development-pepper-change-me"))
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
