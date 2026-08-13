# 📋 Feature: Módulo Encarregado — Ciência e Acompanhamento de Alterações

> **Versão:** 2.0 (Revisada e Corrigida contra o Schema Real)
> **Data:** 2026-08-12
> **Autor:** Arquitetura de Software SAA29
> **Status:** 🟢 Implementado — backend, frontend e testes (`tests/unit/test_encarregado.py`, 8/8) concluídos; migration `3dd0faeb4666_add_encarregado_ciencias` aplicada no banco local
> **Prioridade:** Média
> **Substitui:** `docs/backlog/resolvidos/modulo_auth/feature_encarregado_alteracoes_pendentes.md` e `..._plano.md` — especificados em 26/07/2026, arquivados em `resolvidos/` durante a reorganização de documentação (commit `49000ed`) **sem terem sido implementados**. `app/modules/encarregado/` contém hoje apenas um `__init__.py` com docstring de intenção (commit `77652c4`) — confirmado como "casca vazia" em `docs/backlog/00_mapa_arquitetural.md` §2.

---

## 1. Visão Geral

### 1.1 Problema

O Encarregado precisa transcrever manualmente, para o **SILOMS** (sistema interno de manutenção da FAB), as alterações operacionais que os Mantenedores já registraram no SAA29: panes resolvidas, tarefas de inspeção concluídas, trocas de componentes no inventário e atualizações de vencimento. Hoje isso exige varrer quatro telas separadas (`/panes`, `/inspecoes`, `/inventario`, `/vencimentos`) sem nenhuma marcação do que já foi transcrito — o controle de "o que falta lançar no SILOMS" é mental ou em papel, e nada impede duplicidade ou esquecimento.

### 1.2 Solução Proposta

Um módulo novo, **exclusivamente de leitura sobre os módulos de origem**, que agrega as quatro categorias de alteração em uma única página de cards empilhados, ordenados por data, com um botão de "visto" ao lado de cada item. Marcar o visto remove o item da lista de pendentes — sinalizando que o Encarregado já transcreveu aquela alteração para o SILOMS.

> **Princípio de Design:** **Desacoplamento e Consulta Não-Destrutiva.** O módulo nunca escreve, atualiza ou apaga qualquer linha das tabelas de origem (`panes`, `inspecao_tarefas`, `instalacoes`, `controle_vencimentos` e suas trilhas de histórico). A única escrita do módulo é na sua própria tabela de controle de ciência — mesmo padrão de isolamento usado pelo módulo `pedidos` (RN-PED01) em relação a `equipamentos`/`vencimentos`.

### 1.3 Por que o "visto" precisa de uma tabela (mudança em relação à v1.0 arquivada)

A especificação original (`feature_encarregado_alteracoes_pendentes.md`, item [RESTRIÇÕES]) lia "não deve realizar alterações no banco de dados" como proibição de *qualquer* escrita, e o plano correspondente resolveu isso persistindo o visto em `localStorage` do navegador (`saa29_encarregado_vistos`).

Essa leitura foi revista nesta versão. `localStorage` é por navegador, não por usuário: o visto não acompanha o Encarregado entre o PC do esquadrão e o celular, some ao limpar o cache, e não deixa rastro de quem deu ciência nem quando — inclusive dificultando saber se foi o Encarregado certo. Como o módulo já lida com informação sensível a auditoria (SILOMS é um sistema oficial), a decisão nesta v2.0 é:

- **A restrição correta é:** nenhuma escrita nas tabelas dos módulos de origem (panes, inspeções, inventário, vencimentos).
- **A única exceção:** uma tabela própria do módulo Encarregado, que registra apenas *quem deu ciência de qual alteração e quando* — nunca altera o registro de origem em si.

Isso preserva o espírito da restrição (a "verdade operacional" de cada módulo permanece intocada) e resolve o problema real (visto persistente, auditável, e compartilhado entre dispositivos).

---

## 2. Esclarecimentos e Correções sobre o Esboço Original

O esboço do usuário e o plano de julho/2026 continham suposições sobre o schema que não se confirmam no código atual. Correções aplicadas nesta versão:

