# 🔐 Plano de Execução — ETAPA 4: Autenticação, Sessões & Segurança Central

> **Escopo:** `app/modules/auth/` + `app/shared/middleware/` + `app/bootstrap/dependencies.py`
> **Relatório a gerar:** `docs/backlog/Fable5/relatorio_auth_seguranca.md`
> **Referência de processo:** `docs/backlog/Fable5/Planejamento_revisao.md`
> **Template de auditoria:** `docs/backlog/Fable5/prompt.md`

---

## 📁 Arquivos-Alvo (1.386 linhas)

| Arquivo | Linhas | Prioridade |
|---|---:|:---:|
| `app/modules/auth/router.py` | 479 | 🔴 Alta |
| `app/modules/auth/service.py` | 322 | 🔴 Alta |
| `app/bootstrap/dependencies.py` | 160 | 🔴 Alta |
| `app/modules/auth/security.py` | 107 | 🔴 Alta |
| `app/shared/middleware/csrf.py` | 86 | 🟡 Média |
| `app/shared/middleware/security.py` | 48 | 🟡 Média |
| `app/modules/auth/models.py` | 227 | 🟢 Baixa |
| `app/modules/auth/schemas.py` / `roles.py` | 94 / 19 | 🟢 Baixa |

> ⚠️ **Correção de caminho no plano original:** `Planejamento_revisao.md` lista
> `app/shared/dependencies.py` — **esse arquivo não existe**. O real é
> **`app/bootstrap/dependencies.py`** (contém `get_current_user`, `require_role` e os aliases de RBAC).
> Corrigir a referência no plano-mãe ao consolidar esta etapa.

---

## 🔎 Achados Pré-Verificados

**CONFIRMADO** = verificado nesta sessão; **A VERIFICAR** = forte indício, exige teste na execução.

### 🔴 Críticos

---

#### 1. Revogação de família de refresh tokens é desfeita por rollback — **CONFIRMADO**
- **Tipo:** Vulnerabilidade
- **Evidência (`app/modules/auth/router.py:174-187`):**
  ```python
  if stored_token.revogado_em is not None:
      await db.execute(
          update(TokenRefresh)
          .where((TokenRefresh.usuario_id == stored_token.usuario_id) &
                 (TokenRefresh.revogado_em.is_(None)))
          .values(revogado_em=agora)
      )
      raise HTTPException(401, "Reuso de token detectado. Todos os tokens foram revogados...")
  ```
- **Cadeia que anula a defesa (`app/bootstrap/dependencies.py:30-38`):**
  ```python
  async with get_session_factory()() as session:
      try:
          yield session
          await session.commit()
      except Exception:
          await session.rollback()   # ← desfaz o UPDATE de revogação
          raise
  ```
  O `raise HTTPException` propaga pela dependency `get_db`, cai no `except Exception` e **faz rollback
  do UPDATE de revogação**. A resposta 401 diz ao usuário que *"todos os tokens foram revogados por
  segurança"* — mas **nenhum token foi revogado**.
- **Risco & Impacto:** este é exatamente o mecanismo de defesa citado no plano-mãe
  (*"invalidação de família em tentativa de reuso"*). Um atacante que roubou um refresh token
  continua podendo usá-lo indefinidamente após a detecção; a detecção de reuso é **puramente decorativa**.
- **Contraste que prova o diagnóstico (`app/modules/auth/router.py:46-53`):** o endpoint de **login**
  tem o problema resolvido — faz `await db.commit()` **explícito** antes do `raise`, com o comentário
  *"Commit manual para persistir o incremento de falhas"*. O bloco de reuso **não** faz isso.
  ⇒ O contador de brute force **funciona**; a revogação de família **não**.
- **Correção:** `await db.commit()` antes do `raise`, espelhando o login. Melhor ainda: encapsular como
  `revogar_familia_de_tokens(db, usuario_id)` em `auth/service.py`, com commit próprio, e considerar
  um handler que persista efeitos de segurança independentemente do status da resposta.
- **Teste obrigatório:** reusar um refresh token revogado e, **em nova sessão de banco**, verificar que
  todos os `TokenRefresh` do usuário estão com `revogado_em` preenchido. Hoje esse teste falha.
  `tests/security/test_refresh_token.py` tem **1 único teste** — cobertura insuficiente para este fluxo.

---

#### 2. Ausência de validação do claim `type` em `get_current_user` — **CONFIRMADO** (latente)
- **Tipo:** Vulnerabilidade (defesa em profundidade)
- **Evidência (`app/bootstrap/dependencies.py:79-95`):** valida assinatura, `sub`, `jti` e blacklist —
  **nunca checa `payload.get("type")`**. Access e refresh são assinados com a **mesma chave e o mesmo
  algoritmo** (`security.py:67` e `security.py:86`).
