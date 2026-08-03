"""
app/modules/vencimentos/models.py
Modelos ORM para a inteligência temporal de manutenções e vencimentos.
"""

from __future__ import annotations
import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, Date, Integer, ForeignKey, func, UniqueConstraint, Index, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base
from app.shared.core.enums import StatusVencimento, OrigemControle

if TYPE_CHECKING:
    from app.modules.equipamentos.models import ModeloEquipamento, ItemEquipamento
    from app.modules.auth.models import Usuario

class TipoControle(Base):
    """
    Catálogo de códigos de controle (TLV, CRI, DWL, RBA, TBO...).
    A periodicidade é definida no vínculo com o modelo (EquipamentoControle).
    """
    __tablename__ = "tipos_controle"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    descricao: Mapped[str | None] = mapped_column(String(300), nullable=True)
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
        CheckConstraint("periodicidade_meses > 0", name="ck_equipamento_controle_periodicidade_positiva"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    modelo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modelos_equipamento.id", ondelete="CASCADE"), nullable=False
    )
    tipo_controle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_controle.id", ondelete="CASCADE"), nullable=False
    )
    periodicidade_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    alterado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    # --- Relacionamentos ---
    modelo: Mapped["ModeloEquipamento"] = relationship(back_populates="controles_template")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="equipamento_controles")
    alterado_por: Mapped["Usuario"] = relationship() # type: ignore


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
    executado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="controles_vencimento")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="vencimentos")
    executado_por: Mapped["Usuario"] = relationship() # type: ignore
    prorrogacoes: Mapped[list["ProrrogacaoVencimento"]] = relationship(back_populates="controle", cascade="all, delete-orphan")


class ProrrogacaoVencimento(Base):
    """
    Registro de prorrogação (extensão de prazo) de um vencimento pela Engenharia.
    """
    __tablename__ = "prorrogacoes_vencimento"
    __table_args__ = (
        # No máximo uma prorrogação ativa por controle (RISCO-03,
        # docs/backlog/revisor/achados_vencimentos.md) — rede de segurança
        # contra a corrida de duas requisições concorrentes de prorrogação.
        Index(
            "uq_prorrogacao_ativa_por_controle", "controle_id",
            unique=True, sqlite_where=text("ativo = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    controle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("controle_vencimentos.id"), nullable=False, index=True)
    numero_documento: Mapped[str] = mapped_column(String(50), nullable=False)
    data_concessao: Mapped[date] = mapped_column(Date, nullable=False)
    data_nova_vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    dias_adicionais: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registrado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    controle: Mapped["ControleVencimento"] = relationship(back_populates="prorrogacoes")
    registrado_por: Mapped["Usuario"] = relationship() # type: ignore


class ExecucaoVencimentoHistorico(Base):
    """
    Registro append-only de cada execução de um ControleVencimento.

    `ControleVencimento` guarda apenas o estado atual (última execução) —
    sem esta tabela, cada nova chamada de `registrar_execucao` sobrescreve
    `data_ultima_exec`/`executado_por_id` sem deixar rastro do que havia
    antes. Para manutenção de aeronave isso é uma lacuna de auditoria: quem
    executou o quê, quando, e com qual periodicidade vigente, precisa ser
    reconstituível mesmo depois de execuções futuras. Nenhum código deve
    fazer UPDATE/DELETE nesta tabela — apenas INSERT.
    """
    __tablename__ = "execucoes_vencimento_historico"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    controle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controle_vencimentos.id"), nullable=False, index=True
    )
    data_execucao: Mapped[date] = mapped_column(Date, nullable=False)
    data_vencimento_calculada: Mapped[date] = mapped_column(Date, nullable=False)
    periodicidade_meses: Mapped[int] = mapped_column(Integer, nullable=False)
    executado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registrado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # --- Relacionamentos ---
    controle: Mapped["ControleVencimento"] = relationship()
    executado_por: Mapped["Usuario"] = relationship() # type: ignore
