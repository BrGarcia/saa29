# Plano Detalhado de Implementação - Auditoria SAA29

**Data:** 2026-04-19  
**Versão:** 2.0  
**Status:** 📋 Em Preparação  
**Objetivo:** Executar todas as correções da auditoria em 5 fases (~45-50 horas)

**Documento Complementar:** Veja `IMPLEMENTATION_PLAN.md` para detalhes técnicos passo-a-passo.

---

## 📊 ROADMAP EXECUTIVO

### Fase 1: SECURITY CRITICAL (Semana 1) - 8 horas
Resolver 3 vulnerabilidades críticas que permitem forjamento de tokens e acesso não-autorizado.

| Sprint | Issue | Arquivo | Tempo | Status |
|--------|-------|---------|-------|--------|
| 1.1 | Remove R2 credentials from Git | `.env` | 1-2h | ❌ |
| 1.2 | Fix insecure secret key | `app/config.py:21` | 1h | ❌ |
| 1.3 | Remove hardcoded admin password | `scripts/*.py` | 1h | ❌ |

### Fase 2: SECURITY HIGH (Semana 1-2) - 12 horas
Resolver 10 vulnerabilidades altas de segurança.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 2.1 | Debug mode + JWT expiration | 1.5h | ❌ |
| 2.2 | Cookie flags + CORS | 1.5h | ❌ |
| 2.3 | CSRF protection | 2h | ❌ |
| 2.4 | File upload security | 1.5h | ❌ |

### Fase 3: PERFORMANCE + MEDIUM SECURITY (Semana 2-3) - 14 horas
Otimizar banco de dados e resolver 9 vulnerabilidades médias.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 3.1 | Rate limiting + Account lockout | 2.5h | ❌ |
| 3.2 | N+1 queries + FK indexes | 2.5h | ❌ |
| 3.3 | Async subprocess blocking | 1h | ❌ |

### Fase 4: CODE QUALITY (Semana 3-4) - 12 horas
Eliminar duplicação e melhorar arquitetura.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 4.1 | Extract error handler | 2h | ❌ |
| 4.2 | Extract common helpers | 1.5h | ❌ |
| 4.3 | Security headers middleware | 1h | ❌ |
| 4.4 | Replace print with logging | 1h | ❌ |

### Fase 5: TESTING (Semana 4-5) - 8 horas
Validar todas as correções com testes abrangentes.

| Sprint | Issue | Tempo | Status |
|--------|-------|-------|--------|
| 5.1 | Security tests | 2h | ❌ |
| 5.2 | Performance tests | 1h | ❌ |
| 5.3 | Integration tests | 2h | ❌ |
| 5.4 | Verification script | 1h | ❌ |

---

## 🔴 FASE 1: SECURITY CRITICAL (Máxima Prioridade)

### Problema
3 vulnerabilidades críticas permitem:
1. Acesso ao Cloudflare R2 storage (credenciais expostas no Git)
2. Forjamento de tokens JWT (secret key padrão conhecida)
3. Login como admin com password hardcoded

### Solução Resumida
1. Remover `.env` do histórico Git com `git filter-repo`
2. Adicionar validação em `app/config.py` que rejeita secrets inseguras
3. Remover fallback hardcoded em `scripts/init_db.py` e `scripts/seed.py`

### Próximos Passos Detalhados
Veja `IMPLEMENTATION_PLAN.md` > **FASE 1** para instruções passo-a-passo.

---

## 🟠 FASE 2: SECURITY HIGH

### Problemas
10 vulnerabilidades altas incluem:
- Debug mode habilitado (expõe API internals)
- JWT com 2 horas de validade (muito longo)
- Cookies sem flag `secure` (não HTTPS-only)
- CORS permite wildcard com credentials
- Sem proteção CSRF
- Validação fraca em upload de arquivos

### Solução Resumida
1. Defaults: debug=False, JWT timeout=15min
2. Adicionar refresh token mechanism
3. Enable secure cookie flags dinamicamente
4. Implementar CSRF middleware
5. Validar MIME types em uploads

### Próximos Passos Detalhados
Veja `IMPLEMENTATION_PLAN.md` > **FASE 2** para código específico.

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

[ ] FASE 2: SECURITY HIGH (12h)
    [ ] Sprint 2.1: Debug + JWT (1.5h)
    [ ] Sprint 2.2: Cookies + CORS (1.5h)
    [ ] Sprint 2.3: CSRF (2h)
    [ ] Sprint 2.4: File Upload (1.5h)

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
