# Plano de Implementação: Dashboard Central — SAA29

> **Versão:** 1.0 | **Data:** 2026-05-04 | **Branch sugerida:** `feat/dashboard`
> **Metodologia:** TDD (Test-Driven Development) | **Banco de Dados:** Read-only (sem DDL)

---

## 1. Visão Geral e Objetivos

O Dashboard é o **Centro de Comando** do SAA29. Sua missão é consolidar as informações mais críticas da operação em uma única tela, substituindo a página de listagem de panes (`/panes`) como tela inicial para **todos os perfis de usuário**.

### 1.1 Princípios Arquiteturais

| Princípio | Decisão |
|---|---|
| **Isolamento** | Módulo independente em `app/modules/dashboard/` sem dependências circulares nos outros módulos |
| **Zero DDL** | Apenas queries `SELECT` sobre as tabelas existentes. Nenhuma migration necessária |
| **TDD First** | Testes unitários escritos **antes** do `service.py` |
| **Separação de Camadas** | `service.py` (queries puras) → `schemas.py` (contratos Pydantic) → `router.py` (endpoint REST) → `dashboard.html` + `dashboard.js` (UI) |
| **Página Principal** | Rota `/` redirecionada para `/dashboard` para todos os usuários autenticados |

---

## 2. Inventário de Dados por Card (Queries Planejadas)

Todas as queries são **somente-leitura** sobre as tabelas já existentes. **Nenhuma migration será criada.**

### 2.1 Card: Panes (Prioridade 1 — Destaque máximo)

**Fonte:** Tabela `panes` (modelo `Pane`)

| Dado | Query SQLAlchemy | Campo do Modelo |
|---|---|---|
| Total abertas | `COUNT(*) WHERE status='ABERTA' AND ativo=True` | `Pane.status`, `Pane.ativo` |
| Total resolvidas no mês atual | `COUNT(*) WHERE status='RESOLVIDA' AND data_conclusao >= início_mês` | `Pane.data_conclusao` |
| 5 panes mais antigas (abertas) | `ORDER BY data_abertura ASC LIMIT 5` com eager-load de `aeronave` | `Pane.data_abertura`, `Pane.aeronave.matricula` |

**Exibição:** 2 cards numéricos grandes (Abertas / Resolvidas no mês) + lista das 5 mais antigas + botão "Registrar Pane" (visível para todos os roles).

---

### 2.2 Card: Vencimentos (Prioridade 2)

**Fonte:** Tabela `controle_vencimentos` (modelo `ControleVencimento`)

| Dado | Query | Campo do Modelo |
|---|---|---|
| Contagem por status | `GROUP BY status` | `ControleVencimento.status` |

**Exibição:** 4 badges coloridos (Verde=OK, Amarelo=A Vencer, Vermelho=Vencido, Roxo=Prorrogado). Clique → `/vencimentos`.

---

### 2.3 Card: Inspeções em Andamento (Prioridade 3)

**Fonte:** Tabelas `inspecoes` JOIN `aeronaves` JOIN `inspecao_evento_tipos` → `tipos_inspecao`

| Dado | Query | Campo do Modelo |
|---|---|---|
| Inspeções abertas/em_andamento | `WHERE status IN ('ABERTA', 'EM_ANDAMENTO')` | `Inspecao.status` |
| Matrícula da aeronave | `selectinload(Inspecao.aeronave)` | `Aeronave.matricula` |
| Tipos aplicados | `selectinload(Inspecao.tipos_aplicados)` | `TipoInspecao.codigo` |
| DPE | `Inspecao.data_fim_prevista` | campo direto |

**Exibição:** Chips/badges clicáveis com matrícula + tipo de inspeção. Cada chip → detalhes da inspeção.

---

### 2.4 Card: Inventário — Últimas Movimentações (Prioridade 4)

**Sugestão:** Exibir as **5 últimas movimentações** de inventário como mini-feed de atividade.

**Fonte:** Tabela `historico_movimentacoes` (ou equivalente) JOIN `itens_equipamento` JOIN `aeronaves`

> ⚠️ **Ação necessária:** Verificar o nome exato da tabela de histórico de movimentações no modelo de `equipamentos`. Adaptar a query se necessário. Se não houver tabela de histórico, exibir os **5 itens mais recentemente instalados** (`ItemEquipamento` com `status='ATIVO'` ordenado por `created_at DESC`).

**Exibição:** Feed de 5 itens com ícone de ação, nome do equipamento, aeronave e data.

---

### 2.5 Card: Frota (Prioridade 5)

