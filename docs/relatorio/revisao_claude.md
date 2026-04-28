# Revisão Externa — SAA29

**Auditor:** Claude Opus 4.6  
**Data:** 2026-04-27  
**Escopo:** Segurança, Bugs, Performance, Arquitetura, Integridade de Dados  
**Modo:** Read-only (nenhuma alteração de código realizada)

---

## Resumo Executivo

| Severidade | Qtd |
|:---|:---:|
| 🔴 Critical | 2 |
| 🟠 High | 6 |
| 🟡 Medium | 8 |
| 🔵 Low | 6 |
| **Total** | **22** |

---

## Issues

### 🔴 CRITICAL

---

#### C-01 · CSRF Bypass Header Acessível em Produção (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔴 Critical |
| **Tipo** | Security |
| **Localização** | `app/shared/middleware/csrf.py` L28 |

**Descrição:**  
O middleware CSRF aceita o header `X-Skip-CSRF: true` para desabilitar toda a proteção CSRF. Esse bypass existe para facilitar testes, mas **não está restrito ao ambiente de desenvolvimento**. Um atacante que descobrir esse header pode executar ataques CSRF completos contra qualquer endpoint mutante do sistema.

```python
skip_csrf = request.headers.get("X-Skip-CSRF") == "true"
```

**Fix sugerido:**  
Condicionar o bypass ao `APP_ENV == "development"` e adicionar um log de warning:
```python
settings = get_settings()
skip_csrf = (
    settings.app_env != "production"
    and request.headers.get("X-Skip-CSRF") == "true"
)
```

---

#### C-02 · Cookie `saa29_token` Sem Flag `Secure` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔴 Critical |
| **Tipo** | Security |
| **Localização** | `app/modules/auth/router.py` L73-80 |

**Descrição:**  
O cookie HttpOnly que transporta o JWT de acesso é setado **sem `secure=True`**, mesmo em produção (a linha está comentada). Em produção HTTPS (Railway), o cookie será transmitido em requisições HTTP plain-text se o usuário for redirecionado, expondo o token a interceptação via MITM.

```python
response.set_cookie(
    key="saa29_token",
    value=access_token,
    httponly=True,
    samesite="lax",
    max_age=15*60,
    # secure=True  # ← COMENTADO
)
```

**Fix sugerido:**  
Condicionar dinamicamente:
```python
secure = get_settings().app_env == "production"
response.set_cookie(..., secure=secure)
```

---

### 🟠 HIGH

---

#### H-01 · CSP Permite `script-src 'unsafe-inline'` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security |
| **Localização** | `app/bootstrap/main.py` L185 |

**Descrição:**  
A diretiva `script-src 'self' 'unsafe-inline'` na Content Security Policy anula efetivamente a proteção contra XSS injetado. Qualquer vetor de XSS (stored ou reflected) pode executar scripts arbitrários. O template `base.html` L90 usa `onclick="clearAuth()"` que requer inline, mas deveria ser migrado para event listener externo.

**Fix sugerido:**  
Remover `'unsafe-inline'` de `script-src` e migrar o único `onclick` restante em `base.html` para `auth_check.js`. Usar nonce-based CSP se necessário.

---

#### H-02 · `innerHTML` com Dados do Servidor sem Sanitização (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security (XSS) |
| **Localização** | `app/web/static/js/panes_lista.js`, `panes_detalhe.js`, `inventario.js`, `vencimentos.js`, `configuracoes.js` |

**Descrição:**  
Há dezenas de ocorrências de `innerHTML` usando template literals com dados vindos da API (matrícula, descrição de pane, serial number, etc.) sem uso da função `escapeHtml()` já disponível em `app.js`. Se um atacante conseguir inserir `<script>` ou event handlers em campos como `descricao`, `observacao`, ou `numero_serie`, o XSS é executado no navegador de todos os usuários que visualizarem o dado.

Exemplo em `panes_lista.js` L60:
```javascript
tr.innerHTML = `<td>${p.descricao}</td>`;  // sem escape
```

**Fix sugerido:**  
Substituir interpolações diretas por `escapeHtml(valor)` em todas as inserções de `innerHTML` que envolvam dados do servidor. Isso é especialmente prioritário para os campos de texto livre (`descricao`, `observacao`, `comentarios`).

---

#### H-03 · Token de Acesso Exposto no Body da Resposta de Login (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security |
| **Localização** | `app/modules/auth/router.py` L82-87 |

