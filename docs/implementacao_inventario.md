# Plano de Implementação: Página de Inventário de Equipamentos

Este documento detalha o plano para criar a interface de inventário físico de
equipamentos por aeronave no SAA29, baseada na ficha de inventário (`docs/ficha_inventario.pdf`).

---

## 1. Objetivo

Criar uma nova página acessível pela barra superior de navegação onde o usuário pode:
1. **Visualizar** todos os equipamentos instalados em uma aeronave, com seus Part Numbers (PN), Serial Numbers (SN) e localização (compartimento).
2. **Filtrar** por matrícula da aeronave ou nome do equipamento.
3. **Registrar o campo REAL** — o serial number fisicamente instalado na aeronave aguardando atualização no sistema.

---

## 2. Estado Atual do Backend

> ✅ **O backend já está 100% implementado.** Não será necessário criar modelos, migrações ou lógica de serviço novos.

| Camada | Arquivo | Status |
| :--- | :--- | :---: |
| **Modelos ORM** | `app/equipamentos/models.py` | ✅ Completo |
| **Schemas** | `app/equipamentos/schemas.py` | ✅ Completo |
| **Serviço** | `app/equipamentos/service.py` | ✅ Completo |
| **Router API** | `app/equipamentos/router.py` | ✅ Completo |
| Rota de Página | `app/pages/router.py` | ✅ Completo |
| Template HTML | `templates/inventario.html` | ✅ Incompleto (falta coluna REAL) |
| Ícone na Navbar | `templates/base.html` | ❌ Falta adicionar |

### Endpoints de API Existentes (já funcionais)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/equipamentos/` | Listar todos os tipos de equipamento |
| `POST` | `/equipamentos/` | Cadastrar tipo de equipamento |
| `GET` | `/equipamentos/{id}` | Buscar equipamento por ID |
| `GET` | `/equipamentos/itens/` | Listar itens (filtro opcional por `equipamento_id`) |
| `POST` | `/equipamentos/itens/` | Cadastrar item (herda controles) |
| `POST` | `/equipamentos/itens/{id}/instalar` | Instalar item em aeronave |
| `PATCH` | `/equipamentos/instalacoes/{id}/remover` | Remover item de aeronave |
| `GET` | `/equipamentos/tipos-controle` | Listar tipos de controle |
| `POST` | `/equipamentos/tipos-controle` | Criar tipo de controle |
| `GET` | `/equipamentos/itens/{id}/controles` | Listar controles de um item |
| `PATCH` | `/equipamentos/vencimentos/{id}/executar` | Registrar execução de controle |

### Endpoint Novo Necessário

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/equipamentos/inventario/{aeronave_id}` | **[FUNCIONAL]** Retornar inventário consolidado da aeronave |

Este endpoint deve retornar uma lista de instalações ativas (`data_remocao IS NULL`) com os dados do equipamento e item embarcados (join), evitando N+1 queries no frontend.

---

## 3. Referência Visual: Ficha de Inventário (PDF)

A ficha `docs/ficha_inventario.pdf` define a estrutura de dados organizada por **compartimento/localização**:

### Compartimento Eletrônico

| Item | PN | SN | REAL |
| :--- | :--- | :--- | :--- |
| ADF | 622-7382-101 | — | — |
| DME | 622-7309-101 | — | — |
| TDR | 622-9352-004 | — | — |
| STORMSCOPE | 78-8060-6086-5 | — | — |
| EGIR | 34200802-80RB | — | — |
| VOR | 622-7194-201 | — | — |
| MDP1 | MA902B-02 | — | — |
| MDP2 | MA902B-02 | — | — |
| ARTU | 251-118-012-012 | — | — |
| AFDC | 449100-02-01 | — | — |
| VUHF1 | 6110.3001.12 | — | — |
| VUHF2 | 6106.7006.12 | — | — |

### Posto Dianteiro (1P)

| Item | PN | SN | REAL |
| :--- | :--- | :--- | :--- |
| AMPLIF. MIC 1P | 263-000 | — | — |
| PDU | 4455-1000-01 | — | — |
| UFCP | 4456-1000-02 | — | — |
| CMFD1 | MB387B-01 | — | — |
| CMFD2 | MB387B-01 | — | — |
| GPS | 066-04031-1622 | — | — |
| DVR | MB211E-03 | — | — |

### Posto Traseiro (2P)

| Item | PN | SN | REAL |
| :--- | :--- | :--- | :--- |
| AMPLIF. MIC 2P | 263-000 | — | — |
| PSU | 4458-1000-00 | — | — |
| CMFD3 | MB387B-01 | — | — |
| CMFD4 | MB387B-01 | — | — |
| ASP 2P | 343-001 | — | — |

### Comp. ELT/OBOGS

| Item | PN | SN | REAL |
| :--- | :--- | :--- | :--- |
| VADR | 174521-10-01 | — | — |
| ELT | 453-5000-710 | — | — |

---

## 4. Modelo de Dados para Localização

O campo `sistema` da tabela `slots_inventario` será utilizado como **compartimento/localização** para agrupar os itens na ficha. Os valores seguem a nomenclatura técnica abreviada:

| Sigla | Localização Completa |
| :--- | :--- |
| `CEI` | Compartimento Eletrônico Inferior |
| `1P` | Posto Dianteiro (1P) |
| `2P` | Posto Traseiro (2P) |
| `CES` | Compartimento Eletrônico Superior |

> O campo `sistema` (String 50, nullable) já existe no modelo ORM. Não é necessário criar migração.

---

## 5. Plano de Implementação

### Fase 1: Endpoint de Inventário Consolidado

**Objetivo:** Criar um endpoint otimizado que retorne o inventário completo de uma aeronave em uma única query.

#### Passo 1.1 — Criar schema de resposta
- **Arquivo:** `app/equipamentos/schemas.py`
- **Ação:** Adicionar schema `InventarioItemOut`:

```python
class InventarioItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Dados do equipamento (tipo)
    equipamento_nome: str
    part_number: str
    sistema: str | None          # Localização/compartimento

    # Dados do item (instância física)
    numero_serie: str
    status_item: StatusItem

    # Dados da instalação
    instalacao_id: uuid.UUID
    data_instalacao: date

    # Campo REAL (a ser preenchido pelo usuário)
    serial_real: str | None = None
