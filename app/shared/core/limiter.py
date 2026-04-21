from slowapi import Limiter
from slowapi.util import get_remote_address
from app.bootstrap.config import get_settings

# Desativa o limiter em ambiente de teste para não travar a suite de testes (Dia 3)
settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.app_env != "testing"
)
