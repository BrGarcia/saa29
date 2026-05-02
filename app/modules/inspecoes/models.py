"""
Modelos ORM do modulo isolado de inspecoes.

Os relacionamentos reversos em Aeronave e Usuario nao sao declarados aqui para
manter este modulo desacoplado da logica principal enquanto estiver em backlog.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base


class TipoInspecao(Base):
    """Catalogo de tipos de inspecao, como IF-50H, IF-100H, IPG e IPE."""

    __tablename__ = "tipos_inspecao"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    duracao_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    tarefas_template: Mapped[list["TarefaTemplate"]] = relationship(
        back_populates="tipo_inspecao",
        cascade="all, delete-orphan",
        order_by="TarefaTemplate.ordem",
    )
    inspecoes: Mapped[list["Inspecao"]] = relationship(
        secondary="inspecao_evento_tipos",
        back_populates="tipos_aplicados"
    )

    def __repr__(self) -> str:
        return f"<TipoInspecao codigo={self.codigo!r} ativo={self.ativo!r}>"


class TarefaCatalogo(Base):
    """Catalogo global de tarefas independentes."""

    __tablename__ = "tarefas_catalogo"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    sistema: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    templates_vinculados: Mapped[list["TarefaTemplate"]] = relationship(
        back_populates="tarefa_catalogo",
        cascade="all, delete-orphan"
    )
    tarefas_instanciadas: Mapped[list["InspecaoTarefa"]] = relationship(back_populates="tarefa_catalogo")

    def __repr__(self) -> str:
        return f"<TarefaCatalogo titulo={self.titulo!r} ativa={self.ativa!r}>"


class TarefaTemplate(Base):
    """Vinculo N:N entre TipoInspecao e TarefaCatalogo."""

    __tablename__ = "tarefas_template"
    __table_args__ = (
        UniqueConstraint("tipo_inspecao_id", "tarefa_catalogo_id", name="uq_tarefa_template_por_tipo"),
        UniqueConstraint("tipo_inspecao_id", "ordem", name="uq_tarefa_template_ordem_por_tipo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tipo_inspecao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_inspecao.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tarefa_catalogo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tarefas_catalogo.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    obrigatoria: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    tipo_inspecao: Mapped["TipoInspecao"] = relationship(back_populates="tarefas_template")
    tarefa_catalogo: Mapped["TarefaCatalogo"] = relationship(back_populates="templates_vinculados")

    def __repr__(self) -> str:
        return f"<TarefaTemplate tipo={self.tipo_inspecao_id} tarefa={self.tarefa_catalogo_id} ordem={self.ordem}>"


class InspecaoEventoTipo(Base):
    """Vinculo N:N de Tipos aplicados a um Evento de Inspecao."""

    __tablename__ = "inspecao_evento_tipos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inspecao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspecoes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo_inspecao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_inspecao.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class Inspecao(Base):
    """Inspecao aberta para uma aeronave."""

    __tablename__ = "inspecoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    aeronave_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aeronaves.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ABERTA", index=True)
    data_abertura: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    data_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    data_fim_prevista: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_conclusao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    aberto_por_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    concluido_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    tipos_aplicados: Mapped[list["TipoInspecao"]] = relationship(
        secondary="inspecao_evento_tipos",
        back_populates="inspecoes"
    )
    aeronave = relationship("Aeronave", lazy="select")
    aberto_por = relationship("Usuario", foreign_keys=[aberto_por_id], lazy="select")
    concluido_por = relationship("Usuario", foreign_keys=[concluido_por_id], lazy="select")
    tarefas: Mapped[list["InspecaoTarefa"]] = relationship(
        back_populates="inspecao",
        cascade="all, delete-orphan",
        order_by="InspecaoTarefa.ordem",
    )

    def __repr__(self) -> str:
        return f"<Inspecao id={self.id} status={self.status!r} aeronave={self.aeronave_id}>"


class InspecaoTarefa(Base):
    """Tarefa instanciada dentro de uma inspecao."""

    __tablename__ = "inspecao_tarefas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inspecao_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspecoes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tarefa_catalogo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarefas_catalogo.id", ondelete="SET NULL"),
        nullable=True,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    sistema: Mapped[str | None] = mapped_column(String(100), nullable=True)
    obrigatoria: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDENTE", index=True)
    observacao_execucao: Mapped[str | None] = mapped_column(Text, nullable=True)
    executado_por_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True)
    data_execucao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pane_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("panes.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    inspecao: Mapped["Inspecao"] = relationship(back_populates="tarefas")
    tarefa_catalogo: Mapped["TarefaCatalogo | None"] = relationship(back_populates="tarefas_instanciadas")
    executado_por = relationship("Usuario", foreign_keys=[executado_por_id], lazy="select")

    def __repr__(self) -> str:
        return f"<InspecaoTarefa id={self.id} status={self.status!r} ordem={self.ordem}>"
