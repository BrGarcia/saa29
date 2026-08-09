# 🔒 Relatório de Auditoria de Segurança — SAA29

**Data:** 2026-08-09  
**Auditor:** Engenheiro de Segurança de Software (DevSecOps)  
**Escopo:** Varredura completa pré-deploy — Foco em vulnerabilidades de código gerado por IA  
**Versão do Projeto:** Monolito FastAPI (Python 3.12) + Frontend Jinja2/Vanilla JS

---

## Resumo Executivo

| Severidade    | Qtd | Status     |
|---------------|-----|------------|
| 🔴 CRÍTICA    | 4   | Ação Imediata Necessária |
| 🟠 ALTA       | 3   | Corrigir Antes do Deploy |
| 🟡 MÉDIA      | 5   | Corrigir no Primeiro Sprint |
| 🔵 BAIXA      | 4   | Melhoria Recomendada |
| ✅ CONFORME    | 12  | Sem Ação Necessária |

> [!CAUTION]
> **4 vulnerabilidades CRÍTICAS foram identificadas** que devem ser corrigidas **ANTES** de qualquer exposição pública da aplicação. O deploy sem essas correções expõe credenciais reais ao público.

---

## 1. EXPOSIÇÃO DE CREDENCIAIS

### 🔴 SEC-01 — `.env.backup` versionado no Git com credenciais reais de produção

**Arquivo:** `.env.backup`  
**Evidência:** `git ls-files` confirma que este arquivo está **rastreado no repositório**.

```
R2_ACCOUNT_ID=7fa0ed8254b8f41ec3eb2e83b5bc622f
R2_ACCESS_KEY_ID=dce783c7c9793fbaa2b3a079606ee1ca
R2_SECRET_ACCESS_KEY=3deb304c21438f4cbcdecfdd426b14f4fb40df53798e3618d75ae38ec1e1957a
DEFAULT_ADMIN_PASSWORD=Admin@123
```

**Impacto:** Qualquer pessoa com acesso ao repositório (mesmo histórico) possui as chaves de acesso ao Cloudflare R2 e a senha do administrador. **Mesmo remover o arquivo agora não resolve** — as credenciais estão no histórico do Git.

**Ação Imediata:**
1. **Revogar e rotacionar TODAS as credenciais R2** no painel do Cloudflare
2. Remover o arquivo do Git: `git rm --cached .env.backup`
3. Adicionar `.env.backup` ao `.gitignore`
4. Gerar novas credenciais R2 e uma nova `DEFAULT_ADMIN_PASSWORD` forte (20+ caracteres)
5. Considerar `git filter-branch` ou `BFG Repo-Cleaner` para limpar o histórico, ou criar um repositório limpo

---

### 🔴 SEC-02 — `cookies.txt` versionado no Git com tokens JWT válidos

**Arquivo:** `cookies.txt`  
**Evidência:** `git ls-files` confirma rastreamento. Contém tokens JWT reais (access + refresh) e CSRF.

```
saa29_refresh_token  eyJhbGciOiJIUzI1NiIs...
saa29_token          eyJhbGciOiJIUzI1NiIs...
fastapi-csrf-token   ImNjMWY1MzA3NWE4...
```

**Impacto:** Embora expirem, os tokens podem ser decodificados para extrair user IDs, usernames e timestamps. Combinado com a `APP_SECRET_KEY` exposta, permite forjar novos tokens.

**Ação Imediata:**
1. `git rm --cached cookies.txt`
2. Adicionar `cookies.txt` ao `.gitignore`
3. Rotacionar a `APP_SECRET_KEY` (invalida todos os tokens existentes)

---

### 🔴 SEC-03 — `.env.example` contém senha real do admin

**Arquivo:** `.env.example` (linha 18)

```
DEFAULT_ADMIN_PASSWORD=BisKP76pg3IU
```

**Impacto:** O `.env.example` está versionado (de propósito), mas contém o que aparenta ser uma **senha real**, não um placeholder. Alguém que clone o repo e copie o `.env.example` para `.env` terá acesso imediato como admin.

