from contextlib import asynccontextmanager
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.seed import seed_data
from app.db.session import Base, SessionLocal, engine
from app import models  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.secret_key:
        if settings.is_production:
            raise RuntimeError("SECRET_KEY debe configurarse en produccion.")
        warnings.warn(
            "SECRET_KEY no configurado. El backend usara una clave vacia, "
            "lo que hace los tokens JWT inseguros. Configura SECRET_KEY en .env "
            "para entornos persistentes.",
            stacklevel=2,
        )
    if settings.auth_cookie_samesite.lower() not in {"lax", "strict", "none"}:
        raise RuntimeError("AUTH_COOKIE_SAMESITE debe ser lax, strict o none.")
    if settings.is_production and "*" in {
        origin.strip() for origin in settings.cors_origins.split(",")
    }:
        raise RuntimeError("CORS_ORIGINS no puede usar wildcard en produccion.")

    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        if settings.is_production or not settings.allow_create_all_fallback:
            raise RuntimeError("No se pudieron aplicar migraciones Alembic.") from exc
        warnings.warn(
            "Alembic fallo; usando create_all solo por fallback de desarrollo/test.",
            stacklevel=2,
        )
        Base.metadata.create_all(bind=engine)

    if settings.auto_seed_demo and not settings.is_production:
        with SessionLocal() as db:
            seed_data(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get(f"{settings.api_prefix}/health")
def api_health():
    return {"status": "ok"}
