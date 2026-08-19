# 📋 Plano de Implementação — Gestão de Slots, Itens e Auditoria de Dados Mestres do Inventário

> **Versão:** 1.0
> **Data:** 2026-08-19
> **Referência:** `docs/BACKLOG/modulo_inventario/enhange_gerenciar_inventario.md` (SPEC-CONF-001 v2.0)
> **Status:** 🟢 Pronto para execução
> **Escopo deste documento:** passo a passo técnico para fechar os buracos de CRUD em `slots_inventario` e `itens_equipamento`, corrigir o bug de integração do `posicao_xlsx`, e introduzir a tabela de auditoria de dados mestres `auditoria_dados_mestres`. Tudo dentro do módulo `app/modules/equipamentos/` já existente — não é criado um módulo novo.

> ⚠️ **Nota de coordenação:** este plano edita arquivos **compartilhados**: `app/shared/core/enums.py`, `app/web/templates/configuracoes.html`. A tabela nova (`AuditoriaDadosMestres`) fica dentro de `app/modules/equipamentos/models.py`, que já é importado em `migrations/env.py:27` e `app/bootstrap/main.py:18` — por isso **não é preciso editar nenhum dos dois**. Se outra frente estiver mexendo em `enums.py` ou no template de Configurações em paralelo, reconferir antes de abrir PR.

---

## 0. Visão do que será construído

Ao final deste plano:

- `slots_inventario` terá CRUD completo (hoje só tem `POST`): `PATCH`, `DELETE`, inativar, consultar ocupação.
- `itens_equipamento` terá CRUD completo (hoje só tem `POST`): `PATCH`, `DELETE`.
- O bug de integração do XLSX é corrigido: `posicao_xlsx` passa a ser obrigatório na criação de slot, então todo slot cadastrado pela API casa corretamente com a planilha de importação.
- Toda escrita em `modelos_equipamento`, `slots_inventario` e `itens_equipamento` grava um registro em `auditoria_dados_mestres` (nova tabela, append-only).
- A UI de Configurações ganha um modal "Gerenciar Slots" no card já existente "Equipamentos e PNs", mais um botão "Histórico" nas linhas do catálogo de PNs.
- Nada muda no comportamento de `/inventario`, no fluxo de "Sincronizar" (`ajustar_inventario_item`) nem na importação XLSX além do que está listado acima — RNF-08 da spec.

**Explicitamente fora deste plano** (ver Seção 15 da spec v2.0): persistir `sn_siloms`/`sn_real` como colunas separadas; refatorar os seeds para upsert idempotente; *optimistic locking*; *maker-checker*.

---

## 1. Mapa de arquivos

| Arquivo | Ação | Observação |
|---|---|---|
| `app/shared/core/enums.py` | **editar** | + `EntidadeAuditada`, `AcaoAuditoria` |
| `app/modules/equipamentos/models.py` | **editar** | `SlotInventario` ganha colunas novas; nova classe `AuditoriaDadosMestres` |
| `migrations/versions/<timestamp>_<rev>_gestao_dados_mestres_inventario.py` | criar | 1 tabela nova + alterações em `slots_inventario` + UNIQUE |
| `app/modules/equipamentos/schemas.py` | **editar** | `SlotInventarioCreate` estendido; `SlotInventarioUpdate`, `ItemEquipamentoUpdate`, `RemocaoJustificada`, `AuditoriaOut` novos |
| `app/modules/equipamentos/auditoria_service.py` | criar | `registrar`, `diff_campos`, `listar` |
| `app/modules/equipamentos/service.py` | **editar** | `atualizar_slot`, `remover_slot`, `inativar_slot`, `atualizar_item`, `excluir_item` + auditoria nas funções de PN existentes |
| `app/modules/equipamentos/router.py` | **editar** | 6 endpoints novos |
| `app/modules/equipamentos/xlsx_service.py` | **editar** | filtrar `ativo=True` ao carregar slots |
| `app/web/templates/configuracoes.html` | **editar** | botão + 2 modais novos + botão "Histórico" no catálogo de PN |
| `app/web/static/js/configuracoes_inventario.js` | criar | JS dos modais novos |
| `tests/unit/test_gestao_inventario.py` | criar | cobertura das US-01 a US-03 da spec |

**Ordem recomendada de execução:** 1→2→3→4→5→6→7→8→9→10→11 (cada etapa abaixo já segue essa ordem — evita rota/schema apontando para model ou enum que ainda não existe).

---

## 2. Etapa 1 — Enums (`app/shared/core/enums.py`)

Acrescentar ao final do arquivo, seguindo o estilo já usado por `StatusItem`/`OrigemControle` (herança de `str, enum.Enum`, docstring curta):

```python
class EntidadeAuditada(str, enum.Enum):
    """Entidades de dados mestres do inventário cobertas por auditoria."""
    MODELO_EQUIPAMENTO = "MODELO_EQUIPAMENTO"
    SLOT = "SLOT"
    ITEM = "ITEM"


class AcaoAuditoria(str, enum.Enum):
    """Ação registrada em auditoria_dados_mestres. Append-only — RN-09."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
```

Não remover nem reordenar nenhum enum existente — apenas apensar.

---

## 3. Etapa 2 — Modelos ORM (`app/modules/equipamentos/models.py`)

### 3.1 Estender `SlotInventario`

