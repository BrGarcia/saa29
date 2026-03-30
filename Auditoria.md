# Auditoria de Código — SAA29

**Projeto:** SAA29 – Sistema de Gestão de Panes – Eletrônica A-29  
**Data da auditoria:** 2026-03-30  
**Versão auditada:** 0.6.0 (branch `main`)  
**Auditor:** Antigravity AI  

---

## Sumário Executivo

| Severidade | Contagem |
|------------|----------|
| 🔴 CRITICAL | 4 |
| 🟠 HIGH | 7 |
| 🟡 MEDIUM | 7 |
| 🟢 LOW | 4 |
| **TOTAL** | **22** |

---

## 🔴 CRITICAL

### AUD-01 · Crash em `editar_pane` e `concluir_pane` — Tuple Unpacking em Objeto Pane

| Campo | Valor |
|-------|-------|
| **Severidade** | 🔴 CRITICAL |
| **Módulo** | `app/panes/service.py` |
| **Linhas** | L274-L278 (`editar_pane`), L330-L334 (`concluir_pane`), L371-L374 (`excluir_pane`), L385-L388 (`restaurar_pane`) |

**Problema:**  
`buscar_pane()` retorna `tuple[Pane, int, int] | None`, mas `editar_pane()`, `concluir_pane()`, `excluir_pane()` e `restaurar_pane()` usam o retorno como se fosse um `Pane` direto:

```python
# editar_pane L274
pane = await buscar_pane(db, pane_id)  # ← retorna (Pane, seq, ano)
# ...
status_atual = StatusPane(pane.status)  # ← crash: tuple não tem .status
```

**Impacto:**  
**Toda operação de edição, conclusão, exclusão ou restauração de pane crashará com `AttributeError`** no momento em que `pane.status`, `pane.ativo`, etc. são acessados em uma tupla.

**Causa raiz:**  
`buscar_pane()` foi refatorada para retornar `(Pane, sequencia, ano)` junto com ranking, mas as funções consumidoras não foram atualizadas.

**Correção:**
```python
# Opção A: Desestruturar a tupla em cada chamador
resultado = await buscar_pane(db, pane_id)
if not resultado:
    raise ValueError("Pane não encontrada.")
pane, _, _ = resultado

# Opção B (recomendada): criar buscar_pane_simples() sem ranking
async def _buscar_pane_raw(db, pane_id, incluir_inativos=False) -> Pane | None:
    query = select(Pane).where(Pane.id == pane_id).options(...)
    if not incluir_inativos:
        query = query.where(Pane.ativo == True)
    result = await db.execute(query)
    return result.scalar_one_or_none()
```

---

### AUD-02 · Enum `INSPETOR` inexistente no `TipoPapel` — Frontend cria dados inválidos

| Campo | Valor |
|-------|-------|
| **Severidade** | 🔴 CRITICAL |
| **Módulos** | `app/core/enums.py`, `templates/efetivo.html`, `app/auth/schemas.py`, `app/panes/models.py` |

**Problema:**  
O enum `TipoPapel` define 3 valores: `MANTENEDOR`, `ENCARREGADO`, `ADMINISTRADOR`.  
Porém diversas partes do sistema ainda referenciam `INSPETOR` (um valor **removido/renomeado**):

| Local | Uso de `INSPETOR` |
|-------|--------------------|
| `templates/efetivo.html:L78` | `<option value="INSPETOR">INSPETOR</option>` no dropdown de criação |
| `app/auth/schemas.py:L29` | docstring diz `INSPETOR \| ENCARREGADO \| MANTENEDOR` |
| `app/panes/models.py:L213` | comment do campo `papel` diz `INSPETOR \| ENCARREGADO \| MANTENEDOR` |
| `app/dependencies.py:L121` | `InspetorRequired = AdminRequired` (alias confuso) |
| `tests/test_auth.py:L215` | Cria usuário com `funcao: "INSPETOR"` |

**Impacto:**  
- Criar um usuário com `funcao = "INSPETOR"` via template **não passa validação Pydantic** (`INSPETOR` não existe no enum), gerando HTTP 422 silencioso.
- O dropdown do frontend mostra `INSPETOR` como 1ª opção, sendo a seleção padrão.
- Teste `test_auth.py` que envia `funcao: "INSPETOR"` falha ou recebe 422.

