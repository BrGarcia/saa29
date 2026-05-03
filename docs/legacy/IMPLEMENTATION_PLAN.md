# Plano Detalhado de Implementação - Auditoria SAA29

**Data:** 2026-04-19  
**Versão:** 1.0  
**Status:** Em Preparação  
**Objetivo:** Implementar todas as correções da auditoria em 5 fases (~45-50 horas)

---

## 📋 RESUMO EXECUTIVO

Este documento detalhado especifica como implementar:
- 🔴 **3 vulnerabilidades CRÍTICAS** (Fase 1)
- 🟠 **10 vulnerabilidades ALTAS** (Fase 2)  
- 🟡 **9 vulnerabilidades MÉDIAS** (Fase 3)
- ⚡ **5 problemas de PERFORMANCE** (Fase 3)
- 📋 **7 problemas de DUPLICAÇÃO** (Fase 4)

**Timeline:** 5 sprints em ~4-5 semanas

---

## 🔴 FASE 1: SECURITY CRITICAL - ~8 horas - MÁXIMA PRIORIDADE

### Objetivo
Resolver 3 vulnerabilidades críticas que permitem acesso não-autorizado e forjamento de tokens.

### SPRINT 1.1: Remove Exposed R2 Credentials from Git
**Severidade:** 🔴 CRÍTICA  
**Tempo:** 1-2 horas  
**Status:** ❌ NOT STARTED

#### Problema
```
File: .env (linhas 36-40)
R2_ACCOUNT_ID=7fa0ed8254b8f41ec3eb2e83b5bc622f
R2_ACCESS_KEY_ID=dce783c7c9793fbaa2b3a079606ee1ca
R2_SECRET_ACCESS_KEY=3deb304c21438f4cbcdecfdd426b14f4fb40df53798e3618d75ae38ec1e1957a
```
**Impacto:** Atacantes podem acessar/modificar todos os backups no Cloudflare R2.

#### Execução
**Passo 1:** Instalar git-filter-repo
```bash
pip install git-filter-repo
```

**Passo 2:** Remover .env do histórico completo
```bash
cd C:\Users\brgar\Projetos\SAA29
git filter-repo --path .env --invert-paths
```

**Passo 3:** Verificação
```bash
# Confirmar .env foi removido
git log --all --full-history -- .env
# Esperado: nenhuma saída

# Verificar .gitignore
grep -q "^.env$" .gitignore && echo "✓ .env in .gitignore"
```

**Passo 4:** Rotar credenciais Cloudflare
- Login: https://dash.cloudflare.com
- R2 → API Tokens
- Remover token antigo
- Criar novo token com permissões mínimas
- Atualizar em CI/CD secrets (GitHub/GitLab)

**Passo 5:** Notificar team
- Comunicar que repo foi limpo
- Fazer backup local do .env antes de remover
- Instruir equipe a fazer `git pull` com `--force-with-lease`

#### Verification Checklist
- [ ] git filter-repo executado
- [ ] git log --all --full-history -- .env retorna vazio
- [ ] .gitignore contém .env
- [ ] Credenciais R2 rotacionadas no dashboard
- [ ] CI/CD secrets atualizados
- [ ] Team notificada
- [ ] Backup local confirmado

---

### SPRINT 1.2: Fix Insecure Default Secret Key
**Severidade:** 🔴 CRÍTICA  
**Arquivo:** `app/config.py:21`  
**Tempo:** 1 hora  
**Status:** ❌ NOT STARTED

#### Problema
```python
app_secret_key: str = "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION"
```
**Impacto:** Se APP_SECRET_KEY não for configurado, qualquer pessoa pode forjar tokens JWT.

#### Implementação

