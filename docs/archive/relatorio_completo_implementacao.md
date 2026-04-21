# Plano Detalhado de Implementação - Auditoria SAA29

**Data:** 2026-04-19  
**Versão:** 2.0  
**Status:** 📋 Em Preparação  
**Objetivo:** Executar todas as correções da auditoria em 5 fases (~45-50 horas)

**Documento Complementar:** Veja `IMPLEMENTATION_PLAN.md` para detalhes técnicos passo-a-passo.

---

# Plano Detalhado de Implementação - Auditoria SAA29

**Data:** 2026-04-19  
**Versão:** 3.1 (Progress Update)
**Status:** 🚀 Em Execução (Phase 1 e Phase 2 100% Completos)
**Objetivo:** Executar todas as correções da auditoria em 5 fases (~45-50 horas)

**Documento Complementar:** Veja `IMPLEMENTATION_PLAN.md` para detalhes técnicos passo-a-passo.

---

## 📊 ROADMAP EXECUTIVO

### Fase 1: SECURITY CRITICAL ✓ COMPLETO (8 horas - Semana 1)
Resolver 3 vulnerabilidades críticas que permitem forjamento de tokens e acesso não-autorizado.

| Sprint | Issue | Arquivo | Tempo | Status |
|--------|-------|---------|-------|--------|
| 1.1 | Remove R2 credentials from Git | `.env` | 1-2h | ✅ COMPLETO |
| 1.2 | Fix insecure secret key | `app/config.py:21` | 1h | ✅ COMPLETO |
| 1.3 | Remove hardcoded admin password | `scripts/*.py` | 1h | ✅ COMPLETO |

### Fase 2: SECURITY HIGH 🚀 100% COMPLETO (12 horas - Semana 1-2)
Resolver 10 vulnerabilidades altas de segurança.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 2.1 | Debug mode + JWT expiration + Refresh tokens | 1.5h | ✅ COMPLETO |
| 2.2 | Cookie flags + CORS + Security headers | 1.5h | ✅ COMPLETO |
| 2.3 | CSRF protection | 2h | ✅ COMPLETO |
| 2.4 | File upload security | 1.5h | ✅ COMPLETO |

### Fase 3: PERFORMANCE + MEDIUM SECURITY (14 horas - Semana 2-3)
Otimizar banco de dados e resolver 9 vulnerabilidades médias.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 3.1 | Rate limiting + Account lockout | 2.5h | ⏳ TODO |
| 3.2 | N+1 queries + FK indexes | 2.5h | ⏳ TODO |
| 3.3 | Async subprocess blocking | 1h | ⏳ TODO |

### Fase 4: CODE QUALITY (12 horas - Semana 3-4)
Eliminar duplicação e melhorar arquitetura.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 4.1 | Extract error handler | 2h | ⏳ TODO |
| 4.2 | Extract common helpers | 1.5h | ⏳ TODO |
| 4.3 | Security headers middleware | 1h | ✅ (incluído em 2.2) |
| 4.4 | Replace print with logging | 1h | ⏳ TODO |

### Fase 5: TESTING (8 horas - Semana 4-5)
Validar todas as correções com testes abrangentes.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 5.1 | Security tests | 2h | ⏳ TODO |
| 5.2 | Performance tests | 1h | ⏳ TODO |
| 5.3 | Integration tests | 2h | ⏳ TODO |
| 5.4 | Verification script | 1h | ⏳ TODO |

---

## ✅ FASE 1: SECURITY CRITICAL (Máxima Prioridade)

### Status: COMPLETO

**Implementação Total:** 3/3 Sprints (100%)

#### Sprint 1.1: Remove Exposed R2 Credentials from Git ✅
**Status:** COMPLETO (Verificação passiva - .env nunca foi commitado)

- Verificado: `.env` não existe no histórico Git
- `.gitignore` contém regra para `.env`
- Backup local criado (`.env.backup`)
- **Risco mitigado:** Credenciais R2 nunca foram expostas no Git

