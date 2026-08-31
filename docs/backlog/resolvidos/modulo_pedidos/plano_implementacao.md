# 📋 Plano de Implementação — Módulo Central de Pedidos

> **Versão:** 2.0
> **Data:** 2026-08-10
> **Referência:** `docs/backlog/resolvidos/modulo_pedidos/feature_controle_pedidos.md` (v2.0, desacoplada de INVENTÁRIO/VENCIMENTOS)
> **Status:** ✅ Implementado e em produção (arquivado em 2026-08-31) — backend, frontend e migração entregues; 28 testes automatizados cobrindo o módulo (`tests/unit/test_pedidos.py`).
> **Escopo deste documento:** passo a passo técnico para implementar o módulo `pedidos` do zero, ancorado nos padrões reais já existentes no repositório (o módulo `panes` é a referência de estilo mais próxima).

> ⚠️ **Nota de coordenação:** este módulo é novo (`app/modules/pedidos/` nunca existiu no histórico do repositório), mas várias etapas tocam arquivos **compartilhados** com o restante do sistema (`app/shared/core/enums.py`, `app/bootstrap/main.py`, `migrations/env.py`, `app/web/templates/base.html`, `app/web/pages/router.py`). Se houver outra equipe trabalhando em paralelo no repositório, revisar o §14 (Riscos) antes de abrir PR — em especial o número de revisão do Alembic, que pode ter mudado.

---

## 0. Visão do que será construído

Ao final deste plano, o sistema terá:

- Uma tabela `pedidos` (migração Alembic) e o módulo `app/modules/pedidos/` completo (models, schemas, service, router).
- Uma tela `/pedidos` (Jinja2 + JS vanilla) com cards de resumo, filtros, tabela paginada, modal de criação/edição e modal de cancelamento.
- Cobertura de testes automatizados batendo com os 12 critérios de aceite da spec.

Nenhuma tabela ou rota de INVENTÁRIO/VENCIMENTOS é lida ou escrita — o módulo é standalone, conforme RN-11 da spec.

---

## 1. Mapa de arquivos

| Arquivo | Ação | Observação |
|---|---|---|
| `app/modules/pedidos/__init__.py` | criar | docstring apenas, padrão `panes/__init__.py` |
| `app/modules/pedidos/models.py` | criar | modelo ORM `Pedido` |
| `app/modules/pedidos/schemas.py` | criar | Pydantic v2 |
| `app/modules/pedidos/service.py` | criar | regras de negócio |
| `app/modules/pedidos/router.py` | criar | endpoints REST |
| `migrations/versions/<timestamp>_<rev>_add_pedidos_module.py` | criar | 1 tabela, 5 índices |
| `app/web/templates/pedidos.html` | criar | página Jinja2 |
| `app/web/static/js/pedidos.js` | criar | JS vanilla |
| `tests/unit/test_pedidos.py` | criar | testes automatizados |
| `app/shared/core/enums.py` | **editar** | + `StatusPedido`, `TipoPedido` |
| `app/bootstrap/main.py` | **editar** | import de models, router, `API_PREFIXES` |
| `migrations/env.py` | **editar** | + 1 import de models |
| `app/web/pages/router.py` | **editar** | + rota de página `/pedidos` |
| `app/web/templates/base.html` | **editar** | + ícone de navegação em `#admin-nav` |

**Ordem recomendada de execução:** 1→2→3→4→5→6→7→8→9→10→11 (cada etapa abaixo já segue essa ordem). Isso evita ter router/schemas apontando para um modelo ou enum que ainda não existe.

---

## 2. Etapa 1 — Enums (`app/shared/core/enums.py`)

Acrescentar ao final do arquivo, seguindo o estilo já usado por `StatusPane`/`TipoPapel` (herança de `str, enum.Enum`, docstring curta com a transição de estados):

```python
class StatusPedido(str, enum.Enum):
    """
    Status do ciclo de vida administrativo do pedido.
    Transições permitidas (RN-10): PENDENTE → ATENDIDO | CANCELADO.
    Ambos os estados finais são terminais — não há transição de volta.
    """
    PENDENTE = "PENDENTE"
    ATENDIDO = "ATENDIDO"
    CANCELADO = "CANCELADO"


class TipoPedido(str, enum.Enum):
    """Prioridade/urgência do pedido. EMERGENCIA exige numero_emergencia (RN-03)."""
    NORMAL = "NORMAL"
    EMERGENCIA = "EMERGENCIA"
```

Não remover nem reordenar nenhum enum existente — apenas apensar.

---

## 3. Etapa 2 — Modelo ORM (`app/modules/pedidos/models.py`)

Base: spec §3.3, adaptada ao padrão real de `app/modules/panes/models.py`.

