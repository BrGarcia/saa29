"""
app/main.py
Factory da aplicação FastAPI para o SAA29.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Importar TODOS os modelos explicitamente para o SQLAlchemy Registry (SEC-02/COR-01)
# ATENÇÃO: a ordem importa — equipamentos.models deve vir antes de aeronaves.models
# pois Aeronave tem relationship("Instalacao") e o mapper precisa que Instalacao já esteja registrada.
import app.auth.models
import app.equipamentos.models
import app.aeronaves.models
import app.panes.models

from app.config import get_settings

# Importação dos routers (serão registrados no create_app)
from app.auth.router import router as auth_router
from app.aeronaves.router import router as aeronaves_router
from app.equipamentos.router import router as equipamentos_router
from app.panes.router import router as panes_router
from app.pages.router import router as pages_router
from app.core.limiter import limiter


# Configuração do Rate Limiting
# Removido daqui e movido para app.core.limiter para evitar circularidade



settings = get_settings()
FROTA_PADRAO = (
    "5902", "5905", "5906", "5912", "5914", "5915", "5919", "5937", "5941", "5945",
    "5946", "5947", "5949", "5952", "5954", "5955", "5956", "5957", "5958", "5962",
)


async def _ensure_default_aeronaves() -> None:
    """
    Garante a frota padrão no banco de dados.
    Otimizado para realizar apenas uma query de verificação inicial.
    """
    from sqlalchemy import select
    from app.aeronaves.models import Aeronave
    from app.database import get_session_factory

    async with get_session_factory()() as session:
        try:
            # 1. Buscar todas as matrículas existentes da frota padrão
            result = await session.execute(
                select(Aeronave.matricula).where(Aeronave.matricula.in_(FROTA_PADRAO))
            )
            existentes = {row[0] for row in result.all()}

            # 2. Identificar quais faltam e adicionar
            faltantes = [m for m in FROTA_PADRAO if m not in existentes]
            
            if faltantes:
                print(f"➕ Adicionando {len(faltantes)} aeronaves à frota padrão...")
                for matricula in faltantes:
                    session.add(
                        Aeronave(
                            matricula=matricula,
                            serial_number=f"SN-{matricula}",
                            modelo="A-29",
                        )
                    )
                await session.commit()
        except Exception as e:
            print(f"❌ Erro ao inicializar frota: {e}")
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Backup orientado a eventos (event-driven) — sem timer periódico
# ---------------------------------------------------------------------------

_db_dirty: bool = False          # True quando há escrita não salva no R2
_backup_task = None              # asyncio.Task do debounce em andamento
_BACKUP_DEBOUNCE_SECONDS = 120   # aguarda 2 min após última escrita antes de enviar


def _mark_db_dirty(*args, **kwargs) -> None:
    """Chamado pelo SQLAlchemy after_commit. Agenda o backup com debounce."""
    global _db_dirty
    _db_dirty = True
    _schedule_debounced_backup()


def _schedule_debounced_backup() -> None:
    """Cancela qualquer backup pendente e agenda um novo após DEBOUNCE segundos."""
    import asyncio
    global _backup_task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # Fora de um contexto async, ignora

    if _backup_task and not _backup_task.done():
        _backup_task.cancel()

    _backup_task = loop.create_task(_debounced_backup())


async def _debounced_backup() -> None:
    """Aguarda o debounce e executa o backup se o banco estiver sujo."""
    import asyncio
    global _db_dirty

    try:
        await asyncio.sleep(_BACKUP_DEBOUNCE_SECONDS)
        if _db_dirty:
            _run_r2_backup()
            _db_dirty = False
    except asyncio.CancelledError:
        pass  # Nova escrita chegou — será reagendado pelo próximo commit


def _run_r2_backup() -> None:
    """Executa backup síncrono do banco SQLite para o Cloudflare R2."""
    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, "scripts/r2_manager.py", "backup"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logging.info("[R2 Backup] %s", result.stdout.strip())
        else:
            logging.warning("[R2 Backup] Falha: %s", result.stderr.strip())
    except Exception as exc:
        logging.error("[R2 Backup] Erro inesperado: %s", exc)


# -------- Security Headers Middleware (Sprint 2.2) --------
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adiciona headers de segurança globais:
    - X-Content-Type-Options: nosniff (previne MIME-sniffing)
    - X-Frame-Options: DENY (previne clickjacking)
    - X-XSS-Protection: 1; mode=block (legacy XSS protection)
    - Strict-Transport-Security: enable HSTS em produção
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Previne MIME-sniffing attacks
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Previne clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Legacy XSS protection (newer: use CSP)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy (Ajustada para permitir Google Fonts e inline scripts necessários)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:;"
        )
        
        # HSTS em produção (se usando HTTPS)
        settings = get_settings()
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerenciador de ciclo de vida da aplicação.
    - startup: inicializar conexões, registrar listener de backup, criar uploads/
    - shutdown: backup final (se houver dados não salvos) + fechar conexões
    """
    from app.config import get_settings
    current_settings = get_settings()

    # Startup: criar diretório de uploads se não existir
    os.makedirs(current_settings.upload_dir, exist_ok=True)
    await _ensure_default_aeronaves()

    # Registrar listener de escrita no banco (event-driven backup)
    # Nota: AsyncSession não suporta after_commit diretamente.
    # O evento deve ser registrado no Session síncrono subjacente.
    if current_settings.storage_backend.lower() == "r2" and current_settings.r2_bucket_name:
        from sqlalchemy import event as sa_event
        from sqlalchemy.orm import Session
        sa_event.listen(Session, "after_commit", _mark_db_dirty)
        logging.info("[R2 Backup] Backup orientado a eventos ativo (debounce: %ds).", _BACKUP_DEBOUNCE_SECONDS)

    yield

    # Shutdown: backup final se houver dados não persistidos no R2
    if _db_dirty and current_settings.storage_backend.lower() == "r2" and current_settings.r2_bucket_name:
        logging.info("[R2 Backup] Shutdown com dados não salvos — executando backup final...")
        _run_r2_backup()

    # Fechar engine de banco de dados
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
    from app.config import get_settings
    current_settings = get_settings()

    app = FastAPI(
        title="SAA29 – Sistema de Gestão de Panes",
        description=(
            "Sistema web para gestão de panes de manutenção aeronáutica "
            "com foco na Eletrônica da aeronave A-29."
        ),
        version="1.0.0",
        docs_url="/docs" if current_settings.app_debug else None,
        redoc_url="/redoc" if current_settings.app_debug else None,
        lifespan=lifespan,
    )

    # Configura o estado do limiter no app e o manipulador de exceção
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    _register_middlewares(app)
    _register_routers(app)
    _mount_static(app)

    return app


