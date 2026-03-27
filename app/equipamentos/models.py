"""
app/equipamentos/models.py
Modelos ORM para a gestão de equipamentos aeronáuticos.

Entidades:
    - Equipamento: tipo/part number de equipamento
    - TipoControle: TBV, RBA, CRI etc.
    - EquipamentoControle: relação N:N equipamento x tipo de controle (TEMPLATE)
    - ItemEquipamento: instância física por número de série
    - Instalacao: histórico de instalação em aeronaves
    - ControleVencimento: instância real de controle por item
"""

import uuid
from datetime import datetime, date

from sqlalchemy import String, DateTime, Date, Integer, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.enums import StatusItem, StatusVencimento, OrigemControle


class Equipamento(Base):
    """
    Representa um tipo de equipamento identificado por part number.
    Define o template de controles que todos os itens herdarão.
    """

    __tablename__ = "equipamentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    part_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nome do equipamento (ex: VUHF2, ELT, MDP)",
    )
    sistema: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Sistema ao qual pertence (ex: COM, NAV, AP)",
    )
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relacionamentos ---
    controles: Mapped[list["EquipamentoControle"]] = relationship(
        back_populates="equipamento", lazy="select"
    )
    itens: Mapped[list["ItemEquipamento"]] = relationship(
        back_populates="equipamento", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Equipamento nome={self.nome!r} pn={self.part_number!r}>"


class TipoControle(Base):
    """
    Define um tipo de controle periódico de manutenção.
    Exemplos: TBV (Teste de Bancada de Verificação), RBA, CRI.
    """

    __tablename__ = "tipos_controle"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    descricao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    periodicidade_meses: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Intervalo em meses entre execuções do controle",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relacionamentos ---
    equipamento_controles: Mapped[list["EquipamentoControle"]] = relationship(
        back_populates="tipo_controle", lazy="select"
    )
    vencimentos: Mapped[list["ControleVencimento"]] = relationship(
        back_populates="tipo_controle", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<TipoControle nome={self.nome!r} periodicidade={self.periodicidade_meses}m>"


class EquipamentoControle(Base):
    """
    Relacionamento N:N entre Equipamento e TipoControle.
    Define o TEMPLATE: todo item deste equipamento herda estes controles.
    
    RN: Ao inserir novo EquipamentoControle, propagar para todos os itens existentes.
    """

    __tablename__ = "equipamento_controles"
    __table_args__ = (
        UniqueConstraint("equipamento_id", "tipo_controle_id", name="uq_equip_controle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    equipamento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipamentos.id", ondelete="CASCADE"), nullable=False
    )
    tipo_controle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_controle.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relacionamentos ---
    equipamento: Mapped["Equipamento"] = relationship(back_populates="controles")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="equipamento_controles")


class ItemEquipamento(Base):
    """
    Instância física de um equipamento, identificada por número de série.
    Herda os controles de manutenção do seu tipo de Equipamento.
    """

    __tablename__ = "itens_equipamento"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    equipamento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipamentos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    numero_serie: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="Número de série único do item físico",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatusItem.ATIVO.value,
        comment="Status: ATIVO | ESTOQUE | REMOVIDO",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relacionamentos ---
    equipamento: Mapped["Equipamento"] = relationship(back_populates="itens")
    controles_vencimento: Mapped[list["ControleVencimento"]] = relationship(
        back_populates="item", lazy="select"
    )
    instalacoes: Mapped[list["Instalacao"]] = relationship(
        back_populates="item", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<ItemEquipamento sn={self.numero_serie!r} status={self.status!r}>"


class Instalacao(Base):
    """
    Histórico de instalação de um item em uma aeronave.
    Um item pode ter múltiplas instalações ao longo do tempo.
    data_remocao=NULL indica instalação ativa.
    """

    __tablename__ = "instalacoes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itens_equipamento.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    aeronave_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeronaves.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    data_instalacao: Mapped[date] = mapped_column(Date, nullable=False)
    data_remocao: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="NULL indica que o item ainda está instalado",
    )

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="instalacoes")
    aeronave: Mapped["Aeronave"] = relationship(back_populates="instalacoes")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Instalacao item={self.item_id} aeronave={self.aeronave_id}>"


class ControleVencimento(Base):
    """
    Instância real de controle de vencimento por item físico.

    Criado automaticamente ao cadastrar um ItemEquipamento (herança).
    Atualizado após cada execução do controle de manutenção.
    
    RN: UNIQUE(item_id, tipo_controle_id) — sem duplicidade por item.
    """

    __tablename__ = "controle_vencimentos"
    __table_args__ = (
        UniqueConstraint("item_id", "tipo_controle_id", name="uq_item_controle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("itens_equipamento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo_controle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tipos_controle.id", ondelete="RESTRICT"), nullable=False
    )
    data_ultima_exec: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_vencimento: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True,
        comment="Data calculada: data_ultima_exec + periodicidade_meses",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatusVencimento.OK.value,
        comment="OK | VENCENDO | VENCIDO",
    )
    origem: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrigemControle.PADRAO.value,
        comment="PADRAO (herdado) | ESPECIFICO (adicionado ao item)",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relacionamentos ---
    item: Mapped["ItemEquipamento"] = relationship(back_populates="controles_vencimento")
    tipo_controle: Mapped["TipoControle"] = relationship(back_populates="vencimentos")

    def __repr__(self) -> str:
        return f"<ControleVencimento item={self.item_id} status={self.status!r}>"
