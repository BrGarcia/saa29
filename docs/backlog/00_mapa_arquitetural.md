# 🗺️ Mapa Arquitetural — SAA29

> **Propósito:** documento de contexto compartilhado para as sessões de revisão descritas em
> `docs/backlog/revisor.md`. Uma sessão que vai revisar `app/modules/<MODULO>/` lê este arquivo
> primeiro e evita redescobrir stack, camadas e convenções gastando contexto — e tem uma base
> objetiva para julgar o item **F.6** do checklist ("divergência de padrão entre módulos").
>
> **Verificado em:** 03/08/2026, contra o branch `refactor/fable5-otimizacao-codigo`
> (commit `6e6dd2b`). Toda contagem abaixo vem de leitura de arquivo ou `grep`/`wc` sobre `app/`
> — nenhuma foi inferida de outra documentação. Os comandos usados estão na nota de rodapé §10,
> para reauditoria quando o código mudar.
>
> **Escopo:** estrutura, camadas, dependências e convenções — visão de "voo de pássaro".
> **Fora de escopo:** correção funcional linha a linha (isso é trabalho de cada sessão de
> revisão por módulo, conforme `revisor.md`).

---

## 1. Visão geral

SAA29 é um **monolito modular** em FastAPI para gestão de manutenção aeronáutica (frota A-29).
A cadeia de execução real de uma requisição é:

```
Cliente → Router FastAPI (app/modules/<m>/router.py)
        → Service (app/modules/<m>/service.py)
        → Model SQLAlchemy (app/modules/<m>/models.py)
        → SQLite (via engine assíncrona)
```

**Desvio relevante em relação ao `INICIO.MD`:** o documento normativo (§3 e §7) descreve uma
camada `repositories/` entre service e model. **Ela não existe em nenhum módulo** — todo
service acessa `db.execute(select(...))` diretamente. Isso não é um achado de revisão a
corrigir: é o padrão de fato consolidado no projeto inteiro (100% dos módulos), e nenhuma
sessão de revisão deve reportá-lo como bug isolado do módulo que está olhando. Se for para
mudar, é uma decisão de arquitetura transversal, fora do escopo de uma sessão por módulo.

---

## 2. Responsabilidade de cada módulo (`app/modules/`)

| Módulo | Responsabilidade | Prefixo HTTP | Linhas totais | Endpoints | Tabelas ORM |
|---|---|---|---:|---:|---|
| `auth` | Usuários, hashing de senha, JWT (access+refresh), blacklist, RBAC | `/auth` | 1.239 | 11 | `usuarios`, `token_blacklist`, `token_refresh` |
| `aeronaves` | Cadastro e status operacional da frota | `/aeronaves` | 499 | 5 | `aeronaves` |
| `panes` | Ciclo de vida de panes, anexos (upload/imagem), responsáveis, sistemas ATA | `/panes` | 1.839 | 14 | `sistemas_ata`, `panes`, `anexos`, `pane_responsaveis` |
| `equipamentos` | Catálogo de modelos, slots de inventário, itens por N/S, instalações, importação XLSX | `/equipamentos` | 1.672 | 18 | `modelos_equipamento`, `slots_inventario`, `itens_equipamento`, `instalacoes` |
| `vencimentos` | Controles temporais de manutenção, herança de regras, prorrogação | `/vencimentos` | 930 | 11 | `tipos_controle`, `equipamento_controles`, `controle_vencimentos`, `prorrogacoes_vencimento` |
| `inspecoes` | Tipos de inspeção, catálogo/template de tarefas, execução, geração de PDF | `/inspecoes` | 2.432 | 26 | `tipos_inspecao`, `tarefas_catalogo`, `tarefas_template`, `inspecao_evento_tipos`, `inspecoes`, `inspecao_tarefas` |
| `calendario` | Tipos de evento e eventos de calendário com visibilidade por papel (RBAC) | `/api/v1/calendario` | 728 | 8 | `event_types`, `calendar_events` |
| `dashboard` | Agregação read-only de métricas dos demais módulos | `/dashboard` | 389 | 1 | *(nenhuma — só leitura)* |
| `efetivo` | Indisponibilidades do efetivo (férias, dispensa, folga, serviço) | `/efetivo` | 159 | 4 | (modelo em módulo próprio, ligado a `usuarios`) |
| `encarregado` | **Casca vazia** — só `__init__.py` com docstring de intenção, sem router/model/service | — | 3 | 0 | — |

