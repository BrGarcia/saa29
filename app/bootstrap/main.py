"""
app/main.py
Factory da aplicação FastAPI para o SAA29.
Orquestrador central seguindo o Princípio da Responsabilidade Única (SRP).
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

# --- Registro do SQLAlchemy (Ordem importa) ---
import app.modules.inspecoes.models
import app.modules.auth.models
import app.modules.equipamentos.models
import app.modules.vencimentos.models
import app.modules.aeronaves.models
import app.modules.panes.models
import app.modules.efetivo.models
import app.modules.calendario.models

# --- Configurações e Ciclo de Vida ---
from app.bootstrap.config import get_settings
from app.bootstrap.events import lifespan
from app.shared.core.limiter import limiter

# --- Routers ---
from app.modules.auth.router import router as auth_router
from app.modules.efetivo.router import router as efetivo_router
from app.modules.aeronaves.router import router as aeronaves_router
from app.modules.equipamentos.router import router as equipamentos_router
from app.modules.vencimentos.router import router as vencimentos_router
from app.modules.panes.router import router as panes_router
from app.modules.inspecoes.router import router as inspecoes_router
from app.modules.calendario.router import router as calendario_router
from app.modules.dashboard.router import router as dashboard_router
from app.web.pages.router import router as pages_router
from app.web.pages.mobile_router import router as mobile_router


def create_app() -> FastAPI:
    """
    Factory da aplicação FastAPI.
    Configura middlewares, routers, exception handlers e ciclo de vida.
    """
    settings = get_settings()

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

    # 1. Estado do Limiter
    app.state.limiter = limiter

    # 2. Exception Handlers (Redirects UI e Rate Limits)
    from app.shared.core.exceptions import setup_exception_handlers
    setup_exception_handlers(app)

    # 3. Middlewares e Rotas
    _register_middlewares(app)
    _register_routers(app)
    _mount_static(app)

    return app


def _register_middlewares(app: FastAPI) -> None:
    """Registra os middlewares globais da aplicação."""
    settings = get_settings()

    # Security Headers (MIME, Clickjacking, CSP, HSTS)
    from app.shared.middleware.security import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Proteção CSRF
    from app.shared.middleware.csrf import CSRFMiddleware
    app.add_middleware(CSRFMiddleware)

    # Trusted Hosts
    if "*" not in settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware, 
            allowed_hosts=["localhost", "127.0.0.1", "testserver"] + settings.allowed_hosts
        )

    # CORS Configuration
    cors_origins = settings.allowed_origins
    if "*" in cors_origins:
        cors_origins = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )


def _register_routers(app: FastAPI) -> None:
    """Registra todos os routers de domínio na aplicação."""
    app.include_router(auth_router,         prefix="/auth",         tags=["Autenticação"])
    app.include_router(efetivo_router,      prefix="/efetivo",      tags=["Efetivo"])
    app.include_router(aeronaves_router,    prefix="/aeronaves",    tags=["Aeronaves"])
    app.include_router(equipamentos_router, prefix="/equipamentos", tags=["Equipamentos"])
    app.include_router(vencimentos_router,  prefix="/vencimentos",  tags=["Vencimentos"])
    app.include_router(panes_router,        prefix="/panes",        tags=["Panes"])
    app.include_router(inspecoes_router,    prefix="/inspecoes",    tags=["Inspeções"])
    app.include_router(calendario_router,   prefix="/api/v1/calendario", tags=["Calendario"])
    app.include_router(dashboard_router,    prefix="/dashboard",    tags=["Dashboard"])
    
    # Frontend Pages (Root / UI)
    app.include_router(mobile_router)
    app.include_router(pages_router)


def _mount_static(app: FastAPI) -> None:
    """Monta os arquivos estáticos públicos da aplicação."""
    os.makedirs("app/web/static", exist_ok=True)
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


# Instância global para o servidor ASGI
app = create_app()