#### Sprint 1.2: Fix Insecure Default Secret Key ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `app/config.py` (76 linhas adicionadas/modificadas)
- `.env` (atualizado com chave segura e JWT timeout reduzido)

**Mudanças:**
- Adicionado Field() descriptors com documentação de segurança
- Validação aprimorada `validate_security()`:
  - REJEITA secret keys vazios ou contendo "INSECURE"
  - Enforça mínimo de 32 caracteres
  - Bloqueia `debug=True` em produção
  - Avisa se `debug=True` em desenvolvimento
- `APP_DEBUG`: `True` → `False`
- `APP_SECRET_KEY`: 64 caracteres aleatórios (gerados com `secrets.token_hex(32)`)
- `JWT_EXPIRE_MINUTES`: `480` (8 horas) → `15` (15 minutos)

**Impacto de Segurança:**
- ✅ Forjamento de JWT agora impossível (secret enforçado)
- ✅ Janela de roubo de token reduzida 32x (8h → 15min)
- ✅ Detalhes internos não expostos (debug=False)

#### Sprint 1.3: Remove Hardcoded Admin Password ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `scripts/init_db.py` (+12 linhas)
- `scripts/seed.py` (+12 linhas)
- `scripts/reset_admin.py` (+12 linhas)
- `.env` (atualizado com password segura)

**Mudanças:**
- REMOVIDO fallback hardcoded: `"BisKP76pg3IU"` (init_db, seed)
- REMOVIDO fallback hardcoded: `"admin123"` (reset_admin)
- ADICIONADA validação que REJEITA execução se `DEFAULT_ADMIN_PASSWORD` não definida
- Mensagem de erro clara guiando usuário a definir env var
- `.env` atualizado com password seguro: `SecureAdminPassword2024#Random123ABC`

**Verificação:**
- ✅ Scripts rejeitam execução sem env var
- ✅ Scripts funcionam corretamente quando `DEFAULT_ADMIN_PASSWORD` é definida
- ✅ Password nunca pode ser hardcoded

**Impacto de Segurança:**
- ✅ Eliminada via de acesso não-autorizado via password conhecida
- ✅ Deployer DEVE explicitar password (sem fallback)
- ✅ Previne compromissão por pessoa com acesso ao repositório

---

## 🟠 FASE 2: SECURITY HIGH (50% COMPLETO)

---

## 🟢 FASE 2: SECURITY HIGH (100% COMPLETO)

### Status: Em Execução - 4/4 Sprints Completos

**Implementação Atual:** 4/4 Sprints (100%)

#### Sprint 2.1: Fix Debug Mode and JWT Expiration ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `app/auth/models.py` (+51 linhas) - Adicionado TokenRefresh model
- `app/auth/security.py` (+23 linhas) - Adicionado criar_refresh_token()
- `app/auth/schemas.py` (+6 linhas) - Adicionado RefreshTokenRequest
- `app/auth/router.py` (+135 linhas) - /login e /refresh endpoints
- `migrations/versions/` (novo) - Migração: add_token_refresh_table

**Mudanças:**

1. **Token Refresh Mechanism:**
   - Novo TokenRefresh model com jti único, usuario_id, expira_em (7 dias), revogado_em
   - Refresh tokens válidos por 7 dias (vs access tokens 15 min)
   - Token rotation: novo refresh token gerado em cada `/refresh`
   - Rastreamento de revogação para segurança

2. **Endpoints Atualizados:**
   - `/login` agora retorna `access_token` + `refresh_token`
   - `/refresh` endpoint novo: troca refresh token válido por novo access token
   - Validações: verifica expiração, revogação, usuário ativo

3. **Cookie Seguro:**
   - `httponly=True` (previne XSS access to token)
   - `samesite="lax"` (previne CSRF)
   - `max_age=15*60` (15 minutos)
   - Flag `secure=True` em produção (HTTPS only)

**Impacto de Segurança:**
- ✅ Sessões alongadas sem re-login (refresh token 7 dias)
- ✅ Access tokens curtos (15 min) reduzem impacto de roubo
- ✅ Token rotation automático em cada refresh
- ✅ Possibilidade de revogar tokens individuais
- ✅ HttpOnly cookies previnem XSS token theft