**Correção:**
1. Trocar `INSPETOR` por `ADMINISTRADOR` no dropdown `efetivo.html:L78`
2. Corrigir docstrings e comments em schemas e models
3. Remover aliases `InspetorRequired` / `InspetorOuEncarregado` de `dependencies.py`
4. Corrigir fixture em `test_auth.py`

---

### AUD-03 · Ausência de invalidação JWT no Logout (`/auth/logout`)

| Campo | Valor |
|-------|-------|
| **Severidade** | 🔴 CRITICAL |
| **Módulo** | `app/auth/router.py` L57-69 |

**Problema:**  
O endpoint `/auth/logout` retorna 204 sem nenhuma ação server-side. O token JWT permanece válido por **8 horas** (480 minutos) após o logout.

```python
async def logout(usuario_atual: CurrentUser) -> None:
    # Stateless JWT — o cliente simplesmente descarta o token.
    return None
```

**Impacto:**  
Se um token for interceptado (log, proxy, clipboard), ele permanece utilizável indefinidamente até a expiração natural. Num sistema militar/aeronáutico, isso é inaceitável.

**Correção:**
Implementar token blacklist com Redis/in-memory:
```python
# app/auth/blacklist.py
_blacklist: set[str] = set()  # Em produção, usar Redis com TTL

def blacklist_token(jti: str) -> None:
    _blacklist.add(jti)

def is_blacklisted(jti: str) -> bool:
    return jti in _blacklist
```
- Adicionar `jti` (JWT ID, `uuid4`) ao payload em `criar_token()`
- Validar `jti` contra blacklist em `decodificar_token()`
- Chamar `blacklist_token(jti)` no endpoint `/logout`

---

### AUD-04 · XSS via `innerHTML` com dados do servidor (Frontend)

| Campo | Valor |
|-------|-------|
| **Severidade** | 🔴 CRITICAL |
| **Módulos** | `templates/efetivo.html`, `templates/panes/lista.html` |

**Problema:**  
Dados retornados da API são injetados diretamente em `innerHTML` sem sanitização:

```javascript
// efetivo.html L220-224
tr.innerHTML = `
    <td>${u.posto} ${u.nome} ${u.trigrama ? `...${u.trigrama}...` : ''}
    ...
`;

// lista.html L172
<td>${pane.descricao}</td>
```

Se um campo como `nome`, `descricao` ou `trigrama` contiver HTML malicioso (ex: `<img src=x onerror=alert(1)>`), ele será executado no browser de todos os usuários.

**Impacto:**  
Stored XSS — um usuário malicioso pode roubar tokens JWT de qualquer operador que visualize a página.

**Correção:**
```javascript
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Usar em toda interpolação de dados dinâmicos:
tr.innerHTML = `<td>${escapeHtml(u.nome)}</td>`;
```

---

## 🟠 HIGH

### AUD-05 · Ausência de RBAC nos endpoints de Aeronaves

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/aeronaves/router.py` L78-128 |

**Problema:**  
Os endpoints `PUT /aeronaves/{id}` e `POST /aeronaves/{id}/toggle-status` exigem apenas `CurrentUser` (qualquer usuário autenticado), quando deveriam exigir `AdminRequired` ou `EncarregadoOuAdmin`:

```python
# L83-87 — atualizar_aeronave
async def atualizar_aeronave(..., _: CurrentUser):  # ← sem RBAC

# L110-113 — alternar_status_aeronave
async def alternar_status_aeronave(..., _: CurrentUser):  # ← sem RBAC
```

**Impacto:**  
Qualquer `MANTENEDOR` pode alterar a matrícula, serial number e status de aeronaves.

**Correção:**
```python
async def atualizar_aeronave(..., _: EncarregadoOuAdmin):
async def alternar_status_aeronave(..., _: EncarregadoOuAdmin):
```

---

### AUD-06 · CORS `allow_methods=["*"]` + `allow_headers=["*"]`

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/main.py` L120-126 |