**Ação Imediata:**
- Substituir por placeholder descritivo: `DEFAULT_ADMIN_PASSWORD=GERE_UMA_SENHA_FORTE_AQUI`

---

### 🔴 SEC-04 — `.env` de produção com `ALLOWED_HOSTS="*"` e `ALLOWED_ORIGINS="*"`

**Arquivo:** `.env` (linhas 1-2)

```
ALLOWED_HOSTS="*"
ALLOWED_ORIGINS="*"
```

**Impacto:** Em produção, `ALLOWED_HOSTS="*"` desativa o `TrustedHostMiddleware` (verificado em `main.py:115`). `ALLOWED_ORIGINS="*"` com `allow_credentials=True` é inválido pelo padrão CORS — o código faz fallback silencioso para localhost, o que **quebrará** chamadas de qualquer domínio real em produção.

**Ação Imediata:**
- Configurar explicitamente: `ALLOWED_HOSTS="seu-dominio.com,www.seu-dominio.com"`
- Configurar explicitamente: `ALLOWED_ORIGINS="https://seu-dominio.com"`

---

### 🟠 SEC-05 — `APP_ENV=development` no `.env` que será usado em produção

**Arquivo:** `.env` (linha 4)

```
APP_ENV=development
```

**Impacto:** Em modo development:
- `/docs` e `/redoc` (Swagger) ficam expostos publicamente, revelando toda a API
- `Strict-Transport-Security` (HSTS) não é aplicado
- Cookies não recebem flag `Secure` (transmitidos por HTTP puro)
- O flag de cookie seguro depende desta variável (`_cookies_secure()`)

**Ação Imediata:**
- Definir `APP_ENV=production` no ambiente de produção

---

### 🟠 SEC-06 — `ENABLE_DEV_SEEDS=true` no `.env` de produção

**Arquivo:** `.env` (linha 14)

```
ENABLE_DEV_SEEDS=true
```

**Impacto:** Se `APP_ENV` não estiver definido como `production` no servidor, o script `start.sh` executará seeds de desenvolvimento, potencialmente criando dados fictícios no banco de produção.

**Ação Imediata:**
- Definir `ENABLE_DEV_SEEDS=false` no ambiente de produção

---

### ✅ SEC-07 — Credenciais NÃO expostas no frontend (JavaScript)

**Verificação:** Grep extensivo por `api_key`, `secret_key`, `password`, `token`, URLs externas e referências ao R2 em todos os arquivos JS do diretório `app/web/static/js/`.

**Resultado:** **CONFORME**. Nenhuma credencial, chave de API ou segredo foi encontrado nos arquivos JavaScript do frontend. Os tokens são transportados exclusivamente via cookies `HttpOnly`.

---

## 2. ARQUITETURA DE INTEGRAÇÃO

### ✅ ARCH-01 — Ausência de chamadas diretas do frontend a APIs externas

**Verificação:** Análise de todos os 19 arquivos JavaScript em `app/web/static/js/`. Todas as chamadas `fetch()` utilizam a função `apiFetch()` centralizada que faz requisições exclusivamente ao backend (`/auth/*`, `/panes/*`, `/aeronaves/*`, etc.).

**Resultado:** **CONFORME**. O frontend NÃO faz chamadas diretas a:
- Cloudflare R2
- APIs de terceiros
- Serviços externos de qualquer tipo

O backend (FastAPI) atua como proxy seguro para o R2 (via `R2StorageService` em `app/shared/core/storage.py`), gerando URLs pré-assinadas no servidor e as entregando ao frontend autenticado.

---

### ✅ ARCH-02 — Download de anexos autenticado via proxy

**Arquivo:** `app/modules/panes/router.py` (endpoint `baixar_anexo`)

O endpoint `/panes/{pane_id}/anexos/{anexo_id}/download` exige autenticação (`CurrentUser`), busca a URL pré-assinada do R2 no backend e faz `RedirectResponse` — nunca expõe as credenciais R2 ao cliente.

**Resultado:** **CONFORME**.

---

### ✅ ARCH-03 — Arquitetura monolítica coerente