```python
class SlotInventario(Base):
    """
    Representa uma posição física pré-definida na aeronave (LCN/Slot).
    Slot é GLOBAL da frota (compartilhado por todas as aeronaves) — o vínculo
    por aeronave só existe em Instalacao (ver comentário em Instalacao abaixo).
    """
    __tablename__ = "slots_inventario"
    __table_args__ = (
        UniqueConstraint("nome_posicao", "sistema", name="uq_slot_nome_sistema"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome_posicao: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sistema: Mapped[str] = mapped_column(String(50), nullable=False)
    posicao_xlsx: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="RESTRICT"), nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ordem_exibicao: Mapped[int | None] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # --- Relacionamentos (sem alteração) ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="slots")
    instalacoes: Mapped[list["Instalacao"]] = relationship(back_populates="slot")

    def __repr__(self) -> str:
        return f"<SlotInventario nome={self.nome_posicao!r} pn={self.modelo_id}>"
```

**Pontos críticos (não pular):**
- `sistema` e `posicao_xlsx` passam de `nullable=True` para `nullable=False` — a migration precisa de backfill antes do `ALTER` (Etapa 3).
- `server_default="1"` em `ativo` garante que as 33 linhas já existentes no banco não fiquem com `NULL` após o `ALTER TABLE`.
- `UniqueConstraint` nova formaliza a chave natural que `seed_slots.py:64-69` já usa de fato, mas que hoje **não é garantida pelo banco** — rodar o pré-check de duplicidade (Etapa 3) antes de aplicar.

### 3.2 Nova classe `AuditoriaDadosMestres`

Acrescentar ao final do arquivo, importando os dois enums novos:

```python
from app.shared.core.enums import StatusItem, EntidadeAuditada, AcaoAuditoria

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario
    from app.modules.vencimentos.models import EquipamentoControle, ControleVencimento


class AuditoriaDadosMestres(Base):
    """
    Trilha append-only de escritas em dados mestres do inventário
    (ModeloEquipamento, SlotInventario, ItemEquipamento).

    Sem UPDATE/DELETE pela aplicação — mesmo padrão de
    ExecucaoVencimentoHistorico (app/modules/vencimentos/models.py).
    """
    __tablename__ = "auditoria_dados_mestres"
    __table_args__ = (
        Index("ix_auditoria_entidade", "entidade", "entidade_id"),
        Index("ix_auditoria_criado_em", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entidade: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    acao: Mapped[str] = mapped_column(String(10), nullable=False)
    valores_anteriores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valores_novos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    justificativa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    usuario: Mapped["Usuario | None"] = relationship()

    def __repr__(self) -> str:
        return f"<AuditoriaDadosMestres {self.entidade}:{self.acao} id={self.entidade_id}>"
```

**Pontos críticos (não pular):**
- Import `JSON` de `sqlalchemy` no topo do arquivo (não existe hoje em `models.py`) — SQLite não tem `JSONB`, e `JSON` do SQLAlchemy já serializa/desserializa automaticamente.
- `entidade`/`acao` como `String` (não `Enum` nativo) — mesmo padrão de `ItemEquipamento.status` (`models.py:89`), que trata o enum como aplicacional, não como constraint de banco.
- `usuario_id` nullable — segue o precedente de `Instalacao.usuario_id` (`models.py:125`), para não quebrar se um usuário for removido.

---

## 4. Etapa 3 — Migration

```bash
alembic revision --autogenerate -m "gestao_dados_mestres_inventario"
```

Gerar a partir do head atual `b63e385e3395`. **Antes de rodar o autogenerate**, executar o pré-check de duplicidade no banco local:

```sql
SELECT nome_posicao, sistema, COUNT(*) FROM slots_inventario GROUP BY 1, 2 HAVING COUNT(*) > 1;
SELECT nome_posicao, sistema FROM slots_inventario WHERE sistema IS NULL OR posicao_xlsx IS NULL;
```

Editar a migration gerada para garantir esta ordem dentro de `upgrade()`:

```python
def upgrade() -> None:
    # 1. Backfill ANTES de tornar as colunas NOT NULL
    op.execute("UPDATE slots_inventario SET sistema = '' WHERE sistema IS NULL")
    op.execute("UPDATE slots_inventario SET posicao_xlsx = '' WHERE posicao_xlsx IS NULL")

    # 2. Alterações em slots_inventario — batch mode obrigatório em SQLite
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.alter_column("sistema", existing_type=sa.String(50), nullable=False)
        batch_op.alter_column("posicao_xlsx", existing_type=sa.String(20), nullable=False)
        batch_op.add_column(sa.Column("descricao", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("ordem_exibicao", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_unique_constraint("uq_slot_nome_sistema", ["nome_posicao", "sistema"])

    # 3. Backfill de created_at para as linhas existentes (coluna nasce NOT NULL na prática)
    op.execute("UPDATE slots_inventario SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    # 4. Nova tabela
    op.create_table(
        "auditoria_dados_mestres",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("entidade", sa.String(30), nullable=False),
        sa.Column("entidade_id", sa.CHAR(32), nullable=False),
        sa.Column("acao", sa.String(10), nullable=False),
        sa.Column("valores_anteriores", sa.JSON(), nullable=True),
        sa.Column("valores_novos", sa.JSON(), nullable=True),
        sa.Column("justificativa", sa.String(500), nullable=True),
        sa.Column("usuario_id", sa.CHAR(32), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auditoria_entidade", "auditoria_dados_mestres", ["entidade", "entidade_id"])
    op.create_index("ix_auditoria_criado_em", "auditoria_dados_mestres", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_criado_em", table_name="auditoria_dados_mestres")
    op.drop_index("ix_auditoria_entidade", table_name="auditoria_dados_mestres")
    op.drop_table("auditoria_dados_mestres")
    with op.batch_alter_table("slots_inventario") as batch_op:
        batch_op.drop_constraint("uq_slot_nome_sistema", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("ativo")
        batch_op.drop_column("ordem_exibicao")
        batch_op.drop_column("descricao")
        batch_op.alter_column("posicao_xlsx", existing_type=sa.String(20), nullable=True)
        batch_op.alter_column("sistema", existing_type=sa.String(50), nullable=True)
```