**Problema:**  
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],      # ← Todo método HTTP
    allow_headers=["*"],      # ← Todo header
)
```

Com `allow_credentials=True`, headers wildcard criam superfície de ataque CSRF.

**Correção:**
```python
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
allow_headers=["Authorization", "Content-Type"],
```

---

### AUD-07 · `allowed_hosts: list[str] = ["*"]` — TrustedHostMiddleware ineficaz

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/config.py` L35, `app/main.py` L115-118 |

**Problema:**  
O valor default `["*"]` para `allowed_hosts` resulta em `allowed_hosts=["localhost", "127.0.0.1", "*"]`, que aceita **qualquer Host header**, tornando o middleware de segurança inútil.

**Impacto:**  
Ataques de Host Header Injection, DNS rebinding, e cache poisoning.

**Correção:**
```python
allowed_hosts: list[str] = []  # Em produção, configurar domínios explícitos no .env
```

---

### AUD-08 · `APP_SECRET_KEY` hardcoded e inseguro no default

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/config.py` L20 |

**Problema:**
```python
app_secret_key: str = "INSECURE_DEFAULT_SECRET_KEY_CHANGE_ME_IN_PRODUCTION"
```

Se `.env` não definir `APP_SECRET_KEY`, o sistema usa uma chave previsível para assinar todos os JWTs.

**Correção:**
Forçar exceção em produção quando a chave não é definida:
```python
@model_validator(mode="after")
def validate_secret(self):
    if self.app_env == "production" and "INSECURE" in self.app_secret_key:
        raise ValueError("APP_SECRET_KEY deve ser definida em produção!")
    return self
```

---

### AUD-09 · Validação MIME-type desativada quando `python-magic` não está instalado

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/panes/service.py` L12-16, L430-436 |

**Problema:**
```python
try:
    import magic
    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False
```

Se `python-magic` não estiver instalado (não está em `requirements.txt`), a validação SEC-05 de MIME-type **é silenciosamente desabilitada**. Um atacante pode fazer upload de um `.exe` renomeado para `.jpg`.

**Correção:**
1. Adicionar `python-magic` (ou `python-magic-bin`) ao `requirements.txt`
2. Ou, se não possível, rejeitar uploads quando `magic` não está disponível:
```python
if not _MAGIC_AVAILABLE:
    raise ValueError("Validação de tipo de arquivo indisponível. Contacte o administrador.")
```

---

### AUD-10 · `UsuarioUpdate` permite alterar `funcao` via `setattr` sem restrição

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/auth/service.py` L158-159, `app/auth/schemas.py` L36-43 |

**Problema:**
```python
for campo, valor in dados.model_dump(exclude_unset=True).items():
    setattr(usuario, campo, valor)
```

O schema `UsuarioUpdate` inclui o campo `funcao: TipoPapel | None`, permitindo que um admin altere a função de qualquer usuário. Embora exija `AdminRequired`, não há validação para impedir auto-rebaixamento ou auto-escalação, nem audit log.

Mais grave: o `setattr` genérico aplicaria qualquer campo cegamente ao modelo se adicionado ao schema sem cuidado.

**Correção:**
Usar lista explícita de campos editáveis:
```python
CAMPOS_EDITAVEIS = {"nome", "posto", "especialidade", "funcao", "ramal", "trigrama"}
for campo, valor in dados.model_dump(exclude_unset=True).items():
    if campo not in CAMPOS_EDITAVEIS:
        continue
    setattr(usuario, campo, valor)
