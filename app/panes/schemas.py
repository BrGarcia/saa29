"""
app/panes/schemas.py
Schemas Pydantic v2 para panes, anexos e responsáveis.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatusPane, TipoPapel, TipoAnexo


# ============================================================
# Filtros
# ============================================================

class FiltroPane(BaseModel):
    """Parâmetros de filtro para listagem de panes (RF-06)."""
    texto: str | None = None
    status: StatusPane | None = None
    aeronave_id: uuid.UUID | None = None
    data_inicio: datetime | None = None
    data_fim: datetime | None = None


# ============================================================
# Pane
# ============================================================

class PaneCreate(BaseModel):
    """Payload para abertura de nova pane (RF-07, RF-08)."""
    aeronave_id: uuid.UUID
    sistema_subsistema: str | None = Field(default=None, max_length=100)
    descricao: str = Field(
        default="AGUARDANDO EDICAO",
        description="Descrição da pane. Se vazio, definir como 'AGUARDANDO EDICAO' (RN-05)",
    )
    # status inicial = ABERTA (definido no service, não pelo cliente)


class PaneUpdate(BaseModel):
    """Payload para edição de pane aberta (RF-10). RN-03: apenas panes abertas."""
    sistema_subsistema: str | None = Field(default=None, max_length=100)
    descricao: str | None = None
    status: StatusPane | None = Field(
        default=None,
        description="Transições: ABERTA→EM_PESQUISA, ABERTA→RESOLVIDA, EM_PESQUISA→RESOLVIDA",
    )


class PaneConcluir(BaseModel):
    """Payload para conclusão de pane (RF-12)."""
    observacao_conclusao: str | None = None


class AnexoOut(BaseModel):
    """Representação pública de um anexo."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pane_id: uuid.UUID
    caminho_arquivo: str
    tipo: TipoAnexo
    created_at: datetime


class ResponsavelOut(BaseModel):
    """Representação de um responsável vinculado a uma pane."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    papel: TipoPapel
    created_at: datetime


class PaneOut(BaseModel):
    """Representação detalhada de uma pane (RF-09)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aeronave_id: uuid.UUID
    status: StatusPane
    sistema_subsistema: str | None
    descricao: str
    data_abertura: datetime
    data_conclusao: datetime | None
    criado_por_id: uuid.UUID
    concluido_por_id: uuid.UUID | None
    created_at: datetime
    anexos: list[AnexoOut] = []
    responsaveis: list[ResponsavelOut] = []


class PaneListItem(BaseModel):
    """Representação resumida para cards do dashboard (RF-04, RF-05)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aeronave_id: uuid.UUID
    status: StatusPane
    descricao: str
    data_abertura: datetime
    data_conclusao: datetime | None


# ============================================================
# Responsável
# ============================================================

class AdicionarResponsavel(BaseModel):
    """Payload para vincular responsável a uma pane."""
    usuario_id: uuid.UUID
    papel: TipoPapel