**Arquivo: `app/config.py`**
```python
from pydantic import model_validator
import warnings

class Settings(BaseSettings):
    app_secret_key: str = Field(
        default="",
        description="Secret key for JWT. Must be set in production."
    )
    
    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """Validate that secret key is not the insecure default."""
        
        # Check if empty or default insecure value
        if not self.app_secret_key or \
           self.app_secret_key == "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION":
            
            # In production = FATAL ERROR
            if self.app_env == "production":
                raise ValueError(
                    "FATAL: APP_SECRET_KEY is not set or is the insecure default.\n"
                    "Generate a strong key with:\n"
                    "  python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
                    "Then set: export APP_SECRET_KEY='<generated_value>'"
                )
            
            # In development = warn and use temporary key
            warnings.warn(
                "⚠️  WARNING: APP_SECRET_KEY is using default/empty value.\n"
                "This is INSECURE in production! Generate one with:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
                RuntimeWarning
            )
            self.app_secret_key = "dev_insecure_key_for_testing_only_' + os.urandom(16).hex()"
        
        # Check minimum length
        if len(self.app_secret_key) < 32:
            raise ValueError(
                f"APP_SECRET_KEY must be at least 32 characters long. "
                f"Current length: {len(self.app_secret_key)}\n"
                f"Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        return self
```

**Arquivo: `.env.example`** (update)
```env
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# MUST be at least 32 characters long
APP_SECRET_KEY=your_strong_random_key_min_32_chars_generate_with_secrets_module
```

**Arquivo: `scripts/generate_secrets.py`** (novo)
```python
#!/usr/bin/env python
"""Generate secure random keys for environment variables."""

import secrets
import sys

def generate_app_secret_key() -> str:
    """Generate a strong 32+ character secret key for JWT."""
    return secrets.token_urlsafe(32)

def generate_admin_password() -> str:
    """Generate a strong 16+ character password."""
    return secrets.token_urlsafe(16)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "admin-password":
        print(generate_admin_password())
    else:
        print(generate_app_secret_key())
```

**Testes: `tests/test_config_security.py`** (novo)
```python
import pytest
from app.config import Settings
from fastapi import FastAPI

def test_rejects_empty_secret_key_in_production():
    """Test that empty secret key is rejected in production."""
    with pytest.raises(ValueError, match="APP_SECRET_KEY is not set"):
        Settings(app_env="production", app_secret_key="")

def test_rejects_insecure_default_secret_key_in_production():
    """Test that insecure default is rejected in production."""
    with pytest.raises(ValueError, match="FATAL"):
        Settings(
            app_env="production",
            app_secret_key="INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION"
        )

def test_rejects_short_secret_key():
    """Test that short secret keys are rejected."""
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(app_secret_key="short")

def test_accepts_valid_secret_key():
    """Test that valid 32+ char keys are accepted."""
    valid_key = "x" * 32
    settings = Settings(app_secret_key=valid_key)
    assert settings.app_secret_key == valid_key
```

#### Verification Checklist
- [ ] `app/config.py` validators implementados
- [ ] `.env.example` atualizado
- [ ] `scripts/generate_secrets.py` criado
- [ ] `tests/test_config_security.py` passando
- [ ] `.env` local atualizado com nova key
- [ ] Aplicação inicia sem warnings

---

### SPRINT 1.3: Remove Hardcoded Admin Passwords from Scripts
**Severidade:** 🔴 CRÍTICA  
**Arquivos:** `scripts/init_db.py`, `scripts/seed.py`  
**Tempo:** 1 hora  
**Status:** ❌ NOT STARTED

#### Problema
```python
# scripts/init_db.py
admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "BisKP76pg3IU").strip()
```
**Impacto:** Qualquer pessoa com acesso ao repositório pode usar password padrão "BisKP76pg3IU" para fazer login como admin.

#### Implementação