```

#### Passo 1.2 — Criar função no serviço
- **Arquivo:** `app/equipamentos/service.py`
- **Ação:** Adicionar `listar_inventario_aeronave(db, aeronave_id)`:
  - Query com JOIN: `instalacoes` → `itens_equipamento` → `equipamentos`
  - Filtro: `instalacoes.data_remocao IS NULL` e `instalacoes.aeronave_id = ?`
  - Ordenação: `equipamentos.sistema`, `equipamentos.nome`

#### Passo 1.3 — Criar rota na API
- **Arquivo:** `app/equipamentos/router.py`
- **Ação:** Adicionar:

```python
@router.get(
    "/inventario/{aeronave_id}",
    response_model=list[InventarioItemOut],
    summary="Inventário de equipamentos instalados em uma aeronave",
)
```

**Estimativa:** ~1 hora

---

### Fase 2: Template HTML (Página de Inventário)

**Objetivo:** Criar a interface de visualização do inventário seguindo os padrões visuais existentes.

#### Passo 2.1 — Criar template
- **Arquivo:** `templates/inventario.html`
- **Base:** Estende `base.html` (mesma estrutura de `panes/lista.html`)
- **Layout:**

```
┌───────────────────────────────────────────────────────┐
│  [Dropdown: Aeronave]  [Input: Buscar equipamento]    │
├───────────────────────────────────────────────────────┤
│  COMPARTIMENTO ELETRÔNICO                             │
│  ┌─────────┬─────────────────┬──────────┬───────────┐ │
│  │  Item   │       PN        │    SN    │   REAL    │ │
│  ├─────────┼─────────────────┼──────────┼───────────┤ │
│  │  ADF    │ 622-7382-101    │ SN-00123 │ [input]   │ │
│  │  DME    │ 622-7309-101    │ SN-00456 │ [input]   │ │
│  └─────────┴─────────────────┴──────────┴───────────┘ │
│                                                       │
│  POSTO DIANTEIRO (1P)                                 │
│  ┌─────────┬─────────────────┬──────────┬───────────┐ │
│  │  Item   │       PN        │    SN    │   REAL    │ │
│  │  ...    │  ...            │  ...     │  ...      │ │
│  └─────────┴─────────────────┴──────────┴───────────┘ │
└───────────────────────────────────────────────────────┘
```

#### Funcionalidades da página:
1. **Dropdown de Aeronave:** Lista as aeronaves ativas (mesmo padrão de `panes/lista.html`).
2. **Campo de busca:** Filtra localmente (JavaScript) por nome do equipamento.
3. **Agrupamento por `sistema`:** Os itens são agrupados visualmente por compartimento, com um cabeçalho de seção para cada grupo.
4. **Coluna REAL:** Campo de input editável onde o usuário pode digitar o serial number real observado na aeronave.
5. **Cores de destaque:**
   - 🟢 Verde: `SN == REAL` (conferido e correto)
   - 🟡 Amarelo: `REAL` vazio (pendente de verificação)
   - 🔴 Vermelho: `SN != REAL` (divergência detectada)

#### Passo 2.2 — JavaScript da página
- Ao selecionar uma aeronave (ex: 5916) no dropdown, faz `GET /equipamentos/inventario/{aeronave_id}`
- Agrupa os resultados por `sistema` e renderiza as seções
- Implementa filtro por texto (debounce de 250ms, mesmo padrão das panes)
- A coluna REAL é apenas visual/local nesta fase (sem persistência no banco)

**Estimativa:** ~2 horas

---

### Fase 3: Navegação (Ícone na Navbar)

**Objetivo:** Adicionar o ícone de inventário na barra superior, ao lado dos ícones existentes.

#### Passo 3.1 — Adicionar ícone em `base.html`
- **Arquivo:** `templates/base.html`
- **Posição:** Dentro do `<nav id="admin-nav">`, após o ícone de Efetivo (linha 61)
- **Ícone sugerido:** Clipboard/checklist (SVG inline, mesmo padrão dos demais)

```html
<a href="/inventario" class="btn-icon" aria-label="Inventário" title="Inventário"
    style="width: 38px; height: 38px; {% if request.url.path == '/inventario' %}color: var(--primary-color); background: var(--bg-tertiary); border-color: var(--primary-color);{% endif %}">
    <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4">
        </path>
    </svg>