**Pontos críticos (não pular):**
- A ordem "backfill → batch_alter_table" é obrigatória: alterar `sistema` para `NOT NULL` com linhas `NULL` existentes falha o `ALTER TABLE` mesmo em modo batch.
- `env.py:53` já liga `render_as_batch=True` quando a URL contém `sqlite` — não é preciso configurar isso na migration, só usar `op.batch_alter_table`.
- Nunca editar manualmente uma migration sem revisar o autogenerate primeiro — o Alembic pode detectar mudanças adicionais não intencionais em outros modelos (`CONTRIBUTING.md §7`).

---

## 5. Etapa 4 — Schemas (`app/modules/equipamentos/schemas.py`)

```python
class SlotInventarioCreate(BaseModel):
    nome_posicao: str = Field(..., max_length=100)
    sistema: str = Field(..., max_length=50)
    posicao_xlsx: Identificador = Field(..., max_length=20)
    modelo_id: uuid.UUID
    descricao: str | None = Field(default=None, max_length=200)
    ordem_exibicao: int | None = None


class SlotInventarioUpdate(BaseModel):
    nome_posicao: str | None = Field(None, max_length=100)
    sistema: str | None = Field(None, max_length=50)
    posicao_xlsx: Identificador | None = Field(None, max_length=20)
    modelo_id: uuid.UUID | None = None
    descricao: str | None = Field(None, max_length=200)
    ordem_exibicao: int | None = None


class SlotInventarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome_posicao: str
    sistema: str
    posicao_xlsx: str
    modelo_id: uuid.UUID
    descricao: str | None
    ordem_exibicao: int | None
    ativo: bool


class ItemEquipamentoUpdate(BaseModel):
    numero_serie: Identificador | None = Field(None, max_length=100)
    status: StatusItem | None = None


class RemocaoJustificada(BaseModel):
    justificativa: str = Field(..., min_length=5, max_length=500)


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entidade: str
    entidade_id: uuid.UUID
    acao: str
    valores_anteriores: dict | None
    valores_novos: dict | None
    justificativa: str | None
    usuario_id: uuid.UUID | None
    criado_em: datetime
```

**Pontos críticos (não pular):**
- `SlotInventarioCreate.sistema` e `.posicao_xlsx` passam de opcionais para obrigatórios — isso é uma **mudança de contrato**. Qualquer chamador existente de `POST /equipamentos/slots/` que hoje omite esses campos vai passar a receber `422`. Conferir `configuracoes.js` (hoje não tem formulário de criação de slot pela UI, só a API é usada em testes) antes de mesclar.
- Reaproveitar o tipo `Identificador` já existente (`schemas.py:20`) para `posicao_xlsx` mantém a normalização (maiúsculas/trim) consistente com PN e S/N.

---

## 6. Etapa 5 — Serviço de auditoria (`app/modules/equipamentos/auditoria_service.py`)

```python
"""
app/modules/equipamentos/auditoria_service.py
Trilha append-only de escritas em dados mestres do inventário
(ModeloEquipamento, SlotInventario, ItemEquipamento).

Nenhuma função aqui faz UPDATE ou DELETE sobre AuditoriaDadosMestres —
mesmo padrão de app/modules/vencimentos/service.py para
ExecucaoVencimentoHistorico.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.equipamentos.models import AuditoriaDadosMestres
from app.shared.core.enums import EntidadeAuditada, AcaoAuditoria

CAMPOS_IGNORADOS = {"created_at", "updated_at", "id"}


def diff_campos(antes: dict | None, depois: dict | None) -> tuple[dict, dict]:
    """Retorna (anteriores, novos) apenas com os campos que mudaram.

    `antes=None` (CREATE) devolve depois inteiro em `novos`, `anteriores={}`.
    `depois=None` (DELETE) devolve antes inteiro em `anteriores`, `novos={}`.
    """
    antes = antes or {}
    depois = depois or {}
    chaves = (set(antes) | set(depois)) - CAMPOS_IGNORADOS

    anteriores, novos = {}, {}
    for chave in chaves:
        v_antes, v_depois = antes.get(chave), depois.get(chave)
        if v_antes != v_depois:
            anteriores[chave] = v_antes
            novos[chave] = v_depois
    return anteriores, novos


async def registrar(
    db: AsyncSession,
    *,
    entidade: EntidadeAuditada,
    entidade_id: uuid.UUID,
    acao: AcaoAuditoria,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
    anteriores: dict | None = None,
    novos: dict | None = None,
    justificativa: str | None = None,
) -> None:
    """Grava um registro de auditoria. `usuario_id` deve vir sempre da sessão
    autenticada (RN-05) — nunca de payload do cliente."""
    db.add(AuditoriaDadosMestres(
        id=uuid.uuid4(),
        entidade=entidade.value,
        entidade_id=entidade_id,
        acao=acao.value,
        valores_anteriores=anteriores or None,
        valores_novos=novos or None,
        justificativa=justificativa,
        usuario_id=usuario_id,
        ip_origem=ip_origem,
        criado_em=datetime.now(),
    ))
    await db.flush()


async def listar(
    db: AsyncSession,
    entidade: EntidadeAuditada | None = None,
    entidade_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditoriaDadosMestres]:
    stmt = select(AuditoriaDadosMestres).order_by(desc(AuditoriaDadosMestres.criado_em))
    if entidade:
        stmt = stmt.where(AuditoriaDadosMestres.entidade == entidade.value)
    if entidade_id:
        stmt = stmt.where(AuditoriaDadosMestres.entidade_id == entidade_id)
    stmt = stmt.limit(min(limit, 200)).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

**Pontos críticos (não pular):**
- `diff_campos` grava só o que mudou — evita blob gigante em `UPDATE` de um único campo, no espírito do comentário original da spec ("Somente campos alterados").
- Todo chamador de `registrar()` precisa passar `usuario_id=current_user.id` vindo da dependência FastAPI, nunca de um campo do schema — é a mesma disciplina já aplicada em `ajustar_inventario_item` (`service.py:474-487`) para o BUG-01.

---

## 7. Etapa 6 — Service (`app/modules/equipamentos/service.py`)

Adicionar ao final do arquivo (após a seção de Slots existente, `service.py:270-288`):

```python
# ============================================================
# Slots — CRUD completo
# ============================================================

