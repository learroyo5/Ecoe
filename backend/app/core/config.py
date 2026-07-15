from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Proyecto Tecnologico ECOE"
    api_prefix: str = "/api"
    environment: str = "development"
    auto_seed_demo: bool = True
    # Alembic is the only supported way to create/upgrade the schema.
    # create_all is opt-in for throwaway local environments only.
    allow_create_all_fallback: bool = False
    # SECURITY: secret_key MUST be set via .env in production.
    # The default below is only for local development with Docker Compose.
    secret_key: str = ""
    jwt_issuer: str = "ecoe-backend"
    jwt_audience: str = "ecoe-web"
    # 12h: cubre la jornada completa de un examen sin dejar tokens vivos un dia entero.
    access_token_expire_minutes: int = 60 * 12
    invitation_expire_hours: int = 72
    # Debe cubrir la jornada completa del examen desde que se vincula la tablet.
    kiosk_token_expire_hours: int = 24
    auth_cookie_name: str = "ecoe_session"
    auth_cookie_samesite: str = "lax"
    database_url: str = "postgresql+psycopg://ecoe:ecoe@db:5432/ecoe"
    cors_origins: str = "http://localhost:3000,http://frontend:3000"
    storage_path: str = "/app/storage"
    default_timer_sound: str = "/app/storage/default-bell.mp3"
    # Default passwords are empty — set them via .env or docker-compose env.
    admin_password: str = ""
    coeditor_password: str = ""
    evaluator_password: str = ""
    student_password: str = ""
    coordinator_password: str = ""
    timer_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