#### Sprint 2.2: Secure Cookies and CORS ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `app/main.py` (+57 linhas) - SecurityHeadersMiddleware, CORS fixes

**Mudanças:**

1. **SecurityHeadersMiddleware (Nova):**
   - `X-Content-Type-Options: nosniff` - Previne MIME-sniffing attacks
   - `X-Frame-Options: DENY` - Previne clickjacking
   - `X-XSS-Protection: 1; mode=block` - Legacy XSS protection
   - `Content-Security-Policy` - Restringe scripts/styles a origem
   - `Strict-Transport-Security` - HSTS em produção (31536000s = 1 ano)

2. **CORS Hardened:**
   - Métodos: `["GET", "POST", "PUT", "DELETE", "OPTIONS"]` (era `["*"]`)
   - Headers: `["Content-Type", "Authorization", "X-CSRF-Token"]` (era `["*"]`)
   - Suporte para X-CSRF-Token header (necessário para Sprint 2.3)
   - Origins explícitas em produção (não wildcard com credentials)

**Impacto de Segurança:**
- ✅ Clickjacking attack prevention (X-Frame-Options)
- ✅ MIME-sniffing prevention (X-Content-Type-Options)
- ✅ XSS mitigation (CSP, X-XSS-Protection)
- ✅ Force HTTPS in production (HSTS)
- ✅ CORS não permite métodos/headers desnecessários

#### Sprint 2.3: Add CSRF Protection ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `app/middleware/csrf.py` (Novo)
- `app/main.py` (+ middleware injetado)
- `templates/base.html` (+ tag meta csrf-token)
- `static/js/app.js` (+ header injection X-CSRF-Token)

**Lógica Implementada:**
- Middleware `CSRFMiddleware` customizado intercepta as requisições protegidas usando biblioteca `fastapi-csrf-protect`.
- CSRF Token é repassado nas variáveis de estado (para renderização) e extraido dinamicamente no JS root para todas as mutations de dados da API.

#### Sprint 2.4: File Upload Security ✅
**Status:** COMPLETO

**Arquivos Modificados:**
- `app/core/file_validators.py` (Novo)
- `app/panes/router.py` (Aplicando validador)
- `app/core/storage.py` (Mitigação Path Traversal em ambos os backends Local & R2)

**Lógica Implementada:**
- Magic bytes verification usando `python-magic` (Libmagic). Extensões não combinantes com bytes crus resultam em banimento de operação (HTTP 422).
- Upload payloads são blindados contra RCE ou Directory Traversing (ex. `../../../`).

---

### Resumo Phase 2 - Vulnerabilidades Altas Endereçadas:

| # | Vulnerabilidade | Sprint | Status |
|---|---|---|---|
| 1 | Debug mode exposed | 2.1 | ✅ Incluído em Phase 1 |
| 2 | JWT expiration muito longo | 2.1 | ✅ COMPLETO (480 → 15 min) |
| 3 | Refresh token missing | 2.1 | ✅ COMPLETO (7-day tokens) |
| 4 | Cookies not httponly | 2.1 | ✅ COMPLETO (HttpOnly set) |
| 5 | Cookies not secure | 2.2 | ✅ COMPLETO (com flag) |
| 6 | CORS misconfigured | 2.2 | ✅ COMPLETO (explicit methods) |
| 7 | No CSRF protection | 2.3 | ✅ COMPLETO (Middleware injetado) |
| 8 | Weak file upload validation | 2.4 | ✅ COMPLETO (MagicBytes via libmagic e Storage Strict) |
| 9 | No rate limiting | Phase 3 | ⏳ TODO |
| 10 | No account lockout | Phase 3 | ⏳ TODO |

---

---

## 🟡 FASE 3: PERFORMANCE + MEDIUM SECURITY

### Problemas de Performance
- N+1 queries em lazy-loaded relationships (50%+ mais queries)
- Missing FK indexes
- Per-slot queries em loop
- Subprocess blocking event loop

