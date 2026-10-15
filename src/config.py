from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DB_PATH: Path = BASE_DIR / "data" / "app.db"
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def GEMINI_API_KEY(self) -> Optional[str]:
        return self.gemini_api_key

    @property
    def GEMINI_MODEL(self) -> str:
        return self.gemini_model

    @field_validator("DB_PATH", mode="after")
    @classmethod
    def resolve_db_path(cls, v: Path) -> Path:
        if not v.is_absolute():
            return BASE_DIR / v
        return v


settings = Settings()

# Створення папки data/, якщо вона відсутня
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