def _register_middlewares(app: FastAPI) -> None:
    """Registra os middlewares globais da aplicação."""
    from app.config import get_settings
    current_settings = get_settings()

    # Add Security Headers Middleware (Sprint 2.2)
    app.add_middleware(
        SecurityHeadersMiddleware
    )

    # Add CSRF Middleware (Sprint 2.3)
    from app.middleware.csrf import CSRFMiddleware
    app.add_middleware(CSRFMiddleware)

    # Trusted Hosts (Ajuste para seu domínio real em produção) (AUD-07)
    # No Railway, o host muda dinamicamente. Se estiver como "*", permitimos todos.
    if "*" not in current_settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware, 
            allowed_hosts=["localhost", "127.0.0.1", "testserver"] + current_settings.allowed_hosts
        )

    # CORS (Sprint 2.2: More restrictive)
    # O navegador proíbe allow_origins=["*"] com allow_credentials=True.
    # Como o frontend e a API estão no mesmo app, as chamadas são na mesma origem.
    # Vamos definir explicitamente as origens, métodos e headers permitidos.
    cors_origins = current_settings.allowed_origins
    if "*" in cors_origins:
        # Se for "*", permitimos as origens comuns de dev (não usar "*" em CORS com credentials)
        cors_origins = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods (was "*")
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",  # For CSRF protection
        ],
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