**Descrição:**  
O `access_token` é retornado simultaneamente no cookie HttpOnly **e** no body JSON da resposta. Isso anula parcialmente a proteção HttpOnly, pois o JavaScript no frontend tem acesso ao token via JSON e pode armazená-lo em `localStorage` (onde é acessível via XSS). O objetivo do HttpOnly era justamente impedir esse acesso.

**Fix sugerido:**  
Remover `access_token` do body da resposta de login. O frontend deve usar apenas o cookie para autenticação. O Swagger pode usar um fluxo alternativo de Bearer header.

---

#### H-04 · Refresh Token Exposto Sem Proteção HttpOnly (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security |
| **Localização** | `app/modules/auth/router.py` L84, L98-194 |

**Descrição:**  
O `refresh_token` é retornado no body JSON e gerenciado pelo JavaScript do frontend. Ele tem validade de 7 dias e, se comprometido via XSS (facilitado por H-01 e H-02), permite ao atacante gerar novos access tokens indefinidamente. Deveria ser transportado em cookie HttpOnly separado.

**Fix sugerido:**  
Transportar o refresh token em cookie HttpOnly separado (`saa29_refresh_token`), com `path=/auth/refresh` para restringir o envio apenas ao endpoint de renovação.

---

#### H-05 · JWT Expiry de 480 Minutos no `.env` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security |
| **Localização** | `.env` L20 |

**Descrição:**  
O `config.py` define um default seguro de 15 minutos para JWT, mas o `.env` sobrescreve com `JWT_EXPIRE_MINUTES=480` (8 horas). Isso dá uma janela de ataque de 8 horas para tokens roubados. O cookie `max_age` é hardcoded em 15 minutos (L78), criando uma inconsistência: o token JWT continua válido por 8h mesmo após o cookie expirar.

**Fix sugerido:**  
Reduzir `JWT_EXPIRE_MINUTES` para 15 no `.env` e confiar no fluxo de refresh token para manter sessões longas. Sincronizar `max_age` do cookie com o valor real do JWT.

---

#### H-06 · `ajustar_inventario` Sem Controle de Acesso (RBAC) (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟠 High |
| **Tipo** | Security (AuthZ) |
| **Localização** | `app/modules/equipamentos/router.py` L195-209 |

**Descrição:**  
O endpoint `POST /equipamentos/inventario/ajuste` usa apenas `CurrentUser` (qualquer usuário autenticado), mas permite realizar operações destrutivas: remover instalações existentes, criar novos itens, e forçar transferências entre aeronaves. Deveria exigir `EncarregadoOuAdmin`.

```python
async def ajustar_inventario(
    dados: schemas.AjusteInventarioCreate,
    db: DBSession,
    _: CurrentUser,  # ← Qualquer mantenedor pode alterar inventário de QUALQUER aeronave
)
```

**Fix sugerido:**  
Alterar para `_: EncarregadoOuAdmin`.

---

### 🟡 MEDIUM

---

#### M-01 · Erro de Lógica na Catch-All do Refresh Token (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Bug / Security |
| **Localização** | `app/modules/auth/router.py` L189-194 |

**Descrição:**  
O bloco `except Exception as e` no endpoint de refresh captura **todas** as exceções, incluindo as `HTTPException` lançadas intencionalmente dentro do mesmo `try`. Isso significa que uma HTTPException 401 ("Token inválido") é re-capturada e re-lançada com uma mensagem diferente, além de vazar os primeiros 50 caracteres da mensagem de erro original, potencialmente expondo informações internas.

**Fix sugerido:**  
Re-raise `HTTPException` antes da catch genérica:
```python
except HTTPException:
    raise
except Exception as e:
    raise HTTPException(status_code=401, detail="Refresh token inválido")
```

---

#### M-02 · Double Commit na Dependency `get_db` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Bug |
| **Localização** | `app/bootstrap/dependencies.py` L31-38 vs `app/modules/equipamentos/service.py` L382, L396 |

**Descrição:**  
A dependency `get_db` faz `commit` automaticamente ao final de cada request. Porém, vários endpoints e services fazem `commit` explícito no meio da execução (login, refresh, instalar_item, remover_item, ajustar_inventario). Isso causa double-commit e pode levar a estados inconsistentes se uma exceção ocorrer entre o commit explícito e o commit da dependency.

**Fix sugerido:**  
Padronizar: usar `flush()` nos services e deixar o `get_db` commitar, ou remover o commit automático do `get_db` e commitar explicitamente em cada endpoint.

---

#### M-03 · SQL Injection via `ilike` sem Escape no Inventário (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Security |
| **Localização** | `app/modules/equipamentos/service.py` L144-146 |

