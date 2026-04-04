from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Proyecto Tecnologico ECOE"
    api_prefix: str = "/api"
    secret_key: str = "ecoe-secret-key"
    access_token_expire_minutes: int = 60 * 24
    auth_cookie_name: str = "ecoe_session"
    auth_cookie_samesite: str = "lax"
    database_url: str = "postgresql+psycopg://ecoe:ecoe@db:5432/ecoe"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"
    storage_path: str = "/app/storage"
    default_timer_sound: str = "/app/storage/default-bell.mp3"
    creator_password: str = "change-me-creator"
    coeditor_password: str = "change-me-coeditor"
    evaluator_password: str = "change-me-evaluator"
    student_password: str = "change-me-student"
    coordinator_password: str = "change-me-coordinator"
    timer_password: str = "change-me-timer"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
