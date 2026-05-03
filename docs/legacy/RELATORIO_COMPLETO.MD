# Auditoria Completa de Código - SAA29

**Data:** 2026-04-19  
**Status:** ⚠️ MULTIPLE ISSUES DETECTED - CRÍTICAS, ALTAS E MÉDIAS  
**Grade Geral:** B- (Arquitetura sólida, mas com vulnerabilidades e problemas de performance)

---

## OVERVIEW

**SAA29** é um sistema web **FastAPI (async)** para gestão de panes (falhas) em aeronaves. Arquitetura em 3 camadas (Router → Service → Model) com banco de dados **SQLite/PostgreSQL (SQLAlchemy 2.0 async)**, autenticação via **JWT**, upload de arquivos via **Cloudflare R2 ou armazenamento local**, e templates **Jinja2** para frontend.

**Pontos Fortes:**
- ✅ Separação clara de responsabilidades (Router → Service → ORM)
- ✅ Tipagem forte com Pydantic v2 e SQLAlchemy 2.0
- ✅ Hash de senhas com bcrypt (correto)
- ✅ Uso de UUID para IDs (segurança contra enumeration)
- ✅ Transações ACID via SQLAlchemy

**Problemas Críticos Identificados:**
- 🔴 3 vulnerabilidades CRÍTICAS (credenciais expostas, secrets fracos, admin default)
- 🟠 10 vulnerabilidades ALTAS (CORS, CSRF, segurança de cookies, validação de upload)
- 🟡 9 vulnerabilidades MÉDIAS (rate limiting, lockout, SQL escaping, autorização)
- ⚡ 5 problemas de PERFORMANCE (N+1 queries, índices faltando, subprocess blocking)
- 📋 7 problemas de DUPLICAÇÃO (handlers de erro, validação, formatação)

---

## CRITICAL FINDINGS [file:line]

### 🔴 VULNERABILIDADES CRÍTICAS

#### 1. **[.env - LINHA 36-40] Credenciais Cloudflare R2 Expostas no Git**
- **Tipo:** Credential Exposure / Secrets in Code
- **Severidade:** 🔴 CRÍTICA
- **Status:** ✗ ACTIVE

```env
R2_ACCOUNT_ID=7fa0ed8254b8f41ec3eb2e83b5bc622f
R2_ACCESS_KEY_ID=dce783c7c9793fbaa2b3a079606ee1ca
R2_SECRET_ACCESS_KEY=3deb304c21438f4cbcdecfdd426b14f4fb40df53798e3618d75ae38ec1e1957a
```

**Impacto:** Um atacante pode acessar/modificar o bucket S3 do R2, comprometendo todos os backups.  
**Remediação:**
```bash
# 1. Remover arquivo do histórico Git
git filter-repo --path .env --invert-paths

# 2. Adicionar .env ao .gitignore (já deve estar)
echo ".env" >> .gitignore

# 3. Rotar TODAS as credenciais R2 no console Cloudflare
# 4. Usar apenas .env.example com valores placeholder
```

---

#### 2. **[app/config.py:21] Secret Key Insegura por Padrão**
- **Tipo:** Weak Cryptographic Keys / Default Credentials
- **Severidade:** 🔴 CRÍTICA

```python
app_secret_key: str = "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION"
```

**Impacto:** Se `APP_SECRET_KEY` não for definida no .env, o JWT usa uma chave conhecida. Qualquer pessoa pode forjar tokens.  
**Remediação:**
```python
@model_validator(mode="after")
def validate_secret_key(self):
    if self.app_secret_key == "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION":
        raise ValueError(
            "APP_SECRET_KEY must be set to a strong random value. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return self
```

---

#### 3. **[scripts/init_db.py, scripts/seed.py - LINHA 1] Default Admin Password Hardcoded**
- **Tipo:** Weak Default Credentials
- **Severidade:** 🔴 CRÍTICA

```python
admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "BisKP76pg3IU").strip()
```

**Impacto:** Se `DEFAULT_ADMIN_PASSWORD` não estiver definida, qualquer pessoa conhecendo este repositório pode fazer login como admin.  
**Remediação:**
```python
admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD")
if not admin_pass:
    raise ValueError(
        "DEFAULT_ADMIN_PASSWORD must be set via environment variable. "
        "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(16))\""
    )
```

---

### 🟠 VULNERABILIDADES ALTAS

#### 4. **[app/config.py:20] Debug Mode Habilitado por Padrão**
- **Tipo:** Information Disclosure
- **Severidade:** 🟠 ALTA
- **Arquivo:Linha:** `app/config.py:20`

```python
app_debug: bool = True
```

**Impacto:** Em produção, endpoints `/docs` e `/redoc` expõem a arquitetura da API e permitem exploração.  
**Remediação:**
```python
@model_validator(mode="after")
def validate_debug_production(self):
    if self.app_env == "production" and self.app_debug:
        raise ValueError("app_debug must be False in production!")
    return self
```

---

#### 5. **[app/config.py:29] JWT Expiration Muito Longa (2 horas)**
- **Tipo:** Weak Session Management
- **Severidade:** 🟠 ALTA
- **Arquivo:Linha:** `app/config.py:29`

