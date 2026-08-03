"""
app/shared/core/exceptions.py
Exceções de domínio tipadas e centralização do tratamento de erros (SRP).
"""

import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

logger = logging.getLogger(__name__)

# ===========================================================================
# Exceções de Domínio (Baseadas no Método Akita)
# ===========================================================================

class SAA29BaseException(HTTPException):
    """Classe base para todas as exceções do sistema."""
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)

class EntidadeNaoEncontradaError(SAA29BaseException):
    """Lançada quando um recurso (Aeronave, Item, Usuário) não existe."""
    def __init__(self, detail: str = "Recurso não encontrado"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)

class ConflitoNegocioError(SAA29BaseException):
    """Lançada quando uma regra de negócio impede a operação (ex: item já em uso)."""
    def __init__(self, detail: str = "Conflito na regra de negócio"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)

class PermissaoNegadaError(SAA29BaseException):
    """Lançada quando o usuário não tem autorização para a ação."""
    def __init__(self, detail: str = "Acesso negado"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)

class ContaBloqueadaError(SAA29BaseException):
    """Lançada quando a conta está temporariamente bloqueada por excesso de tentativas de login falhas."""
    def __init__(self, detail: str = "Conta temporariamente bloqueada."):
        super().__init__(detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


# ===========================================================================
# Configuração de Handlers (Fábrica)
# ===========================================================================

def setup_exception_handlers(app: FastAPI, api_prefixes: list[str] | None = None) -> None:
    """
    Configura os handlers globais de exceção para a aplicação.

    Args:
        api_prefixes: prefixos de rotas que são EXCLUSIVAMENTE API (JSON),
            usados para decidir se um 401/403 deve redirecionar para /login
            (navegação de página) ou devolver JSON (chamada de API). Deve
            vir de `main.py:_register_routers` — **fonte única**, para não
            repetir uma segunda lista aqui que fica desatualizada quando um
            router novo é registrado com prefixo fora do padrão (foi
            exatamente o que aconteceu com `/api/v1/calendario`: um 401
            ali, vindo de um cliente que aceitasse text/html, virava um
            redirect 307 para /login em vez de JSON 401, porque a lista
            hardcoded aqui não incluía esse prefixo).
    """
    api_prefixes = api_prefixes or []

    # 1. Rate Limiting (SlowAPI)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 2. Custom HTTP Exception Handler (M-06)
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        """
        Intercepta erros HTTP (principalmente 401/403) para redirecionar
        o usuário para a página de login caso seja uma requisição de página (HTML).
        """
        if exc.status_code in [401, 403]:
            path = request.url.path
            accept = request.headers.get("accept", "").lower()

            is_api = any(path.startswith(p) for p in api_prefixes)

            # Se for navegação via browser (HTML) e não for API, redireciona pro login
            if "text/html" in accept and not is_api and path != "/login":
                logger.warning("[Auth Redirect] Redirecionando %s para /login (Erro %s)", path, exc.status_code)
                return RedirectResponse(url="/login")

        # Fallback para o handler padrão do FastAPI
        return await http_exception_handler(request, exc)

    # 3. Handler genérico para exceções não tratadas (item #9/Etapa 5).
    # Sem isso, uma exceção inesperada subia até o Starlette e, com
    # app_debug=True, podia expor o stack trace completo ao cliente — o
    # AttributeError do item #1/Etapa 3 (domain_exc.NotFoundError
    # inexistente) é um exemplo real de bug que já aconteceu nesse caminho.
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Exceção não tratada em %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Erro interno do servidor."},
        )
