"""Observability configuration; optional Mongo connection overrides the bot database."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOTSPOT_OBSERVABILITY_", env_file=".env", extra="ignore"
    )
    enabled: bool = True
    mongo_url: SecretStr = SecretStr("")
    mongo_database: str = "botspot"
    registry_mongo_url: SecretStr = SecretStr("")
    registry_mongo_database: str = "botspot"
    retention_days: int = Field(default=30, ge=1)
    port: int = Field(default=8091, ge=0, le=65535)
    host: str = "127.0.0.1"
    public_url: str = ""
    token: SecretStr = SecretStr("")
    auth_max_age: int = Field(default=300, ge=1)
    session_ttl: int = Field(default=86400, ge=1)
    dimensions: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ("cost",)

    @field_validator("public_url")
    @classmethod
    def validate_url(cls, value):
        from urllib.parse import urlsplit

        if value:
            parts = urlsplit(value)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
                or parts.path not in ("", "/")
            ):
                raise ValueError("public_url must be an HTTPS origin without a path")
        return value.rstrip("/")
