"""
app/main.py
Factory da aplicação FastAPI para o SAA29.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

# Importação dos routers (serão registrados no create_app)
from app.auth.router import router as auth_router
from app.aeronaves.router import router as aeronaves_router
from app.equipamentos.router import router as equipamentos_router
from app.panes.router import router as panes_router
from app.pages.router import router as pages_router


settings = get_settings()
FROTA_PADRAO = (
    "5902", "5905", "5906", "5912", "5914", "5915", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
)


async def _ensure_default_aeronaves() -> None:
    """
    Garante a frota padrão em ambientes reais, sem interferir nos testes em SQLite.
    """
    if "sqlite" in settings.database_url:
        return

    from sqlalchemy import select

    import app.aeronaves.models  # garante mapeamentos
    from app.aeronaves.models import Aeronave
    from app.database import get_session_factory

    async with get_session_factory()() as session:
        try:
            for matricula in FROTA_PADRAO:
                existente = await session.execute(
                    select(Aeronave).where(Aeronave.matricula == matricula)
                )
                if existente.scalar_one_or_none():
                    continue
                session.add(
                    Aeronave(
                        matricula=matricula,
                        serial_number=f"SN-{matricula}",
                        modelo="A-29",
                    )
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerenciador de ciclo de vida da aplicação.
    - startup: inicializar conexões, criar diretório de uploads
    - shutdown: fechar conexões graciosamente
    """
    # Startup: criar diretório de uploads se não existir
    os.makedirs(settings.upload_dir, exist_ok=True)
    await _ensure_default_aeronaves()

    yield

    # Shutdown: fechar engine de banco de dados
    from app.database import _engine
    if _engine is not None:
        await _engine.dispose()


def create_app() -> FastAPI:
    """
    Factory da aplicação FastAPI.
    Configura middlewares, routers e eventos de ciclo de vida.

    Retorna:
        FastAPI: instância configurada e pronta para uso.
    """
    app = FastAPI(
        title="SAA29 – Sistema de Gestão de Panes",
        description=(
            "Sistema web para gestão de panes de manutenção aeronáutica "
            "com foco na Eletrônica da aeronave A-29."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    _register_middlewares(app)
    _register_routers(app)
    _mount_static(app)

    return app


def _register_middlewares(app: FastAPI) -> None:
    """Registra os middlewares globais da aplicação."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_routers(app: FastAPI) -> None:
    """Registra todos os routers de domínio na aplicação."""
    app.include_router(auth_router,         prefix="/auth",         tags=["Autenticação"])
    app.include_router(aeronaves_router,    prefix="/aeronaves",    tags=["Aeronaves"])
    app.include_router(equipamentos_router, prefix="/equipamentos", tags=["Equipamentos"])
    app.include_router(panes_router,        prefix="/panes",        tags=["Panes"])
    
    # Frontend Pages (sem prefixo de API explícito - Root)
    app.include_router(pages_router)


def _mount_static(app: FastAPI) -> None:
    """
    Monta os arquivos estáticos públicos da aplicação.
    """
    # Cria pasta static caso não exista (para os CSS/JS)
    os.makedirs("static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Instância da aplicação (usada pelo uvicorn: app.main:app)
app = create_app()