```python
"""
app/modules/pedidos/models.py
Modelo ORM da Central de Pedidos — módulo standalone, desacoplado de
INVENTÁRIO e VENCIMENTOS (feature_controle_pedidos.md v2.0, §2.2).
"""

from __future__ import annotations
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import StatusPedido, TipoPedido

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario


class Pedido(Base):
    """Registro administrativo/logístico de um pedido de reposição de equipamento.

    Desacoplado de INVENTÁRIO/VENCIMENTOS por design: `part_number` e
    `nomenclatura` são atributos de texto imutáveis, não FKs para o catálogo
    de equipamentos — o pedido permanece auditável mesmo que o catálogo mude
    depois (feature_controle_pedidos.md §2.1).
    """
    __tablename__ = "pedidos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    numero_pedido: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)

    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    part_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nomenclatura: Mapped[str] = mapped_column(String(100), nullable=False)

    tipo_pedido: Mapped[str] = mapped_column(String(20), nullable=False, default=TipoPedido.NORMAL.value)
    numero_emergencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatusPedido.PENDENTE.value, index=True
    )
    observacao: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    data_pedido: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    data_atendimento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_cancelamento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(500), nullable=True)

    solicitante_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    atendido_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    cancelado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )

    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relacionamentos unidirecionais (sem back_populates) — não é necessário
    # tocar Aeronave nem Usuario para este módulo funcionar, o que também
    # evita conflito de merge com outras equipes editando esses modelos.
    aeronave: Mapped["Aeronave"] = relationship(lazy="select")
    solicitante: Mapped["Usuario"] = relationship(foreign_keys=[solicitante_id], lazy="select")
    atendido_por: Mapped["Usuario | None"] = relationship(foreign_keys=[atendido_por_id], lazy="select")
    cancelado_por: Mapped["Usuario | None"] = relationship(foreign_keys=[cancelado_por_id], lazy="select")

    def __repr__(self) -> str:
        return f"<Pedido id={self.id} numero={self.numero_pedido!r} status={self.status!r}>"
```

**Pontos críticos (não pular):**
- `foreign_keys=[...]` é **obrigatório** em `solicitante`, `atendido_por` e `cancelado_por` — são 3 FKs distintas para `usuarios.id`; sem essa declaração explícita, o SQLAlchemy levanta `AmbiguousForeignKeysError` ao configurar o mapper (mesmo motivo de `Pane.criador`/`Pane.responsavel_conclusao` em `panes/models.py`).
- `status`/`tipo_pedido` são `String(20)` com default `.value`, **não** `sa.Enum` — é o padrão usado em todo o projeto (`panes.status`, `inspecoes.status`), preferido por evitar migração de tipo nativo do Postgres ao adicionar um novo valor de enum no futuro.
- `ondelete="RESTRICT"` em todas as FKs: um pedido nunca deve sobreviver "órfão" de aeronave/usuário, mas também não pode travar a exclusão silenciosamente — RESTRICT torna qualquer tentativa de excluir uma aeronave/usuário referenciado um erro explícito.

---

## 4. Etapa 3 — Migração Alembic

1. **Reconferir o head atual antes de gerar a revisão** (pode ter mudado se outra equipe mesclou migrações):
   ```bash
   alembic heads
   ```
   No momento da escrita deste plano, o head é `dc6bbdf4335a` (`20260808_1240_dc6bbdf4335a_update_publicacoes_upload_jobs_single_.py`).

2. Registrar o import do modelo em `migrations/env.py`, no bloco de imports de models (ao lado de `app.modules.panes.models`):
   ```python
   import app.modules.pedidos.models  # noqa: F401
   ```
   Isso precisa acontecer **antes** de gerar a revisão, para que o metadata do Alembic enxergue a tabela nova.

3. Gerar o arquivo (o `file_template` do `alembic.ini` já produz o padrão `YYYYMMDD_HHMM_<rev>_<slug>.py`):
   ```bash
   alembic revision -m "add_pedidos_module"
   ```

4. Escrever `upgrade()`/`downgrade()` à mão (não confiar no autogenerate para o índice único composto), no molde de `20260805_2141_7daf099e56ed_publicacoes_m2_avulsas.py`:

```python
def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero_pedido", sa.String(length=50), nullable=False),
        sa.Column("aeronave_id", sa.Uuid(), nullable=False),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("nomenclatura", sa.String(length=100), nullable=False),
        sa.Column("tipo_pedido", sa.String(length=20), nullable=False),
        sa.Column("numero_emergencia", sa.String(length=50), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observacao", sa.String(length=1000), nullable=True),
        sa.Column("data_pedido", sa.Date(), nullable=False),
        sa.Column("data_atendimento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_cancelamento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(length=500), nullable=True),
        sa.Column("solicitante_id", sa.Uuid(), nullable=False),
        sa.Column("atendido_por_id", sa.Uuid(), nullable=True),
        sa.Column("cancelado_por_id", sa.Uuid(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["aeronave_id"], ["aeronaves.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["solicitante_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["atendido_por_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelado_por_id"], ["usuarios.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero_pedido", name="uq_pedidos_numero_pedido"),
    )
    with op.batch_alter_table("pedidos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_pedidos_numero_pedido"), ["numero_pedido"], unique=True)
        batch_op.create_index(batch_op.f("ix_pedidos_aeronave_id"), ["aeronave_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_part_number"), ["part_number"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_pedidos_ativo"), ["ativo"], unique=False)


def downgrade() -> None:
    op.drop_table("pedidos")
```

