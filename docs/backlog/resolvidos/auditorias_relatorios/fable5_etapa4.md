# 🔐 Plano de Execução — ETAPA 4: Autenticação, Sessões & Segurança Central

> **Escopo:** `app/modules/auth/` + `app/shared/middleware/` + `app/bootstrap/dependencies.py`
> **Relatório a gerar:** `docs/backlog/Fable5/relatorio_auth_seguranca.md`
> **Referência de processo:** `docs/backlog/Fable5/Planejamento_revisao.md`
> **Template de auditoria:** `docs/backlog/Fable5/prompt.md`
>
> **Status de execução:** 🔴 Críticos ✅ · 🟡 Média ✅ · 🟢 Baixa ✅ — Etapa 4 concluída em 02/08/2026

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

### 🔴 Críticos — ✅ CONCLUÍDO (02/08/2026)

---

#### 1. Revogação de família de refresh tokens é desfeita por rollback — **CONFIRMADO** → ✅ CORRIGIDO
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
- **Correção aplicada:** `await db.commit()` antes do `raise`, espelhando o login (não foi extraído para
  `revogar_familia_de_tokens` em `auth/service.py` — o commit explícito localizado no bloco já resolve o
  problema com uma mudança mínima e de baixo risco, evitando tocar em código compartilhado por outros
  fluxos).
- **Teste:** `test_reuso_de_refresh_token_revogado_persiste_revogacao_da_familia` — cria um segundo token
  "irmão" ativo, provoca a detecção de reuso e, **após um `db.rollback()` manual simulando o que
  aaconteceria de qualquer forma no ciclo de vida da sessão**, confirma que o token irmão continua
  revogado. **Verificado que o teste falha sem a correção** (revertida temporariamente, teste vermelho,
  restaurada) — prova de regressão real, não apenas cobertura decorativa.

---

#### 2. Ausência de validação do claim `type` em `get_current_user` — **CONFIRMADO** (latente) → ✅ CORRIGIDO
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
- **Correção aplicada:** `if payload.get("type") != "access": raise credentials_exception` em
  `get_current_user` (`app/bootstrap/dependencies.py`). A alternativa mais robusta
  (`decodificar_token(token, tipo_esperado)`) não foi aplicada — mudaria a assinatura de uma função usada
  em múltiplos pontos, risco desproporcional para uma correção preventiva. Teste:
  `test_refresh_token_nao_e_aceito_como_access_token`.

---

#### 3. Senha do administrador é sobrescrita a cada execução do seed — **CONFIRMADO** → ✅ CORRIGIDO
- **Tipo:** Bug / Vulnerabilidade operacional
- **⚠️ Correção de premissa:** o achado original dizia "a cada boot" presumindo que
  `garantir_usuarios_essenciais` fosse chamada no lifespan da aplicação — **não é**. Ela só é invocada
  manualmente por `scripts/db/init_db.py` / `scripts/seed/seed_auth.py` (scripts de deploy/setup rodados
  por um operador). Isso reduz a frequência do gatilho, mas não elimina o risco: **toda vez que o script
  de setup for reexecutado** (comum em deploys, reprovisionamento, ou correção de outro dado via o mesmo
  script), a senha do admin volta ao valor do `.env`.
- **Evidência (`app/modules/auth/service.py`, em `garantir_usuarios_essenciais`):**
  ```python
  if not verificar_senha(admin_pass, admin.senha_hash):
      admin.senha_hash = hash_senha(admin_pass)
      print(f"AuthService: Senha do admin atualizada para coincidir com as configurações.")
  ```
- **Risco & Impacto:** o admin troca a senha pela UI; no próximo restart ela **volta silenciosamente**
  para o valor de `DEFAULT_ADMIN_PASSWORD` do `.env`. Qualquer pessoa com acesso ao `.env` (ou ao histórico
  de deploy) tem acesso permanente e **a rotação de senha do admin é impossível na prática**.
  O comentário justifica com *"útil após restore do R2"* — mas o efeito vale em todo boot, não só em restore.
- **Correção aplicada:** senha só é definida na **criação** do admin. Redefinição em execuções
  subsequentes exige o flag explícito e temporário `ADMIN_PASSWORD_RESET=1` (checado via `os.getenv`,
  não um campo persistente de `Settings` — é deliberadamente temporário/manual), com log de auditoria em
  nível `WARNING`. Testes:
  `test_garantir_usuarios_essenciais_nao_sobrescreve_senha_do_admin_ja_trocada`,
  `test_garantir_usuarios_essenciais_com_admin_password_reset_redefine_senha`.

