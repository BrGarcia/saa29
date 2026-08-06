"""
app/main.py
Factory da aplicação FastAPI para o SAA29.
Orquestrador central seguindo o Princípio da Responsabilidade Única (SRP).
"""

import logging
import mimetypes
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
import app.modules.publicacoes.models

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
from app.modules.publicacoes.router import router as publicacoes_router
from app.web.pages.router import router as pages_router
from app.web.pages.mobile_router import router as mobile_router

logger = logging.getLogger(__name__)

# Fonte única de verdade dos prefixos de API (JSON) — usada tanto para
# registrar os routers quanto pelo exception handler global (item #8/Etapa
# 5) para decidir se um 401/403 deve redirecionar para /login (rota de
# página) ou devolver JSON (chamada de API). Manter isso como uma lista
# duplicada e mantida manualmente em dois lugares foi o que causou o bug
# original: o calendário usa /api/v1/calendario, prefixo fora do padrão
# /<modulo> dos demais, e ficou de fora da cópia que existia em
# exceptions.py.
API_PREFIXES = [
    "/auth/", "/efetivo/", "/aeronaves/", "/equipamentos/", "/vencimentos/",
    "/panes/", "/inspecoes/", "/api/v1/calendario/", "/dashboard/",
    # ATENÇÃO: "/publicacoes/api/", NUNCA "/publicacoes/". O módulo serve
    # páginas HTML no mesmo prefixo (/publicacoes, /publicacoes/viewer/...);
    # registrar o prefixo curto aqui faria o handler global devolver JSON 401
    # para elas em vez de redirecionar para /login — o mesmo bug que o
    # calendário já causou, e por isso todo endpoint JSON do módulo vive sob
    # o sub-prefixo /api/ (03_especificacao_tecnica.md §3, risco R20).
    "/publicacoes/api/",
]


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
    setup_exception_handlers(app, api_prefixes=API_PREFIXES)

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
        # allow_credentials=True proíbe usar "*" como origem (regra do
        # CORS): sem este fallback, o middleware simplesmente rejeitaria
        # toda origem em runtime. Silenciosamente trocado por um conjunto
        # fixo de origens de desenvolvimento — se ALLOWED_ORIGINS="*" for
        # deixado assim em produção por engano, o CORS quebra sem que
        # ninguém saiba o motivo. Logado como warning para não passar
        # despercebido num deploy real.
        logger.warning(
            "ALLOWED_ORIGINS=\"*\" não é compatível com allow_credentials=True — "
            "usando origens de desenvolvimento (localhost) como fallback. "
            "Configure ALLOWED_ORIGINS explicitamente em produção."
        )
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
    app.include_router(publicacoes_router,  prefix="/publicacoes",  tags=["Publicações"])
    
    # Frontend Pages (Root / UI)
    app.include_router(mobile_router)
    app.include_router(pages_router)


def _mount_static(app: FastAPI) -> None:
    """Monta os arquivos estáticos públicos da aplicação."""
    os.makedirs("app/web/static", exist_ok=True)

    # `.mjs` (módulos ES do PDF.js vendorizado, `app/web/static/js/pdfjs/`)
    # precisa resolver para um MIME de JavaScript — navegadores rejeitam a
    # execução de `<script type="module">` cujo Content-Type não seja um dos
    # tipos JS reconhecidos (MIME sniffing estrito para módulos). O mapeamento
    # de `mimetypes` vem do SO (`/etc/mime.types` no Linux, registro no
    # Windows) e `.mjs` é recente o bastante para não estar em toda
    # distribuição — registrar aqui torna o resultado igual em qualquer
    # ambiente, em vez de depender do que a máquina tem instalado.
    mimetypes.add_type("text/javascript", ".mjs")

    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")


# Instância global para o servidor ASGI
app = create_app()
