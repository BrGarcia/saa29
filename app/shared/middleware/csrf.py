import logging
import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.bootstrap.config import get_settings

logger = logging.getLogger(__name__)

# Segredo gerado uma única vez por processo, só relevante quando
# APP_ENV=testing. Antes, o bypass dependia só do valor fixo "true" no
# header X-Skip-CSRF — se APP_ENV=testing vazasse para produção (ambiente
# mal configurado, típico de staging), qualquer cliente externo derrubaria
# a proteção CSRF inteira com um header previsível. Agora o valor precisa
# coincidir com este segredo aleatório, conhecido apenas pelo processo da
# aplicação em memória — tests/conftest.py o importa diretamente daqui.
TESTING_CSRF_BYPASS_SECRET = secrets.token_urlsafe(32)


class CsrfSettings(BaseModel):
    # default_factory (não um valor fixo) para que secret_key/cookie_secure
    # sejam resolvidos a cada instanciação de CsrfSettings, não uma única
    # vez em tempo de definição da classe (import do módulo) — do jeito
    # anterior, trocar `get_settings()` em runtime (ex.: monkeypatch em
    # teste) não tinha efeito algum sobre esta configuração.
    secret_key: str = Field(default_factory=lambda: get_settings().app_secret_key)
    cookie_samesite: str = "lax"
    cookie_secure: bool = Field(
        default_factory=lambda: get_settings().force_secure_cookies
    )
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
        # Bypassa validação apenas se o header de bypass estiver presente com o
        # segredo correto (injetado no conftest.py). Isso permite que a suite de
        # testes de lógica funcione enquanto test_csrf.py testa a trava real.
        settings = get_settings()
        skip_csrf = (
            settings.app_env == "testing"
            and request.headers.get("X-Skip-CSRF") == TESTING_CSRF_BYPASS_SECRET
        )

        if request.method in ["POST", "PUT", "PATCH", "DELETE"] and not skip_csrf:
            # A isenção que existia aqui para /auth/login e /auth/logout foi
            # removida: verificado que login.js já lê o token da meta tag
            # <meta name="csrf-token"> (renderizada em base.html a partir de
            # request.state.csrf_token, disponível na página de login antes
            # do POST) e o envia via X-CSRF-Token; e app.js:clearAuth() já
            # faz o mesmo para /auth/logout. A isenção não protegia nenhum
            # fluxo real — apenas abria login CSRF (atacante força a vítima
            # a autenticar numa conta do atacante) e logout CSRF sem
            # necessidade.
            try:
                await csrf_protect.validate_csrf(request)
            except CsrfProtectError as exc:
                # Mensagem genérica ao cliente; detalhe fica só no log do
                # servidor (item #6 — evita vazar informação técnica interna).
                logger.warning("Falha de validação CSRF em %s: %s", request.url.path, exc)
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Erro de segurança (CSRF). Recarregue a página."}
                )
        
        # 2. Geração Inicial de Token no Request State
        # Necessário ANTES de call_next só para o caso de a rota renderizar um
        # template HTML que embuta o token (só acontece em GET). Para
        # arquivos estáticos (`/static/...`) isso nunca acontece — pular a
        # geração aqui evita trabalho desperdiçado em toda requisição de
        # imagem/JS/CSS, que antes gerava um par de tokens só para descartar
        # depois (should_issue_token normalmente é False para esses casos).
        raw_token = signed_token = None
        if not request.url.path.startswith("/static/"):
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

        if is_html_response:
            # Templates HTML carregam o token bruto em <meta name="csrf-token">.
            # Em produção, qualquer cache de navegador/proxy/CDN que reutilize
            # esse HTML pode entregar uma meta tag que não corresponde ao cookie
            # assinado atual, causando 403 no próximo POST válido.
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

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