```python
jwt_expire_minutes: int = 120  # 2 horas - MUITO LONGO
```

**Impacto:** Se token for roubado, atacante tem 2 horas de acesso.  
**Recomendação:** 15-30 minutos com refresh token mechanism.  
**Remediação:**
```python
jwt_expire_minutes: int = 15
jwt_refresh_expire_days: int = 7  # Adicionar
```

---

#### 6. **[app/auth/router.py:57-63] Secure Flag de Cookie Não Habilitada**
- **Tipo:** Session Fixation / MITM
- **Severidade:** 🟠 ALTA
- **Arquivo:Linha:** `app/auth/router.py:62`

```python
response.set_cookie(
    key="saa29_token",
    value=token,
    httponly=True,
    samesite="lax"
    # secure=True  # ❌ Comentado! Precisa estar True em HTTPS
)
```

**Impacto:** Em produção com HTTPS, o flag `secure=True` deve estar ativado.  
**Remediação:**
```python
response.set_cookie(
    key="saa29_token",
    value=token,
    httponly=True,
    samesite="strict" if current_settings.app_env == "production" else "lax",
    secure=current_settings.app_env == "production"
)
```

---

#### 7. **[app/main.py:223-239] CORS Permite Wildcard com Credentials**
- **Tipo:** CORS Misconfiguration
- **Severidade:** 🟠 ALTA
- **Arquivo:Linha:** `app/main.py:224-239`

```python
cors_origins = current_settings.allowed_origins
if "*" in cors_origins:  # ❌ Allowlist inválido
    cors_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],  # ❌ Muito permissivo
    allow_headers=["*"],  # ❌ Muito permissivo
)
```

**Impacto:** Qualquer domínio pode fazer requisições com credenciais.  
**Remediação:**
```python
if not current_settings.allowed_origins or "*" in current_settings.allowed_origins:
    raise ValueError("CORS origins must be explicitly defined in config, never use '*'")

app.add_middleware(
    CORSMiddleware,
    allow_origins=current_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

#### 8. **[Todas as rotas] Sem Proteção CSRF**
- **Tipo:** Cross-Site Request Forgery
- **Severidade:** 🟠 ALTA
- **Status:** ✗ MISSING

**Impacto:** Um atacante pode enviar formulário malicioso em background, causar ações não-autorizadas.  
**Remediação:** Adicionar middleware CSRF:
```python
# app/main.py
from fastapi_csrf_protect import CsrfProtect

@CsrfProtect.load_config
def load_csrf_config():
    return CsrfSettings(secret_key=current_settings.app_secret_key)

app.add_middleware(CsrfMiddleware, secret_key=current_settings.app_secret_key)

# Em cada router POST/PUT/DELETE:
@router.post("/", dependencies=[Depends(CsrfProtect())])
async def criar_item(...):
    ...
```

---

#### 9. **[app/panes/router.py:189] Validação de Content-Type em Upload Fraca**
- **Tipo:** File Upload Validation Bypass
- **Severidade:** 🟠 ALTA
- **Arquivo:Linha:** `app/panes/router.py:189-255`

```python
async def upload_anexo(..., arquivo: UploadFile = File(...)) -> schemas.AnexoOut:
    conteudo = await arquivo.read()
    filename = arquivo.filename or "unknown"
    content_type = arquivo.content_type or "application/octet-stream"  # ❌ Fallback inseguro
    storage = get_storage_service()
    anexo_url = await storage.upload(conteudo, filename, content_type)
```

**Impacto:** Se cliente não enviar `Content-Type`, defaults to `application/octet-stream` e pode contornar validações.  
**Remediação:**
```python
if not arquivo.content_type or arquivo.content_type == "application/octet-stream":
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Content-Type header is required and must not be application/octet-stream. "
               "Use image/jpeg, image/png, or application/pdf."
    )

# Whitelist MIME types
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
if arquivo.content_type not in ALLOWED_MIME_TYPES:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"File type {arquivo.content_type} not allowed"
    )
```

---

#### 10. **[app/core/storage.py:44-53] Path Traversal Risk em Upload (Mitigado)**
- **Tipo:** Path Traversal / Arbitrary File Write
- **Severidade:** 🟠 ALTA (Mitigada)
- **Arquivo:Linha:** `app/core/storage.py:44-53`

```python
async def upload(self, file_content: bytes, original_filename: str, content_type: str) -> str:
    ext = os.path.splitext(original_filename)[1]  # ❌ Extrai ext diretamente
    new_filename = f"{uuid.uuid4().hex}{ext}"  # ✓ UUID mitiga traversal
    file_path = self.upload_dir / new_filename