**Descrição:**  
O filtro de inventário usa `ilike(f"%{nome}%")` diretamente com input do usuário sem escapar os caracteres especiais de LIKE (`%`, `_`). O serviço de panes já implementa `_escape_like()` corretamente, mas o de equipamentos não.

```python
SlotInventario.nome_posicao.ilike(f"%{nome}%"),  # ← sem escape
```

**Fix sugerido:**  
Aplicar a mesma lógica de escape do `panes/service.py`:
```python
from app.modules.panes.service import _escape_like
nome_escaped = _escape_like(nome)
```

---

#### M-04 · Senha de Admin Hardcoded no `.env` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Security |
| **Localização** | `.env` L33, L37 |

**Descrição:**  
O `.env` contém `ADMIN_PASSWORD=admin123` e `DEFAULT_ADMIN_PASSWORD=admin123`. Se o `.env` for acidentalmente commitado (está no `.gitignore`, mas o risco existe), as credenciais de admin ficam expostas. Além disso, o `auth/service.py` L262 cria usuários de teste com senha `"123"` — 3 caracteres, abaixo do mínimo de 6 definido no schema.

**Fix sugerido:**  
Usar senha gerada aleatoriamente para desenvolvimento. Adicionar validação de senha mínima no `garantir_usuarios_essenciais`.

---

#### M-05 · Ausência de Limpeza de Tokens Expirados (Blacklist/Refresh) (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Performance / Data Integrity |
| **Localização** | `app/modules/auth/models.py` (TokenBlacklist, TokenRefresh) |

**Descrição:**  
As tabelas `token_blacklist` e `token_refresh` crescem indefinidamente. Cada login cria um refresh token, cada refresh rotaciona e cria mais um, e cada logout adiciona à blacklist. Não há job de limpeza para remover registros expirados. Com uso contínuo, essas tabelas impactarão a performance das queries de verificação.

**Fix sugerido:**  
Criar um job periódico (pode ser no `lifespan` ou via cron) que delete registros com `expira_em < now()`.

---

#### M-06 · Frontend Auth Check Apenas por `localStorage` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Security (AuthZ) |
| **Localização** | `app/web/static/js/auth_check.js`, `configuracoes.js` |

**Descrição:**  
O controle de acesso a Configurações e o controle de visibilidade do menu admin são feitos exclusivamente via `localStorage("saa29_user")`, manipulável pelo usuário. Embora os endpoints da API validem o papel no backend, um MANTENEDOR pode acessar a **página HTML** de configurações e visualizar o catálogo de equipamentos e tipos de controle (via chamadas GET que exigem apenas `CurrentUser`).

**Fix sugerido:**  
Validar o papel do usuário no backend ao renderizar as rotas protegidas (middleware ou dependency no `pages/router.py`).

---

#### M-07 · Backup R2 Executado Via `subprocess` Síncrono em Contexto Async (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Performance |
| **Localização** | `app/bootstrap/main.py` L138-151 |

**Descrição:**  
A função `_run_r2_backup()` usa `subprocess.run()` síncrono com `timeout=60`. Quando chamada do `_debounced_backup()` (que roda dentro do event loop), ela bloqueia o loop asyncio por até 60 segundos, impedindo que todas as outras requisições sejam processadas.

**Fix sugerido:**  
Usar `asyncio.create_subprocess_exec()` ou `anyio.run_process()` para manter o backup não-bloqueante.

---

#### M-08 · Variável `ext` Sobreescrita no `file_validators.py` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🟡 Medium |
| **Tipo** | Bug |
| **Localização** | `app/shared/core/file_validators.py` L31-32 |

**Descrição:**  
A variável `ext` é usada na L31 para a extensão do arquivo sendo validado, mas na L32 é sobreescrita pelo loop de compreensão que gera `allowed_extensions`. Se por algum motivo a lista estiver vazia, `ext` seria sobreposta.

```python
ext = os.path.splitext(file.filename)[1].lower()      # L31: extensão real
allowed_extensions = [ext for exts in ... for ext in exts]  # L32: sobreescreve `ext`!
```

**Fix sugerido:**  
Renomear a variável na compreensão:
```python
allowed_extensions = [e for exts in ALLOWED_MIME_TYPES.values() for e in exts]
```

---

### 🔵 LOW

---

#### L-01 · `Aeronave.status` Não Usa Enum no Modelo (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Architecture |
| **Localização** | `app/modules/aeronaves/models.py` + `app/modules/vencimentos/service.py` |

