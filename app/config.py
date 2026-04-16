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
    # Padrão: SQLite para instalação local ou produção básica (monolito).
    database_url: str = "sqlite+aiosqlite:///./saa29_local.db"

    # --- JWT ---
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120  # 2 horas (AUD-18)

    # --- Upload ---
    upload_dir: str = "uploads"
    max_upload_size_mb: float = 0.5

    # --- CORS / SEGURANÇA ---
    # Aceita lista via JSON ou string separada por vírgula
    allowed_origins: list[str] | str = ["*"]
    allowed_hosts: list[str] | str = ["*"]

    @model_validator(mode="after")
    def validate_origins_and_hosts(self) -> "Settings":
        """Converte strings separadas por vírgula em listas, se necessário."""
        if isinstance(self.allowed_origins, str):
            self.allowed_origins = [o.strip() for o in self.allowed_origins.split(",")]
        if isinstance(self.allowed_hosts, str):
            self.allowed_hosts = [h.strip() for h in self.allowed_hosts.split(",")]
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


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