| # | Suposição original | Realidade no schema | Ajuste |
|---|---|---|---|
| 1 | Vencimentos: consultar `ControleVencimento` "com atualizações recentes" | `controle_vencimentos` **não tem `updated_at`** (`app/modules/vencimentos/models.py:67-90`) — guarda só o estado corrente, não histórico | Usar as duas trilhas append-only: `execucoes_vencimento_historico` (campo `registrado_em`) e `prorrogacoes_vencimento` (campo `created_at`, `ativo=True`) |
| 2 | Inventário: uma alteração = uma linha | `instalacoes` produz **dois eventos possíveis**: instalação (`created_at`) e remoção (`removido_em`), no mesmo registro | Introduzir um discriminador `evento` (`INSTALACAO`/`REMOCAO`) na chave de ciência — senão vistar a instalação esconderia também a remoção futura da mesma linha |
| 3 | "[PANES] Pane não-programada concluída" | O modelo `Pane` não distingue programada/não-programada — no SAA29 **toda** pane é não-programada por definição (o contraponto programado é o módulo `inspecoes`) | Manter como esclarecimento textual no card, não como filtro de query |
| 4 | Vencimentos: aeronave do item | Não há FK direta de `controle_vencimentos` para aeronave | Resolver via `controle_vencimentos.item_id → itens_equipamento → instalacoes (WHERE data_remocao IS NULL) → aeronave`; item sem instalação ativa exibe `ESTOQUE` |
| 5 | Trigrama sempre presente | `instalacoes.usuario_id`, `controle_vencimentos.executado_por_id`, `inspecao_tarefas.executado_por_id` são **nullable** | Fallback `—` no card quando ausente |
| 6 | — | `panes.ativo` (soft delete) não era mencionado | Excluir `ativo=False` de todas as queries de panes |

---

## 3. Modelo de Dados

### 3.1 Tabela `encarregado_ciencias`

| Campo | Tipo | Restrições | Descrição |
|---|---|---|---|
| `id` | UUID | PK | Identificador do registro de ciência |
| `categoria` | String(20) | NOT NULL, index | `PANES` \| `INSPECAO` \| `INVENTARIO` \| `VENCIMENTOS` |
| `evento` | String(20) | NOT NULL | Discriminador do tipo de evento: `CONCLUSAO`, `EXECUCAO`, `INSTALACAO`, `REMOCAO`, `PRORROGACAO` |
| `registro_id` | String(36) | NOT NULL, index | UUID (como texto) do registro de origem — **sem FK**, por design (ver §1.2) |
| `usuario_id` | UUID | FK `usuarios.id` RESTRICT, NOT NULL | Quem deu ciência |
| `dado_em` | DateTime(tz) | NOT NULL, default `func.now()` | Quando a ciência foi registrada |

`UniqueConstraint("categoria", "evento", "registro_id", name="uq_encarregado_ciencia_evento_unico")`.

A ciência é **global** (não por usuário): uma vez registrada, o item some da lista de pendentes para todos os usuários, e a própria linha guarda quem/quando dela deu ciência — não é necessário compor a chave com `usuario_id`.

Não usar PK composta com colunas nullable — mesmo cuidado documentado em `publicacoes_favoritos` (`app/modules/publicacoes/models.py:494-540`), que é o precedente estrutural mais próximo (relação per-registro, PK surrogate + `UniqueConstraint`).

### 3.2 Enums (`app/shared/core/enums.py`)

```python
class CategoriaCiencia(str, enum.Enum):
    """Categoria de origem de uma alteração pendente de ciência do Encarregado."""
    PANES = "PANES"
    INSPECAO = "INSPECAO"
    INVENTARIO = "INVENTARIO"
    VENCIMENTOS = "VENCIMENTOS"


class EventoCiencia(str, enum.Enum):
    """Tipo de evento dentro de uma categoria — discrimina registros da
    mesma linha de origem que geram mais de um evento (ex.: instalacoes)."""
    CONCLUSAO = "CONCLUSAO"        # Pane resolvida
    EXECUCAO = "EXECUCAO"          # Tarefa de inspeção concluída / vencimento executado
    INSTALACAO = "INSTALACAO"      # Componente instalado
    REMOCAO = "REMOCAO"            # Componente removido
    PRORROGACAO = "PRORROGACAO"    # Vencimento prorrogado
```