---

#### 4. Usuários de teste com senha fixa `123456` criados por variável de ambiente — **CONFIRMADO** → ✅ CORRIGIDO
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
- **Correção aplicada:** `autenticar_usuario` passou a usar `settings.app_env` (fonte única, já validada
  pelo pydantic-settings) em vez de `os.getenv("APP_ENV", ...)` direto. Criação dos usuários de teste
  agora exige **dois gatilhos**: `app_env=="development"` **e** `settings.enable_test_users`.
  **Achado adicional durante a correção:** `ENABLE_TEST_USERS` já estava documentado em `.env.example`
  como se fosse um flag existente — mas **nunca tinha sido adicionado à classe `Settings`**; e
  `scripts/db/init_db.py` reimplementava a própria checagem de `ENABLE_TEST_USERS` via `os.getenv` manual
  (com `_env_flag()`), criando um **segundo conjunto de usuários de teste** (`encarregado`/`mantenedor`,
  senha `"12345678"`, sem `inspetor`), diferente e paralelo ao criado por `garantir_usuarios_essenciais`
  (senha `"123456"`, inclui `inspetor`). Corrigido: campo `enable_test_users` adicionado a `Settings`
  (`app/bootstrap/config/__init__.py`); a implementação duplicada em `init_db.py` foi removida — agora há
  uma única fonte de verdade. Senha literal `"123456"` **mantida** (não gerada aleatoriamente): são contas
  de desenvolvimento local, atrás de dois gatilhos explícitos; gerar senha aleatória exigiria expor o
  valor gerado ao operador de alguma forma, complexidade desproporcional para este escopo. Lockout em dev
  **mantido** desligado — é usado ativamente pelos testes e pelo fluxo de desenvolvimento local; desligá-lo
  quebraria ambos sem necessidade seguindo (a proteção real é o rate limit de 5/min no login).
- **Testes:** `test_usuarios_de_teste_nao_sao_criados_sem_enable_test_users`,
  `test_usuarios_de_teste_criados_com_os_dois_gatilhos`,
  `test_autenticar_usuario_usa_settings_app_env_nao_os_environ_direto`.

---

### 🟡 Média — ✅ CONCLUÍDO (02/08/2026)

#### 5. Bypass de CSRF via header, dependente de uma variável de ambiente — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/shared/middleware/csrf.py:31-34`):**
  ```python
  skip_csrf = (settings.app_env == "testing" and request.headers.get("X-Skip-CSRF") == "true")
  ```
- **Risco:** mesma classe do item #4 — se `APP_ENV` for `testing` em produção, **toda a proteção CSRF cai**
  com um header trivial. A condição está correta hoje; o problema é a fragilidade do gatilho único.
- **Correção aplicada:** o valor fixo `"true"` foi trocado por `TESTING_CSRF_BYPASS_SECRET`, um segredo
  gerado com `secrets.token_urlsafe(32)` **uma vez por processo** (`csrf.py`, tempo de import). Mesmo que
  `APP_ENV=testing` vaze para produção, um atacante externo não tem como adivinhar o segredo — ele nunca
  é persistido, só existe em memória do processo em execução. `tests/conftest.py` importa a mesma
  constante diretamente do módulo para montar o header do `client` fixture, então a suíte de testes
  continua funcionando sem mudança de comportamento observável.

#### 6. CSRF: vazamento de detalhe de exceção e captura genérica — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência (`app/shared/middleware/csrf.py:41-46`):** `except Exception as exc:` retorna
  `detail=f"Erro de Segurança (CSRF): {str(exc)}..."` — devolve a mensagem interna ao cliente.
  O import específico `CsrfProtectError` (L4) **existe e nunca é usado**.
- **Correção aplicada:** troca para `except CsrfProtectError`, mensagem genérica ao cliente
  (`"Erro de segurança (CSRF). Recarregue a página."`), detalhe logado via `logger.warning` no servidor.

