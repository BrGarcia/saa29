"""
app/auth/models.py
Modelo ORM para Usuários (Efetivo) do sistema SAA29.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Usuario(Base):
    """
    Representa um membro do efetivo com acesso ao sistema.

    Perfis disponíveis (campo funcao):
        - Inspetor: supervisão técnica
        - Encarregado: gestão operacional
        - Mantenedor: execução de manutenção
    """

    __tablename__ = "usuarios"

    # --- Chave primária ---
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="Identificador único universal do usuário",
    )

    # --- Dados pessoais ---
    nome: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Nome completo do militar",
    )
    posto: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Posto ou graduação (ex: Ten, Cap, Sgt)",
    )
    especialidade: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Especialidade técnica do militar",
    )
    funcao: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Função no sistema: INSPETOR | ENCARREGADO | MANTENEDOR",
    )
    ramal: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Ramal telefônico para contato",
    )
    trigrama: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="Código de 3 letras que identifica o militar",
    )

    # --- Autenticação ---
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Nome de usuário único para login",
    )
    senha_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash bcrypt da senha do usuário",
    )

    # --- Auditoria ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Atualizado automaticamente em cada modificação",
    )

    # --- Relacionamentos (definidos nos módulos dependentes) ---
    panes_criadas: Mapped[list] = relationship(
        "Pane",
        foreign_keys="Pane.criado_por_id",
        back_populates="criador",
        lazy="select",
    )
    panes_concluidas: Mapped[list] = relationship(
        "Pane",
        foreign_keys="Pane.concluido_por_id",
        back_populates="responsavel_conclusao",
        lazy="select",
    )
    responsabilidades: Mapped[list] = relationship(
        "PaneResponsavel",
        back_populates="usuario",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} username={self.username!r} funcao={self.funcao!r}>"