### 3.3 Modelo ORM (`app/modules/encarregado/models.py`)

```python
"""
app/modules/encarregado/models.py
Modelo ORM da ciência de alterações do Encarregado.

EncarregadoCiencia é a ÚNICA tabela de escrita deste módulo. Não possui FK
para panes/inspecao_tarefas/instalacoes/controle_vencimentos por design —
o módulo consulta essas tabelas apenas em leitura (service.py) e nunca as
referencia estruturalmente, para garantir que nenhuma migração ou exclusão
nos módulos de origem possa quebrar o histórico de ciência.
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Usuario


class EncarregadoCiencia(Base):
    __tablename__ = "encarregado_ciencias"
    __table_args__ = (
        UniqueConstraint("categoria", "evento", "registro_id", name="uq_encarregado_ciencia_evento_unico"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    categoria: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    evento: Mapped[str] = mapped_column(String(20), nullable=False)
    registro_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False,
    )
    dado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    usuario: Mapped["Usuario"] = relationship(lazy="select")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<EncarregadoCiencia categoria={self.categoria!r} evento={self.evento!r} registro={self.registro_id}>"
```

---

## 4. Fontes de Dados por Categoria

Cada categoria é resolvida por uma função própria em `service.py`, seguindo o padrão de agregação já usado por `app/modules/dashboard/service.py` (que também lê models de outros módulos) e inspirado em `listar_historico_recente` (`app/modules/equipamentos/service.py:732`, `union_all` de instalação + remoção). A diferença estrutural: aqui a query precisa de **anti-join contra `encarregado_ciencias`** e do corte de janela **antes** do `LIMIT`, para não truncar a lista descartando itens que na verdade já foram vistados.

| Categoria | Origem | Filtro | Timestamp do evento | Card (formato do esboço original) |
|---|---|---|---|---|
| **PANES** | `panes` | `status = RESOLVIDA`, `ativo = True` | `data_conclusao` | `[AERONAVE] [DESCRICAO] [OBSERVACAO_CONCLUSAO] [TRIGRAMA]` |
| **INSPECAO** | `inspecao_tarefas` join `inspecoes` (aeronave) | `status = CONCLUIDA` | `data_execucao` | `[AERONAVE] [TITULO] [TRIGRAMA]` |
| **INVENTARIO** | `instalacoes` (2 eventos por linha) | evento `INSTALACAO`: sempre; evento `REMOCAO`: `data_remocao IS NOT NULL AND removido_em IS NOT NULL` | `created_at` (instalação) / `removido_em` (remoção) | `[AERONAVE] [SLOT] [SN SAIU] [SN ENTROU] [TRIGRAMA]` |
| **VENCIMENTOS** | `execucoes_vencimento_historico` + `prorrogacoes_vencimento` (ambas via `controle_vencimentos → itens_equipamento`) | prorrogações: `ativo = True` | `registrado_em` / `created_at` | `[AERONAVE] [EQUIPAMENTO] [TIPO CONTROLE] [NOVO VENCIMENTO] [TRIGRAMA]` |

Notas de resolução:

- **Aeronave em Vencimentos** é indireta: `controle_vencimentos.item_id → itens_equipamento.id → instalacoes (WHERE data_remocao IS NULL) → aeronave`. Item sem instalação ativa no momento (em estoque) exibe `ESTOQUE` no lugar da matrícula.
- **"SN que saiu"** em Inventário é derivado: a instalação anterior no mesmo `(aeronave_id, slot_id)`, com `data_remocao` preenchida e anterior à `data_instalacao` da linha corrente. Se não houver instalação anterior no slot, exibir `—` (slot estava vago).
- **Trigrama ausente** (`usuario_id`/`executado_por_id` nulo): exibir `—`.
- Cada linha resultante recebe `registro_id = str(<pk_da_linha_de_origem>)` e o `evento` correspondente da tabela §3.2 — essa dupla é a chave usada no anti-join contra `encarregado_ciencias`.