</a>
```

#### Passo 3.2 — Adicionar rota de página
- **Arquivo:** `app/pages/router.py`
- **Ação:** Adicionar:

```python
@router.get("/inventario", response_class=HTMLResponse, include_in_schema=False)
async def inventario_page(request: Request):
    """Visualização do Inventário de Equipamentos por Aeronave"""
    return templates.TemplateResponse("inventario.html", {"request": request})
```

**Estimativa:** ~30 minutos

---

### Fase 4: Carga Inicial de Dados (Seed)

**Objetivo:** Popular o banco com os equipamentos e itens da ficha de inventário para que a página tenha dados para exibir.

#### Passo 4.1 — Criar script de seed de equipamentos
- **Arquivo:** `scripts/seed_equipamentos.py`
- **Ação:** Inserir os equipamentos listados na ficha com suas respectivas localizações:

| Nome | Part Number | Sistema |
| :--- | :--- | :--- |
| ADF | 622-7382-101 | CEI |
| DME | 622-7309-101 | CEI |
| TDR | 622-9352-004 | CEI |
| STORMSCOPE | 78-8060-6086-5 | CEI |
| EGIR | 34200802-80RB | CEI |
| VOR | 622-7194-201 | CEI |
| MDP1 | MA902B-02 | CEI |
| MDP2 | MA902B-02 | CEI |
| ARTU | 251-118-012-012 | CEI |
| AFDC | 449100-02-01 | CEI |
| VUHF1 | 6110.3001.12 | CEI |
| VUHF2 | 6106.7006.12 | CEI |
| AMPMIC 1P | 263-000 | 1P |
| PDU | 4455-1000-01 | 1P |
| UFCP | 4456-1000-02 | 1P |
| CHVC | VEC00054 | 1P |
| CMFD1 | MB387B-01 | 1P |
| CMFD2 | MB387B-01 | 1P |
| ASP 1P | 343-001 | 1P |
| GPS | 066-04031-1622 | 1P |
| PA CONTROL | 449300-02-01 | 1P |
| PIC/NAV | 314-04895-403 | 1P |
| PUNHO DO MANCHE 1P | 733-0402 | 1P |
| DVR | MB211E-03 | 1P |
| AMPMIC 2P | 263-000 | 2P |
| PSU | 4458-1000-00 | 2P |
| CMFD3 | MB387B-01 | 2P |
| CMFD4 | MB387B-01 | 2P |
| ASP 2P | 343-001 | 2P |
| PUNHO DO MANCHE 2P | 733-0402 | 2P |
| VADR | 174521-10-01 | CES |
| ELT | 453-5000-710 | CES |
| BEACON | 8888-8888 | CES |

> **Nota:** Como os PNs são do tipo de equipamento (não do item), cada aeronave terá sua própria instância (ItemEquipamento) com SN único.

**Estimativa:** ~1 hora

---

## 6. Ordem de Execução Recomendada

```mermaid
graph LR
    A[Fase 4: Seed de Dados] --> B[Fase 1: Endpoint API]
    B --> C[Fase 3: Navbar + Rota]
    C --> D[Fase 2: Template HTML]
```

| Ordem | Fase | Justificativa |
| :---: | :--- | :--- |
| 1º | **Fase 4** — Seed de equipamentos | Ter dados reais para testar o endpoint |
| 2º | **Fase 1** — Endpoint de inventário | Garantir que a API retorna os dados corretos |
| 3º | **Fase 3** — Navbar + Rota de página | Preparar a navegação |
| 4º | **Fase 2** — Template HTML | Montar a interface consumindo a API |

---

## 7. Estimativa Total de Esforço

| Fase | Descrição | Tempo |
| :---: | :--- | :--- |
| 1 | Endpoint de inventário (schema + service + router) | ~1 hora |
| 2 | Template HTML (inventário + filtros + agrupamento) | ~2 horas |
| 3 | Navbar + rota de página | ~30 minutos |
| 4 | Seed de dados (equipamentos da ficha) | ~1 hora |
| — | **Total** | **~4,5 horas** |

---

## 8. Evolução Futura (Não implementar agora)

- **Persistência do campo REAL:** Criar coluna `serial_real` na tabela `instalacoes` para salvar o valor digitado pelo usuário, permitindo comparações históricas.
- **Exportação para PDF:** Gerar uma versão impressa da ficha de inventário no formato do PDF original.
- **Controle de Vencimentos na UI:** Adicionar badges de vencimento (OK/VENCENDO/VENCIDO) ao lado de cada item no inventário.
- **Histórico de movimentações:** Mostrar o log de instalações/remoções de cada item.

---

*Documento criado em 18 de abril de 2026 como plano de implementação do módulo de inventário do SAA29.*