5. Validar localmente:
   ```bash
   alembic upgrade head
   alembic downgrade -1   # confirma que o downgrade não quebra
   alembic upgrade head   # volta ao estado final
   ```

---

## 5. Etapa 4 — Schemas (`app/modules/pedidos/schemas.py`)

Reproduzir a spec §7.2 (`PedidoCreate`, `PedidoUpdate`, `PedidoCancelar`, `PedidoOut`) e complementar com o que a spec não cobre:

```python
"""
app/modules/pedidos/schemas.py
Schemas Pydantic v2 para o módulo Central de Pedidos.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.core.enums import StatusPedido, TipoPedido


class FiltroPedido(BaseModel):
    """Parâmetros de filtro para listagem/resumo de pedidos."""
    texto: str | None = None
    status: StatusPedido | None = None
    tipo_pedido: TipoPedido | None = None
    aeronave_id: uuid.UUID | None = None
    excluidos: bool = Field(default=False, description="Exibir apenas pedidos excluídos (soft delete)")
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class PedidoCreate(BaseModel):
    aeronave_id: uuid.UUID
    part_number: str = Field(..., min_length=1, max_length=50)
    nomenclatura: str = Field(..., min_length=1, max_length=100)
    tipo_pedido: TipoPedido = TipoPedido.NORMAL
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int = Field(default=1, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _validar_regras(self):
        # RN-03 / RN-04. Reforçado também no service (defesa em profundidade).
        if self.tipo_pedido == TipoPedido.EMERGENCIA and not self.numero_emergencia:
            raise ValueError("numero_emergencia é obrigatório para pedidos de EMERGENCIA")
        if self.tipo_pedido == TipoPedido.NORMAL:
            self.numero_emergencia = None
        return self


class PedidoUpdate(BaseModel):
    """RN-09: só é aceito quando o pedido está PENDENTE (checado no service).

    `extra="forbid"`: mesma proteção usada em PaneUpdate contra campos
    desconhecidos silenciosamente ignorados.
    """
    model_config = ConfigDict(extra="forbid")

    part_number: str | None = Field(None, min_length=1, max_length=50)
    nomenclatura: str | None = Field(None, min_length=1, max_length=100)
    tipo_pedido: TipoPedido | None = None
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int | None = Field(None, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)


class PedidoCancelar(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)


class PedidoOut(BaseModel):
    """Representação plana do pedido.

    ATENÇÃO: aeronave_matricula/solicitante_trigrama/atendido_por_trigrama/
    cancelado_por_trigrama NÃO são atributos do ORM `Pedido` — não usar
    `PedidoOut.model_validate(pedido)` diretamente. Montar via
    `service._to_out(pedido)`, que já garante que as relações necessárias
    foram carregadas (selectinload) antes de acessá-las.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_pedido: str
    aeronave_id: uuid.UUID
    aeronave_matricula: str
    part_number: str
    nomenclatura: str
    tipo_pedido: str
    numero_emergencia: str | None
    status: str
    quantidade: int
    observacao: str | None
    data_pedido: date
    data_atendimento: datetime | None
    data_cancelamento: datetime | None
    motivo_cancelamento: str | None
    solicitante_trigrama: str | None
    atendido_por_trigrama: str | None
    cancelado_por_trigrama: str | None
    ativo: bool
    created_at: datetime


class PedidoResumo(BaseModel):
    """Contadores para os cards de resumo da tela — GET /pedidos/resumo.
    Respeita os mesmos filtros (exceto paginação) da listagem."""
    total: int
    pendentes: int
    atendidos: int
    cancelados: int
    emergencias: int
```

---

## 6. Etapa 5 — Service (`app/modules/pedidos/service.py`)

Assinaturas e algoritmo de cada função (nomes e regras alinhados à spec §4):