`inspecoes` e `panes` são, de longe, os módulos mais pesados (2.432 e 1.839 linhas) — se uma
sessão de revisão tiver que dividir um módulo em duas passadas por limite de contexto, são os
dois candidatos.

Total de endpoints no sistema: **117** (100 em `app/modules/*/router.py` + 17 em
`app/web/pages/` servindo HTML/Jinja2).

---

## 3. Camadas de cada módulo e como se comunicam

Layout canônico observado na maioria dos módulos:

```
models.py   → entidades SQLAlchemy (Base declarativa em app/bootstrap/database.py)
schemas.py  → contratos Pydantic (entrada/saída)
service.py  → regras de negócio, único ponto de acesso ao ORM
router.py   → endpoints FastAPI, "thin controller" (nominal — ver §6)
```

Módulos que se desviam desse layout:

- **`dashboard`**: não tem `models.py` — é 100% agregação, lendo modelos de `aeronaves`,
  `equipamentos`, `inspecoes`, `panes` e `vencimentos` diretamente no `service.py`.
- **`encarregado`**: não tem nenhuma das quatro camadas.
- **`inspecoes`**: camada extra `pdf_service.py` (893 linhas, ReportLab) para geração de
  ordens de inspeção e checklists em PDF.
- **`equipamentos`**: camada extra `xlsx_service.py` (239 linhas, openpyxl) para importação de
  inventário via planilha — mesma necessidade de "camada de import/export extra" que
  `inspecoes` tem, resolvida com nome e forma diferentes (ver §6).
- **`auth`**: duas camadas extras — `security.py` (JWT/bcrypt puro, sem acesso a banco) e
  `roles.py` (catálogo de papéis como constantes `frozenset`).

### Fronteira de transação (contrato de sessão)

`get_db()` (`app/bootstrap/dependencies.py:20-38`) abre uma `AsyncSession`, dá `yield` para o
handler, e faz **`commit()` automaticamente ao final da request** (com `rollback()` em
exceção). O padrão esperado, portanto, é que services usem `await db.flush()` para persistir
dentro da mesma unidade de trabalho e deixem o commit final para a dependency.

Na prática, isso não é uniforme — **6 dos 9 services de domínio também chamam `db.commit()`
diretamente**, dentro do próprio service:

| Service | `flush()`+`commit()` (chamadas) |
|---|---:|
| `inspecoes/service.py` | 18 |
| `panes/service.py` | 13 |
| `auth/service.py` | 11 |
| `vencimentos/service.py` | 10 |
| `equipamentos/service.py` | 9 |
| `calendario/service.py` | 6 |
| `aeronaves/service.py` | 6 (só `flush`, nunca `commit` direto) |
| `efetivo/service.py` | 2 |
| `dashboard/service.py` | 0 (read-only) |

Além disso, **2 routers fazem `commit()` diretamente** (`auth/router.py:51,182`), fora de
qualquer service. Isso é registrado aqui como fato do projeto, não como veredito — mas é o eixo
com maior potencial de bug de concorrência/corrupção, e cada sessão de revisão deveria
verificar se o `commit()` extra do seu módulo é redundante (inofensivo) ou esconde um commit
parcial fora da transação da request.

---

## 4. Dependências entre módulos

Mapeadas a partir de ~170 imports internos (`from app....` dentro de `app/modules` e
`app/shared`). Três classes:

**a) Infra (esperado, não é acoplamento de domínio):** todo módulo importa de
`app/bootstrap/{database,dependencies,config}` e `app/shared/core/*`.

**b) Cross-module por *model* (leitura/agregação):**
- `dashboard.service` → models de `aeronaves`, `equipamentos`, `inspecoes`, `panes`, `vencimentos`
- `vencimentos.service` e `inspecoes.pdf_service` → `equipamentos.models`
- `panes.schemas` → `aeronaves.schemas` + `auth.schemas`
- `calendario.service` → `auth.models` + `auth.roles`

