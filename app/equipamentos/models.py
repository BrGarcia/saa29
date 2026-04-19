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

from sqlalchemy import String, DateTime, Date, Integer, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.enums import StatusItem, StatusVencimento, OrigemControle

if TYPE_CHECKING:
    from app.aeronaves.models import Aeronave


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
    sistema: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="RESTRICT"), nullable=False
    )

    # --- Relacionamentos ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="slots")
    instalacoes: Mapped[list["Instalacao"]] = relationship(back_populates="slot")

    def __repr__(self) -> str:
        return f"<SlotInventario nome={self.nome_posicao!r} pn={self.modelo_id}>"


class TipoControle(Base):
    """
    Define um tipo de controle periódico de manutenção (TBV, RBA, CRI).
    """
    __tablename__ = "tipos_controle"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    descricao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    periodicidade_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    vencimentos: Mapped[list["ControleVencimento"]] = relationship(back_populates="tipo_controle")
    equipamento_controles: Mapped[list["EquipamentoControle"]] = relationship(back_populates="tipo_controle")


class EquipamentoControle(Base):
    """
    Relacionamento N:N entre ModeloEquipamento e TipoControle.
    Define quais controles um PN exige.
    """
    __tablename__ = "equipamento_controles"
    __table_args__ = (
        UniqueConstraint("modelo_id", "tipo_controle_id", name="uq_equip_controle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="CASCADE"), nullable=False
    )
    tipo_controle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_controle.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relacionamentos ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="controles_template")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="equipamento_controles")


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

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("itens_equipamento.id"), nullable=False, index=True)
    aeronave_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aeronaves.id"), nullable=False, index=True)
    slot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slots_inventario.id"), nullable=False, index=True)
    data_instalacao: Mapped[date] = mapped_column(Date, nullable=False)
    data_remocao: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="instalacoes")
    slot: Mapped["SlotInventario"] = relationship(back_populates="instalacoes")
    aeronave: Mapped["Aeronave"] = relationship(back_populates="instalacoes")  # type: ignore

    def __repr__(self) -> str:
        return f"<Instalacao item_id={self.item_id} slot_id={self.slot_id}>"


class ControleVencimento(Base):
    """
    Controle real de manutenção vinculado a um item físico.
    """
    __tablename__ = "controle_vencimentos"
    __table_args__ = (
        UniqueConstraint("item_id", "tipo_controle_id", name="uq_item_controle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("itens_equipamento.id"), nullable=False, index=True)
    tipo_controle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tipos_controle.id"), nullable=False)
    data_ultima_exec: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_vencimento: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StatusVencimento.OK.value)
    origem: Mapped[str] = mapped_column(String(20), nullable=False, default=OrigemControle.PADRAO.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="controles_vencimento")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="vencimentos")