### `_gerar_numero_pedido(db, ano: int) -> str` — **superada** (enhancement Nº Pedido manual)
> A geração automática descrita abaixo foi removida: o número oficial do pedido é emitido no
> sistema interno da FAB e informado manualmente pelo usuário no formulário. `criar_pedido`
> passou a receber `dados.numero_pedido` e apenas checar unicidade (pre-check + SAVEPOINT),
> sem gerar nada. Ver RN-02 atualizada em `feature_controle_pedidos.md`.
```
SELECT numero_pedido FROM pedidos
WHERE numero_pedido LIKE 'P-{ano}-%'
ORDER BY numero_pedido DESC LIMIT 1
```
Parseia o sufixo numérico do resultado (ou usa `0` se não houver nenhum), soma 1, formata como `P-{ano}-{seq:04d}`.
**Não usar `COUNT(*)`** para gerar a sequência — soft deletes e cancelamentos abrem buracos na contagem e produziriam números duplicados.

### `criar_pedido(db, dados: PedidoCreate, solicitante_id) -> Pedido`
1. Busca a aeronave via `aeronaves.service.buscar_aeronave(db, dados.aeronave_id)` → se `None`, `EntidadeNaoEncontradaError` (404).
2. Reforça no servidor: `EMERGENCIA` sem `numero_emergencia` → `ConflitoNegocioError`; `NORMAL` força `numero_emergencia = None` (RN-03/RN-04 — já validado no schema, mas repetido aqui como defesa em profundidade, já que o service pode ser chamado fora do router no futuro).
3. `status = StatusPedido.PENDENTE.value` (RN-05), `data_pedido = date.today()` (RN-08, nunca aceito do payload).
4. **(Atualizado)** `dados.numero_pedido` é informado manualmente pelo usuário. Pre-check de unicidade (`_numero_pedido_em_uso`) e insere dentro de `async with db.begin_nested():`. Em caso de `IntegrityError` (corrida entre duas criações concorrentes com o mesmo número), `ConflitoNegocioError` (409, RN-02). Padrão idêntico ao SAVEPOINT já usado em `panes.service.adicionar_responsavel`/`concluir_pane`.
5. `await db.flush()`, depois `await db.refresh(pedido, ["aeronave", "solicitante"])` para deixar pronta a montagem do `PedidoOut`.

### `listar_pedidos(db, filtros: FiltroPedido) -> tuple[list[Pedido], int]`
- Query dinâmica: filtra por `status`, `tipo_pedido`, `aeronave_id` quando informados.
- Filtro `ativo` **sempre** aplicado (ativo=True por padrão, ou `ativo=False` se `filtros.excluidos=True`) — mesma disciplina de `panes.service.listar_panes` (COR-01: nunca deixar passar sem esse filtro).
- Busca textual (`filtros.texto`) em `numero_pedido`, `part_number`, `nomenclatura` e `aeronave.matricula` (via outerjoin), usando `escape_like()` de `app/shared/core/db_utils.py` e `.like(..., escape="\\")` — mesma técnica de `panes.service.listar_panes` (SEC-07, evita que `%`/`_` no texto de busca virem wildcard).
- Ordena por `data_pedido DESC, created_at DESC`.
- `selectinload(Pedido.aeronave, Pedido.solicitante, Pedido.atendido_por, Pedido.cancelado_por)` — sem isso, montar `PedidoOut` dispara lazy-load síncrono sob `AsyncSession` e quebra com `MissingGreenlet` (mesmo risco documentado em `PaneResponsavel.trigrama`, `panes/models.py:253-266`).
- `total` calculado com `select(func.count()).select_from(...)` aplicando o mesmo `where` **antes** de `offset`/`limit`.
- Retorna `(lista_paginada, total)` — o router usa `total` para o header `X-Total-Count`.

### `obter_resumo(db, filtros: FiltroPedido) -> PedidoResumo`
Uma única query de agregação condicional (sem os 4 SELECTs separados), aplicando os mesmos filtros de `listar_pedidos` exceto paginação:
```python
select(
    func.count().label("total"),
    func.sum(case((Pedido.status == StatusPedido.PENDENTE.value, 1), else_=0)).label("pendentes"),
    func.sum(case((Pedido.status == StatusPedido.ATENDIDO.value, 1), else_=0)).label("atendidos"),
    func.sum(case((Pedido.status == StatusPedido.CANCELADO.value, 1), else_=0)).label("cancelados"),
    func.sum(case((Pedido.tipo_pedido == TipoPedido.EMERGENCIA.value, 1), else_=0)).label("emergencias"),
)
```
`func.sum` sobre SQLite/Postgres pode retornar `None` quando não há linhas — tratar com `or 0` em cada campo antes de montar `PedidoResumo`.

### `buscar_pedido(db, pedido_id, incluir_inativos=False) -> Pedido | None`
Busca por PK com o mesmo `selectinload` de `listar_pedidos`; filtra `ativo=True` a menos que `incluir_inativos=True`.

