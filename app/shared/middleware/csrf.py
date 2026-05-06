from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.bootstrap.config import get_settings

class CsrfSettings(BaseModel):
    secret_key: str = get_settings().app_secret_key
    cookie_samesite: str = "lax"
    cookie_secure: bool = get_settings().app_env == "production"
    # O contrato exige que o token assinado fique no cookie
    # e o token bruto seja enviado pelo Header.
    cookie_name: str = "fastapi-csrf-token"
    # Ensure PATCH is supported
    methods: set[str] = {"POST", "PUT", "PATCH", "DELETE"}

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        csrf_protect = CsrfProtect()
        
        # 1. Validação CSRF (Somente mutações)
        # Bypassa validação apenas se o header de bypass estiver presente (injetado no conftest.py)
        # Isso permite que a suite de testes de lógica funcione enquanto test_csrf.py testa a trava real.
        settings = get_settings()
        skip_csrf = (
            settings.app_env == "testing" 
            and request.headers.get("X-Skip-CSRF") == "true"
        )

        if request.method in ["POST", "PUT", "PATCH", "DELETE"] and not skip_csrf:
            # Excessão para rotas de entrada de sessão
            if request.url.path not in ["/auth/login", "/auth/logout"]:
                try:
                    await csrf_protect.validate_csrf(request)
                except Exception as exc:
                    # Retornamos 403 Forbidden para não deslogar o usuário via app.js
                    return JSONResponse(
                        status_code=403, 
                        content={"detail": f"Erro de Segurança (CSRF): {str(exc)}. Recarregue a página."}
                    )
        
        # 2. Obtenção/Geração de Tokens
        # Reemitimos o par CSRF apenas quando:
        # - ainda não existe cookie;
        # - a resposta precisa renderizar HTML completo (meta tag);
        # - o frontend já enviou um token e espera sincronização de volta.
        # Isso evita invalidar a meta tag atual ao abrir anexos/imagens/PDFs direto no navegador.
        csrf_cookie = request.cookies.get("fastapi-csrf-token")
        accept = request.headers.get("accept", "").lower()
        sec_fetch_dest = request.headers.get("sec-fetch-dest", "").lower()
        csrf_header = request.headers.get("X-CSRF-Token")
        is_html_navigation = "text/html" in accept or sec_fetch_dest == "document"
        should_issue_token = (
            request.method != "GET"
            or not csrf_cookie
            or is_html_navigation
            or bool(csrf_header)
        )

        raw_token = None
        signed_token = None
        if should_issue_token:
            # De acordo com a documentação, generate_csrf() retorna (csrf_token, signed_token)
            # csrf_token -> Plain text (para o Header/Meta)
            # signed_token -> Signed (para o Cookie)
            token_pair = csrf_protect.generate_csrf()
            raw_token, signed_token = (
                token_pair if isinstance(token_pair, tuple) else (token_pair, token_pair)
            )
            request.state.csrf_token = raw_token

        # 3. Processa a requisição
        response = await call_next(request)

        if should_issue_token and signed_token and raw_token:
            # 4. Seta o cookie com o token ASSINADO (contrato correto)
            csrf_protect.set_csrf_cookie(signed_token, response)

            # 5. Sincroniza o token BRUTO no header para chamadas AJAX subsequentes
            response.headers["X-CSRF-Token"] = raw_token
        
        return response