O projeto é um **monolito server-rendered** (FastAPI + Jinja2) onde frontend e backend coexistem no mesmo processo. Não há separação SPA/API que criaria vetores de comunicação direta. As "páginas" são renderizadas no servidor com `Depends(get_current_user)`, e os dados são carregados via `fetch()` do JavaScript para endpoints autenticados do próprio backend.

**Resultado:** **CONFORME** — Arquitetura adequada para o cenário.

---

## 3. MANIPULAÇÃO DE PAYLOAD E DADOS SENSÍVEIS

### ✅ PAYLOAD-01 — PaneCreate envia apenas identificadores

**Arquivo:** `app/modules/panes/schemas.py`

```python
class PaneCreate(BaseModel):
    aeronave_id: uuid.UUID
    sistema_ata_id: uuid.UUID | None
    descricao: str
    mantenedor_responsavel_id: uuid.UUID | None
    # status inicial = ABERTA (definido no service, não pelo cliente)
```

**Resultado:** **CONFORME**. O status da pane é definido pelo backend (`service.criar_pane`), não pelo cliente. O frontend envia apenas IDs e descrição textual.

---

### ✅ PAYLOAD-02 — PaneConcluir não aceita status do cliente

**Arquivo:** `app/modules/panes/schemas.py`

```python
class PaneConcluir(BaseModel):
    observacao_conclusao: str | None = None
```

O endpoint `POST /{pane_id}/concluir` aceita apenas uma observação opcional. A transição de status (ABERTA → RESOLVIDA) e o preenchimento de `data_conclusao` são feitos exclusivamente no service.

**Resultado:** **CONFORME**.

---

### 🟡 PAYLOAD-03 — PaneUpdate aceita campo `status` no payload

**Arquivo:** `app/modules/panes/schemas.py` (linhas 61-73)

```python
class PaneUpdate(BaseModel):
    status: StatusPane | None = Field(default=None, ...)
```

Embora o comentário do código indique que `status=RESOLVIDA` é rejeitado com 409 pelo service, o campo `status` **continua aceitável** no payload de edição. Isso amplia a superfície de ataque — um atacante pode tentar outros valores de status (`ABERTA` → `ABERTA`, ou futuros valores do enum).

**Recomendação:** Remover o campo `status` do schema `PaneUpdate` por completo. Se um dia for necessário, criar um endpoint dedicado com RBAC adequado.

---

### ✅ PAYLOAD-04 — UsuarioCreate não permite escalação de privilégios por padrão

**Arquivo:** `app/modules/auth/router.py` (linhas 390-397)

```python
async def criar_usuario(
    dados: schemas.UsuarioCreate,
    db: DBSession,
    _: AdminRequired,   # ← Protegido
)
```

A criação de usuários exige `AdminRequired`. O campo `funcao` no payload é controlado pelo enum `TipoPapel`, e a operação inteira é gated por RBAC.

**Resultado:** **CONFORME**.

---

### 🟡 PAYLOAD-05 — Token JWT retorna dados do usuário completos (incluindo username)

**Arquivo:** `app/modules/auth/schemas.py` (linhas 55-68)

O schema `UsuarioOut` retornado no login inclui `username`, `funcao`, `posto`, `especialidade`, `trigrama` — todos armazenados em `localStorage` pelo frontend.

**Risco:** O `localStorage` é acessível a qualquer JavaScript no mesmo domínio. Uma vulnerabilidade XSS (mesmo que mitigada pela CSP) poderia exfiltrar esses dados.

**Recomendação:** Avaliar se todos esses campos são realmente necessários no localStorage. O mínimo seria `funcao` (para UI condicional) e `nome` (para exibição). Os demais poderiam ser buscados sob demanda via `/auth/me`.

---

## 4. VALIDAÇÃO DE REGRAS DE NEGÓCIO

### ✅ RBAC-01 — Controle de acesso no backend via Dependencies

**Arquivos:** `app/bootstrap/dependencies.py`

O sistema implementa RBAC (Role-Based Access Control) robusto via FastAPI Dependencies:

| Dependency | Papéis Permitidos |
|---|---|
| `CurrentUser` | Qualquer autenticado |
| `AdminRequired` | ADMINISTRADOR |
| `EncarregadoRequired` | ENCARREGADO |
| `EncarregadoOuAdmin` | ENCARREGADO, ADMINISTRADOR |
| `InspetorOuAdmin` | INSPETOR, ADMINISTRADOR |
| `ExecucaoPermitida` | MANTENEDOR, ENCARREGADO, ADMINISTRADOR |

**Resultado:** **CONFORME** — A checagem é feita no backend (FastAPI Depends), não no frontend.

---

### ✅ RBAC-02 — Rotas de página também protegidas

**Arquivo:** `app/web/pages/router.py`

Todas as rotas HTML (exceto `/login`) utilizam `Depends(get_current_user)`, garantindo que um acesso direto via URL também requer autenticação. A rota `/configuracoes` usa `AdminRequired`.

**Resultado:** **CONFORME**.

---

### 🟡 RBAC-03 — Visibilidade de UI baseia-se em `localStorage` manipulável

**Arquivo:** `app/web/static/js/auth_check.js` (linhas 69-100)

```javascript
window.hasPermission = function(requiredRole) {
    const userJson = localStorage.getItem("saa29_user");
    const user = JSON.parse(userJson);
    const funcao = user.funcao ? user.funcao.toUpperCase() : '';
    // ...
```

A função `hasPermission()` decide a visibilidade de botões/seções com base no `localStorage`, que é **trivialmente manipulável** via DevTools do navegador. Um MANTENEDOR pode alterar `funcao: "ADMINISTRADOR"` no localStorage e ver botões de admin.

**Mitigação existente:** Todos os endpoints de API verificam o papel no backend — logo, embora o botão apareça, a ação será rejeitada com 403. **O risco é de UI leak, não de bypass funcional.**

**Recomendação:** Considerar injetar `funcao` via variável no template Jinja2 (server-side), eliminando a dependência de localStorage para a renderização inicial.

---

### 🟡 RBAC-04 — Endpoint `PUT /panes/{id}` com RBAC condicional complexo

**Arquivo:** `app/modules/panes/router.py` (linhas 204-236)

```python
async def editar_pane(..., usuario_atual: CurrentUser):
    if dados.descricao is not None or dados.sistema_ata_id is not None:
        ensure_role(usuario_atual, "ENCARREGADO", "INSPETOR", "ADMINISTRADOR")
```

O RBAC é condicional: se o payload contiver apenas `comentarios`, **qualquer** `CurrentUser` (incluindo MANTENEDOR) pode editar. Se contiver `descricao` ou `sistema_ata_id`, exige papéis elevados.

**Risco:** A lógica de "quais campos requerem que papel" está no router, não documentada, e pode divergir conforme o código evolui.

**Recomendação:** Documentar a matriz de permissões por campo ou separar em dois endpoints (`PUT /panes/{id}/comentar` e `PUT /panes/{id}/editar`).

---

### ✅ RBAC-05 — Endpoints administrativos protegidos

Verificação cruzada dos endpoints sensíveis:

| Endpoint | Proteção |
|---|---|
| `POST /auth/usuarios` (criar) | `AdminRequired` ✅ |
| `PUT /auth/usuarios/{id}` (editar) | `AdminRequired` ✅ |
| `DELETE /auth/usuarios/{id}` (desativar) | `AdminRequired` ✅ |
| `PUT /auth/usuarios/{id}/senha` (reset) | `AdminRequired` ✅ |
| `DELETE /panes/{id}` (excluir) | `EncarregadoOuAdmin` ✅ |
| `DELETE /panes/{id}/anexos/{id}` | `EncarregadoOuAdmin` ✅ |
| `GET /configuracoes` (página) | `AdminRequired` ✅ |

**Resultado:** **CONFORME**.

---

## 5. ACHADOS ADICIONAIS (Segurança Geral)

### 🟠 EXTRA-01 — `fim.json` (92 KB) versionado no repositório

**Arquivo:** `fim.json` (rastreado pelo Git)

Este arquivo contém 92 KB de dados estruturados do sistema. Dependendo do conteúdo, pode expor dados operacionais sensíveis.