### `editar_pedido(db, pedido_id, dados: PedidoUpdate) -> Pedido`
- 404 se não existe. RN-09: se `pedido.status != PENDENTE`, `ConflitoNegocioError` (409) — pedido `ATENDIDO`/`CANCELADO` é somente leitura.
- Aplica os campos não-`None` de `dados`.
- Reforça a coerência tipo/emergência após aplicar: se o `tipo_pedido` resultante for `NORMAL`, força `numero_emergencia = None`; se `EMERGENCIA` e o `numero_emergencia` resultante ficar vazio, `ConflitoNegocioError`.

### `atender_pedido(db, pedido_id, usuario_id) -> Pedido`
RN-10/RN-11: só a partir de `PENDENTE` (senão 409). Marca `status=ATENDIDO`, `data_atendimento=datetime.now(timezone.utc)`, `atendido_por_id=usuario_id`. **Nenhuma outra tabela é tocada** — é puramente administrativo, não gera `instalacoes` nem altera inventário (é o ponto central do desacoplamento da spec v2.0).

### `cancelar_pedido(db, pedido_id, usuario_id, motivo: str) -> Pedido`
RN-10/RN-12: só a partir de `PENDENTE` (senão 409). `motivo` já validado como não-vazio pelo schema `PedidoCancelar`. Marca `status=CANCELADO`, `data_cancelamento=now()`, `cancelado_por_id=usuario_id`, `motivo_cancelamento=motivo`.

### `excluir_pedido(db, pedido_id) -> Pedido` / `restaurar_pedido(db, pedido_id) -> Pedido`
RN-13, soft delete. Idempotência: excluir um já inativo, ou restaurar um já ativo, é `ConflitoNegocioError` — mesmo padrão de `panes.service.excluir_pane`/`restaurar_pane`.

**Todas as funções lançam exceções de `app/shared/core/exceptions.py`** (`EntidadeNaoEncontradaError`, `ConflitoNegocioError`) em vez de `ValueError`/string — o handler global (`setup_exception_handlers`) já converte para o status HTTP correto, então o router não precisa de `try/except`.

---

## 7. Etapa 6 — Router (`app/modules/pedidos/router.py`)

Estrutura (sem prefixo — o prefixo `/pedidos` é aplicado em `main.py`):

```python
router = APIRouter()

@router.get("/", response_model=list[schemas.PedidoOut])
async def listar_pedidos(db: DBSession, _: CurrentUser, response: Response, ...) -> list[schemas.PedidoOut]: ...

@router.get("/resumo", response_model=schemas.PedidoResumo)
async def obter_resumo(db: DBSession, _: CurrentUser, ...) -> schemas.PedidoResumo: ...

@router.get("/export")
@limiter.limit("10/minute")
async def exportar_pedidos(request: Request, db: DBSession, _: CurrentUser, ...): ...

@router.post("/", response_model=schemas.PedidoOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(dados: schemas.PedidoCreate, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> schemas.PedidoOut: ...

@router.get("/{pedido_id}", response_model=schemas.PedidoOut)
async def buscar_pedido(pedido_id: uuid.UUID, db: DBSession, _: CurrentUser) -> schemas.PedidoOut: ...

@router.put("/{pedido_id}", response_model=schemas.PedidoOut)
async def editar_pedido(pedido_id: uuid.UUID, dados: schemas.PedidoUpdate, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> schemas.PedidoOut: ...

@router.post("/{pedido_id}/atender", response_model=schemas.PedidoOut)
async def atender_pedido(pedido_id: uuid.UUID, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> schemas.PedidoOut: ...

@router.post("/{pedido_id}/cancelar", response_model=schemas.PedidoOut)
async def cancelar_pedido(pedido_id: uuid.UUID, dados: schemas.PedidoCancelar, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> schemas.PedidoOut: ...

@router.delete("/{pedido_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_pedido(pedido_id: uuid.UUID, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> None: ...

@router.post("/{pedido_id}/restaurar", response_model=schemas.PedidoOut)
async def restaurar_pedido(pedido_id: uuid.UUID, db: DBSession, usuario_atual: EncarregadoInspetorOuAdmin) -> schemas.PedidoOut: ...
```

**Pontos críticos:**
- **Ordem das rotas**: `/`, `/resumo`, `/export` são declaradas **antes** de `/{pedido_id}` — senão FastAPI tentaria casar `"resumo"`/`"export"` como `uuid.UUID` e devolveria 422 (mesma convenção já seguida em `equipamentos/router.py:194-195` e citada na spec §7).
- **RBAC**: usar as dependências já existentes em `app/bootstrap/dependencies.py` — `CurrentUser` para leitura, `EncarregadoInspetorOuAdmin` (linha 159) para escrita. **Não criar** uma dependência nova equivalente.
- **Nome do parâmetro `status`**: usar `status_filtro: schemas.StatusPedido | None = Query(default=None, alias="status")` no `listar_pedidos`/`obter_resumo`/`exportar_pedidos` — `status` como nome de variável local sombrearia o módulo `fastapi.status` importado no arquivo (mesma armadilha documentada em `panes/router.py:75`, RISCO-11).
- `listar_pedidos` grava o total no header antes de retornar: `response.headers["X-Total-Count"] = str(total)`.
- `exportar_pedidos`: réplica fiel do padrão em `panes/router.py:103-172` — `gerar_csv`/`gerar_xlsx` de `app/shared/exporter.py` (já neutraliza fórmulas maliciosas), `limit_export = 1000`, header `X-Export-Truncated` se o teto foi atingido, `Content-Disposition: attachment`.