#### 7. `/auth/login` e `/auth/logout` isentos de CSRF — **A VERIFICAR** → ✅ CORRIGIDO (isenção removida)
- **Evidência (`app/shared/middleware/csrf.py:38`).**
- **Verificação feita:** `app/web/templates/base.html:11-12` renderiza
  `<meta name="csrf-token" content="{{ request.state.csrf_token }}">` a partir do valor que o próprio
  middleware injeta em `request.state` **antes** de `call_next` — logo a página de login já chega ao
  navegador com o token disponível. `login.js:34-41` já lê essa meta tag e envia
  `X-CSRF-Token` no POST de login; `app.js:clearAuth()` (L124-135) já faz o mesmo para `/auth/logout`.
  A isenção não protegia nenhum fluxo real que dependesse dela.
- **Correção aplicada:** isenção removida — `/auth/login` e `/auth/logout` agora passam pela validação
  CSRF normal, como qualquer outra rota de mutação. Testes de `tests/security/test_csrf.py` e
  `tests/security/test_refresh_token*.py` continuam verdes (usam o bypass de teste, item #5).

#### 8. `generate_csrf()` executado em toda requisição — **CONFIRMADO** → ✅ CORRIGIDO (parcial, ver nota)
- **Evidência (`app/shared/middleware/csrf.py:50`):** o par de tokens é gerado **antes** de qualquer
  decisão sobre emissão (a decisão só ocorre depois de `call_next`). Inclui GETs de assets estáticos.
- **Nota de design:** a geração **não pode**, de forma geral, ser adiada para depois de `call_next` —
  rotas que renderizam HTML (sempre GET) leem `request.state.csrf_token` **durante** o processamento da
  requisição (Jinja) para montar a meta tag; se o token só existisse depois de `call_next`, essas rotas
  quebrariam. A decisão de emitir cookie/header (`should_issue_token`) também só é conhecida depois de
  `call_next` (depende do `Content-Type` da resposta), então adiar geração para "dentro do
  `if should_issue_token`" como o plano sugeria ingenuamente teria esse conflito.
- **Correção aplicada (mais restrita e ainda segura):** pular a geração quando `request.url.path` começa
  com `/static/` — arquivos estáticos nunca renderizam um template que precise do token, e é exatamente o
  caso citado como desperdício na evidência original ("GETs de assets estáticos"). Rotas de página e de
  API continuam gerando o par eagerly, sem mudança de comportamento.

#### 9. Timing/enumeração de usuários no login — **A VERIFICAR** → ✅ CONFIRMADO E CORRIGIDO
- **Evidência (`app/modules/auth/service.py`):** `if not usuario: return None` retornava **antes** de
  qualquer hashing.
- **Medição feita (antes de classificar a severidade, como o plano pedia):** `verificar_senha` real
  (bcrypt) leva **~227ms**; o caminho de early-return leva **<0.001ms**. Diferença de ~227x, trivialmente
  distinguível numa única requisição — o rate limit de 5/min no login (`router.py:33`) reduz o volume de
  tentativas, mas não esconde essa diferença de magnitude.
- **Correção aplicada:** hash dummy fixo (`_DUMMY_HASH`, gerado uma vez no import do módulo) verificado
  via `verificar_senha` sempre que o usuário não existe ou está inativo, antes de retornar `None` — paga
  o mesmo custo de bcrypt do caminho "usuário existe, senha errada". Teste funcional (não baseado em
  timing, que seria flaky em CI): `test_autenticar_usuario_inexistente_paga_custo_de_bcrypt` espiona
  `verificar_senha` e confirma que é chamada mesmo para usuário inexistente.

#### 10. Expiração do refresh token duplicada em 3 lugares — **CONFIRMADO** → ✅ CORRIGIDO
- **Evidência:** `security.py:78` (`timedelta(days=7)` no JWT), `router.py:69` (`expira_em` no banco, login),
  `router.py:219` (`expira_em` no banco, refresh), `router.py:244` (`max_age` do cookie).
- **Risco:** o JWT e o registro no banco podem divergir numa alteração — token válido no banco e
  expirado no JWT (ou o inverso).
- **Correção aplicada:** campo `refresh_token_expire_days` adicionado a `Settings`
  (`app/bootstrap/config/__init__.py`, default `7`, preservando o valor atual); `security.py` e as duas
  ocorrências em `router.py` (login e refresh) passaram a derivar de `settings.refresh_token_expire_days`
  em vez de `timedelta(days=7)`/`7*24*60*60` hardcoded em cada lugar.

#### 11. `path` do cookie de refresh inconsistente — **VERIFICADO: FALSO-POSITIVO**
- **Evidência:** login (`router.py:86-93`) e refresh (`router.py:239-247`) **ambos** usam
  `path="/auth/refresh"`.
- **Verificação feita:** `logout` (`router.py:284`) já faz
  `response.delete_cookie(key="saa29_refresh_token", path="/auth/refresh")` — mesmo `path` usado no
  `set_cookie`. Navegadores só removem um cookie via `delete_cookie` se `path` (e `domain`) coincidirem
  exatamente com os usados na criação; aqui coincidem.
- **Conclusão:** não é bug. Nenhuma correção aplicada.

### 🟢 Baixa — ✅ CONCLUÍDO (02/08/2026)

#### 12. Limpezas — **CONFIRMADO** → ✅ CORRIGIDO (quase integral, ver nota sobre magic numbers)
- **`print()` em código de aplicação:** já convertidos para `logger.info`/`logger.warning` como parte da
  correção dos itens #3/#4 (mesmo bloco de código). ✅
- **8 `raise ValueError`** em `auth/service.py` → migrados para `domain_exc` (classificação automática por
  conteúdo da mensagem, mesmo script usado na Etapa 3: "não encontrad" → `EntidadeNaoEncontradaError`,
  demais → `ConflitoNegocioError`). 6 blocos `try/except ValueError` removidos do router (as exceções já
  propagam com o status correto). Testes:
  `test_criar_usuario_username_duplicado_retorna_409_via_router`,
  `test_atualizar_usuario_inexistente_retorna_404_via_router`. ✅
- **Imports dentro de função:** todos os imports locais de `service.py` e `router.py` movidos para o topo
  (exceção deliberada: `Indisponibilidade`/`TipoIndisponibilidade` em `garantir_usuarios_essenciais`
  permanecem locais — evita acoplar `auth/service.py`, importado sempre, ao módulo `efetivo` só para um
  branch de seed de desenvolvimento raramente executado). ✅
- **`== True`** em `auth/service.py` (2 ocorrências) → `.is_(True)`. ✅
- **Duplicação de pré-hash** SHA-256+base64 → extraído `_preparar_senha(senha)` em `security.py`,
  reaproveitado por `hash_senha` e `verificar_senha`. ✅
- **TOCTOU** em `criar_usuario` — SAVEPOINT + `IntegrityError` → `ConflitoNegocioError` (padrão das
  Etapas 1-3). Teste:
  `test_criar_usuario_savepoint_absorve_integrity_error_sem_derrubar_sessao`. ✅
- **Magic numbers de lockout:** extraídos para constantes de módulo `_LOCKOUT_MAX_TENTATIVAS = 5` e
  `_LOCKOUT_DURACAO_MINUTOS = 15` em `auth/service.py` — **não movidos para `Settings`** como o achado
  sugeria: são regras de negócio de domínio (auth), não configuração de ambiente/infraestrutura como o
  resto de `Settings`; nomear como constantes já resolve o problema de "número mágico sem nome" sem
  espalhar regra de negócio pela camada de configuração. Decisão consciente, documentada aqui em vez de
  aplicada literalmente.
- **`CsrfSettings`** resolvia `get_settings()` em **tempo de definição de classe** (import), não em
  runtime — dificultava troca de configuração em testes (ex.: monkeypatch em `settings.app_env` não tinha
  efeito). Corrigido com `Field(default_factory=lambda: get_settings()....)` para os dois campos
  derivados de `settings`, resolvidos a cada instanciação de `CsrfSettings` (uma por requisição). ✅

---

## 🗺️ Plano de Ação em Fases

### Fase 0 — Baseline
1. `.venv\Scripts\pytest` → 261/261.
2. Mapear a cobertura de segurança atual: `tests/security/test_csrf.py` (9 testes) e
   `tests/security/test_refresh_token.py` (**1 teste**), `tests/unit/test_auth.py` (15).
   A lacuna do item #1 está justamente onde há 1 teste só.
3. Escrever **primeiro** o teste que falha do item #1 (revogação de família) — prova o bug antes da correção.

### Fase 1 — Vulnerabilidades de sessão (núcleo desta etapa) — ✅ CONCLUÍDA
- Item **#1** (commit da revogação de família) — corrigido e comprovado por teste que falha sem a
  correção (revertida temporariamente, vermelho, restaurada). ✅
- Item **#2** (validação do claim `type`). ✅
- Item **#10** (constante única de expiração). ✅
- Item **#11** verificado como **falso-positivo** (path do cookie já consistente entre set/delete). ✅
- ✅ *Checkpoint: 288/288 (baseline 281 + 7 novos).*

### Fase 2 — Contas e credenciais — ✅ CONCLUÍDA
- Item **#3** (senha do admin só na criação, redefinição via `ADMIN_PASSWORD_RESET=1`). ✅
- Item **#4** (dois gatilhos para usuários de teste + unificação de `APP_ENV`). Achado adicional: campo
  `enable_test_users` documentado em `.env.example` mas nunca adicionado a `Settings`, e
  `scripts/db/init_db.py` tinha uma segunda implementação divergente (usuários/senhas diferentes) —
  ambos corrigidos/removidos. ✅
- ✅ *Checkpoint (dentro do total de 288 acima — Fases 1 e 2 rodaram na mesma leva de testes).*

### Fase 3 — Middleware CSRF — ✅ CONCLUÍDA
- Item **#5** (segredo aleatório por processo em vez de header fixo `"true"`; `conftest.py` ajustado). ✅
- Item **#6** (`CsrfProtectError` específico, mensagem genérica, log do detalhe). ✅
- Item **#7** (isenção de `/auth/login`/`/auth/logout` removida — verificado que o frontend já envia o
  header em ambos os fluxos). ✅