**c) Cross-module por *service* (acoplamento funcional real):**
- `equipamentos.service` → `vencimentos.service.criar_controles_para_item`
- `inspecoes.service` → `panes.service.sincronizar_status_aeronave`
- `panes.service` → `aeronaves.service.buscar_aeronave` + `auth.service.buscar_por_id`
- `aeronaves.service` → `inspecoes.service.STATUS_ATIVOS`
- `auth.service` → `efetivo.models.Indisponibilidade`

### Ciclo de dependência

`aeronaves → inspecoes → panes → aeronaves` fecha um ciclo. Ele só "funciona" porque **todos
esses imports são feitos dentro de função** (lazy import), não no topo do módulo — evita
`ImportError` de import circular no boot, mas o acoplamento real continua lá, apenas adiado
para o momento da chamada. Qualquer refatoração que mova uma dessas funções para o topo do
arquivo quebra o boot da aplicação inteira sem aviso prévio no code review.

`app/shared/contracts.py` define `AeronaveLookupProtocol` — um `Protocol` justamente para
desacoplar esse tipo de dependência via interface (DDD). **Nenhum módulo o implementa ou o
usa.** É abstração morta hoje; se uma sessão de revisão for mexer no ciclo acima, este é o
mecanismo já pensado para a correção, não algo a inventar do zero.

**Inversão notável:** `app/shared/core/helpers.py`, que por estar em `shared/` deveria ser
importável por qualquer módulo sem criar acoplamento, importa `auth.models.Usuario` e
`aeronaves.models.Aeronave` — ou seja, "shared" depende de "domínio", não o contrário.

---

## 5. Padrões que divergem entre módulos

Esta é a seção-chave para o item **F.6** do checklist de `revisor.md`. Todas as contagens são
literais (comando no rodapé), não impressão de leitura.

| Eixo | O que diverge |
|---|---|
| **Erro de domínio no service** | `inspecoes` (38×) e `equipamentos` (12×) usam as exceções tipadas de `app/shared/core/exceptions.py` (`domain_exc.EntidadeNaoEncontradaError` etc.). `panes` (19×), `calendario` (13×) e `aeronaves` (12×) ainda fazem `raise ValueError(...)` cru. `calendario` inventou um **terceiro dialeto**: `LookupError` + `PermissionError` nativos do Python, nenhum dos dois usado em outro módulo. |
| **Tradução de erro no router** | A maioria mapeia `ValueError`/exceção de domínio para status HTTP de forma direta. `aeronaves/router.py` faz *string-matching* em português — `"não encontrada" in detail.lower()` — para decidir entre 404 e 409, o que quebra silenciosamente se a mensagem do service mudar de texto. |
| **RBAC no endpoint** | 8 dos 9 routers de domínio usam os atalhos `Annotated` de `app/bootstrap/dependencies.py` (`AdminRequired`, `EncarregadoOuAdmin`, `ExecucaoPermitida`, ...) direto na assinatura. `panes/router.py` é o único que chama `ensure_role(usuario, ...)` imperativamente dentro do corpo do handler (7 ocorrências) em vez de na assinatura. |
| **Acesso a banco fora do service** | `INICIO.MD` §8 proíbe SQL fora de repository/service. Ainda assim: `auth/router.py` executa `db.execute`/`db.add`/`db.commit` diretamente em ~7 pontos (fluxo de login/refresh/logout); `panes/router.py` executa 5 blocos de `db.execute` (contagem de panes/inspeções ativas e um `UPDATE` de status de aeronave, ver §7 item 4); `equipamentos/router.py:92` faz um `select(SlotInventario)` direto no handler. |
| **Serialização de resposta** | A maioria chama `Schema.model_validate(objeto_orm)` explicitamente antes de retornar. `calendario/router.py` devolve o objeto ORM cru e deixa o FastAPI serializar via `response_model` — funciona, mas é o único módulo que faz assim. |
| **Rate limiting** | `INICIO.MD` §7 pede rate limit em toda criação de endpoint. Na prática, `@limiter.limit(...)` existe em **1 único endpoint de todo o sistema** — `auth/router.py:36` (login). Upload de anexos, exportação de relatórios e todos os outros 116 endpoints não têm. |
| **Prefixo de rota** | Todo módulo usa `/<nome-do-modulo>` como prefixo — exceto `calendario`, montado em `/api/v1/calendario`. Essa assimetria já causou um bug real e documentado (comentário em `app/shared/core/exceptions.py:44-58`): um 401 em `/api/v1/calendario` virava redirect 307 para `/login` em vez de JSON, porque a lista de prefixos de API estava hardcoded e desatualizada em dois lugares. Hoje corrigida com `API_PREFIXES` como fonte única em `app/bootstrap/main.py:50-53`, mas o prefixo continua sendo a única exceção ao padrão. |
| **Packaging** | `app/modules/vencimentos/` é o único módulo de domínio sem `__init__.py`. |

