"""
app/config.py
Configurações da aplicação via pydantic-settings.
Os valores são lidos do arquivo .env (ou variáveis de ambiente).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field
from functools import lru_cache
import warnings
import os


class Settings(BaseSettings):
    """
    Configurações globais da aplicação SAA29.
    Todas as variáveis são lidas do arquivo .env automaticamente.
    """

    # --- Aplicação ---
    app_env: str = Field(
        default="development",
        description="Environment: development or production"
    )
    app_debug: bool = Field(
        default=False,
        description="Debug mode. MUST be False in production."
    )
    app_secret_key: str = Field(
        default="",
        description="Secret key for JWT encoding. MUST be set securely."
    )

    # --- Banco de Dados ---
    # Padrão: SQLite para instalação local ou produção básica (monolito).
    database_url: str = "sqlite+aiosqlite:///./saa29_local.db"

    # --- JWT ---
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    jwt_expire_minutes: int = Field(
        default=15,
        description="JWT token expiry in minutes (AUD-18: reduced from 480 to 15)"
    )

    # --- Upload e Storage ---
    upload_dir: str = "uploads"
    max_upload_size_mb: float = 0.5
    storage_backend: str = "local"  # local | r2

    # --- Cloudflare R2 ---
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_endpoint: str | None = None
    r2_bucket_name: str | None = None

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
    def validate_security(self):
        """
        Enforce security best practices:
        1. APP_SECRET_KEY must never use defaults (empty or "INSECURE_...")
        2. debug=False required in production
        3. Warn if debug=True in production
        """
        # CRITICAL: Secret key validation (AUD-08)
        if not self.app_secret_key or \
           self.app_secret_key == "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION" or \
           "INSECURE" in self.app_secret_key:
            raise ValueError(
                "CRITICAL SECURITY ERROR: APP_SECRET_KEY is not set or uses insecure default.\n"
                "  - This allows attackers to forge JWT tokens.\n"
                "  - Set APP_SECRET_KEY environment variable to a strong random value.\n"
                "  - Example: openssl rand -hex 32"
            )
        
        # Enforce minimum key length (32 bytes = 64 hex chars)
        if len(self.app_secret_key) < 32:
            raise ValueError(
                f"APP_SECRET_KEY must be at least 32 characters long (got {len(self.app_secret_key)}).\n"
                "  - Recommended: 64+ characters for production.\n"
                "  - Generate with: openssl rand -hex 32"
            )
        
        # DEBUG mode validation (AUD-01)
        if self.app_env == "production":
            if self.app_debug:
                raise ValueError(
                    "CRITICAL: app_debug=True in production.\n"
                    "  - Disables this immediately (set APP_DEBUG=False).\n"
                    "  - Exposes internal exception details to attackers."
                )
        else:
            # Development mode - warn if debug is true
            if self.app_debug:
                warnings.warn(
                    "Running in development mode with debug=True (allowed but not for production)",
                    UserWarning
                )
        
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    Usar como dependência FastAPI: Depends(get_settings).
    """
    return Settings()