- Item **#8** (geração de token pulada para `/static/*`; geração eager mantida para páginas/API por
  necessidade de design — ver nota completa no achado). ✅
- ✅ *Checkpoint: `tests/security/` verde (27 testes).*

### Fase 4 — Timing e limpezas — ✅ CONCLUÍDA
- Item **#9**: medido antes de corrigir (227ms vs <0.001ms) — confirmado como achado real, corrigido com
  hash dummy. ✅
- Item **#12** (limpezas 🟢) — ✅ concluído (ver detalhamento no achado #12 acima).

### Fase 5 — Consolidação — ✅ CONCLUÍDA
- `relatorio_auth_seguranca.md` gerado no formato do `prompt.md`.
- `Planejamento_revisao.md` atualizado: matriz + seção da Etapa 4 + caminho de `dependencies.py`
  corrigido (`app/shared/dependencies.py` → `app/bootstrap/dependencies.py`).
- Commit no padrão das Etapas 1-3.

---

## 🧪 Estratégia de Testes

| Arquivo | Cobre |
|---|---|
| `tests/security/test_refresh_token_rotacao.py` (2 testes, novo) | #1 (revogação persistida — verificado em cenário com `db.rollback()` manual simulando o que a sessão faria de qualquer forma), #2 (type confusion) |
| `tests/unit/test_auth_contas.py` (9 testes, novo) | #3, #4, #9 (funcional, sem depender de timing real), #12 (ValueError→domain_exc, TOCTOU) |
| `tests/security/`, `tests/unit/test_auth.py` (existentes, sem novo arquivo) | #5-#8, #10 exercitados pelos testes já existentes, que continuam verdes após as mudanças |

