from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import get_settings

class CsrfSettings(BaseModel):
    secret_key: str = get_settings().app_secret_key
    cookie_samesite: str = "lax"
    cookie_secure: bool = get_settings().app_env == "production"

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        csrf_protect = CsrfProtect()
        
        # 1. Validação CSRF
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            if request.url.path not in ["/auth/login", "/auth/logout"]:
                try:
                    await csrf_protect.validate_csrf(request)
                except Exception as exc:
                    print(f"CSRF Error: {exc}")
                    return JSONResponse(
                        status_code=401, 
                        content={"detail": "Sessão de segurança expirada. Recarregue a página (F5)."}
                    )
        
        # 2. Gerenciamento Inteligente de Token
        # Se o navegador já tem um token bruto no cookie, usamos ele para gerar a assinatura.
        # Isso evita trocar o segredo a cada requisição GET.
        raw_token = request.cookies.get("fastapi-csrf-token")
        
        if raw_token:
            # Gera a assinatura baseada no token que o usuário JÁ TEM
            signed_token = csrf_protect.generate_csrf(raw_token)
            # Se retornar tupla, pegamos a parte assinada
            if isinstance(signed_token, tuple):
                signed_token = signed_token[1]
        else:
            # Se não tem token, gera um novo par
            token_pair = csrf_protect.generate_csrf()
            if isinstance(token_pair, tuple):
                raw_token, signed_token = token_pair
            else:
                raw_token = signed_token = token_pair
        
        # Garante que não existam aspas literais na string enviada ao HTML
        if isinstance(signed_token, str):
            signed_token = signed_token.strip('"')

        # 3. Disponibiliza para o Template
        request.state.csrf_token = signed_token
        
        # 4. Processa
        response = await call_next(request)
        
        # 5. Só renovamos o cookie se ele for novo
        if raw_token:
            csrf_protect.set_csrf_cookie(raw_token, response)
        
        # 6. Envia o token ASSINADO no header para o frontend se manter sincronizado (AJAX)
        response.headers["X-CSRF-Token"] = signed_token
        
        return response
