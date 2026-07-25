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
        
        # 2. Geração Inicial de Token no Request State
        # Sempre geramos o token no request.state para o caso de um template HTML ser renderizado.
        token_pair = csrf_protect.generate_csrf()
        raw_token, signed_token = (
            token_pair if isinstance(token_pair, tuple) else (token_pair, token_pair)
        )
        request.state.csrf_token = raw_token

        # 3. Processa a requisição
        response = await call_next(request)

        # 4. Obtenção/Decisão de Emissão de Tokens na Resposta
        # Reemitimos o par CSRF no cookie e no header apenas quando:
        # - Requisição de mutação (POST, PUT, PATCH, DELETE);
        # - Ainda não existe cookie na sessão do usuário (primeira requisição);
        # - O frontend enviou explicitamente o header X-CSRF-Token (sincronização via AJAX/apiFetch);
        # - A resposta é um documento HTML completo (Content-Type text/html), onde a meta tag CSRF é renderizada.
        # Evitamos reemitir o cookie em requisições GET para recursos não-HTML (PDF, CSV, XLSX, imagens, etc.),
        # pois o navegador não recarrega o DOM e a meta tag ficaria dessincronizada com o cookie.
        csrf_cookie = request.cookies.get("fastapi-csrf-token")
        csrf_header = request.headers.get("X-CSRF-Token")
        response_content_type = response.headers.get("content-type", "").lower()
        is_html_response = "text/html" in response_content_type

        should_issue_token = (
            request.method != "GET"
            or not csrf_cookie
            or bool(csrf_header)
            or is_html_response
        )

        if should_issue_token and signed_token and raw_token:
            # Seta o cookie com o token ASSINADO (contrato correto)
            csrf_protect.set_csrf_cookie(signed_token, response)

            # Sincroniza o token BRUTO no header para chamadas AJAX subsequentes
            response.headers["X-CSRF-Token"] = raw_token
        
        return response