Os itens #10 e #11 (constante de expiração / path do cookie) não geraram teste dedicado — #10 é uma
mudança de implementação sem comportamento observável diferente (mesmos 7 dias, agora numa única fonte);
#11 foi verificado como falso-positivo.

**Ponto crítico de metodologia para o item #1:** o teste precisa confirmar a revogação **depois de um
rollback manual** que simula o que a sessão de teste faria de qualquer forma — validar pelo objeto ORM
sem forçar esse rollback passaria mesmo com o bug presente. **Verificado experimentalmente**: revertendo
a correção temporariamente, o teste fica vermelho (`KeyError` — token irmão não encontrado como revogado);
restaurada a correção, verde.

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

- [x] Achados 🔴 corrigidos ou adiados **com justificativa escrita** no relatório.
- [x] Teste que prova o item #1 escrito e verificado (revertido/vermelho, restaurado/verde).
- [x] `.venv\Scripts\pytest` = 100% verde, sem skips novos (292/292).
- [x] `relatorio_auth_seguranca.md` gerado no formato do `prompt.md`.
- [x] `Planejamento_revisao.md` atualizado + caminho de `dependencies.py` corrigido.
- [x] Zero `print()` remanescente em `app/modules/auth/`.
- [x] Nenhuma resposta de erro devolvendo `str(exc)` interno ao cliente (CSRF corrigido; demais endpoints
      já usavam exceções de domínio com mensagens estáticas).

---
*Plano de execução da Etapa 4 — FABLE 5 / SAA29. Achados levantados em 02/08/2026.*
