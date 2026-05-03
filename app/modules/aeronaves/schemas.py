"""
app/aeronaves/schemas.py
Schemas Pydantic v2 para aeronaves.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.core.enums import StatusAeronave


class AeronaveCreate(BaseModel):
    """Payload para cadastro de nova aeronave."""
    part_number: str | None = Field(default=None, max_length=50)
    serial_number: str = Field(..., max_length=50)
    matricula: str = Field(..., max_length=20, examples=["5916"])
    modelo: str = Field(default="A-29", max_length=50)
    status: StatusAeronave = StatusAeronave.DISPONIVEL
    horas_voo_total: float = Field(default=0.0, ge=0)
    data_inicio_operacao: date
    horas_atualizadas_em: datetime | None = None


class AeronaveUpdate(BaseModel):
    """Payload para atualização parcial de aeronave."""
    part_number: str | None = Field(default=None, max_length=50)
    serial_number: str | None = Field(default=None, max_length=50)
    matricula: str | None = Field(default=None, max_length=20, examples=["5916"])
    modelo: str | None = Field(default=None, max_length=50)
    status: StatusAeronave | None = None
    horas_voo_total: float | None = Field(default=None, ge=0)
    data_inicio_operacao: date | None = None
    horas_atualizadas_em: datetime | None = None


class AeronaveOut(BaseModel):
    """Representação pública de uma aeronave."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    part_number: str | None
    serial_number: str
    matricula: str
    modelo: str
    status: StatusAeronave
    horas_voo_total: float
    data_inicio_operacao: date
    horas_atualizadas_em: datetime | None
    created_at: datetime


class AeronaveListItem(BaseModel):
    """Representação resumida para listagem (cards do dashboard)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    serial_number: str
    matricula: str
    modelo: str
    status: StatusAeronave