**Arquivo: `scripts/init_db.py`** (replace beginning)
```python
#!/usr/bin/env python
"""Initialize database with default admin user."""

import os
import sys
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, Base, _engine
from app.auth.models import Usuario
from app.auth.security import hash_senha

def get_admin_password() -> str:
    """
    Get admin password from environment or fail loudly.
    
    Raises:
        ValueError: If password not set or too weak
    """
    admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "").strip()
    
    if not admin_pass:
        raise ValueError(
            "❌ FATAL: DEFAULT_ADMIN_PASSWORD must be set via environment variable.\n\n"
            "Generate a strong password with:\n"
            "  python -c \"import secrets; print(secrets.token_urlsafe(16))\"\n\n"
            "Then set it:\n"
            "  export DEFAULT_ADMIN_PASSWORD='<generated_password>'\n\n"
            "Recommended: Use at least 16 characters with mix of upper/lower/numbers/special chars."
        )
    
    if len(admin_pass) < 12:
        raise ValueError(
            f"❌ DEFAULT_ADMIN_PASSWORD must be at least 12 characters long.\n"
            f"Current length: {len(admin_pass)} characters.\n\n"
            f"Generate strong password with:\n"
            f"  python -c \"import secrets; print(secrets.token_urlsafe(16))\""
        )
    
    return admin_pass

async def initialize_db():
    """Initialize database and create default admin user."""
    try:
        admin_pass = get_admin_password()
    except ValueError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)
    
    # ... rest of init_db code
```

**Arquivo: `scripts/seed.py`** (update imports)
```python
#!/usr/bin/env python
"""Seed development database with test data."""

import asyncio
from scripts.init_db import get_admin_password
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.auth.models import Usuario

async def seed_data():
    try:
        admin_pass = get_admin_password()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # ... rest of seed code
```

**Arquivo: `README.md`** (add section)
```markdown
## Development Setup

### 1. Initialize Database

Generate a strong admin password:
```bash
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

Export it:
```bash
export DEFAULT_ADMIN_PASSWORD="your_generated_password"
```

Initialize database:
```bash
python -m scripts.init_db
python -m scripts.seed
```

