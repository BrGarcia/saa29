arquivo:
app/modules/auth/router.py, app/modules/auth/service.py, app/modules/auth/security.py,
app/bootstrap/dependencies.py, app/bootstrap/config/__init__.py, app/shared/middleware/csrf.py,
scripts/db/init_db.py

> ## ✅ DOCUMENTO FINALIZADO — 02/08/2026
> Todos os itens priorizados (Crítica 4/4, Média 6/6 — sendo #11 falso-positivo verificado, Baixa 1/1)
> foram corrigidos e verificados. Suíte completa final: **292 testes, 0 falhas** (baseline da etapa: 281).
> Plano de execução detalhado, com evidências completas de verificação e decisões de escopo, está em
> `docs/backlog/Fable5/Etapa4.md`.

---

## 📌 Status de Execução (02/08/2026)

**Todos os itens foram corrigidos ou verificados: Crítica 4/4, Média 6/6, Baixa 1/1.**

| Item | Prioridade | Status | Onde |
|---|---|---|---|
| #1 Revogação de família de tokens desfeita por rollback | 🔴 Crítica | ✅ CORRIGIDO | `auth/router.py:refresh_access_token` — `db.commit()` antes do `raise` |
| #2 Sem validação do claim `type` (type confusion) | 🔴 Crítica | ✅ CORRIGIDO | `get_current_user` valida `type == "access"` |
| #3 Senha do admin sobrescrita a cada execução do seed | 🔴 Crítica | ✅ CORRIGIDO | só na criação; redefinição exige `ADMIN_PASSWORD_RESET=1` |
| #4 Usuários de teste com um único gatilho frágil | 🔴 Crítica | ✅ CORRIGIDO | dois gatilhos (`app_env` + `enable_test_users`); duplicação em `init_db.py` removida |
| #5 Bypass de CSRF com header previsível | 🟡 Média | ✅ CORRIGIDO | segredo aleatório por processo |
| #6 CSRF vaza detalhe de exceção | 🟡 Média | ✅ CORRIGIDO | `CsrfProtectError` específico, mensagem genérica |
| #7 `/auth/login`/`/auth/logout` isentos de CSRF sem necessidade | 🟡 Média | ✅ CORRIGIDO | isenção removida (frontend já envia o header) |
| #8 `generate_csrf()` em toda requisição, incl. estáticos | 🟡 Média | ✅ CORRIGIDO (parcial — ver nota) | pulado para `/static/*` |
| #9 Timing/enumeração de usuários no login | 🟡 Média | ✅ CONFIRMADO E CORRIGIDO | hash dummy equaliza o tempo |
| #10 Expiração do refresh token duplicada em 3 lugares | 🟡 Média | ✅ CORRIGIDO | `settings.refresh_token_expire_days` |
| #11 Path do cookie de refresh inconsistente | 🟡 Média | ✅ VERIFICADO: FALSO-POSITIVO | logout já usa o mesmo path |
| #12 Limpezas (print, ValueError, imports, TOCTOU, etc.) | 🟢 Baixa | ✅ CORRIGIDO (quase integral) | ver detalhamento |

**Arquivos alterados (consolidado — todas as prioridades):**
- `app/modules/auth/router.py`, `service.py`, `security.py`
- `app/bootstrap/dependencies.py`, `app/bootstrap/config/__init__.py` (+2 campos: `refresh_token_expire_days`, `enable_test_users`)
- `app/shared/middleware/csrf.py`
- `scripts/db/init_db.py` (implementação duplicada de usuários de teste removida)
- `tests/security/test_refresh_token_rotacao.py` (2 testes — novo)
- `tests/unit/test_auth_contas.py` (9 testes — novo)
- `tests/conftest.py` (ajustado ao novo segredo de bypass de CSRF)

**Suíte completa final:** `.venv\Scripts\pytest` → **292 testes, 0 falhas** (baseline: 281).

**Pendências conscientes que saem do escopo desta etapa** (documentadas, não bloqueiam o fechamento):
- Magic numbers de lockout viraram constantes de módulo, não campos de `Settings` (decisão: são regra de
  negócio de domínio, não configuração de ambiente).
- `decodificar_token(token, tipo_esperado)` não foi implementado como alternativa mais robusta ao item #2
  — mudaria assinatura usada em múltiplos pontos; a checagem inline no `get_current_user` já fecha o gap.
- `revogar_familia_de_tokens` não foi extraída como função nomeada em `auth/service.py` — o commit
  explícito localizado no bloco do router já resolve o item #1 com risco mínimo.

---

Relatorio:
Revisão de Código: app/modules/auth/router.py, app/modules/auth/service.py, app/modules/auth/security.py,
app/bootstrap/dependencies.py, app/shared/middleware/csrf.py

🔴 Vulnerabilidades e Bugs Críticos

### [1] Revogação de família de refresh tokens é desfeita por rollback
- **Severidade:** 🔴 Crítica
- **Tipo:** Vulnerabilidade
- **Evidência (`app/modules/auth/router.py`, `refresh_access_token`, antes da correção):** ao detectar
  reuso de um refresh token já revogado, o código executava um `UPDATE` revogando toda a família de
  tokens do usuário e, em seguida, levantava `HTTPException(401, ...)`. Essa exceção propaga pela
  dependency `get_db` (`app/bootstrap/dependencies.py`), cujo bloco `except Exception: await
  session.rollback()` **desfazia o UPDATE**. A resposta ao cliente dizia "todos os tokens foram
  revogados por segurança" — mas nenhum token era, de fato, revogado.
- **Contraste que revelou o bug:** o endpoint de login, ao lado, já fazia `await db.commit()` explícito
  antes de um `raise` equivalente (para persistir o contador de tentativas falhas) — só o bloco de reuso
  não seguia o mesmo padrão.
- **Risco & Impacto:** o mecanismo de defesa contra reuso de refresh token — citado explicitamente no
  escopo desta etapa — era puramente decorativo. Um atacante que roubasse um refresh token continuaria
  podendo usá-lo indefinidamente após a "detecção".
- **Correção Recomendada:** `await db.commit()` antes do `raise`. **Aplicada.** Teste
  `test_reuso_de_refresh_token_revogado_persiste_revogacao_da_familia` — cria um segundo token "irmão"
  ativo, provoca a detecção de reuso e, **após um `db.rollback()` manual** simulando o que a sessão faria
  de qualquer forma, confirma que o token irmão continua revogado. Verificado que o teste falha sem a
  correção (revertida temporariamente, vermelho; restaurada, verde).

### [2] Ausência de validação do claim `type` em get_current_user
- **Severidade:** 🔴 Crítica (latente/preventiva)
- **Tipo:** Vulnerabilidade
- **Evidência:** `get_current_user` validava assinatura, `sub`, `jti` e blacklist — nunca checava
  `payload.get("type")`. Access e refresh tokens são assinados com a mesma chave/algoritmo.
- **Por que era latente:** o `sub` difere por acaso entre os dois tipos de token (access usa username,
  refresh usa UUID do usuário), então um refresh enviado como access falhava na busca por username — mas
  essa proteção era um efeito colateral, não uma verificação deliberada. `/auth/refresh`, ao lado, já
  fazia a checagem correta no sentido oposto (`type != "refresh"`).
- **Risco & Impacto:** uma refatoração aparentemente inofensiva (padronizar o `sub`) abriria um bypass —
  um refresh token de 7 dias valendo como access token de 15 minutos, ignorando a blacklist de access.
- **Correção Recomendada:** `if payload.get("type") != "access": raise credentials_exception`.
  **Aplicada** em `app/bootstrap/dependencies.py`. Teste: `test_refresh_token_nao_e_aceito_como_access_token`.

### [3] Senha do administrador sobrescrita a cada execução do seed
- **Severidade:** 🔴 Crítica
- **Tipo:** Bug / Vulnerabilidade operacional
- **Correção de premissa em relação ao achado original:** a hipótese inicial era "a cada boot da
  aplicação"; verificado que `garantir_usuarios_essenciais` **não** roda no lifespan — é invocada
  manualmente por `scripts/db/init_db.py`/`scripts/seed/seed_auth.py` (scripts de deploy/setup). Isso
  reduz a frequência do gatilho, mas não elimina o risco: toda vez que o script de setup é reexecutado
  (deploy, reprovisionamento), a senha do admin volta ao valor do `.env`.
- **Evidência:** `if not verificar_senha(admin_pass, admin.senha_hash): admin.senha_hash =
  hash_senha(admin_pass)` rodava incondicionalmente.
- **Risco & Impacto:** rotação de senha do admin pela UI era anulada no próximo boot/seed; qualquer
  pessoa com acesso ao `.env`/histórico de deploy tinha acesso permanente.
- **Correção Recomendada:** aplicar só na criação; redefinição exige flag explícito. **Aplicada:**
  `ADMIN_PASSWORD_RESET=1` (checado via `os.getenv`, deliberadamente não persistido em `Settings`), com
  log de auditoria `WARNING`.

### [4] Usuários de teste com senha fixa protegidos por um único gatilho frágil
- **Severidade:** 🔴 Crítica
- **Tipo:** Vulnerabilidade
- **Evidência:** criação de 3 contas privilegiadas (`encarregado`/`inspetor`/`mantenedor`, senha
  `"123456"`) dependia só de `settings.app_env == "development"`. `autenticar_usuario` lia
  `os.getenv("APP_ENV")` direto, uma segunda fonte de verdade divergente de `settings.app_env`.
- **Achado adicional durante a correção:** `ENABLE_TEST_USERS` já estava documentado em `.env.example`
  mas **nunca fora adicionado à classe `Settings`**; `scripts/db/init_db.py` reimplementava sua própria
  checagem via `os.getenv` manual, criando um **segundo conjunto de usuários de teste**
  (`encarregado`/`mantenedor`, senha `"12345678"`, sem `inspetor`) — diferente e paralelo ao criado por
  `garantir_usuarios_essenciais`.
- **Correção Recomendada:** unificar fonte do ambiente; exigir segundo gatilho explícito. **Aplicada:**
  `autenticar_usuario` usa `settings.app_env`; criação de usuários de teste exige **dois gatilhos**
  (`app_env=="development"` E `settings.enable_test_users`, campo novo em `Settings`); implementação
  duplicada em `init_db.py` removida — única fonte de verdade agora.

🟡 Problemas de Média Prioridade

### [5] Bypass de CSRF via header previsível dependente de variável de ambiente
- **Severidade:** 🟡 Média
- **Tipo:** Vulnerabilidade
- **Evidência:** `skip_csrf = settings.app_env == "testing" and header == "true"` — se `APP_ENV=testing`
  vazasse para produção, qualquer cliente derrubava a proteção CSRF com um header trivial e previsível.
- **Correção Recomendada:** condicionar a algo não previsível por um cliente externo. **Aplicada:**
  `TESTING_CSRF_BYPASS_SECRET = secrets.token_urlsafe(32)`, gerado uma vez por processo; `conftest.py`
  importa a mesma constante para montar o header de teste.

### [6] CSRF: vazamento de detalhe de exceção e captura genérica
- **Severidade:** 🟡 Média
- **Tipo:** Information disclosure
- **Evidência:** `except Exception as exc: ... detail=f"...{str(exc)}..."` devolvia mensagem interna ao
  cliente; import de `CsrfProtectError` existia e nunca era usado.
- **Correção Recomendada:** capturar o tipo específico, resposta genérica, log do detalhe no servidor.
  **Aplicada.**

### [7] `/auth/login` e `/auth/logout` isentos de CSRF sem necessidade
- **Severidade:** 🟡 Média
- **Tipo:** Vulnerabilidade
- **Verificação feita:** `base.html` renderiza a meta tag `csrf-token` a partir de
  `request.state.csrf_token` (disponível antes de qualquer POST); `login.js` já lê e envia o header;
  `app.js:clearAuth()` já faz o mesmo para logout. A isenção não protegia nenhum fluxo real.
- **Correção Recomendada:** remover a isenção. **Aplicada** — ambas as rotas passam pela validação CSRF
  normal agora.

### [8] `generate_csrf()` executado em toda requisição, incluindo assets estáticos
- **Severidade:** 🟡 Média
- **Tipo:** Performance
- **Nota de design:** a geração não pode, em geral, ser adiada para depois de `call_next` — rotas HTML
  (sempre GET) leem `request.state.csrf_token` durante o processamento para montar a meta tag; adiar
  quebraria essas rotas.
- **Correção Recomendada (aplicada, mais restrita que o sugerido originalmente):** pular a geração quando
  `request.url.path` começa com `/static/` — exatamente o caso citado como desperdício na evidência
  original.

### [9] Timing/enumeração de usuários no login
- **Severidade:** 🟡 Média (confirmada com medição, não só suspeita)
- **Tipo:** Vulnerabilidade
- **Medição feita antes de classificar a severidade:** `verificar_senha` real (bcrypt) leva **~227ms**; o
  caminho de early-return (usuário inexistente) leva **<0.001ms** — diferença de ~227x, trivialmente
  distinguível numa única requisição.
- **Correção Recomendada:** hash dummy verificado quando o usuário não existe/está inativo. **Aplicada.**
  Teste funcional (não baseado em timing, que seria flaky em CI):
  `test_autenticar_usuario_inexistente_paga_custo_de_bcrypt`.

### [10] Expiração do refresh token duplicada em 3 lugares
- **Severidade:** 🟡 Média
- **Tipo:** Dívida técnica
- **Evidência:** `timedelta(days=7)` no JWT, `expira_em` no banco (2 lugares) e `max_age` do cookie (2
  lugares) — 5 ocorrências hardcoded do valor `7`.
- **Correção Recomendada:** constante única em `Settings`. **Aplicada:**
  `refresh_token_expire_days`, default `7` (preserva o valor atual).

### [11] Path do cookie de refresh inconsistente
- **Severidade:** 🟡 Média (verificado como falso-positivo)
- **Verificação feita:** `logout` já usa `path="/auth/refresh"`, igual ao `set_cookie` do login/refresh.
- **Conclusão:** não é bug.

🟢 Baixa Prioridade

### [12] Limpezas diversas
- **Severidade:** 🟢 Baixa
- **Correções aplicadas:** `print()` → `logging`; 8 `raise ValueError` → `domain_exc` (6 blocos
  `try/except` removidos do router); imports locais movidos para o topo (exceção deliberada:
  `Indisponibilidade`/`TipoIndisponibilidade`, para não acoplar `auth/service.py` ao módulo `efetivo` só
  para um branch de seed raro); `== True` → `.is_(True)`; pré-hash SHA-256+base64 duplicado extraído em
  `_preparar_senha`; TOCTOU em `criar_usuario` protegido por SAVEPOINT; `CsrfSettings` corrigido para
  resolver `get_settings()` em runtime via `default_factory`.
- **Não aplicado (decisão consciente):** magic numbers de lockout viraram constantes de módulo nomeadas,
  não campos de `Settings` — são regra de negócio de domínio, não configuração de ambiente.

---

## 📋 Plano de Ação (já executado nesta etapa)

| Fase | Prioridade | Itens |
|---|---|---|
| 1-2 | 🔴 Crítica | #1-#4 |
| 3-4 | 🟡 Média | #5-#11 |
| 4 | 🟢 Baixa | #12 |
| 5 | Consolidação | Este relatório + `Planejamento_revisao.md` |

Detalhamento completo de cada fase, incluindo evidências de verificação, testes escritos e decisões de
escopo tomadas durante a execução, está em `docs/backlog/Fable5/Etapa4.md`.