**Fonte:** Tabela `aeronaves` (modelo `Aeronave`)

| Dado | Query | Campo do Modelo |
|---|---|---|
| Contagem por status | `GROUP BY status` | `Aeronave.status` |

**Exibição:** Chips com contadores por status. Clique → `/frota`.

---

## 3. Estrutura de Arquivos do Módulo

```
app/modules/dashboard/
├── __init__.py         # Vazio (marca o pacote)
├── router.py           # GET /dashboard/resumo (JSON)
├── schemas.py          # DashboardResumo e sub-schemas Pydantic
└── service.py          # 5 funções de consulta ao banco (puras, sem lógica HTTP)

app/web/pages/router.py
└── [MODIFICAR] Adicionar rota GET /dashboard (HTML) e alterar redirect de /

app/web/templates/
└── dashboard.html      # Jinja2 (extends base.html)

app/web/static/js/
└── dashboard.js        # Fetch /dashboard/resumo, renderização dos cards

app/bootstrap/main.py
└── [MODIFICAR] Registrar dashboard_router

tests/unit/
└── test_dashboard.py   # Testes TDD — escritos ANTES do service.py
```

---

## 4. Contratos de API — Schemas Pydantic

```python
# app/modules/dashboard/schemas.py

from pydantic import BaseModel

class PaneCritica(BaseModel):
    id: str
    matricula: str
    sistema: str | None
    data_abertura: str  # ISO format

class PanesSummary(BaseModel):
    total_abertas: int
    total_resolvidas_mes: int
    panes_criticas: list[PaneCritica]

class VencimentosSummary(BaseModel):
    ok: int
    vencendo: int
    vencido: int
    prorrogado: int

class InspecaoAtiva(BaseModel):
    inspecao_id: str
    matricula: str
    tipos: list[str]         # ex: ["50h", "PS"]
    status: str
    data_fim_prevista: str | None

class MovimentacaoRecente(BaseModel):
    descricao: str           # ex: "VUHF instalado"
    aeronave_matricula: str | None
    data: str                # ISO format

class FrotaSummary(BaseModel):
    disponivel: int
    indisponivel: int
    inspecao: int
    estocada: int
    inativa: int
    operacional: int

class DashboardResumo(BaseModel):
    panes: PanesSummary
    vencimentos: VencimentosSummary
    inspecoes_ativas: list[InspecaoAtiva]
    movimentacoes_recentes: list[MovimentacaoRecente]
    frota: FrotaSummary
```

---

## 5. Plano TDD — Ciclos Red → Green → Refactor

> **Regra:** O arquivo `tests/unit/test_dashboard.py` deve ser criado e todos os testes devem estar **em estado RED (falhando)** antes de qualquer linha do `service.py` ser escrita.

### Ciclo 1 — Panes Summary

```python
async def test_panes_summary_retorna_contagens_corretas(db):
    # Arrange: criar 3 panes ABERTA + 2 RESOLVIDA no mês atual
    # Act: resultado = await service.get_panes_summary(db)
    # Assert:
    assert resultado.total_abertas == 3
    assert resultado.total_resolvidas_mes == 2
    assert len(resultado.panes_criticas) <= 5

async def test_panes_summary_banco_vazio_retorna_zeros(db):
    resultado = await service.get_panes_summary(db)
    assert resultado.total_abertas == 0
    assert resultado.total_resolvidas_mes == 0
    assert resultado.panes_criticas == []

async def test_panes_criticas_ordenadas_por_data_mais_antiga(db):
    # Assert: primeira pane da lista é a mais antiga
    assert resultado.panes_criticas[0].data_abertura < resultado.panes_criticas[1].data_abertura
```

### Ciclo 2 — Vencimentos Summary

```python
async def test_vencimentos_summary_agrupa_por_status(db):
    # Arrange: criar itens com status VENCIDO=1, VENCENDO=2, OK=3
    # Assert:
    assert resultado.vencido == 1
    assert resultado.vencendo == 2
    assert resultado.ok == 3

async def test_vencimentos_summary_sem_dados(db):
    resultado = await service.get_vencimentos_summary(db)
    assert resultado.ok == 0
    assert resultado.vencido == 0
```

### Ciclo 3 — Inspeções Ativas

```python
async def test_inspecoes_ativas_retorna_apenas_abertas_e_em_andamento(db):
    # Arrange: criar 1 ABERTA, 1 EM_ANDAMENTO, 1 CONCLUIDA, 1 CANCELADA
    resultado = await service.get_inspecoes_ativas(db)
    assert len(resultado) == 2

async def test_inspecoes_ativas_inclui_matricula_e_tipos(db):
    # Assert:
    assert resultado[0].matricula == "5902"
    assert len(resultado[0].tipos) > 0
```