---

## 6. Stack confirmada lendo o código

Onde `requirements.txt`/docs e código divergirem, vale o código — o que segue foi lido, não
copiado de outra documentação.

- **Pydantic:** v2.10.4 (`requirements.txt`), uso **consistente** em todo o projeto —
  `ConfigDict(from_attributes=True)` (9 ocorrências) e `@field_validator`/`@model_validator`
  em `schemas.py` de `calendario`, `equipamentos` e em `bootstrap/config/__init__.py`.
  **Zero ocorrências** de `class Config`, `orm_mode` ou `@validator` (API v1) em toda a base —
  não há mistura v1/v2 (item **C.1** do checklist do `revisor.md`: verificado, resultado
  negativo, não é achado).
- **ORM:** SQLAlchemy 2.0.36, **assíncrono de ponta a ponta** —
  `create_async_engine`/`async_sessionmaker` em `app/bootstrap/database.py`, driver
  `aiosqlite`. Os 117 endpoints do sistema são `async def`; não há nenhum `def` síncrono
  misturado (itens **A.1–A.3** do checklist: verificado, resultado negativo).
- **Banco:** SQLite com PRAGMAs `foreign_keys=ON`, `journal_mode=WAL`, `synchronous=NORMAL` e
  `busy_timeout=15000` (`app/bootstrap/database.py:47-65` — o valor de 15s foi calibrado
  experimentalmente contra os escritores concorrentes de background, conforme comentário no
  próprio arquivo).
- **Autenticação:** cadeia real em `app/bootstrap/dependencies.py`:
  `get_token_from_request` (header `Authorization: Bearer` **ou** cookie `saa29_token`, nessa
  ordem) → `decodificar_token` (JWT HS256, `app/modules/auth/security.py`) → checagem
  `payload["type"] == "access"` (bloqueia uso de refresh token como access) → consulta de
  blacklist por `jti` no banco (1 query) → `buscar_por_username` (2ª query) → checagem
  `usuario.ativo`. Access token expira em 15 min, refresh em 7 dias, refresh em cookie
  HttpOnly. RBAC via `require_role(*roles)`, comparando `usuario.funcao` (string) contra os
  papéis exigidos — com **duas fontes canônicas coexistindo**: o catálogo
  `app/modules/auth/roles.py` (`ALL_FUNCTIONS`, `PRIVILEGED_FUNCTIONS`, `ADMIN_FUNCTIONS`) e o
  enum `TipoPapel` em `app/shared/core/enums.py`. Nenhum dos dois referencia o outro.
- **Middlewares** (ordem real de execução na request — que é a **inversa** da ordem de
  `add_middleware` em `app/bootstrap/main.py`, por como o Starlette empilha middlewares):
  `SecurityHeadersMiddleware` → `CSRFMiddleware` → `TrustedHostMiddleware` → `CORSMiddleware`.
- **Migrações:** Alembic, 24 revisões em `migrations/versions/`.
- **Rate limit:** SlowAPI, `Limiter` desabilitado quando `APP_ENV=testing`
  (`app/shared/core/limiter.py`).
- **Upload/Storage:** abstração `StorageService` (local ou Cloudflare R2), validação de
  MIME via `python-magic` com fallback, pipeline de imagem (Pillow + pillow-heif + imgdiet).

---

## 7. Riscos estruturais visíveis sem leitura detalhada

Riscos de nível arquitetural — cada um aponta para o módulo onde a sessão de revisão
correspondente deveria investigar a fundo, mas nenhum foi investigado linha a linha aqui.

