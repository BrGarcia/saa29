"""
app/shared/core/exceptions.py
Exceções de domínio tipadas e centralização do tratamento de erros (SRP).
"""

import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

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


# ===========================================================================
# Configuração de Handlers (Fábrica)
# ===========================================================================

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configura os handlers globais de exceção para a aplicação.
    """
    
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
            
            # Lista de prefixos que são EXCLUSIVAMENTE API (JSON)
            api_prefixes = ["/auth/", "/efetivo/", "/aeronaves/", "/equipamentos/", "/vencimentos/", "/panes/", "/inspecoes/", "/dashboard/"]
            is_api = any(path.startswith(p) for p in api_prefixes)
            
            # Se for navegação via browser (HTML) e não for API, redireciona pro login
            if "text/html" in accept and not is_api and path != "/login":
                logging.warning(f"[Auth Redirect] Redirecionando {path} para /login (Erro {exc.status_code})")
                return RedirectResponse(url="/login")
        
        # Fallback para o handler padrão do FastAPI
        return await http_exception_handler(request, exc)