---

## 8. Etapa 7 — Bootstrap (`app/bootstrap/main.py`)

Três alterações pontuais:

1. No bloco de registro do SQLAlchemy (linhas 16-24 hoje), acrescentar:
   ```python
   import app.modules.pedidos.models
   ```

2. No bloco de imports de routers (linhas 32-42 hoje):
   ```python
   from app.modules.pedidos.router import router as pedidos_router
   ```

3. Em `_register_routers`, junto dos demais `include_router`:
   ```python
   app.include_router(pedidos_router, prefix="/pedidos", tags=["Pedidos"])
   ```

4. Em `API_PREFIXES` (linhas 55-65), acrescentar **`"/pedidos/"` com barra final**:
   ```python
   API_PREFIXES = [
       "/auth/", "/efetivo/", "/aeronaves/", "/equipamentos/", "/vencimentos/",
       "/panes/", "/inspecoes/", "/api/v1/calendario/", "/dashboard/",
       "/publicacoes/api/",
       "/pedidos/",
   ]
   ```
   **Por quê a barra importa:** a página HTML fica em `/pedidos` (sem barra, servida por `pages_router`) e a API fica em `/pedidos/...` (com barra, servida por `pedidos_router`). O handler global de exceções decide "isso é chamada de API ou navegação de página?" checando `path.startswith(prefixo)` — com `"/pedidos/"`, um 401/403 em `/pedidos/123/atender` devolve JSON (comportamento de API), e um 401/403 na própria página `/pedidos` ainda redireciona para `/login` (comportamento de página). Registrar `"/pedidos"` sem barra reintroduziria, para este módulo, o mesmo bug que o comentário em `main.py:58-64` documenta ter acontecido com `/publicacoes` (e com `/api/v1/calendario` antes disso).

---

## 9. Etapa 8 — Página e navegação

**`app/web/pages/router.py`** — nova rota, no mesmo formato de `vencimentos_page`:
```python
@router.get("/pedidos", response_class=HTMLResponse, include_in_schema=False)
async def pedidos_page(request: Request, _=Depends(get_current_user)):
    """Central de Pedidos — ciclo de vida administrativo dos pedidos de reposição."""
    return templates.TemplateResponse("pedidos.html", {"request": request})
```

**`app/web/templates/base.html`** — novo item dentro de `<nav id="admin-nav">`, seguindo exatamente o padrão dos vizinhos (ícone + realce condicional pela URL atual):
```html
<a href="/pedidos" class="btn-icon" aria-label="Pedidos" title="Central de Pedidos"
    style="width: 38px; height: 38px; {% if request.url.path == '/pedidos' %}color: var(--primary-color); background: var(--bg-tertiary); border-color: var(--primary-color);{% endif %}">
    <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4">
        </path>
    </svg>
</a>
```
Posicionar entre os links de "Panes" e "Inspeções" (ou onde fizer sentido operacionalmente) — não precisa ser exatamente ali, só manter o mesmo padrão de marcação dos outros `<a>` do bloco.

---

## 10. Etapa 9 — Template (`app/web/templates/pedidos.html`)

`{% extends "base.html" %}`, `{% block page_title %}Central de Pedidos{% endblock %}`, CSS embutido em `<style>` dentro do `{% block content %}` (padrão de `vencimentos.html`), script próprio em `{% block scripts %}`.

O layout visual reaproveita a estrutura do `mockup_pedidos.html` existente (cards, badges de status/tipo, linhas expansíveis, paginação), **adaptada à v2** — removendo o que pertencia à v1.3 (select de Slot de inventário, input manual de Nº do Pedido) e adicionando os campos próprios da v2 (Part Number, Nomenclatura como texto livre):