- **Por que ainda não é explorável — e por que isso é frágil:** o `sub` difere por acaso.
  Access token usa `sub = usuario.username` (`router.py:56`); refresh usa `sub = str(usuario_id)`
  (`security.py:80`). Um refresh token enviado como access cai em
  `buscar_por_username(db, "<uuid>")` → `None` → 401. **A proteção é um efeito colateral da escolha de
  `sub`, não uma verificação deliberada.** Basta alguém padronizar `sub` para o UUID — refatoração
  plausível e aparentemente inofensiva — para abrir um bypass: um refresh token de **7 dias** passaria a
  valer como access token de **15 minutos**, ignorando a blacklist de access.
- **Assimetria que confirma a omissão:** o endpoint `/auth/refresh` **faz** a checagem correta
  (`router.py:141`: `if payload.get("type") != "refresh"`). A validação existe num sentido e falta no outro.
- **Correção:** `if payload.get("type") != "access": raise credentials_exception` em `get_current_user`.
  Alternativa mais robusta: `decodificar_token(token, tipo_esperado: str)` obrigando a escolha no call site.

---

#### 3. Senha do administrador é sobrescrita a cada boot — **CONFIRMADO**
- **Tipo:** Bug / Vulnerabilidade operacional
- **Evidência (`app/modules/auth/service.py:267-269`), em `garantir_usuarios_essenciais` (chamada no lifespan):**
  ```python
  if not verificar_senha(admin_pass, admin.senha_hash):
      admin.senha_hash = hash_senha(admin_pass)
      print(f"AuthService: Senha do admin atualizada para coincidir com as configurações.")
  ```
- **Risco & Impacto:** o admin troca a senha pela UI; no próximo restart ela **volta silenciosamente**
  para o valor de `DEFAULT_ADMIN_PASSWORD` do `.env`. Qualquer pessoa com acesso ao `.env` (ou ao histórico
  de deploy) tem acesso permanente e **a rotação de senha do admin é impossível na prática**.
  O comentário justifica com *"útil após restore do R2"* — mas o efeito vale em todo boot, não só em restore.
- **Correção:** aplicar **somente na criação** do admin. Para o cenário de restore, exigir um flag
  explícito e temporário (ex.: `ADMIN_PASSWORD_RESET=1`), com log de auditoria em nível `WARNING`.

---

#### 4. Usuários de teste com senha fixa `123456` criados por variável de ambiente — **CONFIRMADO**
- **Tipo:** Vulnerabilidade
- **Evidência (`app/modules/auth/service.py:272-291`):** se `settings.app_env == "development"`, cria
  `encarregado`, `inspetor` e `mantenedor` — todos com `hash_senha("123456")` — cobrindo os três papéis
  privilegiados do RBAC.
- **Risco & Impacto:** a criação de contas privilegiadas depende de **uma única variável de ambiente**.
  Um deploy com `APP_ENV` ausente/errado (typo, container sem env, default herdado) instala três
  backdoors com senha trivial. Não há segunda barreira.
- **Agravante correlato (`app/modules/auth/service.py:37`):** `autenticar_usuario` lê
  `os.getenv("APP_ENV", "production")` **direto**, em vez de `settings.app_env` usado no resto do arquivo
  — duas fontes de verdade para a mesma decisão de segurança, que podem divergir. E quando `_is_dev` é
  verdadeiro, **todo o account lockout é desativado** (L39, L54).
- **Correção:** unificar em `settings.app_env`; exigir um segundo gatilho explícito
  (ex.: `SEED_TEST_USERS=1`) para criar os usuários de teste; nunca usar senha literal — gerar aleatória
  e logar uma única vez. Reavaliar se desligar o lockout em dev é mesmo necessário.

---

### 🟡 Média

#### 5. Bypass de CSRF via header, dependente de uma variável de ambiente — **CONFIRMADO**
- **Evidência (`app/shared/middleware/csrf.py:31-34`):**
  ```python
  skip_csrf = (settings.app_env == "testing" and request.headers.get("X-Skip-CSRF") == "true")
  ```
- **Risco:** mesma classe do item #4 — se `APP_ENV` for `testing` em produção, **toda a proteção CSRF cai**
  com um header trivial. A condição está correta hoje; o problema é a fragilidade do gatilho único.
- **Correção:** manter a checagem de ambiente **e** condicionar à presença do `conftest`
  (ex.: flag setada em runtime pelos testes, não header vindo do cliente). Idealmente o bypass não deve
  existir no código de produção.

