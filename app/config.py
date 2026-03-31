"""
app/config.py
Configurações da aplicação via pydantic-settings.
Os valores são lidos do arquivo .env (ou variáveis de ambiente).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
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
    jwt_expire_minutes: int = 120  # 2 horas (AUD-18)

    # --- Upload ---
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10

    # --- CORS / SEGURANÇA ---
    allowed_origins: list[str] = ["http://localhost:8000"]
    allowed_hosts: list[str] = []  # Em produção, especifique os hosts permitidos (AUD-07)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_db_url(self):
        """Força SQLite se em development e a URL for a padrão do exemplo (AUD-07)."""
        if self.app_env == "development" and "postgresql" in self.database_url:
             # Se o usuário não trocou a URL padrão no .env local, usamos SQLite para facilitar
             self.database_url = "sqlite+aiosqlite:///./saa29_local.db"
        return self

    @model_validator(mode="after")
    def validate_secret(self):
        """Impede o uso de chave insegura em ambiente de produção (AUD-08)."""
        if self.app_env == "production" and "INSECURE" in self.app_secret_key:
            raise ValueError("APP_SECRET_KEY deve ser definida em produção!")
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    Usar como dependência FastAPI: Depends(get_settings).
    """
    return Settings()
