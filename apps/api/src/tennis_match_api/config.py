import logging
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.is_file() else None,
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    port: int = 8080
    log_level: str = "INFO"
    mysql_address: str = "127.0.0.1:3306"
    mysql_username: str
    mysql_password: SecretStr
    mysql_database: str = "tennis"
    migration_mysql_username: str | None = None
    migration_mysql_password: SecretStr | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle_seconds: int = 280
    db_connect_max_wait_seconds: float = 20
    run_migrations_on_start: bool = True
    auth_mode: Literal["wxcloud", "dev"] = "wxcloud"
    wechat_appid: str
    cbr_env_id: str | None = None
    avatar_path_prefix: str = "avatars/"
    wechat_content_check_enabled: bool = False
    business_tz: str = "Asia/Shanghai"
    supported_cities: list[str] = Field(default_factory=lambda: ["武汉"])
    ntrp_hard_diff: Decimal = Decimal("0.5")
    auto_cancel_hours: int = 24
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 300
    recommend_candidate_cap: int = 200
    rank_weight_credit: float = 0.3
    rank_weight_ntrp: float = 0.3
    rank_weight_llm: float = 0.4
    credit_norm_cap: int = 20
    llm_enabled: bool = True
    llm_timeout_seconds: float = 3.0
    llm_background_timeout_seconds: float = 15.0
    llm_top_n: int = 20
    llm_default_score: int = 50
    llm_cache_ttl_days: int = 7
    llm_daily_limit_global: int = 2000
    llm_daily_limit_per_user: int = 30
    llm_json_mode: bool = True
    llm_extra_body: dict[str, object] = Field(default_factory=dict)
    llm_prompt_version: str = "v2"
    llm_debug_api_enabled: bool = False
    internal_api_token: SecretStr | None = None
    ai_model_base_url: str | None = None
    ai_model_api_key: SecretStr | None = None
    ai_model_name: str | None = None

    @field_validator(
        "migration_mysql_username",
        "cbr_env_id",
        "ai_model_base_url",
        "ai_model_name",
        mode="before",
    )
    @classmethod
    def _blank_string_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "migration_mysql_password",
        "ai_model_api_key",
        "internal_api_token",
        mode="before",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _check_runtime_rules(self) -> "Settings":
        host, separator, port = self.mysql_address.rpartition(":")
        if not host or not separator or not port.isdigit():
            raise ValueError("MYSQL_ADDRESS must be host:port")
        if self.app_env == "prod" and self.auth_mode == "dev":
            raise ValueError("AUTH_MODE=dev is forbidden when APP_ENV=prod")
        weights = (self.rank_weight_credit, self.rank_weight_ntrp, self.rank_weight_llm)
        if any(weight < 0 for weight in weights):
            raise ValueError("rank weights must be >= 0")
        total = sum(weights)
        if total <= 0:
            raise ValueError("rank weights must sum to a positive number")
        if abs(total - 1) > 1e-9:
            self.rank_weight_credit /= total
            self.rank_weight_ntrp /= total
            self.rank_weight_llm /= total
            logging.getLogger(__name__).warning("rank weights normalized to sum to 1")
        api_key = self.ai_model_api_key.get_secret_value() if self.ai_model_api_key else ""
        if not (self.ai_model_base_url and api_key and self.ai_model_name):
            self.llm_enabled = False
        return self

    def mysql_endpoint(self, *, migration: bool = False) -> tuple[str, int, str, str, str]:
        host, _, port = self.mysql_address.rpartition(":")
        if migration and self.migration_mysql_username:
            username = self.migration_mysql_username
            secret = self.migration_mysql_password or self.mysql_password
        else:
            username = self.mysql_username
            secret = self.mysql_password
        return host, int(port), username, secret.get_secret_value(), self.mysql_database


@lru_cache
def get_settings() -> Settings:
    return Settings()
