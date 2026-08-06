"""
app/shared/middleware/security.py
Middleware para injeção de headers de segurança globais (SEC-04).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.bootstrap.config import get_settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adiciona headers de segurança globais:
    - X-Content-Type-Options: nosniff (previne MIME-sniffing)
    - X-Frame-Options: DENY (previne clickjacking)
    - X-XSS-Protection: 1; mode=block (legacy XSS protection)
    - Content-Security-Policy: CSP robusta (Zero Inline Scripts)
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
        
        # Content Security Policy (Ajustada para permitir Google Fonts, R2 storage e banner styles)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self'; "
            "img-src 'self' data: https://*.r2.cloudflarestorage.com; "
            "connect-src 'self' https://*.r2.cloudflarestorage.com; "
            "frame-src 'self' https://*.r2.cloudflarestorage.com; "
            # Delta do viewer de PDF do módulo publicacoes (M1): o PDF.js
            # vendorizado instancia o worker via `new Worker(workerSrc, {type:
            # "module"})` apontando para um arquivo same-origin
            # (`/static/js/pdfjs/pdf.worker.min.mjs`), nunca um Blob — por
            # isso `'self'` basta, sem precisar de `blob:`. Sem `worker-src`
            # explícito o worker cairia no fallback de `default-src 'self'`,
            # que já cobriria o mesmo caso; a diretiva foi tornada explícita
            # para não depender desse fallback caso `default-src` mude no
            # futuro. Ver docs/methodology/CSP.md.
            "worker-src 'self';"
        )
        
        # HSTS em produção (se usando HTTPS)
        settings = get_settings()
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
