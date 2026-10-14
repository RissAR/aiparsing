from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DB_PATH: Path = BASE_DIR / "data" / "app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DB_PATH", mode="after")
    @classmethod
    def resolve_db_path(cls, v: Path) -> Path:
        if not v.is_absolute():
            return BASE_DIR / v
        return v


settings = Settings()

# Створення папки data/, якщо вона відсутня
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