async def atualizar_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    dados: SlotInventarioUpdate,
    usuario_id: uuid.UUID | None,
    ip_origem: str | None = None,
) -> SlotInventario:
    """Atualiza um slot. Troca de modelo_id (PN esperado) é bloqueada
    enquanto houver instalação ativa nesse slot em qualquer aeronave —
    RN-04: slot é global da frota, então a troca afeta todas as aeronaves.

    Raises:
        EntidadeNaoEncontradaError: slot ou novo modelo_id inexistente.
        ConflitoNegocioError: (nome_posicao, sistema) já em uso; ou troca de
            modelo_id com instalação ativa.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    antes = {c.name: getattr(slot, c.name) for c in slot.__table__.columns}

    if dados.modelo_id is not None and dados.modelo_id != slot.modelo_id:
        res = await db.execute(
            select(Instalacao.id).where(Instalacao.slot_id == slot_id, Instalacao.data_remocao.is_(None))
        )
        if res.first():
            raise domain_exc.ConflitoNegocioError(
                "Não é possível trocar o PN esperado: este slot tem instalação ativa em ao menos uma aeronave."
            )
        if not await db.get(ModeloEquipamento, dados.modelo_id):
            raise domain_exc.EntidadeNaoEncontradaError(f"Equipamento {dados.modelo_id} não encontrado.")
        slot.modelo_id = dados.modelo_id

    novo_nome = dados.nome_posicao if dados.nome_posicao is not None else slot.nome_posicao
    novo_sistema = dados.sistema if dados.sistema is not None else slot.sistema
    if (novo_nome, novo_sistema) != (slot.nome_posicao, slot.sistema):
        res = await db.execute(
            select(SlotInventario.id).where(
                SlotInventario.nome_posicao == novo_nome,
                SlotInventario.sistema == novo_sistema,
                SlotInventario.id != slot_id,
            )
        )
        if res.first():
            raise domain_exc.ConflitoNegocioError("Já existe um slot com este nome nesta localização.")

    for campo in ("nome_posicao", "sistema", "posicao_xlsx", "descricao", "ordem_exibicao"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(slot, campo, valor)

    await db.flush()

    depois = {c.name: getattr(slot, c.name) for c in slot.__table__.columns}
    anteriores, novos = auditoria_service.diff_campos(antes, depois)
    if novos:
        await auditoria_service.registrar(
            db, entidade=EntidadeAuditada.SLOT, entidade_id=slot.id, acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id, ip_origem=ip_origem, anteriores=anteriores, novos=novos,
        )
    return slot


async def _contar_instalacoes_slot(db: AsyncSession, slot_id: uuid.UUID) -> list[dict]:
    """Lista aeronaves/instalações vinculadas a um slot (ativas e históricas)."""
    res = await db.execute(
        select(Aeronave.matricula, Instalacao.data_remocao)
        .join(Instalacao, Instalacao.aeronave_id == Aeronave.id)
        .where(Instalacao.slot_id == slot_id)
    )
    return [{"aeronave": m, "ativa": rem is None} for m, rem in res.all()]


async def remover_slot(
    db: AsyncSession, slot_id: uuid.UUID, justificativa: str,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um slot sem nenhuma instalação vinculada.

    Raises:
        EntidadeNaoEncontradaError: slot inexistente.
        ConflitoNegocioError: existe instalação (ativa ou histórica) vinculada.
    """
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")

    ocupacao = await _contar_instalacoes_slot(db, slot_id)
    if ocupacao:
        raise domain_exc.ConflitoNegocioError(
            f"Não é possível excluir: {len(ocupacao)} instalação(ões) vinculada(s) a este slot. "
            "Considere inativar o slot."
        )

    antes = {c.name: getattr(slot, c.name) for c in slot.__table__.columns}
    await db.delete(slot)
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.SLOT, entidade_id=slot_id, acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id, ip_origem=ip_origem, anteriores=antes, justificativa=justificativa,
    )