1. **Cards de resumo** (4): `#card-total`, `#card-pendentes`, `#card-atendidos`, `#card-emergencias` — populados por `GET /pedidos/resumo`.
2. **Barra de filtros**: select Aeronave (populado de `GET /aeronaves/`), select Status, select Tipo, campo de busca textual, checkbox "Ver excluídos" (`?excluidos=true`), botão **+ Novo Pedido** com `data-role="ENCARREGADO,INSPETOR,ADMINISTRADOR"` (o `auth_check.js` já existente oculta automaticamente para quem não tem o papel).
3. **Tabela** com colunas: `STATUS | DATA | ANV | TIPO | Nº PEDIDO | P/N | NOMENCLATURA | Nº EMERG | QTD | AÇÕES`, e linha de detalhe expansível com observação, solicitante, quem atendeu/cancelou e motivo do cancelamento.
4. **Paginação** — usa o `X-Total-Count` devolvido por `GET /pedidos/`.
5. **Modal Novo/Editar Pedido** — campos: Aeronave* (select), Part Number* (texto), Nomenclatura* (texto), Quantidade (número, 1–999), Tipo (radio NORMAL/EMERGÊNCIA), Nº Emergência* (só visível/obrigatório quando EMERGÊNCIA), Observação (textarea). **Não** há campo de número de pedido (gerado no servidor) nem select de slot (removido na v2).
6. **Modal Cancelar** — textarea `motivo` obrigatório (RN-12).

---

## 11. Etapa 10 — JavaScript (`app/web/static/js/pedidos.js`)

IIFE `(function () { "use strict"; ... })();`, seguindo o molde de `publicacoes_avulsas.js`/`vencimentos.js`. Regras obrigatórias:

- Toda chamada à API via `apiFetch(...)` (global de `app.js`) — já injeta o token CSRF e trata 401 (logout automático).
- Todo texto vindo do backend renderizado via `escapeHtml(...)` antes de ir para `innerHTML`.
- **Nenhum atributo `onclick=` inline**: a CSP do projeto é `script-src 'self'` sem `'unsafe-inline'` (`app/shared/middleware/security.py:33-51`) — um handler inline simplesmente não executa. Usar `addEventListener` com delegação de evento (`data-action`, `data-id` nos botões da tabela).
- Ações visíveis por status: `PENDENTE` → Alterar / Cancelar / ✓ Atendido / 🗑 Excluir; `ATENDIDO`/`CANCELADO` → nenhuma ação (somente leitura, RN-09); item excluído (quando `?excluidos=true`) → ↺ Restaurar.
- Botões de escrita marcados com `data-role="ENCARREGADO,INSPETOR,ADMINISTRADOR"` para ocultação client-side — a garantia real de segurança é o 403 do backend, isto é só UX.
- `change` nos radios de tipo alterna a visibilidade/obrigatoriedade do campo Nº Emergência.
- Ao submeter o modal de criação/edição, montar o payload **incluindo** `numero_pedido` (informado manualmente pelo usuário — enhancement Nº Pedido manual).

---

## 12. Etapa 11 — Testes (`tests/unit/test_pedidos.py`)

Usar as fixtures já existentes em `tests/conftest.py` (não criar fixtures novas de usuário/aeronave): `client`, `db`, `usuario_e_token` (ADMINISTRADOR), `usuario_encarregado_e_token`, `usuario_mantenedor_e_token`, `dados_aeronave_valida`. Para o mantenedor, criar analogamente a `usuario_encarregado_e_token` se não existir uma fixture de token pronta — reaproveitar `dados_usuario_mantenedor` já disponível.

Casos mínimos (um por critério de aceite da spec §11):

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | Listar com cada filtro (`status`, `tipo_pedido`, `aeronave_id`, `texto`) | filtra corretamente |
| 2 | Criar pedido `NORMAL` | 201, sem `numero_emergencia` |
| 3 | Criar `EMERGENCIA` sem `numero_emergencia` | 422 |
| 4 | Criar `EMERGENCIA` com `numero_emergencia`, depois editar para `NORMAL` | `numero_emergencia` volta a `null` |
| 5 | Criar dois pedidos no mesmo ano | números sequenciais `P-{ano}-0001`, `P-{ano}-0002` |
| 6 | Atender pedido `PENDENTE` | `data_atendimento`/`atendido_por_id` preenchidos, status `ATENDIDO` |
| 7 | Atender pedido já `ATENDIDO` | 409 |
| 8 | Editar pedido `ATENDIDO` | 409 |
| 9 | Cancelar sem `motivo` | 422 |
| 10 | Cancelar `PENDENTE` com motivo | `data_cancelamento`/`cancelado_por_id`/`motivo_cancelamento` preenchidos |
| 11 | MANTENEDOR tenta criar/atender/cancelar | 403 |
| 12 | Soft delete some da listagem padrão, aparece com `?excluidos=true`, some de novo após `/restaurar` | comportamento correto em cada etapa |
| 13 | `GET /pedidos/resumo` | contadores batem com os pedidos criados no teste |
| 14 | `GET /pedidos/export?format=csv` e `format=xlsx` | 200, `Content-Disposition` de anexo |
| 15 | Atender um pedido e confirmar que nenhuma linha em outra tabela (ex.: se existir `instalacoes` no ambiente de teste) foi criada | reforça RN-11 |

