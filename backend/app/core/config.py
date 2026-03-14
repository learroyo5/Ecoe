from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Proyecto Tecnologico ECOE"
    api_prefix: str = "/api"
    secret_key: str = "ecoe-secret-key"
    access_token_expire_minutes: int = 60 * 24
    database_url: str = "postgresql+psycopg://ecoe:ecoe@db:5432/ecoe"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"
    storage_path: str = "/app/storage"
    default_timer_sound: str = "/app/storage/default-bell.mp3"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