async def inativar_slot(
    db: AsyncSession, slot_id: uuid.UUID, usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> SlotInventario:
    """Marca ativo=False. Não exige ausência de instalações (RF-05)."""
    slot = await db.get(SlotInventario, slot_id)
    if not slot:
        raise domain_exc.EntidadeNaoEncontradaError("Slot não encontrado.")
    slot.ativo = False
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.SLOT, entidade_id=slot_id, acao=AcaoAuditoria.UPDATE,
        usuario_id=usuario_id, ip_origem=ip_origem, anteriores={"ativo": True}, novos={"ativo": False},
    )
    return slot


# ============================================================
# Itens de Equipamento — CRUD completo
# ============================================================

async def atualizar_item(
    db: AsyncSession, item_id: uuid.UUID, dados: ItemEquipamentoUpdate,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> ItemEquipamento:
    """Corrige S/N ou status de um item físico.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: novo S/N já usado por outro item do mesmo PN.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    antes = {"numero_serie": item.numero_serie, "status": item.status}

    if dados.numero_serie is not None and dados.numero_serie != item.numero_serie:
        if await _buscar_item_por_sn(db, item.modelo_id, dados.numero_serie):
            raise domain_exc.ConflitoNegocioError(f"S/N '{dados.numero_serie}' já cadastrado para este P/N.")
        item.numero_serie = dados.numero_serie
    if dados.status is not None:
        item.status = dados.status.value

    await db.flush()
    anteriores, novos = auditoria_service.diff_campos(antes, {"numero_serie": item.numero_serie, "status": item.status})
    if novos:
        await auditoria_service.registrar(
            db, entidade=EntidadeAuditada.ITEM, entidade_id=item.id, acao=AcaoAuditoria.UPDATE,
            usuario_id=usuario_id, ip_origem=ip_origem, anteriores=anteriores, novos=novos,
        )
    return item


async def excluir_item(
    db: AsyncSession, item_id: uuid.UUID, justificativa: str,
    usuario_id: uuid.UUID | None, ip_origem: str | None = None,
) -> None:
    """Exclui fisicamente um item sem instalação vinculada.

    Nome deliberadamente distinto de `remover_item` (service.py:714), que já
    significa "encerrar a instalação ativa de um item" — não confundir.

    Raises:
        EntidadeNaoEncontradaError: item inexistente.
        ConflitoNegocioError: existe instalação vinculada a este item.
    """
    item = await db.get(ItemEquipamento, item_id)
    if not item:
        raise domain_exc.EntidadeNaoEncontradaError("Item não encontrado.")

    res = await db.execute(select(Instalacao.id).where(Instalacao.item_id == item_id))
    if res.first():
        raise domain_exc.ConflitoNegocioError(
            "Não é possível excluir: este item tem instalação vinculada. Considere status=REMOVIDO."
        )

    antes = {"numero_serie": item.numero_serie, "modelo_id": str(item.modelo_id), "status": item.status}
    await db.delete(item)
    await db.flush()
    await auditoria_service.registrar(
        db, entidade=EntidadeAuditada.ITEM, entidade_id=item_id, acao=AcaoAuditoria.DELETE,
        usuario_id=usuario_id, ip_origem=ip_origem, anteriores=antes, justificativa=justificativa,
    )
```

Também editar `_buscar_slots` (`service.py:341-348`) para filtrar slots ativos por padrão:

```python
async def _buscar_slots(db: AsyncSession, nome: str | None = None, apenas_ativos: bool = True) -> list[SlotInventario]:
    stmt = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if apenas_ativos:
        stmt = stmt.where(SlotInventario.ativo.is_(True))
    if nome:
        ...  # sem alteração no resto da função
    return list((await db.execute(stmt.order_by(SlotInventario.ordem_exibicao, SlotInventario.nome_posicao))).scalars().all())
```

E instrumentar `criar_slot` (`service.py:270-282`) com UNIQUE + auditoria, e `criar_modelo`/`atualizar_modelo`/`remover_modelo` (`service.py:57-190`) com chamadas a `auditoria_service.registrar(...)` no mesmo padrão acima — passar `usuario_id`/`ip_origem` como novos parâmetros dessas funções (o router já tem acesso a `current_user` e `request`).

**Pontos críticos (não pular):**
- **Colisão de nome deliberadamente evitada:** `service.remover_item` (linha 714) já existe e significa "encerrar instalação". A função nova **precisa** se chamar `excluir_item` — reaproveitar o nome `remover_item` sobrescreveria o fluxo operacional de desinstalação usado por `PATCH /instalacoes/{id}/remover`.
- `_contar_instalacoes_slot` inclui instalações **históricas** (não só ativas) — RN-03 da spec é mais rígida que a de item (RN-06), porque um slot removido apaga rastreabilidade de toda a frota, não de uma linha isolada.
- `atualizar_slot`/`atualizar_item` só chamam `auditoria_service.registrar` quando `diff_campos` encontra mudança real — evita registro de auditoria vazio em um PATCH que não alterou nada.
- Imports novos no topo de `service.py`: `auditoria_service`, `EntidadeAuditada`, `AcaoAuditoria`, `SlotInventarioUpdate`, `ItemEquipamentoUpdate`.

---

## 8. Etapa 7 — Router (`app/modules/equipamentos/router.py`)

Inserir nas seções já existentes de Slots (após linha 107) e Itens (após linha 137), e uma seção nova de Auditoria ao final:

```python
@router.patch("/slots/{slot_id}", response_model=schemas.SlotInventarioOut, summary="Atualizar slot")
async def atualizar_slot(
    slot_id: uuid.UUID, dados: schemas.SlotInventarioUpdate,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    slot = await service.atualizar_slot(
        db, slot_id, dados, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.SlotInventarioOut.model_validate(slot)


@router.delete("/slots/{slot_id}", summary="Excluir slot")
async def remover_slot(
    slot_id: uuid.UUID, dados: schemas.RemocaoJustificada,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    await service.remover_slot(
        db, slot_id, dados.justificativa, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return {"success": True, "message": "Slot removido com sucesso."}


@router.post("/slots/{slot_id}/inativar", response_model=schemas.SlotInventarioOut, summary="Inativar slot")
async def inativar_slot(slot_id: uuid.UUID, db: DBSession, request: Request, current_user: AdminRequired):
    slot = await service.inativar_slot(
        db, slot_id, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.SlotInventarioOut.model_validate(slot)


@router.get("/slots/{slot_id}/ocupacao", summary="Listar aeronaves que ocupam o slot")
async def ocupacao_slot(slot_id: uuid.UUID, db: DBSession, _: AdminRequired):
    return await service._contar_instalacoes_slot(db, slot_id)


@router.patch("/itens/{item_id}", response_model=schemas.ItemEquipamentoOut, summary="Atualizar item")
async def atualizar_item(
    item_id: uuid.UUID, dados: schemas.ItemEquipamentoUpdate,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    item = await service.atualizar_item(
        db, item_id, dados, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return schemas.ItemEquipamentoOut.model_validate(item)


@router.delete("/itens/{item_id}", summary="Excluir item")
async def excluir_item(
    item_id: uuid.UUID, dados: schemas.RemocaoJustificada,
    db: DBSession, request: Request, current_user: AdminRequired,
):
    await service.excluir_item(
        db, item_id, dados.justificativa, usuario_id=current_user.id,
        ip_origem=request.client.host if request.client else None,
    )
    return {"success": True, "message": "Item removido com sucesso."}


# ---- Auditoria de Dados Mestres ----

@router.get("/auditoria", response_model=list[schemas.AuditoriaOut], summary="Consultar auditoria de dados mestres")
async def listar_auditoria(
    db: DBSession, _: AdminRequired,
    entidade: EntidadeAuditada | None = None,
    entidade_id: uuid.UUID | None = None,
    limit: int = 50, offset: int = 0,
):
    registros = await auditoria_service.listar(db, entidade, entidade_id, limit, offset)
    return [schemas.AuditoriaOut.model_validate(r) for r in registros]
```

Imports novos no topo: `from fastapi import Request`, `from app.modules.equipamentos import auditoria_service`, `from app.shared.core.enums import EntidadeAuditada`.

**Pontos críticos (não pular):**
- `_contar_instalacoes_slot` é "privada" por convenção (`_` no nome) mas reaproveitada direto no endpoint de ocupação — mesmo padrão de `router.py:89` que já expõe `service.listar_slots` sem passar por uma função pública dedicada. Se preferir manter a convenção estrita, renomear para `contar_instalacoes_slot` (pública) na Etapa 6.
- `DELETE /slots/{slot_id}` e `DELETE /itens/{item_id}` recebem corpo JSON (`RemocaoJustificada`) — FastAPI aceita body em `DELETE`; testar explicitamente porque alguns clientes HTTP omitem body em DELETE por padrão (o `apiFetch` do frontend já suporta, mesmo padrão usado por `pedidos` — ver `pedidos/router.py` para o precedente).
- Nenhuma destas rotas colide com `/{equipamento_id}` (`router.py:51`) porque todas têm 2+ segmentos de path.

---

## 9. Etapa 8 — Consumidor de slots (`app/modules/equipamentos/xlsx_service.py`)

```python
# xlsx_service.py:138-142 — filtrar apenas slots ativos
res_slots = await db.execute(
    select(SlotInventario, ModeloEquipamento)
    .join(ModeloEquipamento, SlotInventario.modelo_id == ModeloEquipamento.id)
    .where(SlotInventario.ativo.is_(True))
)
slots_ativos = res_slots.all()
```

**Pontos críticos (não pular):** sem este filtro, um slot inativado continua entrando no preview de importação XLSX e recebendo o serial sintético `XXXXXXX-{nome_posicao}` (mesmo bug descrito na Seção 1 da spec, só que para slots inativos em vez de slots sem `posicao_xlsx`).

---

## 10. Etapa 9 — UI (`app/web/templates/configuracoes.html` + `app/web/static/js/configuracoes_inventario.js`)

### 10.1 Template

No card "Equipamentos e PNs" (`configuracoes.html:77-93`), adicionar um botão após `#btn-gerenciar-catalogo`:

```html
<button class="btn btn-equipamento" id="btn-gerenciar-slots" style="width: 100%;">
    <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"
        style="vertical-align: middle; margin-right: 5px;">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
    Gerenciar Slots
</button>
```

Dois modais novos, clonando o esqueleto `glass-panel` de `#modal-catalogo` (`configuracoes.html:405-440`):
- `#modal-slots` — tabela (Loc, Slot, PN esperado, `posicao_xlsx`, ativo, ações Editar/Inativar/Remover/Histórico) + botão "Novo Slot".
- `#modal-form-slot` — formulário de criar/editar slot (campos: `nome_posicao`, `sistema`, `posicao_xlsx`, `modelo_id` como `<select>` populado do catálogo, `descricao`, `ordem_exibicao`).
- Reaproveitar `#modal-catalogo` existente: adicionar botão "Histórico" (ícone de relógio) em cada linha, ao lado de Editar/Remover (`configuracoes.js:759-766`).

### 10.2 JavaScript (`configuracoes_inventario.js`)

Novo arquivo (precedente: `configuracoes_publicacoes.js`, extraído do principal por tamanho — `configuracoes.js` já tem 1937 linhas). Carregar em `configuracoes.html` junto da linha 1186:

```html
<script src="/static/js/configuracoes_inventario.js"></script>
```

Estrutura seguindo `configuracoes.js:690-840` (abrir modal → `carregarLista*` via `apiFetch` → renderizar linhas com `escapeHtml` → `addEventListener` nos botões, nunca `onclick` inline):

```javascript
// app/web/static/js/configuracoes_inventario.js
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-gerenciar-slots')?.addEventListener('click', openModalSlots);
    document.getElementById('btn-close-modal-slots')?.addEventListener('click', closeModalSlots);
    document.getElementById('btn-novo-slot')?.addEventListener('click', () => openModalFormSlot());
    document.getElementById('formSlot')?.addEventListener('submit', salvarSlot);
});

let slotsCache = [];

async function carregarListaSlots() {
    const tbody = document.getElementById('lista-slots-body');
    if (!tbody) return;
    try {
        slotsCache = await apiFetch('/equipamentos/slots/');
        tbody.innerHTML = '';
        slotsCache.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${escapeHtml(s.sistema)}</td>
                <td>${escapeHtml(s.nome_posicao)}</td>
                <td>${escapeHtml(s.posicao_xlsx)}</td>
                <td>${s.ativo ? 'Ativo' : 'Inativo'}</td>
                <td class="acoes"></td>
            `;
            const acoes = tr.querySelector('.acoes');
            const btnEdit = document.createElement('button');
            btnEdit.className = 'btn-icon';
            btnEdit.addEventListener('click', () => openModalFormSlot(s.id));
            acoes.appendChild(btnEdit);
            // botões de inativar/remover/histórico seguem o mesmo padrão
            tbody.appendChild(tr);
        });
    } catch (e) {
        showToast(e.message || 'Erro ao carregar slots.', 'error');
    }
}
```

(Código completo a implementar seguindo fielmente o molde já citado — este trecho fixa a estrutura mínima obrigatória: `apiFetch`, `escapeHtml`, `addEventListener`, `showToast`.)

**Pontos críticos (não pular):**
- CSP do projeto é `script-src 'self'` sem `'unsafe-inline'` — qualquer `onclick=` inline simplesmente não executa (RN-16, `docs/ia/rules.ctx`).
- `#modal-slots` usa `data-role="ADMINISTRADOR"` no botão do card, coerente com a decisão de escopo (admin-only) e com `/configuracoes` já ser `AdminRequired` no backend.

---

## 11. Etapa 10 — Testes (`tests/unit/test_gestao_inventario.py`)

Usar as fixtures já existentes em `tests/conftest.py` — não criar fixtures novas: `client`, `db`, `usuario_e_token` (ADMINISTRADOR), `usuario_encarregado_e_token`, `dados_aeronave_valida`, `dados_equipamento_valido`. Seguir o padrão de helpers privados de `tests/unit/test_inventario.py` (`_criar_modelo`, `_criar_slot`, `_criar_aeronave`).

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | Criar slot sem `posicao_xlsx` | 422 |
| 2 | Criar slot com `(nome_posicao, sistema)` duplicado | 409 |
| 3 | Criar slot via API e depois rodar preview XLSX com PN/posição correspondentes | slot é encontrado (regressão do bug da Seção 1) |
| 4 | Editar `nome_posicao`/`descricao` de slot | 200, auditoria UPDATE com diff correto |
| 5 | Editar `modelo_id` de slot com instalação ativa | 409 |
| 6 | Editar `modelo_id` de slot sem instalação | 200 |
| 7 | Remover slot com instalação (ativa ou histórica) | 409, sugestão "inativar" |
| 8 | Remover slot sem instalação | 204/200, auditoria DELETE, exige `justificativa` (ausente → 422) |
| 9 | Inativar slot | `ativo=false`; some de `GET /equipamentos/slots/` (lista padrão) e do preview XLSX |
| 10 | Editar S/N de item para valor já usado no mesmo PN | 409 |
| 11 | Editar S/N de item para valor livre | 200, auditoria UPDATE |
| 12 | Excluir item com instalação vinculada | 409, sugestão `status=REMOVIDO` |
| 13 | Excluir item sem instalação | 200, auditoria DELETE |
| 14 | ENCARREGADO tenta qualquer escrita de slot/item | 403 |
| 15 | `GET /equipamentos/auditoria?entidade=SLOT&entidade_id=...` | retorna os registros na ordem certa |
| 16 | Suíte de regressão `test_inventario.py`, `test_equipamentos.py`, `test_equipamentos_xlsx.py` | continua verde sem alteração |

---

## 12. Verificação end-to-end

```bash
alembic upgrade head                                              # aplica a migration
alembic downgrade -1 && alembic upgrade head                      # confirma downgrade/upgrade limpos
pytest tests/unit/test_gestao_inventario.py -v                    # testes do plano
pytest tests/unit/test_inventario.py tests/unit/test_equipamentos.py tests/unit/test_equipamentos_xlsx.py -v  # regressão (RNF-08)
pytest -q                                                          # suíte completa
ruff check app/modules/equipamentos/ app/shared/core/enums.py
python scripts/run_app.py                                         # smoke manual
```

**Smoke manual** (navegador, usuário ADMINISTRADOR):
1. Acessar `/configuracoes` → card "Equipamentos e PNs" → "Gerenciar Slots".
2. Criar um slot novo com `posicao_xlsx` preenchido.
3. Abrir `/inventario`, escolher uma aeronave, confirmar que o slot novo aparece na Loc certa (vazio).
4. Subir um XLSX de teste com PN/posição batendo com o slot novo → preview mostra o S/N encontrado (não `XXXXXXX-...`).
5. Editar o slot (descrição, ordem) e salvar — toast de sucesso.
6. Inativar o slot — confirmar que ele some de `/inventario` e do preview XLSX.
7. Tentar remover um slot ocupado — modal mostra a lista de aeronaves impedientes.
8. No catálogo de PNs, clicar "Histórico" de um item — ver os registros CREATE/UPDATE com autor e data.
9. Corrigir um S/N de item errado pelo CRUD de itens.
10. Abrir DevTools → Console: nenhuma violação de CSP durante todo o fluxo.
11. Logar como ENCARREGADO: botões de escrita ocultos; tentativa direta via API retorna 403.

---

## 13. Riscos e armadilhas conhecidas

| # | Risco | Mitigação |
|---|---|---|
| R1 | `ALTER TABLE ... NOT NULL` falha se houver `sistema`/`posicao_xlsx` nulos no banco local | Backfill (`UPDATE ... SET x = ''`) **antes** do `batch_alter_table`, dentro da própria migration (Etapa 3) |
| R2 | `SlotInventarioCreate` com campos agora obrigatórios quebra algum chamador que hoje omite `sistema`/`posicao_xlsx` | Grep por `POST /equipamentos/slots/` em `app/web/static/js/` e `tests/` antes de mesclar; hoje não há formulário de criação de slot na UI, só a API crua |
| R3 | Confundir `excluir_item` (novo, exclusão física do item) com `remover_item` (existente, encerra instalação) | Nomes deliberadamente diferentes (Etapa 7); revisar imports no router para não chamar a função errada |
| R4 | Slot inativado continua aparecendo no preview XLSX se o filtro da Etapa 8 for esquecido | Teste #3 e #9 da Etapa 10 cobrem isso explicitamente |
| R5 | `usuario_id` de auditoria vindo do payload em vez da sessão, reintroduzindo o BUG-01 | Toda assinatura de service novo recebe `usuario_id` como parâmetro explícito setado pelo router a partir de `current_user.id` — nunca de um campo do schema |
| R6 | `EntidadeAuditada`/`AcaoAuditoria` merge simultâneo em `enums.py` com outra feature em paralelo | Commits pequenos; conferir `git diff` de `enums.py` antes de abrir PR |
| R7 | Migration em conflito de `down_revision` com outra branch que também gera migration a partir do mesmo head `b63e385e3395` | Reconferir `alembic heads` (deve haver 1 só) antes de abrir PR; rebase se necessário |
| R8 | Duas fontes de PN por slot já divergentes (`seed_slots.py` vs `scripts/maintenance/force_sync_slots.py` — MDP, DVR, UFCP, PIC/NAV) podem gerar confusão ao editar slot pela UI nova | Fora de escopo corrigir aqui; documentar no PR como débito técnico pré-existente, não introduzido por este plano |

---

## 14. Checklist de aceite (espelha a spec v2.0 §11 e §18)

- [ ] `PATCH /equipamentos/slots/{id}` edita slot; bloqueia troca de PN esperado com instalação ativa (409).
- [ ] `DELETE /equipamentos/slots/{id}` exige justificativa; bloqueia se houver qualquer instalação vinculada (409).
- [ ] `POST /equipamentos/slots/{id}/inativar` marca `ativo=false` sem apagar histórico.
- [ ] `GET /equipamentos/slots/{id}/ocupacao` lista as aeronaves impedientes.
- [ ] Criar slot sem `posicao_xlsx` retorna 422.
- [ ] Slot duplicado `(nome_posicao, sistema)` retorna 409.
- [ ] `PATCH /equipamentos/itens/{id}` corrige S/N/status; S/N duplicado no mesmo PN retorna 409.
- [ ] `DELETE /equipamentos/itens/{id}` exige justificativa; bloqueia se houver instalação (409).
- [ ] Toda escrita em PN/Slot/Item grava 1 registro em `auditoria_dados_mestres` com `usuario_id` da sessão (nunca do payload).
- [ ] `GET /equipamentos/auditoria` consulta a trilha, filtrável por entidade.
- [ ] Slot inativo não aparece em `/inventario` nem no preview XLSX.
- [ ] Slot novo criado pela API casa corretamente no preview XLSX (regressão do bug da Seção 1 da spec).
- [ ] ENCARREGADO/MANTENEDOR/INSPETOR recebem 403 em toda escrita nova.
- [ ] UI: modal "Gerenciar Slots" funcional em `/configuracoes`; zero violação de CSP.
- [ ] `pytest -q` verde (suíte completa, sem regressão em `/inventario` ou XLSX).
- [ ] `ruff check .` limpo.
- [ ] `alembic upgrade head` e `alembic downgrade -1` funcionam sem erro.