### Important Security Notes
- ⚠️ **NEVER** commit `.env` with real passwords/keys
- Always use `.env.example` with placeholders
- Generate strong secrets for production
- Rotate admin passwords regularly
```

#### Verification Checklist
- [ ] `scripts/init_db.py` atualizado (remove fallback)
- [ ] `scripts/seed.py` importa função de init_db
- [ ] `get_admin_password()` function reutilizável
- [ ] README.md com instruções de setup
- [ ] Testes manuais executados:
  ```bash
  # Test 1: Sem variável - deve falhar
  unset DEFAULT_ADMIN_PASSWORD
  python -m scripts.init_db 2>&1 | grep "FATAL"
  
  # Test 2: Com password curta - deve falhar
  export DEFAULT_ADMIN_PASSWORD="short"
  python -m scripts.init_db 2>&1 | grep "at least 12 characters"
  
  # Test 3: Com password válida - deve funcionar
  export DEFAULT_ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(16))")
  python -m scripts.init_db && echo "✓ Success"
  ```

---

## 🟠 FASE 2: SECURITY HIGH - ~12 horas

### SPRINT 2.1: Fix Debug Mode and JWT Expiration
**Issues:**
- Debug mode enabled by default (info disclosure)
- JWT expiration too long (2 hours)

**Tempo:** 1.5 horas  
**Status:** ❌ NOT STARTED

#### Changes Required
1. `app/config.py` - change defaults
2. `app/auth/models.py` - add RefreshToken model
3. `app/auth/security.py` - add refresh token functions
4. `app/auth/router.py` - add /refresh endpoint
5. `migrations/versions/` - new migration

---

### SPRINT 2.2: Secure Cookies and CORS
**Issues:**
- Cookie secure flag not enabled for HTTPS
- CORS allows credentials with wildcard

**Tempo:** 1.5 horas  
**Status:** ❌ NOT STARTED

#### Changes Required
1. `app/auth/router.py` - enable secure flag dynamically
2. `app/main.py` - validate CORS origins, whitelist methods/headers

---

### SPRINT 2.3: Add CSRF Protection
**Issue:** No CSRF token validation

**Tempo:** 2 horas  
**Status:** ❌ NOT STARTED

#### Changes Required
1. `pip install fastapi-csrf-protect`
2. `app/middleware/csrf.py` - new middleware
3. `app/main.py` - register middleware
4. `templates/base.html` - extract CSRF token
5. `static/js/app.js` - add CSRF to fetch requests

---

### SPRINT 2.4: File Upload Security
**Issues:**
- Weak Content-Type validation
- Path traversal risk

**Tempo:** 1.5 horas  
**Status:** ❌ NOT STARTED

#### Changes Required
1. `app/core/file_validators.py` - new file
2. `app/panes/router.py` - validate uploads
3. Add whitelist of allowed MIME types and extensions
4. Test malicious uploads

---

## 🟡 FASE 3: PERFORMANCE + MEDIUM SECURITY - ~14 horas

### SPRINT 3.1: Rate Limiting and Account Lockout
**Tempo:** 2.5 horas

#### Changes
- Install `slowapi`
- Add rate limiting to `/auth/login` (5/minute)
- Add account lockout after 5 failed attempts
- Add `failed_login_attempts`, `locked_until` fields to Usuario

---

### SPRINT 3.2: Performance - N+1 Queries and Indexes
**Tempo:** 2.5 horas

#### Changes
- Create migration to add FK indexes
- Add `selectinload()` to relationship queries
- Batch-load empty slot removals
- Add DB connection timeout

---

### SPRINT 3.3: Fix Async Subprocess Blocking
**Tempo:** 1 hour

#### Changes
- Move `_run_r2_backup()` to async
- Use `loop.run_in_executor()` to not block event loop

---

## 📋 FASE 4: CODE QUALITY - ~12 horas

### SPRINT 4.1: Extract Error Handling Decorator
**Tempo:** 2 hours
- Create `app/core/decorators.py`
- Decorator `@handle_service_errors` converts ValueError → HTTP 409/404
- Apply to ~15 endpoints

### SPRINT 4.2: Extract Common Helpers
**Tempo:** 1.5 hours
- Create `check_unique_field()` generic helper
- Create `get_or_404()` generic helper
- Create `format_pane_codigo()` helper

### SPRINT 4.3: Add Security Headers Middleware
**Tempo:** 1 hour
- X-Content-Type-Options, X-Frame-Options, CSP, etc.

### SPRINT 4.4: Replace Print with Logging
**Tempo:** 1 hour
- Remove print() statements
- Use logging module throughout

---

## 🧪 FASE 5: TESTING - ~8 horas

### SPRINT 5.1: Security Tests
**Tempo:** 2 hours
- Rate limiting tests
- CSRF protection tests
- Password strength validation
- File upload security tests
- Authorization tests

### SPRINT 5.2: Performance Tests
**Tempo:** 1 hour
- N+1 query detection
- Response time benchmarks

### SPRINT 5.3: Integration Tests
**Tempo:** 2 hours
- Full auth flow
- File upload flow
- Authorization flows

### SPRINT 5.4: Verification
**Tempo:** 1 hour
- Create `scripts/verify_fixes.sh`
- Run all verification tests

---

## 📊 SUMMARY BY PHASE

| Phase | Sprints | Hours | Dependencies |
|-------|---------|-------|--------------|
| **1: CRITICAL** | 1.1-1.3 | 8 | None |
| **2: HIGH** | 2.1-2.4 | 12 | Requires Phase 1 |
| **3: PERF+MED** | 3.1-3.3 | 14 | Requires Phase 1-2 |
| **4: QUALITY** | 4.1-4.4 | 12 | Requires Phase 1-3 |
| **5: TESTING** | 5.1-5.4 | 8 | Requires Phase 1-4 |
| | **TOTAL** | **~54** | |

---

## 🎯 IMMEDIATE ACTION ITEMS

- [ ] Review this plan with development team
- [ ] Prioritize phases based on availability
- [ ] Create Git branches for each phase
- [ ] Assign tasks to developers
- [ ] Schedule security code reviews
- [ ] Plan deployment strategy

---

## ⚠️ CRITICAL REMINDERS

- **Security First:** Prioritize all CRITICAL issues in Phase 1
- **Testing:** Test ALL changes in dev/staging before production
- **Communication:** Notify team about Git history rewrite (Phase 1.1)
- **Monitoring:** Monitor application after each phase for regressions
- **Documentation:** Update READMEs and setup guides
- **Backup:** Backup `.env` before removing from Git