### Ciclo 4 — Frota Summary

```python
async def test_frota_summary_conta_por_status(db):
    # Arrange: aeronaves com status variados
    resultado = await service.get_frota_summary(db)
    assert resultado.disponivel >= 0
    assert resultado.inspecao >= 0
```

### Ciclo 5 — Endpoint REST

```python
async def test_get_dashboard_resumo_retorna_200(client_autenticado):
    response = await client_autenticado.get("/dashboard/resumo")
    assert response.status_code == 200
    data = response.json()
    assert "panes" in data
    assert "vencimentos" in data
    assert "inspecoes_ativas" in data
    assert "movimentacoes_recentes" in data
    assert "frota" in data

async def test_dashboard_requer_autenticacao(client):
    response = await client.get("/dashboard/resumo")
    assert response.status_code in [401, 403]

async def test_dashboard_todos_roles_tem_acesso(client_autenticado):
    # Verificar que mantenedor, encarregado, inspetor e admin recebem 200
    response = await client_autenticado.get("/dashboard/resumo")
    assert response.status_code == 200
```

---

## 6. Plano de Implementação em Fases

### Fase 1 — Fundação e Testes (TDD) `[✅ CONCLUÍDA — 2026-05-04]`

- [x] Criar branch `feat/dashboard` a partir de `development`
- [x] Criar `app/modules/dashboard/__init__.py`
- [x] Criar `app/modules/dashboard/schemas.py` (contratos primeiro)
- [x] Criar `tests/unit/test_dashboard.py` com **todos os testes** (estado RED confirmado: `ModuleNotFoundError`)
- [x] Implementar `app/modules/dashboard/service.py` (tornar testes GREEN)
- [x] Rodar `pytest tests/unit/test_dashboard.py -k "not endpoint"` — **15/15 PASSED** ✅

> **Resultado:** 15 testes de service passando. 3 testes de endpoint aguardam a Fase 2 (router inexistente → 404 esperado).
> **Commit:** `feat(dashboard): Fase 1 — schemas, service e testes TDD (15/15 GREEN)`

### Fase 2 — Camada de API `[⏳ PRÓXIMA]`

- [ ] Criar `app/modules/dashboard/router.py` com `GET /dashboard/resumo`
- [ ] Registrar o router em `app/bootstrap/main.py`
- [ ] Adicionar rota de página `GET /dashboard` em `app/web/pages/router.py`
- [ ] Alterar redirect de `/` para `/dashboard` (era `/panes`) em `app/web/pages/router.py`
- [ ] Rodar `pytest tests/unit/test_dashboard.py` — confirmar **18/18 PASSED** (incluindo os 3 testes de endpoint)

### Fase 3 — Interface (UI) `[Sprint 2]`

- [ ] Criar `app/web/templates/dashboard.html` (extends `base.html`)
- [ ] Criar `app/web/static/js/dashboard.js`
- [ ] Adicionar link "Dashboard" na barra de navegação em `base.html`
- [ ] Marcar o link como ativo visualmente via JS quando na página `/dashboard`
- [ ] Validar design: modo claro e escuro, cards responsivos

### Fase 4 — Polimento `[Sprint 2]`

- [ ] Skeleton loaders nos cards enquanto dados carregam
- [ ] Animações suaves de entrada (CSS `@keyframes`)
- [ ] Auto-refresh a cada 5 minutos (`setInterval`)
- [ ] Responsividade mobile (grid adaptável)
- [ ] Acessibilidade: `aria-label` nos cards e botões

---

## 7. Design Visual e UX

### 7.1 Layout de Grid (Prioridade Visual)

```
┌─────────────────────────────────────────────────────────────────┐
│  🚨 PANES (Largura total, destaque máximo)                      │
│  [ 3 Abertas ]  [ 12 Resolvidas no mês ]  [+ Registrar Pane]   │
│  Lista: A-29 5902 | AVIÔNICA | Aberta há 5 dias                 │
├──────────────────────────┬──────────────────────────────────────┤
│  ⚠️  VENCIMENTOS         │  🔍 INSPEÇÕES EM ANDAMENTO           │
│  ✅ OK:  45              │  [A-29 5902 — 50h] [A-29 5914 — PS]  │
│  🟡 A vencer: 3          │  Clique em cada chip vai aos detalhes │
│  🔴 Vencido: 1           │                                       │
│  🟣 Prorrogado: 2        │                                       │
├──────────────────────────┼──────────────────────────────────────┤
│  📦 INVENTÁRIO (feed)    │  ✈️  FROTA                           │
│  VUHF inst. em FAB 5902  │  DISP: 15 | INDISP: 3 | INSP: 2     │
│  GPS rem. de FAB 5914    │  ESTOC: 0  | INATIVA: 0              │
└──────────────────────────┴──────────────────────────────────────┘
```

