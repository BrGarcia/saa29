"""
app/config.py
Configurações da aplicação via pydantic-settings.
Os valores são lidos do arquivo .env (ou variáveis de ambiente).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configurações globais da aplicação SAA29.
    Todas as variáveis são lidas do arquivo .env automaticamente.
    """

    # --- Aplicação ---
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION"

    # --- Banco de Dados ---
    database_url: str = "postgresql+asyncpg://saa29_user:senha@localhost:5432/saa29_db"

    # --- JWT ---
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 horas

    # --- Upload ---
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    Usar como dependência FastAPI: Depends(get_settings).
    """
    return Settings()
