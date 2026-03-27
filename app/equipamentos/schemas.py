"""
app/equipamentos/schemas.py
Schemas Pydantic v2 para equipamentos, itens, controles e vencimentos.
"""

import uuid
from datetime import datetime, date

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatusItem, StatusVencimento, OrigemControle


# ============================================================
# TipoControle
# ============================================================

class TipoControleCreate(BaseModel):
    nome: str = Field(..., max_length=50, examples=["TBV"])
    descricao: str | None = None
    periodicidade_meses: int = Field(..., gt=0)


class TipoControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    descricao: str | None
    periodicidade_meses: int
    created_at: datetime


# ============================================================
# Equipamento
# ============================================================

class EquipamentoCreate(BaseModel):
    part_number: str = Field(..., max_length=50)
    nome: str = Field(..., max_length=100)
    sistema: str | None = Field(default=None, max_length=50)
    descricao: str | None = None


class EquipamentoUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=100)
    sistema: str | None = None
    descricao: str | None = None


class EquipamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    part_number: str
    nome: str
    sistema: str | None
    descricao: str | None
    created_at: datetime


# ============================================================
# ItemEquipamento
# ============================================================

class ItemEquipamentoCreate(BaseModel):
    equipamento_id: uuid.UUID
    numero_serie: str = Field(..., max_length=100)
    status: StatusItem = StatusItem.ATIVO


class ItemEquipamentoUpdate(BaseModel):
    status: StatusItem | None = None


class ItemEquipamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipamento_id: uuid.UUID
    numero_serie: str
    status: StatusItem
    created_at: datetime


# ============================================================
# Instalacao
# ============================================================

class InstalacaoCreate(BaseModel):
    item_id: uuid.UUID
    aeronave_id: uuid.UUID
    data_instalacao: date


class InstalacaoRemocao(BaseModel):
    data_remocao: date


class InstalacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    aeronave_id: uuid.UUID
    data_instalacao: date
    data_remocao: date | None


# ============================================================
# ControleVencimento
# ============================================================

class ControleVencimentoUpdate(BaseModel):
    """Payload para registrar a execução de um controle."""
    data_ultima_exec: date
    observacao: str | None = None


class ControleVencimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    tipo_controle_id: uuid.UUID
    data_ultima_exec: date | None
    data_vencimento: date | None
    status: StatusVencimento
    origem: OrigemControle
    created_at: datetime