#### 6. CSRF: vazamento de detalhe de exceção e captura genérica — **CONFIRMADO**
- **Evidência (`app/shared/middleware/csrf.py:41-46`):** `except Exception as exc:` retorna
  `detail=f"Erro de Segurança (CSRF): {str(exc)}..."` — devolve a mensagem interna ao cliente.
  O import específico `CsrfProtectError` (L4) **existe e nunca é usado**.
- **Risco:** information disclosure; alinhado ao foco do plano-mãe (*"prevenção de vazamento de
  informações técnicas em respostas de erro"*).
- **Correção:** capturar `CsrfProtectError`, responder mensagem genérica e logar o detalhe no servidor.

#### 7. `/auth/login` e `/auth/logout` isentos de CSRF — **A VERIFICAR**
- **Evidência (`app/shared/middleware/csrf.py:38`).**
- **Risco:** `logout` sem CSRF permite forçar o logout de um usuário via requisição cross-site (baixo
  impacto, mas é DoS de sessão). `login` sem CSRF abre **login CSRF** (atacante força a vítima a autenticar
  numa conta controlada por ele).
- **Verificar:** se o fluxo de login do frontend consegue obter o token antes do POST (é o motivo usual
  da isenção). Se sim, remover ao menos a isenção de `logout`.

#### 8. `generate_csrf()` executado em toda requisição — **CONFIRMADO**
- **Evidência (`app/shared/middleware/csrf.py:50`):** o par de tokens é gerado **antes** de qualquer
  decisão sobre emissão (a decisão só ocorre na L72). Inclui GETs de assets estáticos.
- **Correção:** gerar sob demanda, dentro do `if should_issue_token`.

#### 9. Timing/enumeração de usuários no login — **A VERIFICAR**
- **Evidência (`app/modules/auth/service.py:30-34`):** `if not usuario: return None` retorna **antes** de
  qualquer hashing. Usuário inexistente responde rápido; usuário existente com senha errada paga o custo
  do bcrypt (~100ms+).
- **Risco:** oráculo de enumeração de usernames. O plano-mãe cita explicitamente *"mitigação de ataques
  de timing"*.
- **Atenuante a confirmar:** há `@limiter.limit("5/minute")` no login (`router.py:33`), o que reduz
  bastante a exploração prática. **Medir a diferença real antes de classificar a severidade** —
  se o rate limit for por IP, ainda é explorável de forma distribuída.
- **Correção:** executar um `verificar_senha` contra um hash dummy fixo quando o usuário não existe.

#### 10. Expiração do refresh token duplicada em 3 lugares — **CONFIRMADO**
- **Evidência:** `security.py:78` (`timedelta(days=7)` no JWT), `router.py:69` (`expira_em` no banco, login),
  `router.py:219` (`expira_em` no banco, refresh), `router.py:244` (`max_age` do cookie).
- **Risco:** o JWT e o registro no banco podem divergir numa alteração — token válido no banco e
  expirado no JWT (ou o inverso).
- **Correção:** uma constante única em `settings` (ex.: `refresh_token_expire_days`), derivando os demais.

#### 11. `path` do cookie de refresh inconsistente — **A VERIFICAR**
- **Evidência:** login (`router.py:86-93`) e refresh (`router.py:239-247`) **ambos** usam
  `path="/auth/refresh"`. Confirmar que o **logout** apaga o cookie com o **mesmo** `path` — caso
  contrário o `delete_cookie` não o remove e a sessão sobrevive ao logout.
- **Ação:** localizar o endpoint de logout e verificar `delete_cookie(..., path="/auth/refresh")`.

### 🟢 Baixa

#### 12. Limpezas — **CONFIRMADO**
- **`print()` em código de aplicação:** `auth/service.py:249, 264, 269, 282, 300` — inclusive imprimindo o
  username do admin. Mesmo anti-padrão erradicado na Etapa 1 → `logging`.
- **8 `raise ValueError`** em `auth/service.py` (L82, 137, 163, 178, 193, 197, 208, 223) → `domain_exc`.
- **Imports dentro de função** em `service.py:26-28, 235-238, 297-299, 313-315` e
  `router.py:59-61, 75, 123-127, 175, 190-191` → topo do módulo.
- **`== True`** em `auth/service.py:122, 204` → `.is_(True)`.
- **Duplicação de pré-hash** SHA-256+base64 em `security.py:29-31` e `security.py:39-41` →
  extrair `_preparar_senha(senha)`.
- **TOCTOU** em `criar_usuario` (`service.py:79-82`) — UNIQUE em `username`; aplicar SAVEPOINT (padrão Etapa 1).
- **Magic numbers** de lockout (`service.py:58-59`: 5 tentativas / 15 min) → `settings`.
- **`CsrfSettings`** (`csrf.py:10-12`) resolve `get_settings()` em **tempo de definição de classe**
  (import), não em runtime — dificulta troca de configuração em testes.

---

## 🗺️ Plano de Ação em Fases

### Fase 0 — Baseline
1. `.venv\Scripts\pytest` → 261/261.
2. Mapear a cobertura de segurança atual: `tests/security/test_csrf.py` (9 testes) e
   `tests/security/test_refresh_token.py` (**1 teste**), `tests/unit/test_auth.py` (15).
   A lacuna do item #1 está justamente onde há 1 teste só.
3. Escrever **primeiro** o teste que falha do item #1 (revogação de família) — prova o bug antes da correção.

### Fase 1 — Vulnerabilidades de sessão (núcleo desta etapa)
- Item **#1** (commit da revogação de família) — maior severidade, corrigir primeiro.
- Item **#2** (validação do claim `type`).
- Item **#10** (constante única de expiração), **#11** (path do cookie no logout).
- ✅ *Checkpoint: `tests/security/` verde e ampliado.*

### Fase 2 — Contas e credenciais
- Item **#3** (senha do admin), **#4** (usuários de teste + unificação de `APP_ENV`).
- ⚠️ **Impacto operacional direto:** mudar o comportamento de `garantir_usuarios_essenciais` pode
  quebrar o fluxo de desenvolvimento local e as fixtures. Verificar `conftest.py` antes.
- ✅ *Checkpoint.*

### Fase 3 — Middleware CSRF
- Itens **#5**, **#6**, **#7**, **#8**.
- ⚠️ `tests/security/test_csrf.py` depende do header de bypass — alterar #5 **exige** ajustar o `conftest`.
- ✅ *Checkpoint.*

### Fase 4 — Timing e limpezas
- Itens **#9** (medir antes de corrigir) e **#12**.

### Fase 5 — Consolidação
- `relatorio_auth_seguranca.md` no formato do `prompt.md`.
- Atualizar `Planejamento_revisao.md`: matriz, seção da Etapa 4, **e corrigir o caminho**
  `app/shared/dependencies.py` → `app/bootstrap/dependencies.py`.
- Commit no padrão das Etapas 1-2.

---

## 🧪 Estratégia de Testes

| Arquivo | Cobre |
|---|---|
| `tests/security/test_refresh_token_rotacao.py` | #1 (revogação persistida — **verificar em sessão nova**), #2 (type confusion), #10, #11 |
| `tests/security/test_csrf_hardening.py` | #5, #6 (sem vazamento de `str(exc)`), #7, #8 |
| `tests/unit/test_auth_contas.py` | #3 (senha do admin preservada após boot), #4, #9, #12 |

**Ponto crítico de metodologia para o item #1:** o teste **precisa** confirmar a revogação em uma
**sessão de banco diferente** da que atendeu a requisição. Validar pelo objeto ORM da mesma sessão
passaria mesmo com o bug presente (o rollback é o que se quer detectar).

---

## ⚠️ Riscos Conhecidos desta Etapa

1. **Alterar `get_db`** (item #1) afeta **toda** a aplicação, não só auth — preferir commit explícito
   e localizado no bloco de reuso a mexer na dependency global.
2. **Itens #3 e #4 mudam o comportamento de startup** — risco de quebrar o ambiente local e o CI.
3. **Item #5 acopla-se ao `conftest.py`** — a suíte inteira passa pelo bypass de CSRF.
4. **Item #2 é preventivo**, não corrige exploração ativa. Documentar como tal no relatório — não inflar
   a severidade no texto final.
5. **Não alterar o esquema de hashing de senha** (`security.py:19-42`): mudar o `CryptContext` invalida
   todas as senhas existentes. Fora do escopo desta etapa.

---

## ✅ Definition of Done

- [ ] Achados 🔴 corrigidos ou adiados **com justificativa escrita** no relatório.
- [ ] Teste que prova o item #1 escrito **antes** da correção, falhando, e verde depois.
- [ ] `.venv\Scripts\pytest` = 100% verde, sem skips novos.
- [ ] `relatorio_auth_seguranca.md` gerado no formato do `prompt.md`.
- [ ] `Planejamento_revisao.md` atualizado + caminho de `dependencies.py` corrigido.
- [ ] Zero `print()` remanescente em `app/modules/auth/`.
- [ ] Nenhuma resposta de erro devolvendo `str(exc)` interno ao cliente.

---
*Plano de execução da Etapa 4 — FABLE 5 / SAA29. Achados levantados em 02/08/2026.*