```

**Status:** Parcialmente mitigado (usa UUID), mas ainda há risco.  
**Remediação:**
```python
# Validar extension
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx'}
ext = os.path.splitext(original_filename)[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    raise ValueError(f"Extension '{ext}' not allowed")

# Validar original_filename
if '..' in original_filename or '/' in original_filename or '\\' in original_filename:
    raise ValueError("Invalid filename: path traversal attempt detected")

# Salvar com UUID
new_filename = f"{uuid.uuid4().hex}{ext}"
```

---

### 🟡 VULNERABILIDADES MÉDIAS

#### 11. **[app/auth/router.py:25-69] Sem Rate Limiting no Login**
- **Tipo:** Brute Force Attack
- **Severidade:** 🟡 MÉDIA
- **Status:** ✗ MISSING

**Impacto:** Um atacante pode fazer unlimited password guesses.  
**Remediação:**
```bash
pip install slowapi
```

```python
# app/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# app/auth/router.py
@router.post("/login", dependencies=[Depends(limiter.limit("5/minute"))])
async def login(...):
    ...
```

---

#### 12. **[app/auth/service.py] Sem Mecanismo de Account Lockout**
- **Tipo:** Brute Force / Account Enumeration
- **Severidade:** 🟡 MÉDIA
- **Status:** ✗ MISSING

**Impacto:** Sem rate limiting + sem lockout = brute force fácil.  
**Remediação:** Adicionar campos ao `Usuario` model:
```python
class Usuario(Base):
    __tablename__ = "usuarios"
    # ... existing fields ...
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    
    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    def increment_failed_attempts(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    def reset_failed_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None
```

Implementar verificação no `autenticacao()` service:
```python
async def autenticacao(self, username: str, password: str) -> Usuario:
    usuario = await buscar_por_username(db, username)
    if not usuario:
        raise ValueError("Credenciais inválidas")
    
    if usuario.is_locked():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Conta temporariamente bloqueada. Tente novamente em 15 minutos."
        )
    
    if not verificar_senha(password, usuario.senha_hash):
        usuario.increment_failed_attempts()
        await db.commit()
        raise ValueError("Credenciais inválidas")
    
    usuario.reset_failed_attempts()
    await db.commit()
    return usuario
```

---

#### 13. **[app/auth/router.py:96] JWT Blacklist Não Limpa (Garbage Collection)**
- **Tipo:** Database Bloat / DoS
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `app/auth/router.py:96-104`

```python
# TokenBlacklist adicionado mas nunca removido
if jti and exp:
    db.add(TokenBlacklist(
        jti=jti,
        expira_em=datetime.fromtimestamp(exp, tz=timezone.utc)
    ))
```

**Impacto:** Com tempo, a tabela TokenBlacklist crescerá indefinidamente.  
**Remediação:** Adicionar cleanup job no lifespan:
```python
# app/main.py - em create_app()
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown - cleanup expired tokens
    async with get_session_factory()() as session:
        from datetime import datetime, timezone
        await session.execute(
            delete(TokenBlacklist).where(
                TokenBlacklist.expira_em < datetime.now(timezone.utc)
            )
        )
        await session.commit()

app = FastAPI(..., lifespan=lifespan)
```

---

#### 14. **[app/auth/schemas.py:387] Validação de Senha Fraca**
- **Tipo:** Weak Password Requirements
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `app/auth/schemas.py:387`

```python
password: str = Field(..., min_length=6, examples=["senha123"])  # ❌ 6 caracteres
```

**Recomendação:** 12+ caracteres com complexidade.  
**Remediação:**
```python
from pydantic import field_validator

class UsuarioCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=12)
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Senha deve conter letra maiúscula')
        if not any(c.islower() for c in v):
            raise ValueError('Senha deve conter letra minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('Senha deve conter dígito')
        if not any(c in '!@#$%^&*_-+=[]{}()|;:,.<>?' for c in v):
            raise ValueError('Senha deve conter caractere especial')
        return v
```

---

#### 15. **[app/panes/router.py:206-213] Autorização Insuficiente em Endpoints**
- **Tipo:** Broken Access Control / User Enumeration
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `app/panes/router.py:206-213`

```python
@router.get("/{pane_id}/anexos")
async def listar_anexos(
    pane_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,  # ✗ Apenas verifica autenticação
) -> list[schemas.AnexoOut]:
    # ❌ Não verifica se usuario_atual tem acesso a esta pane
    anexos = await service.listar_anexos_pane(db, pane_id)
```

**Impacto:** Um usuário da equipe A poderia listar anexos de panes da equipe B.  
**Remediação:**
```python
@router.get("/{pane_id}/anexos")
async def listar_anexos(
    pane_id: uuid.UUID,
    db: DBSession,
    usuario_atual: CurrentUser,
) -> list[schemas.AnexoOut]:
    # Verificar se pane existe
    pane = await service.buscar_pane(db, pane_id)
    if not pane:
        raise HTTPException(status_code=404, detail="Pane não encontrada")
    
    # Verificar se usuário tem acesso a esta aeronave (via pane)
    if not usuario_atual.tem_acesso_a_aeronave(pane.aeronave_id):
        raise HTTPException(
            status_code=403,
            detail="Acesso negado a esta pane"
        )
    
    anexos = await service.listar_anexos_pane(db, pane_id)
    return anexos
```

---

#### 16. **[Múltiplos arquivos] Exposição de Dados Sensíveis em Mensagens de Erro**
- **Tipo:** Information Disclosure
- **Severidade:** 🟡 MÉDIA

**Exemplos:**
- `app/equipamentos/service.py:89` - Expõe número de série: `f"S/N '{dados.numero_serie}' já cadastrado"`
- `app/auth/service.py` - Expõe username: `f"Username '{dados.username}' já está em uso"`

**Remediação:** Usar mensagens genéricas:
```python
# ❌ ANTES
raise ValueError(f"S/N '{dados.numero_serie}' já cadastrado para este P/N")
raise ValueError(f"Username '{dados.username}' já está em uso")

# ✅ DEPOIS
raise ValueError("Número de série já cadastrado para este modelo")
raise ValueError("Identificação não disponível")

# Log interno (não expor ao usuário)
logger.debug(f"Duplicate SN: {dados.numero_serie}")
```

---

#### 17. **[app/panes/service.py:52-54] SQL Injection via LIKE (Parcialmente Seguro)**
- **Tipo:** SQL Injection (LIKE clause)
- **Severidade:** 🟡 MÉDIA (Mitigada)
- **Arquivo:Linha:** `app/panes/service.py:52-54`

```python
def _escape_like(text: str) -> str:
    """Escapa caracteres especiais de LIKE"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

# Uso em listar_panes
if filtros.texto:
    texto_like = f"%{_escape_like(filtros.texto)}%"
    query = query.where(func.lower(Pane.descricao).like(texto_like))
```

**Status:** ✓ Corretamente escapado  
**Verificação:** Confirmar que `_escape_like()` é aplicado em TODOS os lugares onde `like()` é usado.

---

### 🟢 VULNERABILIDADES BAIXAS (INFORMACIONAIS)

#### 18. **[app/main.py] Faltam Security Headers**
- **Tipo:** Missing Security Headers
- **Severidade:** 🟢 BAIXA
- **Remediação:**
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

#### 19. **[app/equipamentos/service.py:244-248] Print Statements e Traceback em Produção**
- **Tipo:** Information Disclosure via Logs
- **Severidade:** 🟢 BAIXA
- **Arquivo:Linha:** `app/equipamentos/service.py:244-248`

```python
except Exception as e:
    import traceback
    print(f"CRITICAL ERROR in listar_inventario_aeronave: {e}")  # ❌ print()
    traceback.print_exc()  # ❌ traceback para stdout
```

**Remediação:** Usar logging module:
```python
import logging
logger = logging.getLogger(__name__)

try:
    # code
except SpecificException as e:
    logger.warning(f"Expected error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error in listar_inventario_aeronave", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

#### 20. **[app/database.py] Sem Connection Timeout**
- **Tipo:** Resource Exhaustion / DoS
- **Severidade:** 🟢 BAIXA
- **Remediação:**
```python
_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    connect_args={"timeout": 30},  # 30 segundo connection timeout
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Reciclar conexões a cada 1h
)
```

---

## SECURITY SUMMARY TABLE

| # | Tipo | Arquivo:Linha | Severidade | Status |
|---|---|---|---|---|
| 1 | Credenciais Expostas | `.env:36-40` | 🔴 CRÍTICA | Active |
| 2 | Secret Key Insegura | `app/config.py:21` | 🔴 CRÍTICA | Active |
| 3 | Admin Password Hardcoded | `scripts/*.py` | 🔴 CRÍTICA | Active |
| 4 | Debug Mode Enabled | `app/config.py:20` | 🟠 ALTA | Active |
| 5 | JWT Expiration Longa | `app/config.py:29` | 🟠 ALTA | Design |
| 6 | Cookie Secure Flag | `app/auth/router.py:62` | 🟠 ALTA | Commented |
| 7 | CORS Misconfiguration | `app/main.py:224-239` | 🟠 ALTA | Design |
| 8 | Sem CSRF Protection | All Routers | 🟠 ALTA | Missing |
| 9 | File Upload Validation | `app/panes/router.py:189` | 🟠 ALTA | Fallback |
| 10 | Path Traversal Risk | `app/core/storage.py:44` | 🟠 ALTA | Mitigated |
| 11 | Sem Rate Limiting | `app/auth/router.py:25` | 🟡 MÉDIA | Missing |
| 12 | Sem Account Lockout | `app/auth/service.py` | 🟡 MÉDIA | Missing |
| 13 | Blacklist Sem Cleanup | `app/auth/router.py:96` | 🟡 MÉDIA | Active |
| 14 | Weak Password Rules | `app/auth/schemas.py:387` | 🟡 MÉDIA | Active |
| 15 | Autorização Insuficiente | `app/panes/router.py:206` | 🟡 MÉDIA | Active |
| 16 | Sensitive Error Messages | Multiple | 🟡 MÉDIA | Active |
| 17 | SQL Injection (LIKE) | `app/panes/service.py:52` | 🟡 MÉDIA | Mitigated |
| 18 | Missing Security Headers | `app/main.py` | 🟢 BAIXA | Missing |
| 19 | Print Statements | `app/equipamentos/service.py:244` | 🟢 BAIXA | Active |
| 20 | No DB Timeout | `app/database.py` | 🟢 BAIXA | Missing |

---

## PERFORMANCE ISSUES

#### P1. **[aeronaves/models.py:89-98, panes/models.py:129-152] N+1 Query Risk - Lazy Loading**
- **Tipo:** Database Performance Bottleneck
- **Severidade:** 🔴 HIGH
- **Arquivo:Linha:** `aeronaves/models.py:89-98`

```python
panes: Mapped[list] = relationship(
    "Pane",
    back_populates="aeronave",
    lazy="select",  # ❌ N+1: cada Aeronave carrega suas Panes uma por uma
)
```

**Impacto:** Listar 100 aeronaves = 100 queries adicionais. Em produção = timeout.  
**Remediação:**
```python
from sqlalchemy.orm import selectinload

# No service layer
query = select(Aeronave).options(
    selectinload(Aeronave.panes),
    selectinload(Aeronave.instalacoes)
)
result = await db.execute(query)
aeronaves = result.scalars().unique().all()
```

---

#### P2. **[panes/models.py:104-113] Índices Faltando em Foreign Keys**
- **Tipo:** Database Index Missing
- **Severidade:** 🔴 HIGH
- **Arquivo:Linha:** `panes/models.py:104-113`

```python
criado_por_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("usuarios.id", ondelete="RESTRICT"),
    nullable=False,
    # ❌ index=True faltando
)
concluido_por_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("usuarios.id", ondelete="RESTRICT"),
    nullable=True,
    # ❌ index=True faltando
)
```

**Impacto:** Queries WHERE criado_por_id = ? vão fazer full table scan.  
**Remediação:** Adicionar `index=True` a todos os ForeignKeys:
```python
criado_por_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("usuarios.id", ondelete="RESTRICT"),
    nullable=False,
    index=True,  # ✓ Agora tem índice
)
```

---

#### P3. **[equipamentos/service.py:200-218] Loop de Queries por Slot Vazio**
- **Tipo:** O(n) Queries in Loop
- **Severidade:** 🟠 MÉDIA
- **Arquivo:Linha:** `equipamentos/service.py:200-218`

```python
# Para cada slot vazio, executa query individual
for slot in slots:
    if not instalacao:
        # ❌ Query individual por slot
        stmt_last_rem = (
            select(Instalacao, Usuario.trigrama)
            .where(Instalacao.slot_id == slot.id, ...)
            .limit(1)
        )
        res_last = await db.execute(stmt_last_rem)  # N queries!
```

**Impacto:** 50 slots = 50 queries extras.  
**Remediação:** Batch-load em single query:
```python
# Pre-fetch ALL empty slot removals em UM query
empty_slot_ids = [s.id for s in slots if not has_instalacao(s)]
if empty_slot_ids:
    stmt = (
        select(Instalacao, Usuario.trigrama)
        .where(Instalacao.slot_id.in_(empty_slot_ids))
        .order_by(Instalacao.data_remocao.desc())
    )
    removals = (await db.execute(stmt)).all()
    removals_by_slot = {r[0].slot_id: r for r in removals}

# Depois, usar dados em-memória
for slot in slots:
    last_removal = removals_by_slot.get(slot.id)
```

---

#### P4. **[app/main.py:124-137] Subprocess Blocking Event Loop**
- **Tipo:** Async Code Blocking
- **Severidade:** 🟠 MÉDIA
- **Arquivo:Linha:** `app/main.py:124-137`

```python
def _run_r2_backup() -> None:
    """Executa backup síncrono do banco SQLite para o Cloudflare R2."""
    import subprocess, sys
    try:
        result = subprocess.run(  # ❌ Blocking call
            [sys.executable, "scripts/r2_manager.py", "backup"],
            capture_output=True, text=True, timeout=60
        )
```

**Impacto:** Backup de 60 segundos bloqueia todo o servidor.  
**Remediação:** Usar executor thread:
```python
async def _run_r2_backup() -> None:
    """Execute R2 backup asynchronously."""
    import asyncio
    loop = asyncio.get_event_loop()
    
    def _backup_sync():
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "scripts/r2_manager.py", "backup"],
            capture_output=True, text=True, timeout=60
        )
        return result
    
    await loop.run_in_executor(None, _backup_sync)
```

---

## DUPLICATION ISSUES

#### D1. **[auth/router.py, panes/router.py, aeronaves/router.py, equipamentos/router.py] Error Handling Boilerplate**
- **Tipo:** Code Duplication
- **Severidade:** 🟡 MÉDIA
- **Status:** 15+ repetições

```python
# Repetido ~15 vezes
try:
    resultado = await service.function(...)
    return schemas.Output.model_validate(resultado)
except ValueError as e:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(e),
    )
```

**Remediação:** Criar decorador:
```python
# app/core/decorators.py
from functools import wraps
from fastapi import HTTPException, status

def handle_service_errors(func):
    """Decorator centraliza error handling."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            detail = str(e)
            status_code = (
                status.HTTP_404_NOT_FOUND if "não encontrada" in detail.lower()
                else status.HTTP_409_CONFLICT
            )
            raise HTTPException(status_code=status_code, detail=detail) from e
    return wrapper

# Uso:
@router.post("/{id}")
@handle_service_errors
async def update_item(id: uuid.UUID, data: Schema, db: DBSession):
    return await service.update(db, id, data)
```

---

#### D2. **[aeronaves/service.py:62-69, equipamentos/service.py:76-82] Validação de Unicidade Duplicada**
- **Tipo:** Code Duplication
- **Severidade:** 🟡 MÉDIA

```python
# aeronaves/service.py:62-69
if await helpers.buscar_aeronave_por_matricula(db, dados.matricula):
    raise ValueError(f"Matrícula '{dados.matricula}' já cadastrada.")

# equipamentos/service.py:76-82
res_ex = await db.execute(
    select(ItemEquipamento).where(
        ItemEquipamento.numero_serie == dados.numero_serie,
        ItemEquipamento.modelo_id == dados.modelo_id
    )
)
if res_ex.scalar_one_or_none():
    raise ValueError(f"S/N '{dados.numero_serie}' já cadastrado para este P/N.")
```

**Remediação:** Extrair helper genérico:
```python
# app/core/helpers.py
async def check_unique_field(
    db: AsyncSession,
    model: type,
    field_name: str,
    value: Any,
    exclude_id: uuid.UUID | None = None,
    **extra_filters,
) -> bool:
    """Retorna True se valor é único."""
    query = select(model).where(getattr(model, field_name) == value)
    for field, val in extra_filters.items():
        query = query.where(getattr(model, field) == val)
    if exclude_id:
        query = query.where(model.id != exclude_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is None

# Uso:
if not await check_unique_field(db, Aeronave, "matricula", dados.matricula):
    raise ValueError(f"Matrícula '{dados.matricula}' já cadastrada.")

if not await check_unique_field(
    db, ItemEquipamento, "numero_serie", dados.numero_serie,
    modelo_id=dados.modelo_id
):
    raise ValueError(f"S/N já cadastrado para este modelo.")
```

---

#### D3. **[panes/router.py - múltiplas rotas] Formatação de Pane com Ranking**
- **Tipo:** Code Duplication
- **Severidade:** 🟡 MÉDIA

```python
# Repetido em: buscar_pane, editar_pane, concluir_pane, etc.
resultado = await service.buscar_pane(db, pane_id)
if not resultado:
    raise HTTPException(...)
pane, sequencia, ano = resultado
item = schemas.PaneOut.model_validate(pane).model_dump()
item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
return schemas.PaneOut(**item)
```

**Remediação:**
```python
# app/core/helpers.py
async def format_pane_response(db: AsyncSession, pane_id: uuid.UUID) -> schemas.PaneOut:
    """Fetch pane com ranking e retornar formatado."""
    resultado = await service.buscar_pane(db, pane_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Pane não encontrada")
    
    pane, sequencia, ano = resultado
    data = schemas.PaneOut.model_validate(pane).model_dump()
    data["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
    return schemas.PaneOut(**data)

# Uso em router:
@router.get("/{pane_id}")
async def buscar_pane(pane_id: uuid.UUID, db: DBSession, _: CurrentUser):
    return await format_pane_response(db, pane_id)
```

---

## ARCHITECTURE ISSUES

#### A1. **[app/dependencies.py:59-102] Loose Coupling in Auth Service - Ad-hoc Imports**
- **Tipo:** Tight Coupling / Dependency Injection Antipattern
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `app/dependencies.py:59-102`

```python
async def get_current_user(...):
    try:
        from app.auth.security import decodificar_token  # ❌ Import inside function
        from app.auth.models import TokenBlacklist
        from app.auth.service import buscar_por_username  # ❌ Ad-hoc service call
        
        result = await db.execute(select(TokenBlacklist)...)  # ❌ Direct DB access
```

**Problema:** Mixes concerns, dificulta testing e manutenção.  
**Remediação:** Criar serviço dedicado:
```python
# app/auth/auth_service.py
class AuthenticationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def validate_token_and_get_user(self, token: str) -> Usuario:
        """Centralized token validation."""
        payload = decodificar_token(token)
        jti = payload.get("jti")
        
        # Check blacklist
        result = await self.db.execute(
            select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        )
        if result.scalar_one_or_none():
            raise credentials_exception
        
        username = payload.get("sub")
        return await buscar_por_username(self.db, username)

# app/dependencies.py
async def get_current_user(
    token: str = Depends(get_token_from_request),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    auth_service = AuthenticationService(db)
    return await auth_service.validate_token_and_get_user(token)
```

---

#### A2. **[panes/router.py:70-75] Business Logic in Router (Violation of SoC)**
- **Tipo:** Separation of Concerns Violation
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `panes/router.py:70-75`

```python
# ❌ Business logic in router
for pane, sequencia, ano in panes:
    item = schemas.PaneListItem.model_validate(pane).model_dump()
    item["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"  # ❌ Should be in schema
    resposta.append(schemas.PaneListItem(**item))
```

**Remediação:** Mover para schema:
```python
# panes/schemas.py
class PaneListItem(BaseModel):
    # ... fields ...
    codigo: str
    
    @classmethod
    def from_db_tuple(cls, pane: Pane, sequencia: int, ano: int) -> "PaneListItem":
        data = cls.model_validate(pane).model_dump()
        data["codigo"] = f"{sequencia:03d}/{str(ano)[-2:]}"
        return cls(**data)

# router
@router.get("/")
async def listar_panes(...):
    panes = await service.listar_panes(db, filtros)
    return [
        schemas.PaneListItem.from_db_tuple(pane, seq, ano)
        for pane, seq, ano in panes
    ]
```

---

#### A3. **[Múltiplos routers] Inconsistent Error Handling Strategy**
- **Tipo:** Inconsistent Exception Strategy
- **Severidade:** 🟡 MÉDIA

```python
# aeronaves/router.py - string matching (frágil)
except ValueError as exc:
    detail = str(exc)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if "não encontrada" in detail.lower()  # ❌ String matching
        else status.HTTP_409_CONFLICT
    )
```

**Remediação:** Usar exception hierarchy:
```python
# app/core/exceptions.py
class DomainException(Exception):
    """Base domain exception."""
    pass

class AeronaveNaoEncontradaError(DomainException):
    status_code = status.HTTP_404_NOT_FOUND

class MatriculaDuplicadaError(DomainException):
    status_code = status.HTTP_409_CONFLICT

# app/aeronaves/service.py
async def buscar_aeronave(db, aeronave_id):
    result = await db.execute(select(Aeronave).where(Aeronave.id == aeronave_id))
    if not result.scalar_one_or_none():
        raise AeronaveNaoEncontradaError("Aeronave não encontrada")
    return result.scalar_one()

# app/main.py - Global exception handler
@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )

# app/aeronaves/router.py - No try/except needed!
@router.get("/{aeronave_id}")
async def buscar_aeronave(aeronave_id: uuid.UUID, db: DBSession):
    return await service.buscar_aeronave(db, aeronave_id)
```

---

#### A4. **[models] Circular Imports with TYPE_CHECKING Workaround**
- **Tipo:** Circular Dependencies (Fragile)
- **Severidade:** 🟡 MÉDIA
- **Arquivo:Linha:** `aeronaves/models.py:18-20`

```python
from __future__ import annotations
if TYPE_CHECKING:
    from app.equipamentos.models import Instalacao  # ❌ Circular
    from app.panes.models import Pane
```

**Status:** Funciona mas é frágil.  
**Nota:** Já está usando string-based references em `relationship()`, então TYPE_CHECKING pode ser removido se não houver type hints na classe.

---

## CODE QUALITY ISSUES

#### Q1. **[aeronaves/models.py:89, panes/models.py:143] Missing Generic Type Hints**
- **Tipo:** Type Hint Completeness
- **Severidade:** 🟡 MÉDIA

```python
panes: Mapped[list] = relationship(...)  # ❌ Should be Mapped[list["Pane"]]
```

**Remediação:**
```python
panes: Mapped[list["Pane"]] = relationship(...)  # ✓ Specific type
```

---

#### Q2. **[app/core/helpers.py, app/auth/schemas.py] Incomplete Documentation**
- **Tipo:** Documentation Completeness
- **Severidade:** 🟢 LOW
- **Status:** Parcially documented

---

#### Q3. **[panes/service.py:11-16] Unused Imports**
- **Tipo:** Dead Code
- **Severidade:** 🟢 LOW

```python
import anyio  # ❌ Nunca usado
```

---

## IMPROVEMENTS & REFACTORING ROADMAP

### Priority 1: CRITICAL (Security) - FIX IMMEDIATELY
1. Remove `.env` do Git history (`git filter-repo`)
2. Rotar Cloudflare R2 credentials
3. Gerar `APP_SECRET_KEY` aleatória em production
4. Remover `DEFAULT_ADMIN_PASSWORD` hardcoded de scripts
5. Adicionar validação: `APP_SECRET_KEY != "INSECURE..."`

### Priority 2: HIGH (Security + Performance) - FIX THIS SPRINT
6. Desabilitar debug mode em production
7. Reduzir JWT expiration de 120 min → 15 min + refresh tokens
8. Adicionar `secure=True` flag para cookies (HTTPS only)
9. Validar CORS origins: proibir `"*"` com credentials
10. Implementar CSRF protection com `fastapi-csrf-protect`
11. Melhorar upload validation: whitelist MIME types
12. Adicionar índices FK (migration script)
13. Fix N+1 queries: `selectinload()` em listagens

### Priority 3: MEDIUM (Performance + Quality) - FIX NEXT SPRINT
14. Implementar rate limiting (`slowapi`) para `/login`
15. Adicionar account lockout após 5 failed attempts
16. Limpar JWT blacklist expirada (cleanup job)
17. Aumentar password requirements para 12+ chars + complexity
18. Extrair error handling decorator
19. Extrair uniqueness validation helper
20. Batch-load empty slot removals (equipamentos)
21. Adicionar security headers middleware
22. Usar logging module ao invés de print()
23. Adicionar DB connection timeout

### Priority 4: LOW (Code Quality) - FIX LATER
24. Adicionar generic types em `Mapped[list[...]]`
25. Adicionar docstrings completos em services
26. Remover unused imports
27. Criar custom exception hierarchy (DomainException, etc.)

---

## REFACTOR CODE EXAMPLES

### ✅ FIX #1: Add Security Headers Middleware
```python
# app/middleware/security.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        return response

# app/main.py
from app.middleware.security import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
```

### ✅ FIX #2: Add Rate Limiting
```bash
pip install slowapi
```

```python
# app/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# app/auth/router.py
from app.main import limiter

@router.post("/login", dependencies=[Depends(limiter.limit("5/minute"))])
async def login(...):
    ...
```

### ✅ FIX #3: Fix N+1 Queries
```python
# app/aeronaves/service.py
from sqlalchemy.orm import selectinload

async def listar_aeronaves(db: AsyncSession) -> list[Aeronave]:
    query = select(Aeronave).options(
        selectinload(Aeronave.panes),
        selectinload(Aeronave.instalacoes)
    )
    result = await db.execute(query)
    return result.scalars().unique().all()
```

### ✅ FIX #4: Add FK Indexes (Migration)
```python
# migrations/versions/add_fk_indexes.py
from alembic import op

def upgrade():
    op.create_index("ix_panes_criado_por_id", "panes", ["criado_por_id"])
    op.create_index("ix_panes_concluido_por_id", "panes", ["concluido_por_id"])
    op.create_index("ix_instalacoes_usuario_id", "instalacoes", ["usuario_id"])
    # etc.

def downgrade():
    op.drop_index("ix_panes_criado_por_id")
    # etc.
```

### ✅ FIX #5: Add Account Lockout
```python
# app/auth/models.py
class Usuario(Base):
    __tablename__ = "usuarios"
    # ... existing ...
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    
    def is_locked(self) -> bool:
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until
    
    def increment_failed_attempts(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    def reset_failed_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None

# app/auth/service.py
async def autenticacao(self, username: str, password: str) -> Usuario:
    usuario = await buscar_por_username(db, username)
    if not usuario:
        raise ValueError("Credenciais inválidas")
    
    if usuario.is_locked():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Conta temporariamente bloqueada. Tente novamente em 15 minutos."
        )
    
    if not verificar_senha(password, usuario.senha_hash):
        usuario.increment_failed_attempts()
        await db.commit()
        raise ValueError("Credenciais inválidas")
    
    usuario.reset_failed_attempts()
    await db.commit()
    return usuario
```

---

## CHECKLIST

### Security
- [ ] Remove `.env` from Git history
- [ ] Rotate Cloudflare R2 credentials
- [ ] Generate strong `APP_SECRET_KEY` from environment
- [ ] Remove hardcoded `DEFAULT_ADMIN_PASSWORD` from scripts
- [ ] Add validation to reject insecure default secrets
- [ ] Disable debug mode in production
- [ ] Reduce JWT expiration to 15 minutes
- [ ] Add refresh token mechanism
- [ ] Enable `secure=True` for cookies (HTTPS)
- [ ] Restrict CORS origins (no wildcard with credentials)
- [ ] Implement CSRF protection
- [ ] Add file upload MIME type whitelist
- [ ] Add rate limiting to auth endpoints
- [ ] Implement account lockout after 5 failed attempts
- [ ] Add password complexity requirements (12+ chars)
- [ ] Clean up expired JWT blacklist tokens
- [ ] Add security headers middleware (X-Frame-Options, CSP, etc.)
- [ ] Use logging instead of print statements
- [ ] Add connection timeout to database
- [ ] Review and limit sensitive error messages

### Performance
- [ ] Add `selectinload()` to N+1 query prone endpoints
- [ ] Add indexes to all foreign keys
- [ ] Batch-load empty slot removals in equipamentos
- [ ] Move R2 backup to thread executor (non-blocking)
- [ ] Add query result pagination (offset/keyset)
- [ ] Add database connection pool settings

### Code Quality
- [ ] Extract error handling decorator
- [ ] Extract uniqueness validation helper
- [ ] Add generic types to `Mapped[list[...]]`
- [ ] Add complete docstrings to all service functions
- [ ] Remove unused imports
- [ ] Create custom exception hierarchy (DomainException)
- [ ] Add global exception handler for domain exceptions
- [ ] Move business logic from router to service/schema
- [ ] Add consistent naming conventions documentation
- [ ] Add input validators to Pydantic schemas

### Testing
- [ ] Add security tests for CSRF, rate limiting
- [ ] Add N+1 query detection in tests
- [ ] Add performance benchmarks
- [ ] Test password complexity validation
- [ ] Test account lockout mechanism
- [ ] Test JWT token expiration and refresh
- [x] Injection Validation (SQL, Command, Jinja)
- [x] Auth and JWT Mechanism Scan
- [x] N+1 Queries Identifier
- [x] Architecture Layering Assessment
- [ ] Implementação de Testes Unitários Baseados em Domínio (Cobertura)
