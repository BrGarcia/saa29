"""
app/equipamentos/schemas.py
Schemas Pydantic v2 para Modelos, Slots, Itens e Inventário.
"""

import uuid
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import StatusItem, StatusVencimento, OrigemControle

# ============================================================
# ModeloEquipamento (Part Number)
# ============================================================

class ModeloEquipamentoCreate(BaseModel):
    part_number: str = Field(..., max_length=50)
    nome_generico: str = Field(..., max_length=100)
    descricao: str | None = None

class ModeloEquipamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    part_number: str
    nome_generico: str
    descricao: str | None
    created_at: datetime

# ============================================================
# SlotInventario (Posição na ANV)
# ============================================================

class SlotInventarioCreate(BaseModel):
    nome_posicao: str = Field(..., max_length=100)
    sistema: str | None = Field(default=None, max_length=50)
    modelo_id: uuid.UUID

class SlotInventarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome_posicao: str
    sistema: str | None
    modelo_id: uuid.UUID

# ============================================================
# ItemEquipamento (Instância Física)
# ============================================================

class ItemEquipamentoCreate(BaseModel):
    modelo_id: uuid.UUID
    numero_serie: str = Field(..., max_length=100)
    status: StatusItem = StatusItem.ATIVO

class ItemEquipamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    modelo_id: uuid.UUID
    numero_serie: str
    status: StatusItem
    created_at: datetime

# ============================================================
# Instalações
# ============================================================

class InstalacaoCreate(BaseModel):
    aeronave_id: uuid.UUID
    data_instalacao: date = Field(default_factory=date.today)

class InstalacaoRemocao(BaseModel):
    data_remocao: date = Field(default_factory=date.today)

class InstalacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_id: uuid.UUID
    aeronave_id: uuid.UUID
    slot_id: uuid.UUID | None = None
    data_instalacao: date
    data_remocao: date | None

# ============================================================
# Inventário e Ajuste
# ============================================================

class InventarioItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slot_id: uuid.UUID
    nome_posicao: str
    sistema: str | None = None
    part_number: str
    nome_generico: str
    
    # Compatibilidade Frontend (V1)
    equipamento_nome: str | None = None
    equipamento_id: uuid.UUID | None = None

    # Dados do item instalado (podem ser nulos se slot vazio)
    item_id: uuid.UUID | None = None
    numero_serie: str | None = None
    status_item: StatusItem | None = None
    instalacao_id: uuid.UUID | None = None
    data_instalacao: date | None = None
    aeronave_anterior: str | None = None

class AjusteInventarioCreate(BaseModel):
    aeronave_id: uuid.UUID
    slot_id: uuid.UUID | None = None
    equipamento_id: uuid.UUID | None = None  # Compatibilidade Frontend (V1)
    numero_serie_real: str = Field(..., min_length=1)
    forcar_transferencia: bool = False

class AjusteInventarioResponse(BaseModel):
    sucesso: bool
    mensagem: str
    requer_confirmacao: bool = False
    aeronave_conflito: str | None = None

# ============================================================
# Legado / Outros (Manter compatibilidade se necessário)
# ============================================================

class TipoControleCreate(BaseModel):
    nome: str = Field(..., max_length=50)
    descricao: str | None = None
    periodicidade_meses: int = Field(..., gt=0)

class TipoControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome: str
    descricao: str | None
    periodicidade_meses: int
    created_at: datetime

class ControleVencimentoUpdate(BaseModel):
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
