"""
app/config.py
Configurações da aplicação via pydantic-settings.
Os valores são lidos do arquivo .env (ou variáveis de ambiente).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field
from functools import lru_cache
import warnings


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
    force_secure_cookies: bool = Field(
        default=False,
        description=(
            "Força o atributo Secure nos cookies de sessão mesmo quando "
            "app_env != 'production' — para ambientes intermediários "
            "(staging/homolog) servidos via HTTPS."
        ),
    )

    # --- Usuário Inicial ---
    default_admin_user: str = "admin"
    default_admin_password: str | None = None
    admin_password_reset: bool = Field(
        default=False,
        description=(
            "Flag temporária para o cenário de restore de banco: quando "
            "True, garantir_usuarios_essenciais redefine a senha do admin "
            "para o valor de default_admin_password no próximo boot/seed."
        ),
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
    refresh_token_expire_days: int = Field(
        default=7,
        description=(
            "Validade do refresh token, usada para expirar o JWT, o registro "
            "TokenRefresh.expira_em e o max_age do cookie saa29_refresh_token "
            "— fonte única para os três, que antes tinham o valor 7 hardcoded "
            "em separado em security.py e router.py e podiam divergir."
        ),
    )

    # --- Upload e Storage ---
    upload_dir: str = "var/uploads"
    max_upload_size_mb: float = 0.5
    storage_backend: str = "local"  # local | r2

    # --- Cloudflare R2 ---
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_endpoint: str | None = None
    r2_bucket_name: str | None = None

    # --- Módulo Publicações ---
    publicacoes_acervo_dir: str = Field(
        default="var/publicacoes/acervo",
        description="Diretório dos PDFs do acervo — dev e produção (VPS com disco persistente)."
    )
    publicacoes_index_path: str = Field(
        default="var/publicacoes/catalog.db",
        description=(
            "SQLite dedicado do índice de busca full-text — deliberadamente FORA do "
            "database_url: é aberto com sqlite3 puro em modo somente-leitura, nunca "
            "por SQLAlchemy, para não disparar o listener de backup R2 (ADR-004)."
        )
    )
    publicacoes_categorias_path: str = Field(
        default="config/categorias_manuais.toml",
        description=(
            "Mapa estático de categoria/descrição por manual — substitui o "
            "manual_type.xml que o acervo real não possui."
        )
    )
    publicacoes_avulsas_max_upload_mb: float = Field(
        default=50.0,
        description=(
            "Limite de anexo das publicações avulsas. Separado de max_upload_size_mb "
            "(0.5 MB), que vale para foto de pane e não muda: BS escaneado é PDF "
            "grande e não passa pelo pipeline de imagem."
        )
    )
    publicacoes_edicoes_retidas: int = Field(
        default=2,
        description="M4 — quantas edições ficam online simultaneamente (vigente + anterior)."
    )
    publicacoes_snapshots_retidos: int = Field(
        default=3,
        description="M4 — quantos snapshots ZIP de edição são mantidos no R2."
    )

    # --- CORS / SEGURANÇA ---
    # Aceita lista via JSON ou string separada por vírgula
    allowed_origins: list[str] | str = ["*"]
    allowed_hosts: list[str] | str = ["*"]

    # --- Seed / Desenvolvimento ---
    enable_dev_seeds: bool = Field(
        default=False,
        description="Permite carregar dados de teste (panes, inspeções, etc) durante o seed."
    )
    enable_test_users: bool = Field(
        default=False,
        description=(
            "Segundo gatilho explícito (além de APP_ENV=development) exigido para criar as contas de "
            "teste (encarregado/inspetor/mantenedor) em garantir_usuarios_essenciais. Documentado em "
            ".env.example, mas não existia como campo de Settings até esta correção."
        ),
    )

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
        # noqa S105: a literal abaixo e justamente o valor inseguro que este
        # bloco existe para REJEITAR — nao e uma credencial embutida.
        if not self.app_secret_key or \
           self.app_secret_key == "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION" or \
           "INSECURE" in self.app_secret_key:  # noqa: S105
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
                    UserWarning,
                    # stacklevel=2 aponta o aviso para quem instanciou Settings,
                    # nao para esta linha do validador.
                    stacklevel=2,
                )
        
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância cacheada das configurações.
    Usar como dependência FastAPI: Depends(get_settings).
    """
    return Settings()