**Recomendação:** Avaliar se deve ser removido do repositório e adicionado ao `.gitignore`.

---

### 🟡 EXTRA-02 — Usuários de teste com senha fraca no código-fonte

**Arquivo:** `app/modules/auth/service.py` (linha 394)

```python
senha_hash=await asyncio.to_thread(hash_senha, "123456"),
```

Embora protegido por **dois gatilhos** (`APP_ENV=development` + `ENABLE_TEST_USERS=true`), a senha `123456` está hardcoded no código-fonte. Se ambos os gatilhos forem ativados acidentalmente em produção, três contas privilegiadas (encarregado, inspetor, mantenedor) seriam criadas com senha trivial.

**Mitigação existente:** A defesa em profundidade (dois flags) é boa. A `start.sh` também verifica `APP_ENV != production`.

**Recomendação:** Adicionar um terceiro gatilho: rejeitar a criação de test users se `ALLOWED_HOSTS != "*"` (indicador de que o ambiente é real).

---

### ✅ EXTRA-03 — Content Security Policy (CSP) bem configurada

**Arquivo:** `app/shared/middleware/security.py`

```
script-src 'self';     → Nenhum inline JS permitido
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
img-src 'self' data: https://*.r2.cloudflarestorage.com;
```

A CSP bloqueia scripts inline e de terceiros. `unsafe-inline` em styles é necessário para funcionalidades dinâmicas mas não representa risco significativo.

**Resultado:** **CONFORME**.

---

### ✅ EXTRA-04 — Proteção CSRF implementada e funcional

**Arquivo:** `app/shared/middleware/csrf.py`

Middleware custom com `fastapi-csrf-protect`. Todas as mutações (POST/PUT/PATCH/DELETE) são protegidas, incluindo `/auth/login` e `/auth/logout`. O bypass de testes usa um segredo aleatório por processo.

**Resultado:** **CONFORME**.

---

### ✅ EXTRA-05 — Rate Limiting em endpoints sensíveis

| Endpoint | Limite |
|---|---|
| `POST /auth/login` | 5/minuto |
| `POST /auth/refresh` | 20/minuto |
| `PUT /auth/usuarios/senha` | 5/minuto |
| `GET /panes/export` | 10/minuto |

**Resultado:** **CONFORME**.

---

### ✅ EXTRA-06 — JWT com blacklist e refresh token rotation

O sistema implementa:
- Access token de 15 minutos (curto ✅)
- Refresh token de 7 dias com rotation
- Detecção de reuso de refresh token (revoga toda a família)
- Claim atômico via UPDATE condicional (protege contra race condition)
- Blacklist de JTI no banco

**Resultado:** **CONFORME** — Implementação robusta.

---

### ✅ EXTRA-07 — Tokens JWT não são expostos no corpo da resposta

**Arquivo:** `app/modules/auth/router.py` (linhas 114-119)

```python
return schemas.Token(
    access_token="hidden",
    refresh_token="hidden",
    token_type="bearer",
    ...
)
```

Os tokens reais são entregues exclusivamente via cookies `HttpOnly`. O corpo da resposta contém apenas placeholders.

**Resultado:** **CONFORME**.

---

### ✅ EXTRA-08 — Upload de arquivos com validação em profundidade

**Arquivo:** `app/shared/core/file_validators.py`

Pipeline de validação:
1. Verificação de path traversal no nome
2. Whitelist de extensões
3. Detecção de MIME por magic bytes (libmagic ou fallback manual)
4. Cross-check extensão vs conteúdo real
5. Leitura em chunks com limite de tamanho (`ler_upload_com_limite`)

**Resultado:** **CONFORME**.

---

### ✅ EXTRA-09 — Exception handler genérico sanitiza erros

**Arquivo:** `app/shared/core/exceptions.py` (linhas 96-111)

Exceções não tratadas retornam apenas `{"detail": "Erro interno do servidor."}` — sem stack trace, sem detalhes internos para o cliente. O stack trace completo vai apenas para o log do servidor.

**Resultado:** **CONFORME**.

---

## 6. CHECKLIST PRÉ-DEPLOY — AÇÕES OBRIGATÓRIAS

