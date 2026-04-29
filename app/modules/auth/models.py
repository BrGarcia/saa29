"""
app/auth/models.py
Modelo ORM para Usuários (Efetivo) do sistema SAA29.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.bootstrap.database import Base


class Usuario(Base):
    """
    Representa um membro do efetivo com acesso ao sistema.

    Perfis disponíveis (campo funcao):
        - Administrador: supervisão técnica e gestão total
        - Encarregado: gestão operacional e delegação
        - Mantenedor: execução de manutenção e reporte
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
        comment="Função no sistema: ADMINISTRADOR | ENCARREGADO | MANTENEDOR",
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
    ativo: Mapped[bool] = mapped_column(
        default=True,
        index=True,
        comment="Controle de exclusão lógica (soft delete)",
    )

    # --- Segurança e Bloqueio ---
    failed_login_attempts: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Contador de tentativas de login falhas consecutivas",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Se preenchido, a conta está bloqueada até este horário",
    )

    # --- Auditoria ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
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
    inspecoes_abertas: Mapped[list] = relationship(
        "Inspecao",
        foreign_keys="Inspecao.aberto_por_id",
        back_populates="aberto_por",
        lazy="select",
    )
    inspecoes_concluidas: Mapped[list] = relationship(
        "Inspecao",
        foreign_keys="Inspecao.concluido_por_id",
        back_populates="concluido_por",
        lazy="select",
    )
    tarefas_inspecao_executadas: Mapped[list] = relationship(
        "InspecaoTarefa",
        foreign_keys="InspecaoTarefa.executado_por_id",
        back_populates="executado_por",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} username={self.username!r} funcao={self.funcao!r}>"


class TokenBlacklist(Base):
    """
    Armazena os identificadores (JTI) dos de tokens JWT invalidados (logout)
    para permitir escalabilidade e sobrevivência a reinicializações.
    """
    __tablename__ = "token_blacklist"

    jti: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        index=True,
        comment="JWT ID do token invalidado"
    )
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Data de expiração original do token. Útil para limpeza periódica da tabela."
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TokenBlacklist jti={self.jti!r}>"


class TokenRefresh(Base):
    """
    Armazena refresh tokens para estender sessões sem exigir re-autenticação.
    
    Fluxo:
    1. Access token expira a cada 15 min
    2. Client usa refresh token para obter novo access token (via /auth/refresh)
    3. Refresh token válido por 7 dias
    4. Novo refresh token gerado em cada requisição de refresh
    5. Tokens revogados ficam na blacklist
    """
    __tablename__ = "token_refresh"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="ID único do refresh token"
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        index=True,
        nullable=False,
        comment="Referência ao usuário"
    )
    jti: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        comment="JWT ID do refresh token (para rastreamento)"
    )
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Data de expiração do refresh token (7 dias)"
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
    revogado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Se preenchido, o token foi revogado"
    )
    
    def __repr__(self) -> str:
        status = "revoked" if self.revogado_em else "active"
        return f"<TokenRefresh jti={self.jti!r} status={status}>"