---

## 5. Regras de Negócio

| ID | Regra |
|---|---|
| RN-ENC-01 | Item pendente = evento ocorrido nos últimos **90 dias** para o qual não existe linha em `encarregado_ciencias` com o mesmo `(categoria, evento, registro_id)` (anti-join `NOT EXISTS`, aplicado antes do corte de quantidade). |
| RN-ENC-02 | Teto de **100 itens por categoria** por resposta, ordenados por data do evento decrescente. |
| RN-ENC-03 | Dar ciência é **idempotente**: repetir a chamada para um item já vistado retorna 200 com o registro existente, não 409. |
| RN-ENC-04 | É possível **desfazer** uma ciência (o item volta a aparecer como pendente) — mitiga erro de clique. |
| RN-ENC-05 | O módulo nunca escreve, atualiza ou apaga linhas em `panes`, `inspecao_tarefas`, `instalacoes`, `controle_vencimentos`, `execucoes_vencimento_historico` ou `prorrogacoes_vencimento`. A única tabela de escrita é `encarregado_ciencias`. |
| RN-ENC-06 | Panes com `ativo = False` (soft delete) não entram no feed. |

---

## 6. RBAC

> **Princípio:** leitura ampla (todo usuário autenticado pode ver o que está pendente de ciência — útil inclusive para o Mantenedor conferir se o que fez já foi transcrito), escrita restrita a quem de fato dá a ciência.

| Ação | Perfis Permitidos | Dependência Backend |
|---|---|---|
| Listar alterações pendentes | Todos autenticados | `CurrentUser` |
| Dar ciência (POST) | ENCARREGADO, ADMINISTRADOR | `EncarregadoOuAdmin` (`app/bootstrap/dependencies.py:151`) |
| Desfazer ciência (DELETE) | ENCARREGADO, ADMINISTRADOR | `EncarregadoOuAdmin` |

> **Ponto revisável:** restringir a escrita a `EncarregadoOuAdmin` é uma decisão desta especificação, não um requisito explícito do usuário — a leitura foi definida como aberta a todos, mas a ação de "dar ciência" só faz sentido operacional para quem de fato transcreve para o SILOMS. Se o Inspetor também tiver essa responsabilidade em algum esquadrão, trocar por `EncarregadoInspetorOuAdmin` (já existe pronta em `dependencies.py:159`) é uma mudança de uma linha.

---

## 7. Estrutura de Arquivos

```text
app/modules/encarregado/
├── __init__.py       [JÁ EXISTE]
├── models.py          [NOVO] — EncarregadoCiencia
├── schemas.py          [NOVO] — AlteracaoPendenteItem, DarCienciaRequest, CienciaOut
├── service.py          [NOVO] — listar_pendentes(), dar_ciencia(), desfazer_ciencia()
└── router.py           [NOVO] — GET/POST/DELETE sob /api/v1/encarregado

app/web/
├── pages/router.py                    [EDITAR] — rota de página /encarregado
├── templates/encarregado.html         [NOVO]
├── templates/base.html                [EDITAR] — ícone no <nav id="admin-nav">
└── static/js/encarregado.js           [NOVO]

app/shared/core/enums.py               [EDITAR] — CategoriaCiencia, EventoCiencia
app/bootstrap/main.py                  [EDITAR] — import de models, registro do router, API_PREFIXES
migrations/versions/                   [NOVO] — CREATE TABLE encarregado_ciencias
tests/unit/test_encarregado.py         [NOVO]
```

### Registro em `app/bootstrap/main.py`

Três pontos de edição, todos já existentes no arquivo:

1. **Import do model** (bloco "Registro do SQLAlchemy — Ordem importa", linhas 16-25): adicionar `import app.modules.encarregado.models`.
2. **Registro do router**: `from app.modules.encarregado.router import router as encarregado_router` + `app.include_router(encarregado_router, prefix="/api/v1/encarregado", tags=["Encarregado"])`.
3. **`API_PREFIXES`** (linha 57): adicionar `"/api/v1/encarregado/"`. **Crítico** — sem essa entrada, o exception handler global não reconhece a rota como API, e um 401 devolve redirect 307 para `/login` em vez de JSON (o mesmo bug já documentado ali no comentário sobre o calendário).

### Ordem recomendada de execução

1. Enums (`enums.py`)
2. Model (`models.py`) + migration Alembic
3. Schemas (`schemas.py`)
4. Service (`service.py`) — uma função por categoria + agregador + `dar_ciencia`/`desfazer_ciencia`
5. Router (`router.py`)
6. Bootstrap (`main.py`) — os 3 pontos acima
7. Página (`pages/router.py`) + template + JS
8. Navegação (`base.html`)
9. Testes

---

## 8. API REST

### 8.1 Endpoints

| Método | Rota | Permissão | Descrição |
|---|---|---|---|
| GET | `/api/v1/encarregado/pendentes` | `CurrentUser` | Lista alterações pendentes de ciência, agrupadas por categoria |
| POST | `/api/v1/encarregado/ciencia` | `EncarregadoOuAdmin` | Registra ciência de um item (`categoria`, `evento`, `registro_id`) |
| DELETE | `/api/v1/encarregado/ciencia/{id}` | `EncarregadoOuAdmin` | Desfaz uma ciência já registrada |

### 8.2 Schemas Pydantic (`schemas.py`)

```python
class AlteracaoPendenteItem(BaseModel):
    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str
    aeronave_matricula: str | None  # None só é esperado se a origem realmente não resolver aeronave
    titulo: str            # descrição sucinta (1ª linha do card)
    detalhe: str | None    # 2ª linha do card (solução, SN, novo vencimento)
    responsavel_trigrama: str | None
    data_evento: datetime

class ListaPendentesResponse(BaseModel):
    total: int
    itens_por_categoria: dict[CategoriaCiencia, list[AlteracaoPendenteItem]]

class DarCienciaRequest(BaseModel):
    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str

class CienciaOut(BaseModel):
    id: uuid.UUID
    categoria: CategoriaCiencia
    evento: EventoCiencia
    registro_id: str
    usuario_trigrama: str | None
    dado_em: datetime
```

---

## 9. Interface do Usuário

Página `/encarregado`, seguindo o layout Jinja2 + vanilla JS + CSS do restante do sistema (`{% extends "base.html" %}`), com binding de eventos 100% em JS externo (RN-16, CSP proíbe `onclick` inline).

| Elemento | Descrição |
|---|---|
| Contador no topo | Total de pendências e subtotal por categoria |
| Abas/seções por categoria | `[PANES]`, `[INSPEÇÃO]`, `[INVENTÁRIO]`, `[VENCIMENTOS]` — cards empilhados dentro de cada uma |
| Card | Compacto: título (1 linha), detalhe (1 linha), trigrama do responsável, data do evento, botão de visto (ícone check) |
| Botão de visto | Ao clicar: `POST /api/v1/encarregado/ciencia`; sucesso → animação de colapso do card e atualização do contador |
| "Desfazer" (toast/undo) | Após vistar, uma ação temporária de desfazer chama `DELETE /api/v1/encarregado/ciencia/{id}` |
| Estado vazio | Mensagem "Nenhuma alteração pendente de ciência" por categoria sem itens |

Nenhum botão de cópia ou exportação — a página serve apenas para visualizar e vistar, conforme decidido pelo usuário.

---

## 10. Plano de Testes

`tests/unit/test_encarregado.py`, seguindo o padrão de fixtures de `tests/conftest.py`:

1. **Agregação por categoria:** criar via fixture uma pane resolvida, uma tarefa de inspeção concluída, uma instalação e uma remoção, uma execução de vencimento e uma prorrogação ativa. Chamar `GET /pendentes` e validar que os 6 eventos aparecem com os campos corretos (incluindo o discriminador `evento` distinguindo instalação de remoção da mesma linha).
2. **Janela de 90 dias:** evento com `data_evento` fora da janela não aparece.
3. **Ciência oculta o item:** `POST /ciencia` seguido de `GET /pendentes` — o item some da lista.
4. **Idempotência (RN-ENC-03):** `POST /ciencia` duas vezes para o mesmo `(categoria, evento, registro_id)` retorna 200 nas duas, sem 409, e não duplica linha em `encarregado_ciencias`.
5. **Desfazer (RN-ENC-04):** `DELETE /ciencia/{id}` faz o item reaparecer em `/pendentes`.
6. **RBAC:** usuário MANTENEDOR consegue `GET /pendentes` mas recebe 403 em `POST /ciencia`; usuário não autenticado recebe 401.
7. **Read-only (RN-ENC-05):** snapshot dos módulos de origem antes/depois de exercitar o fluxo completo — nenhuma tabela de origem sofre alteração.
8. **Soft delete de panes (RN-ENC-06):** pane resolvida com `ativo=False` não aparece em `/pendentes`.

Como o banco local de desenvolvimento hoje tem zero eventos qualificáveis (0 panes concluídas, 0 tarefas executadas, 0 remoções, 0 execuções de vencimento), os testes dependem inteiramente de fixtures — não há dado de seed reaproveitável.

---

## 11. Riscos e Armadilhas Conhecidas

- **Colisão de prefixo de rota:** a API vive em `/api/v1/encarregado` (padrão do calendário) e a página em `/encarregado`; usar `/encarregado` cru como prefixo de API colidiria com a rota HTML. A entrada em `API_PREFIXES` precisa ser exatamente `"/api/v1/encarregado/"`.
- **CSP (RN-16):** nenhum script inline, nenhum atributo `onclick` no template — todo binding de evento do botão de visto via `encarregado.js`.
- **Migração em banco ativo:** seguir `docs/ia/CTX.md` — backup do `saa29_local.db` antes de aplicar a migration. A migration é puramente aditiva (`CREATE TABLE`), sem tocar tabelas existentes.
- **Anti-join antes do LIMIT:** aplicar o filtro de "sem ciência" e a janela de 90 dias antes do `LIMIT 100`, nunca depois — paginar primeiro e filtrar depois esconderia itens pendentes reais atrás de itens já vistados mais recentes.
- **Duplo evento por linha em `instalacoes`:** sem o discriminador `evento` na chave de ciência, vistar a instalação de um componente também ocultaria (incorretamente) sua remoção futura, porque ambas compartilham o mesmo `registro_id`.

---

## 12. Critérios de Aceite

- [ ] Existe uma página própria em `/encarregado` para o módulo.
- [ ] A página lista apenas alterações pendentes de visto (RN-ENC-01), com janela de 90 dias e teto de 100 itens por categoria (RN-ENC-02).
- [ ] Os itens aparecem em cards empilhados, separados pelas 4 categorias do esboço original: PANES, INSPEÇÃO, INVENTÁRIO, VENCIMENTOS.
- [ ] Cada card usa o formato de campos especificado no esboço original (§4 desta especificação).
- [ ] Cada item exibe um botão de visto visual, que registra ciência via `POST /api/v1/encarregado/ciencia`.
- [ ] É possível desfazer uma ciência dada por engano (RN-ENC-04).
- [ ] Nenhuma ação do módulo altera dados persistidos nas tabelas de origem (`panes`, `inspecao_tarefas`, `instalacoes`, `controle_vencimentos` e trilhas de histórico) — verificado por teste de snapshot (RN-ENC-05).
- [ ] A leitura é acessível a qualquer usuário autenticado; dar/desfazer ciência é restrito a ENCARREGADO/ADMINISTRADOR (§6).
- [ ] `"/api/v1/encarregado/"` está presente em `API_PREFIXES` (`app/bootstrap/main.py`).
- [ ] Suite de testes de `tests/unit/test_encarregado.py` cobre os 8 casos do §10, 100% passando.
- [ ] O módulo atende ao objetivo de apoio operacional ao lançamento posterior no SILOMS.