> [!IMPORTANT]
> Complete **todos** os itens abaixo antes de expor a aplicação à internet.

### Ações Bloqueantes (CRÍTICAS)

- [x] **SEC-01:** Remover `.env.backup` do Git (`git rm --cached .env.backup`) e adicionar ao `.gitignore` ✅ *2026-08-09*
- [ ] **SEC-01:** **Revogar e rotacionar TODAS as credenciais Cloudflare R2** (account ID, access key, secret key) ⚠️ *Requer ação manual no painel Cloudflare*
- [x] **SEC-02:** Remover `cookies.txt` do Git (`git rm --cached cookies.txt`) e adicionar ao `.gitignore` ✅ *2026-08-09*
- [x] **SEC-03:** Substituir senha real em `.env.example` por placeholder ✅ *2026-08-09*
- [x] **SEC-04:** Configurar `ALLOWED_HOSTS` e `ALLOWED_ORIGINS` com IP real da VPS ✅ *2026-08-09*

### Ações de Alta Prioridade

- [x] **SEC-05:** Garantir `APP_ENV=production` no `.env` do servidor ✅ *2026-08-09*
- [x] **SEC-05:** Garantir `APP_DEBUG=False` no `.env` do servidor ✅ *2026-08-09*
- [x] **SEC-06:** Garantir `ENABLE_DEV_SEEDS=false` e `ENABLE_TEST_USERS=false` no servidor ✅ *2026-08-09*
- [x] Rotacionar `APP_SECRET_KEY` (gerada nova chave segura de 64 hex chars) ✅ *2026-08-09*
- [x] Rotacionar `DEFAULT_ADMIN_PASSWORD` (gerada nova senha de 32 chars) ✅ *2026-08-09*
- [x] Configurar `FORCE_SECURE_COOKIES=true` no `.env` ✅ *2026-08-09*

### Ações de Média Severidade / Primeiro Sprint

- [x] **PAYLOAD-03:** Removido campo `status` do schema `PaneUpdate` para fechar superfície de ataque via PUT ✅ *2026-08-09*
- [x] **PAYLOAD-05:** Sanitizados dados gravados em `localStorage` no `login.js` e `auth_check.js` para manter apenas o mínimo de metadados de UI ✅ *2026-08-09*
- [x] **RBAC-03:** Sincronização automática dos metadados de UI no `auth_check.js` a partir da resposta validada pelo backend (`/auth/me`), sobrescrevendo adulterações locais no DevTools ✅ *2026-08-09*
- [x] **RBAC-04:** Centralizada validação de permissões de edição de campos em `service.editar_pane` ✅ *2026-08-09*
- [x] **EXTRA-02:** Adicionada trava de segurança estrita em `garantir_usuarios_essenciais` impedindo a criação de usuários de teste em produção ✅ *2026-08-09*
- [x] **EXTRA-01:** Remover `fim.json` do repositório ✅ *2026-08-09*
- [ ] Limpar histórico do Git (BFG Repo-Cleaner) para remover credenciais do passado
- [ ] Configurar HSTS preload após confirmar que HTTPS está funcional

---

## 7. PONTOS FORTES IDENTIFICADOS

O projeto demonstra maturidade de segurança acima da média para código gerado por IA:

1. **JWT HttpOnly cookies** — tokens nunca expostos ao JavaScript
2. **Refresh token rotation com detecção de reuso** — implementação de referência
3. **CSP restritiva** com `script-src 'self'` (zero inline)
4. **CSRF robusto** em todas as mutações, sem exceções
5. **RBAC via Dependencies** — impossível esquecer a checagem
6. **Upload seguro** com magic bytes + cross-check extensão
7. **Rate limiting** nos endpoints sensíveis
8. **Exception handler genérico** que nunca vaza stack trace
9. **Validação de APP_SECRET_KEY** no boot (rejeita chaves fracas/default)
10. **Swagger desabilitado em produção** (condicionado a `app_debug`)

---

*Relatório gerado em 2026-08-09. Próxima auditoria recomendada: após aplicação das correções e antes da exposição pública.*