---

## 13. Verificação end-to-end

```bash
alembic upgrade head                     # cria a tabela pedidos
pytest tests/unit/test_pedidos.py -v     # testes do módulo
pytest -q                                # suíte completa — sem regressão em outros módulos
ruff check app/modules/pedidos/          # lint
python scripts/run_app.py                # sobe a aplicação para smoke manual
```

**Smoke manual** (navegador, usuário ENCARREGADO ou ADMINISTRADOR):
1. Acessar `/pedidos` — os 4 cards carregam e batem com a tabela.
2. Criar um pedido `NORMAL` e um `EMERGENCIA` (campo Nº Emergência aparece só na segunda).
3. Atender um pedido — status muda, ações somem.
4. Cancelar outro — modal exige motivo.
5. Excluir um pedido `PENDENTE`, marcar "Ver excluídos", restaurar.
6. Exportar CSV e XLSX — arquivo baixa com dados corretos.
7. Abrir o DevTools → aba Console: **nenhuma violação de CSP** ao longo do fluxo acima.
8. Logar como MANTENEDOR: só consegue visualizar, botões de escrita ficam ocultos e uma tentativa direta via API retorna 403.

---

## 14. Riscos e armadilhas conhecidas

| # | Risco | Mitigação |
|---|---|---|
| R1 | `"/pedidos"` sem barra final em `API_PREFIXES` faz a própria página HTML devolver JSON 401 em vez de redirecionar para `/login` | usar `"/pedidos/"` (com barra) — ver `main.py:58-64` para o precedente documentado com `/publicacoes` |
| R2 | 3 FKs para `usuarios.id` sem `foreign_keys=` explícito nas relations | declarar `foreign_keys=[...]` nas 3 relações de auditoria (§3) |
| R3 | Serializar uma relação não carregada sob `AsyncSession` dispara `MissingGreenlet` | `selectinload` de `aeronave`/`solicitante`/`atendido_por`/`cancelado_por` antes de montar `PedidoOut` |
| R4 | Corrida entre duas criações/edições simultâneas informando o mesmo `numero_pedido` | pre-check de unicidade + SAVEPOINT (`db.begin_nested()`) + captura de `IntegrityError`, depois 409 |
| R5 | Este plano toca arquivos compartilhados (`enums.py`, `main.py`, `migrations/env.py`, `base.html`, `pages/router.py`) que outra equipe pode estar editando em paralelo | commits pequenos por etapa; reconferir `alembic heads` e fazer rebase antes de abrir PR |
| R6 | Nome de parâmetro `status` sombreando `fastapi.status` importado no router | usar `status_filtro: ... = Query(alias="status")`, igual `panes/router.py` |
| R7 | Reintroduzir por engano os campos de v1.3 (slot de inventário, vencimento) copiando o mockup literalmente | RN-11 é a linha vermelha: atender é só marcação administrativa, nenhuma escrita fora de `pedidos` |
| R8 | `func.sum` retornando `None` em vez de `0` quando não há linhas na agregação de `/resumo` | tratar cada campo com `or 0` antes de construir `PedidoResumo` |

---

## 15. Checklist de aceite (espelha a spec §11)

- [ ] Listar pedidos com filtros funcionais (`status`, `tipo_pedido`, `aeronave_id`, busca textual por nº pedido ou PN).
- [ ] Criar pedido `NORMAL` sem campo de emergência.
- [ ] Criar pedido `EMERGENCIA` com `numero_emergencia` obrigatório (validado no backend).
- [ ] `numero_emergencia` forçado a NULL quando `NORMAL`.
- [ ] Atender registra `data_atendimento` e `atendido_por_id` e **não** altera o módulo de inventário.
- [ ] Cancelar exige `motivo_cancelamento` (mínimo 1 caractere) e registra `data_cancelamento` + `cancelado_por_id`.
- [ ] Editar apenas pedidos com status `PENDENTE`. Pedidos `ATENDIDO`/`CANCELADO` são read-only.
- [ ] Transições inválidas de status retornam HTTP 409.
- [ ] `numero_pedido` informado manualmente pelo usuário e obrigatório na criação; colisão retorna HTTP 409.
- [ ] Usuário sem permissão (MANTENEDOR tentando criar/atender/cancelar) recebe HTTP 403.
- [ ] Soft delete e restauração funcionam corretamente.
- [ ] Sem violações de CSP ou XSS no frontend.
- [ ] `pytest -q` verde (suíte completa, sem regressão).
- [ ] `ruff check app/modules/pedidos/` limpo.
- [ ] `alembic upgrade head` e `alembic downgrade -1` funcionam sem erro.
- [ ] Ícone de navegação para `/pedidos` visível em `#admin-nav` para os papéis corretos.