**Descrição:**  
O status da aeronave é armazenado como `String` livre, enquanto existe o enum `StatusAeronave`. Comparações nos services usam string literal `"INATIVA"`, tornando o código frágil a typos e refatorações. Idem para `panes/service.py` L99.

**Fix sugerido:**  
Usar `StatusAeronave.INATIVA.value` nas comparações e idealmente trocar o tipo da coluna para `Enum` no modelo.

---

#### L-02 · `pane_id` Não Validado para Responsabilidade no Upload (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Security (IDOR) |
| **Localização** | `app/modules/panes/router.py` L180-201 |

**Descrição:**  
No upload de anexo, o `pane_id` vem da URL e o serviço valida a existência da pane, mas um usuário autenticado pode fazer upload de anexos em **qualquer** pane aberta, mesmo que não seja responsável por ela. Isso foi confirmado como intencional no workflow atual de manutenção para permitir a colaboração de equipes (documentado).

---

#### L-03 · Módulo `_engine` Importado Diretamente no `lifespan` (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Architecture |
| **Localização** | `app/bootstrap/main.py` L231-233 |

**Descrição:**  
O `lifespan` importa `_engine` (variável privada) diretamente do módulo `database`. Isso quebra o encapsulamento.

**Fix sugerido:**  
Expor uma função `dispose_engine()` no módulo `database.py`.

---

#### L-04 · Verificação Duplicada de Matrícula no Frontend (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Architecture / Performance |
| **Localização** | `app/web/static/js/configuracoes.js` L86-94 |

**Descrição:**  
Antes de criar uma aeronave, o frontend busca **todas** as aeronaves (`?limit=1000&incluir_inativas=true`) para verificar duplicidade. Isso é redundante (o backend já valida unicidade) e potencialmente lento com frotas maiores.

**Fix sugerido:**  
Remover a verificação client-side e confiar no backend (HTTP 409 já tratado no `catch`).

---

#### L-05 · Service de Vencimentos Sem Tipagem Explícita (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Architecture |
| **Localização** | `app/modules/vencimentos/service.py` |

**Descrição:**  
Algumas funções no service de vencimentos usam `dados` como parâmetro sem referência explícita ao schema Pydantic correspondente, reduzindo a segurança de tipo estático.

**Fix sugerido:**  
Tipar explicitamente todos os parâmetros com os schemas correspondentes.

---

#### L-06 · `database_url` Default Aponta para Caminho Sem Extensão (✅ Corrigido)

| Campo | Valor |
|:---|:---|
| **Severidade** | 🔵 Low |
| **Tipo** | Bug |
| **Localização** | `app/bootstrap/config.py` L36 |

**Descrição:**  
O default do `database_url` é `sqlite+aiosqlite:///./var/db` que cria um **arquivo** chamado `db` (sem extensão). O `.env` sobrescreve corretamente, mas se `.env` faltar, o sistema criará o banco em local inesperado.

**Fix sugerido:**  
Alterar default para `sqlite+aiosqlite:///./saa29_local.db`.

---

## Matriz de Priorização

| Prioridade | Issues | Esforço Estimado |
|:---|:---|:---|
| **Sprint imediato** | C-01, C-02, H-05, H-06 | **✅ Concluído** |
| **Sprint corrente** | H-01, H-02, H-03, H-04 | **✅ Concluído** |
| **Backlog técnico** | M-01..M-08 | **✅ Concluído** |
| **Nice to have** | L-01..L-06 | **✅ Concluído** |

---

## Observações Positivas

A auditoria também registra práticas de segurança **bem implementadas**:

1. ✅ **Account Lockout** — Proteção contra brute force com bloqueio temporário após 5 tentativas
2. ✅ **JWT Blacklist** — Tokens revogados são verificados a cada request
3. ✅ **Refresh Token Rotation** — Rotação automática no endpoint `/auth/refresh`
4. ✅ **File Upload Validation** — Magic bytes + extensão + cross-check (defesa em profundidade)
5. ✅ **Path Traversal Prevention** — Validação de `..`, `/` e `\` em nomes de arquivo
6. ✅ **LIKE Escape** — Implementado no módulo de panes (falta propagar para equipamentos)
7. ✅ **Soft Delete** — Panes usam exclusão lógica com idempotência verificada
8. ✅ **Rate Limiting** — Login protegido com 5/minute via SlowAPI
9. ✅ **Security Headers** — X-Content-Type-Options, X-Frame-Options, HSTS (em produção)
10. ✅ **SQLite Pragmas** — FK enforcement, WAL mode e synchronous=NORMAL configurados