### 7.2 Paleta de Cores por Card

| Card | Cor Header | Justificativa |
|---|---|---|
| Panes | `var(--status-danger)` vermelho | Máxima criticidade operacional |
| Vencimentos | `var(--status-warning)` amarelo | Atenção moderada/preventiva |
| Inspeções | `#1abc9c` verde-água | Já associada ao módulo no sistema |
| Inventário | `var(--primary-color)` azul | Informativo neutro |
| Frota | `var(--status-ok)` verde | Status operacional positivo |

### 7.3 Acessibilidade por Role

> O Dashboard é **100% read-only e universal**. Todos os cards e dados são visíveis para todos os perfis. A diferença entre roles está **nos botões de ação** (ex: "Registrar Pane" — já permitido a todos).

---

## 8. Dependências e Impacto

### Arquivos Modificados (fora do módulo)

| Arquivo | Modificação | Risco |
|---|---|---|
| `app/bootstrap/main.py` | +4 linhas: import e include_router | ⬜ Baixo |
| `app/web/pages/router.py` | +1 rota `/dashboard`, muda redirect `/` | ⬜ Baixo |
| `app/web/templates/base.html` | +1 link na nav | ⬜ Baixo |

### Dependências de Runtime (sem novas instalações)

- `sqlalchemy` (já instalado) — queries async
- `pydantic` (já instalado) — schemas
- `fastapi` (já instalado) — router

---

## 9. Arquivo .ctx para LLMs

Ver `docs/BACKLOG/dashboard.ctx` — Intermediate Representation (IR) para uso em prompts de LLMs.

---

## 10. Critérios de Aceite

- [ ] `/` redireciona para `/dashboard` após login bem-sucedido
- [ ] Dashboard carrega em < 1 segundo com banco populado
- [ ] Todos os 5 cards exibem dados reais do banco
- [ ] Clicar em qualquer card/elemento navega para o módulo correto
- [ ] Botão "Registrar Pane" visível para todos os perfis
- [ ] Suite `tests/unit/test_dashboard.py` passa com 100% das funções testadas
- [ ] Zero novas tabelas ou colunas criadas no banco de dados
- [ ] Funciona em modo escuro e claro
- [ ] Aprovado visualmente com dados de seed (`init_local.py`)

---

## 11. Status da Implementação

| Componente | Arquivo | Status |
|---|---|---|
| Branch | `feat/dashboard` | ✅ Criada |
| Testes TDD | `tests/unit/test_dashboard.py` | ✅ 15/15 GREEN (service) |
| Schemas | `app/modules/dashboard/schemas.py` | ✅ Concluído |
| Service | `app/modules/dashboard/service.py` | ✅ Concluído |
| Router API | `app/modules/dashboard/router.py` | ⏳ Fase 2 |
| Registro no App | `app/bootstrap/main.py` | ⏳ Fase 2 |
| Rota de Página + Redirect | `app/web/pages/router.py` | ⏳ Fase 2 |
| Template HTML | `app/web/templates/dashboard.html` | ⏳ Fase 3 |
| JavaScript | `app/web/static/js/dashboard.js` | ⏳ Fase 3 |
| Link na Nav | `app/web/templates/base.html` | ⏳ Fase 3 |
| Arquivo IR (.ctx) | `docs/BACKLOG/dashboard.ctx` | ✅ Concluído |

---

## 12. Log de Execução

| Data | Fase | Ação | Resultado |
|---|---|---|---|
| 2026-05-04 | Planejamento | Criação do plano e arquivo `.ctx` | ✅ Publicado em `development` |
| 2026-05-04 | Fase 1 | Criação da branch `feat/dashboard` | ✅ |
| 2026-05-04 | Fase 1 | Schemas Pydantic (`schemas.py`) | ✅ 6 schemas definidos |
| 2026-05-04 | Fase 1 | Suite de testes TDD (`test_dashboard.py`) | ✅ RED confirmado |
| 2026-05-04 | Fase 1 | Service layer (`service.py`) | ✅ GREEN: 15/15 passed |
| 2026-05-04 | Fase 1 | Commit na branch `feat/dashboard` | ✅ `9f7f064` |
