"""
app/panes/models.py
Modelos ORM para gestão de panes aeronáuticas.

Entidades:
    - Pane: ocorrência de falha/pane em uma aeronave
    - Anexo: arquivo (imagem/documento) vinculado a uma pane
    - PaneResponsavel: relação N:N entre Pane e Usuário com papel definido
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.enums import StatusPane, TipoPapel, TipoAnexo


class Pane(Base):
    """
    Representa uma pane (ocorrência de falha) em uma aeronave.

    Fluxo de status (SPECS §8):
        ABERTA → EM_PESQUISA → RESOLVIDA
        ABERTA → RESOLVIDA (conclusão direta)

    RN-03: Apenas panes com status ABERTA ou EM_PESQUISA podem ser editadas.
    RN-04: data_conclusao é preenchida automaticamente ao concluir.
    RN-05: Descrição padrão = "AGUARDANDO EDICAO" se campos vazios.
    """

    __tablename__ = "panes"

    # --- Chave primária ---
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # --- Aeronave vinculada ---
    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Aeronave à qual a pane está vinculada (RN-01)",
    )

    # --- Status ---
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=StatusPane.ABERTA.value,
        index=True,
        comment="Status da pane: ABERTA | EM_PESQUISA | RESOLVIDA",
    )

    # --- Conteúdo ---
    sistema_subsistema: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Sistema/subsistema onde a pane foi identificada",
    )
    descricao: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="AGUARDANDO EDICAO",
        comment="Descrição detalhada da pane (RN-05)",
    )

    # --- Datas ---
    data_abertura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Data/hora de abertura automática (RN-08)",
    )
    data_conclusao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Preenchido automaticamente ao concluir (RN-04)",
    )

    # --- Rastreabilidade ---
    criado_por_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Usuário que registrou a pane",
    )
    concluido_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Usuário que concluiu a pane",
    )

    # --- Auditoria ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relacionamentos ---
    aeronave: Mapped["Aeronave"] = relationship(  # type: ignore[name-defined]
        back_populates="panes",
        lazy="select",
    )
    criador: Mapped["Usuario"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[criado_por_id],
        back_populates="panes_criadas",
        lazy="select",
    )
    responsavel_conclusao: Mapped["Usuario | None"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[concluido_por_id],
        back_populates="panes_concluidas",
        lazy="select",
    )
    anexos: Mapped[list["Anexo"]] = relationship(
        back_populates="pane",
        lazy="select",
        cascade="all, delete-orphan",
    )
    responsaveis: Mapped[list["PaneResponsavel"]] = relationship(
        back_populates="pane",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Pane id={self.id} status={self.status!r} aeronave={self.aeronave_id}>"


class Anexo(Base):
    """
    Arquivo (imagem ou documento) vinculado a uma pane.
    O arquivo físico é armazenado no diretório de uploads (ou cloud).
    O caminho_arquivo aponta para a localização do arquivo.
    """

    __tablename__ = "anexos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pane_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("panes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    caminho_arquivo: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Caminho relativo ao diretório de uploads",
    )
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TipoAnexo.IMAGEM.value,
        comment="IMAGEM | DOCUMENTO",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relacionamentos ---
    pane: Mapped["Pane"] = relationship(back_populates="anexos")

    def __repr__(self) -> str:
        return f"<Anexo id={self.id} tipo={self.tipo!r} pane={self.pane_id}>"


class PaneResponsavel(Base):
    """
    Relacionamento N:N entre Pane e Usuario com papel definido.
    Permite rastreabilidade de múltiplos responsáveis por uma pane.
    """

    __tablename__ = "pane_responsaveis"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pane_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("panes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    papel: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Papel do responsável: INSPETOR | ENCARREGADO | MANTENEDOR",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relacionamentos ---
    pane: Mapped["Pane"] = relationship(back_populates="responsaveis")
    usuario: Mapped["Usuario"] = relationship(back_populates="responsabilidades")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PaneResponsavel pane={self.pane_id} usuario={self.usuario_id} papel={self.papel!r}>"