```

---

### AUD-11 · `exclude_none` vs `exclude_unset` em `atualizar_equipamento`

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟠 HIGH |
| **Módulo** | `app/equipamentos/service.py` L66 |

**Problema:**
```python
for campo, valor in dados.model_dump(exclude_none=True).items():
```

Usa `exclude_none` em vez de `exclude_unset`. Isso impede que um campo seja intencionalmente definido como `None` (ex: limpar `descricao` ou `sistema`). Em contraste, `app/auth/service.py` usa corretamente `exclude_unset`.

**Impacto:**  
Impossível limpar/resetar campos opcionais de equipamentos.

**Correção:**
```python
for campo, valor in dados.model_dump(exclude_unset=True).items():
```

---

## 🟡 MEDIUM

### AUD-12 · Ausência de RBAC nos endpoints de Equipamentos

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `app/equipamentos/router.py` (todos os endpoints) |

**Problema:**  
Todos os endpoints do módulo de equipamentos exigem apenas `CurrentUser`. Operações de criação, instalação e execução de controle de vencimento deveriam exigir pelo menos `EncarregadoOuAdmin`.

---

### AUD-13 · Ausência de `ALLOWED_ORIGINS` no `.env`

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `.env`, `app/config.py` L34 |

**Problema:**
O `.env` não define `ALLOWED_ORIGINS`. O default é `["http://localhost:8000"]`, mas em produção isso deve ser configurado explicitamente. Não há alerta ou validação.

---

### AUD-14 · Paginação sem limite máximo efetivo no `listar_panes`

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `app/panes/service.py` L196, `app/panes/schemas.py` L29 |

**Problema:**  
O filtro define `limit: int = Field(default=100, ge=1, le=1000)`. Mas quando `filtros` é `None`, nenhum `limit` é aplicado:

```python
if filtros:
    # ...
    query = query.offset(filtros.skip).limit(filtros.limit)
# ← Se filtros is None, retorna TODOS os registros
```

**Impacto:**  
Se chamado sem filtros, retorna todas as panes do banco sem limite.

**Correção:**
Aplicar `limit` sempre:
```python
if filtros:
    query = query.offset(filtros.skip).limit(filtros.limit)
else:
    query = query.limit(100)
