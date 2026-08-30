"""
app/equipamentos/models.py
Modelos ORM para a gestão de equipamentos aeronáuticos.

Nova Estrutura:
    - ModeloEquipamento: Catálogo de Part Numbers (PNs únicos)
    - SlotInventario: Definição de posições na aeronave (ex: MDP1, MDP2)
    - ItemEquipamento: Instância física vinculada ao PN (Serial Number)
    - Instalacao: Registro histórico de item em um slot de uma aeronave
"""

from __future__ import annotations
import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Date, ForeignKey, func, UniqueConstraint, Index, JSON, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import StatusItem  # noqa: F401  (usado no default de ItemEquipamento.status)

if TYPE_CHECKING:
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario
    from app.modules.vencimentos.models import EquipamentoControle, ControleVencimento


class ModeloEquipamento(Base):
    """
    Representa o Catálogo de Part Numbers (PN).
    É a entidade base que define o que o equipamento é.
    """
    __tablename__ = "modelos_equipamento"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    part_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    nome_generico: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    slots: Mapped[list["SlotInventario"]] = relationship(back_populates="modelo")
    itens: Mapped[list["ItemEquipamento"]] = relationship(back_populates="modelo")
    # Template de controles (TBV, RBA) vinculados ao PN
    controles_template: Mapped[list["EquipamentoControle"]] = relationship(back_populates="modelo")

    def __repr__(self) -> str:
        return f"<ModeloEquipamento pn={self.part_number!r}>"


class SlotInventario(Base):
    """
    Representa uma posição física pré-definida na aeronave (LCN/Slot).
    Exemplos: MDP1, MDP2, CMFD1, CMFD2, VUHF1.
    """
    __tablename__ = "slots_inventario"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome_posicao: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # NULABILIDADE FASEADA — `sistema`, `posicao_xlsx` e `created_at` continuam
    # nullable aqui de propósito. A obrigatoriedade que corrige o bug de
    # integração do XLSX é a do schema Pydantic (SlotInventarioCreate); apertar
    # o banco é uma alteração destrutiva, isolada num PR próprio.
    # Declarar nullable=False antes disso faria o `alembic --autogenerate`
    # emitir o ALTER destrutivo por conta própria.
    # Ver docs/BACKLOG/modulo_inventario/plano_implementacao.md §0.1.
    sistema: Mapped[str | None] = mapped_column(String(50), nullable=True)
    posicao_xlsx: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="RESTRICT"), nullable=False
    )
    descricao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Ordem de exibição na grade de /inventario. Sem valor definido, o slot vai
    # para o fim da lista (ver service._ordenar_inventario).
    ordem_exibicao: Mapped[int | None] = mapped_column(nullable=True)
    # Inativação em vez de exclusão física quando o slot já tem histórico:
    # apagar a linha levaria junto a rastreabilidade de toda a frota.
    ativo: Mapped[bool] = mapped_column(default=True, server_default="1", nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # --- Relacionamentos ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="slots")
    instalacoes: Mapped[list["Instalacao"]] = relationship(back_populates="slot")

    def __repr__(self) -> str:
        return f"<SlotInventario nome={self.nome_posicao!r} pn={self.modelo_id}>"


class ItemEquipamento(Base):
    """
    Instância física de um PN (box), identificada por Serial Number.
    A unicidade é garantida para a combinação (Modelo/PN + SN).
    """
    __tablename__ = "itens_equipamento"
    __table_args__ = (
        UniqueConstraint("modelo_id", "numero_serie", name="uq_item_sn_per_pn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    numero_serie: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusItem.ATIVO.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # --- Relacionamentos ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="itens")
    instalacoes: Mapped[list["Instalacao"]] = relationship(back_populates="item")
    controles_vencimento: Mapped[list["ControleVencimento"]] = relationship(back_populates="item")

    def __repr__(self) -> str:
        return f"<ItemEquipamento sn={self.numero_serie!r}>"


class Instalacao(Base):
    """
    Registro histórico e atual de um Item em um Slot de uma Aeronave.
    """
    __tablename__ = "instalacoes"
    __table_args__ = (
        # No máximo uma instalação ativa por (slot, aeronave) — RISCO-05,
        # docs/backlog/revisor/achados_equipamentos.md. A invariante real é
        # por par (slot_id, aeronave_id), não por slot_id isolado: um slot é
        # uma posição compartilhada por toda a frota, então cada aeronave tem
        # sua própria instalação ativa no mesmo slot_id — confirmado contra
        # dados reais (0 violações agrupando por par; dezenas de "duplicatas"
        # falsas agrupando só por slot_id, que são aeronaves diferentes).
        Index(
            "uq_instalacao_ativa_por_slot_aeronave", "slot_id", "aeronave_id",
            unique=True, sqlite_where=text("data_remocao IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("itens_equipamento.id"), nullable=False, index=True)
    aeronave_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aeronaves.id"), nullable=False, index=True)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slots_inventario.id"), nullable=False, index=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    data_instalacao: Mapped[date] = mapped_column(Date, nullable=False)
    data_remocao: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Timestamp do EVENTO de remoção. Não usar updated_at para isso: qualquer
    # update posterior no registro corromperia o histórico.
    removido_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Data/hora em que a remoção foi registrada (histórico imutável)",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="instalacoes")
    slot: Mapped["SlotInventario"] = relationship(back_populates="instalacoes")
    aeronave: Mapped["Aeronave"] = relationship(back_populates="instalacoes")  # type: ignore

    def __repr__(self) -> str:
        return f"<Instalacao item_id={self.item_id} slot_id={self.slot_id}>"


class AuditoriaDadosMestres(Base):
    """
    Trilha append-only de escritas em dados mestres do inventário
    (ModeloEquipamento, SlotInventario, ItemEquipamento).

    Nenhuma rotina da aplicação faz UPDATE ou DELETE sobre esta tabela —
    mesmo padrão de ExecucaoVencimentoHistorico (vencimentos/models.py).

    `usuario_id` vem SEMPRE da sessão autenticada, nunca de payload do
    cliente: aceitar o autor por payload foi o BUG-01 já corrigido em
    `ajustar_inventario_item` (service.py), e a mesma disciplina vale aqui.
    """
    __tablename__ = "auditoria_dados_mestres"
    __table_args__ = (
        Index("ix_auditoria_entidade", "entidade", "entidade_id"),
        Index("ix_auditoria_criado_em", "criado_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # String, não Enum nativo — mesmo padrão de ItemEquipamento.status: o enum
    # é aplicacional, não vira constraint de banco.
    entidade: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    acao: Mapped[str] = mapped_column(String(10), nullable=False)
    # JSON (não JSONB — SQLite). Todo valor gravado precisa ser serializável
    # por json.dumps: UUID e datetime passam por auditoria_service.snapshot()
    # antes de chegar aqui.
    valores_anteriores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valores_novos: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    justificativa: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Nullable seguindo o precedente de Instalacao.usuario_id: a trilha não
    # pode impedir a remoção de um usuário nem sumir junto com ele.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    # 45 caracteres cobrem IPv6. Atrás do nginx da VPS este campo registra o
    # IP do proxy, não o do usuário — limitação conhecida, ver a spec §6.6.
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    usuario: Mapped["Usuario | None"] = relationship()

    def __repr__(self) -> str:
        return f"<AuditoriaDadosMestres {self.entidade}:{self.acao} id={self.entidade_id}>"