### Problemas de Segurança Média
- Sem rate limiting no login (brute force possível)
- Sem account lockout
- JWT blacklist nunca limpa
- Senhas com apenas 6 caracteres

### Solução Resumida
1. Add `selectinload()` a todas as queries
2. Create FK indexes via migration
3. Batch-load empty slot data
4. Implementar rate limiting (slowapi)
5. Adicionar account lockout (15 min após 5 tentativas)

### Próximos Passos Detalhados
Veja `IMPLEMENTATION_PLAN.md` > **FASE 3**.

---

## 📋 FASE 4: CODE QUALITY

### Problemas
- 15+ repetições de try/except ValueError boilerplate
- Duplicação de validação de unicidade
- Sem security headers (X-Frame-Options, CSP)
- Print statements ao invés de logging

### Solução Resumida
1. Criar `@handle_service_errors` decorator
2. Extrair helpers genéricos (check_unique_field, get_or_404)
3. Add security headers middleware
4. Replace print() com logging.Logger

### Redução de Código
- ~300 linhas removidas (try/except boilerplate)
- ~200 linhas removidas (validação duplicada)

---

## 🧪 FASE 5: TESTING

### Testes a Adicionar
- Security tests (15+ casos)
- Performance regression tests (query counting)
- Integration tests (full flows)
- Verification script

### Target Coverage
- All critical security features tested
- No N+1 regressions
- All new features validated

---

## 🔄 PRÓXIMOS PASSOS IMEDIATOS

1. **Revisar este plano** com development team
2. **Briefing sobre segurança:**
   - Explicar impacto de cada vulnerabilidade
   - Aprovar abordagem de fix
3. **Criar feature branches:**
   ```bash
   git checkout -b fix/security-critical
   git checkout -b fix/security-high
   etc.
   ```
4. **Assign tasks** aos desenvolvedores
5. **Schedule code reviews** com security team
6. **Plan deployment:**
   - Dev → Staging (test 2-3 dias)
   - Staging → Production (durante low-traffic time)

---

## 📝 NOTA IMPORTANTE

Para instruções TÉCNICAS DETALHADAS (código específico, passo-a-passo):
👉 **Consulte: `IMPLEMENTATION_PLAN.md`**

Aqui mantemos um resumo executivo de alto nível para planejamento e acompanhamento.

---

## ✅ Checklist de Progresso

Usar este documento para rastrear progresso:

```
[ ] FASE 1: SECURITY CRITICAL (8h)
    [ ] Sprint 1.1: Remove R2 credentials (2h)
    [ ] Sprint 1.2: Fix secret key (1h)
    [ ] Sprint 1.3: Remove admin password (1h)

[x] FASE 2: SECURITY HIGH (12h)
    [x] Sprint 2.1: Debug + JWT (1.5h)
    [x] Sprint 2.2: Cookies + CORS (1.5h)
    [x] Sprint 2.3: CSRF (2h)
    [x] Sprint 2.4: File Upload (1.5h)

[ ] FASE 3: PERFORMANCE + MED (14h)
    [ ] Sprint 3.1: Rate limiting (2.5h)
    [ ] Sprint 3.2: N+1 queries (2.5h)
    [ ] Sprint 3.3: Async blocking (1h)

[ ] FASE 4: CODE QUALITY (12h)
    [ ] Sprint 4.1: Error handler (2h)
    [ ] Sprint 4.2: Helpers (1.5h)
    [ ] Sprint 4.3: Security headers (1h)
    [ ] Sprint 4.4: Logging (1h)

[ ] FASE 5: TESTING (8h)
    [ ] Sprint 5.1: Security tests (2h)
    [ ] Sprint 5.2: Performance tests (1h)
    [ ] Sprint 5.3: Integration tests (2h)
    [ ] Sprint 5.4: Verification (1h)
```

---

## 📞 CONTATO E DÚVIDAS

Para dúvidas sobre implementação específica:
- Consulte `IMPLEMENTATION_PLAN.md` para código passo-a-passo
- Consulte `RELATORIO_COMPLETO.MD` para análise detalhada
- Contacte security team para revisão
