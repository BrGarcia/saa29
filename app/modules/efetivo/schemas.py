"""
app/modules/efetivo/schemas.py
Schemas Pydantic v2 para gestão de disponibilidade de pessoal.
"""

import uuid
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field
from app.shared.core.enums import TipoIndisponibilidade

class IndisponibilidadeCreate(BaseModel):
    usuario_id: uuid.UUID
    tipo: TipoIndisponibilidade
    data_inicio: date
    data_fim: date
    observacao: str | None = None

class IndisponibilidadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    usuario_id: uuid.UUID
    tipo: TipoIndisponibilidade
    data_inicio: date
    data_fim: date
    observacao: str | None
    created_at: datetime