```

---

### AUD-15 · `Jinja2 {% if/else/endif %}` cruza escopo `<body>` — `base.html` mal estruturado

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `templates/base.html` L14-104 |

**Problema:**  
O bloco `{% if request.url.path != "/login" %}` em L14 abre tags HTML (`<div>`, `<main>`, `<header>`) e o `{% else %}` em L101 **está dentro de um `<script>`**, criando uma estrutura confusa:

```
L14:  {% if request.url.path != "/login" %}
L15:  <div class="app-container">
...
L75:  </header>
L78:  {% block content %}{% endblock %}
L79:  </main>
L80:  </div>
L83:  <script>
...
L100: </script>
L101: {% else %}         ← O else está FORA do div mas DEPOIS do script
L103: {% block login_content %}{% endblock %}
L104: {% endif %}
```

Este é a causa do erro `{ expected @[base.html:L28]` reportado pelo linter/editor — parsers se confundem com Jinja dentro de HTML.

**Correção:**
Reestruturar o template para que o `{% if %}` / `{% else %}` envolva blocos semânticos claros:
```html
<body>
{% if request.url.path != "/login" %}
    <div class="app-container">
        ...
    </div>
    <script>/* auth check */</script>
{% else %}
    {% block login_content %}{% endblock %}
{% endif %}

    <script src="/static/js/app.js"></script>
    {% block scripts %}{% endblock %}
</body>
```

---

### AUD-16 · `showToast` vulnerável a XSS

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `static/js/app.js` L114 |

**Problema:**
```javascript
toast.innerHTML = `${icon} <span>${message}</span>`;
```

Se `message` contiver HTML (ex: mensagem de erro da API com user input), ele será executado.

**Correção:**
```javascript
const span = document.createElement('span');
span.textContent = message;
toast.innerHTML = icon;
toast.appendChild(span);
```

---

### AUD-17 · Auto-exclusão de administrador não impedida

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `app/auth/service.py` L188-207, `app/auth/router.py` L167-184 |

**Problema:**  
Um administrador pode desativar **a si mesmo** via `DELETE /auth/usuarios/{seu_id}`, perdendo acesso ao sistema. Se for o único admin, o sistema fica sem administradores.

**Correção:**
```python
async def excluir_usuario(db, usuario_id, usuario_logado_id):
    if usuario_id == usuario_logado_id:
        raise ValueError("Não é possível desativar o próprio usuário.")
    # Verificar se é o último administrador ativo
    admins_ativos = await db.execute(
        select(func.count()).where(
            Usuario.funcao == "ADMINISTRADOR", Usuario.ativo == True
        )
    )
    if admins_ativos.scalar() <= 1:
        usuario = await buscar_por_id(db, usuario_id)
        if usuario and usuario.funcao == "ADMINISTRADOR":
            raise ValueError("Não é possível desativar o último administrador do sistema.")
```

---

### AUD-18 · Token JWT com 8 horas de expiração

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟡 MEDIUM |
| **Módulo** | `app/config.py` L27 |

**Problema:**  
`jwt_expire_minutes: int = 480` (8 horas) é excessivamente longo para um sistema militar. OWASP recomenda tokens de curta duração (15-30 min) com refresh tokens.

**Correção:**
- Reduzir para 60-120 minutos
- Implementar refresh token endpoint

---

## 🟢 LOW

### AUD-19 · `saa29_user` armazenado em `localStorage` sem criptografia

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟢 LOW |
| **Módulo** | `templates/login.html` L82, `static/js/app.js` L41-46 |

**Problema:**  
Token JWT e dados do usuário (incluindo `funcao`) são armazenados em `localStorage`, acessível por qualquer script na mesma origem. Um ataque XSS (ver AUD-04) pode exfiltrar esses dados.

**Mitigação:**
- Corrigir XSS primeiro (AUD-04)
- Considerar cookies `HttpOnly` + `Secure` para o token em produção

---

### AUD-20 · RBAC client-side no frontend é facilmente burlável

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟢 LOW |
| **Módulo** | `templates/base.html` L92-96, `templates/efetivo.html` L267 |

**Problema:**  
Verificações de role no frontend (mostrar/esconder botões baseado em `saa29_user.funcao`) são decorativas. A proteção real está no backend, que corretamente valida RBAC — mas endpoints como Aeronaves e Equipamentos **não possuem** RBAC (ver AUD-05, AUD-12).

---

### AUD-21 · `_ensure_default_aeronaves` executa N queries sequenciais

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟢 LOW |
| **Módulo** | `app/main.py` L32-63 |

**Problema:**  
Verifica cada matrícula individualmente com 20 SELECTs, depois 20 INSERTs potenciais.

**Correção:**
Usar `INSERT ... ON CONFLICT DO NOTHING` ou `SELECT ... WHERE matricula IN (...)` para batch.

---

### AUD-22 · `.env` possivelmente commitado no histórico Git

| Campo | Valor |
|-------|-------|
| **Severidade** | 🟢 LOW |
| **Módulo** | `.env` |

**Problema:**  
Apesar de listado no `.gitignore`, o `.env` contém credenciais. Se já foi commitado antes de adicionar ao `.gitignore`, as credenciais estão no histórico do Git.

**Correção:**
```bash
git rm --cached .env
git commit -m "Remove .env do tracking"
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch .env' -- --all
```

---

## Mapa de Impacto por Módulo

| Módulo | C | H | M | L |
|--------|---|---|---|---|
| `app/panes/service.py` | 1 | 1 | 1 | 0 |
| `app/auth/*` | 1 | 2 | 2 | 0 |
| `app/main.py` | 0 | 2 | 0 | 1 |
| `app/config.py` | 0 | 1 | 1 | 0 |
| `app/aeronaves/router.py` | 0 | 1 | 0 | 0 |
| `app/equipamentos/*` | 0 | 1 | 1 | 0 |
| `templates/*` | 1 | 0 | 1 | 1 |
| `static/js/app.js` | 0 | 0 | 1 | 1 |
| `app/core/enums.py` | 1 | 0 | 0 | 0 |

---

## Prioridade de Correção Recomendada

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. AUD-01  Tuple unpacking crash (deploy-blocker)              │
│ 2. AUD-02  INSPETOR enum mismatch (dados inválidos)            │
│ 3. AUD-04  XSS stored via innerHTML                            │
│ 4. AUD-05  RBAC faltando em Aeronaves                          │
│ 5. AUD-03  JWT blacklist no logout                             │
│ 6. AUD-08  Secret key validation                               │
│ 7. AUD-09  python-magic obrigatório                            │
│ 8. AUD-06  CORS hardening                                      │
│ 9. AUD-07  TrustedHost wildcard                                │
│ 10. Restantes (por severidade decrescente)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

> **Nota:** Esta auditoria cobre o código-fonte (backend Python + frontend JS/HTML). Não inclui auditoria de infraestrutura (Docker, CI/CD), dependências de terceiros (CVE scan), ou testes de penetração black-box.