1. **Ciclo de dependência `aeronaves ↔ inspecoes ↔ panes`** mascarado por imports dentro de
   função (§4). Frágil a qualquer refatoração que promova esses imports para o topo do arquivo.
2. **Fronteira de transação ambígua** (`flush` do service vs. `commit` automático da
   dependency vs. `commit` manual em 6 services e 2 routers, §3) — o eixo com maior
   probabilidade de bug de corrupção/estado parcial sob concorrência.
3. **`INICIO.MD` promete uma camada `repositories/` que nunca existiu** (§1). Um documento
   normativo divergente do código real é fonte garantida de falso-positivo em revisão.
4. **Regra de negócio dentro do router:** `panes/router.py:50-64`, no handler
   `criar_pane`, executa um `UPDATE` de status de aeronave direto via SQLAlchemy como
   "safety net" — comentário no próprio código admite que é para cobrir cache de ORM,
   duplicando lógica que deveria estar inteiramente em `service.py`.
5. **Rate limiting em 1 de 117 endpoints** — upload de anexos e exportação de relatórios
   (potencialmente custosos) não têm nenhum limite.
6. **`app/shared/contracts.py`** define um protocolo de desacoplamento (`AeronaveLookupProtocol`)
   que zero módulos implementam — abstração morta, não solução ativa para o ciclo do item 1.
7. **Inversão de camada em `shared/`:** `app/shared/core/helpers.py` importa models de domínio
   (`auth`, `aeronaves`) — o que deveria ser genérico depende do específico.
8. **`__init__.py` ausente** em `app/shared/`, `app/bootstrap/`, `app/modules/` (nível
   intermediário) e `app/modules/vencimentos/`. Funciona hoje via namespace packages implícitos
   do Python 3, mas deixa o comportamento de import dependente de como o processo é iniciado
   (`sys.path`), o que é frágil em scripts avulsos ou ferramentas de terceiros.
9. **`app/brain/<uuid>/scratch/`** — diretório de scratch de ferramenta de IA versionado
   dentro de `app/`, junto do código-fonte de produção.
10. **`encarregado`** é um módulo fantasma: existe como pacote no domínio, mas não tem router,
    model, schema nem service — qualquer import de `app.modules.encarregado` além do
    `__init__.py` falha.

---

## 8. Divergências encontradas em `docs/architecture/overview.md`

Registradas para decisão posterior — **este mapa não altera `overview.md`**.

- A árvore de `app/modules/` no overview lista apenas `auth`, `aeronaves`, `equipamentos`,
  `inspecoes` e `panes` — **omite `vencimentos`, `calendario`, `dashboard` e `efetivo`**, todos
  ativos e registrados no bootstrap.
- A seção "Bootstrap da Aplicação" descreve o `main.py` montando "routers de `auth`,
  `aeronaves`, `equipamentos`, `panes` e das páginas HTML" — incompleta frente aos 9 routers de
  domínio hoje registrados em `app/bootstrap/main.py:137-149`.
- Afirma "o router não acessa o banco diretamente" como regra do fluxo de requisição — ver §5/§6
  acima: 3 routers (`auth`, `panes`, `equipamentos`) o fazem hoje.

---

## Notas de rodapé — reprodutibilidade das contagens

Comandos usados para gerar as tabelas acima (rodar da raiz do repo):

```bash
# linhas totais e endpoints por módulo
for m in auth aeronaves panes equipamentos vencimentos inspecoes calendario dashboard efetivo encarregado; do
  find app/modules/$m -name "*.py" -not -path "*__pycache__*" -exec wc -l {} \; | awk '{s+=$1} END{print s+0}'
  grep -h "^@router\." app/modules/$m/router.py 2>/dev/null | wc -l
done

# tabelas ORM por módulo
grep -h "__tablename__" app/modules/<m>/models.py

# domain_exc vs ValueError cru por service
grep -rc "domain_exc\." app/modules/*/service.py
grep -rc "raise ValueError" app/modules/*/service.py

# commit/flush por service
grep -rc "await db.commit()\|await db.flush()" app/modules/*/service.py

# imports internos completos
grep -rn "^from app\.\|^import app\.\|    from app\." app/modules app/shared app/web --include=*.py
```
