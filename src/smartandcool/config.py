from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://smartandcool:local-dev-only@127.0.0.1:54329/smartandcool"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    http_timeout_seconds: float = Field(default=15, gt=0, le=60)
    http_max_attempts: int = Field(default=3, ge=1, le=3)
    live_checks_enabled: bool = False
    cj_api_key: SecretStr | None = None
    cj_access_token: SecretStr | None = None
    cj_access_token_expires_at: AwareDatetime | None = None
    cj_refresh_token: SecretStr | None = None
    cj_refresh_token_expires_at: AwareDatetime | None = None
    woo_base_url: str | None = None
    woo_consumer_key: SecretStr | None = None
    woo_consumer_secret: SecretStr | None = None
    amazon_client_id: SecretStr | None = None
    amazon_client_secret: SecretStr | None = None
    amazon_refresh_token: SecretStr | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_optional_values(cls, value):
        return None if value == "" else value

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        try:
            valid = make_url(value.get_secret_value()).drivername == "postgresql+psycopg"
        except Exception:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator("woo_base_url")
    @classmethod
    def secure_store_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "WOO_BASE_URL must be an HTTPS store root without credentials or query"
            )
        return value.rstrip("/")
