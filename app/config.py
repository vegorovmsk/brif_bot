"""Настройки приложения из .env и переменных окружения (ТЗ, раздел 15, ADR-14)."""

import sys

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все параметры бота. Обязателен только BOT_TOKEN; секреты — SecretStr."""

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    # --- Общее ---
    env: str = "dev"  # dev | prod
    tz: str = "Europe/Moscow"

    # --- Telegram ---
    bot_token: SecretStr
    owner_telegram_id: int | None = None
    owner_chat_id: int | None = None
    owner_username: str = "vegorovmsk"
    owner_full_name: str = "Владимир Егоров"
    telegram_proxy: str | None = None

    # --- Данные ---
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    data_retention_days: int = 180
    abandoned_session_days: int = 14
    consent_version: str = "2026-10-23"
    privacy_policy_url: str | None = None
    audit_hash_salt: SecretStr | None = None

    # --- Лимиты ---
    rate_limit_per_minute: int = 20
    max_briefs_per_user_per_day: int = 3
    max_revisions: int = 3

    # --- LLM ---
    llm_enabled: bool = True
    llm_provider: str = "yandex"  # yandex | openrouter | fake
    llm_base_url: str = "https://llm.api.cloud.yandex.net/v1"
    llm_api_key: SecretStr | None = None
    llm_project: str | None = None
    llm_model: str | None = None
    llm_model_estimate: str | None = None
    llm_judge_base_url: str = "https://openrouter.ai/api/v1"
    llm_judge_api_key: SecretStr | None = None
    llm_judge_model: str | None = None
    llm_price_per_1k_input_rub: float | None = None
    llm_price_per_1k_output_rub: float | None = None
    llm_daily_budget_rub: float = 300
    llm_proxy: str | None = None

    # --- Google ---
    gdrive_enabled: bool = False
    gdrive_oauth_client_id: str | None = None
    gdrive_oauth_client_secret: SecretStr | None = None
    gdrive_oauth_refresh_token: SecretStr | None = None
    gdrive_folder_id: str | None = None
    gsheets_enabled: bool = False
    gsheets_sa_key_path: str = "secrets/gsheets-sa.json"
    gsheet_id: str | None = None
    gsheet_worksheet: str = "Брифы"
    sheets_include_contacts: bool = False

    # --- Яндекс Диск ---
    yadisk_enabled: bool = False
    yadisk_oauth_token: SecretStr | None = None
    yadisk_base_path: str = "app:/briefs"
    cloud_file_ttl_days: int = 30

    # --- Почта ---
    email_enabled: bool = False
    smtp_host: str = "smtp.yandex.ru"
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str | None = None
    email_reply_to: str | None = None
    email_per_brief_limit: int = 2
    email_per_user_daily_limit: int = 3
    email_daily_limit: int = 50

    # --- VK (этап 6) ---
    vk_enabled: bool = False
    vk_group_id: int | None = None
    vk_group_token: SecretStr | None = None


def load_settings() -> Settings:
    """Прочитать настройки; при ошибке — понятное сообщение и выход, а не traceback."""
    try:
        return Settings()
    except ValidationError as exc:
        fields = ", ".join(str(err["loc"][0]).upper() for err in exc.errors())
        sys.exit(f"Ошибка конфигурации: проверьте переменные {fields} в .env")
