"""
app/modules/vencimentos/schemas.py
Schemas Pydantic v2 para Inteligência Temporal e Vencimentos.
"""

import uuid
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field
from app.shared.core.enums import StatusVencimento, OrigemControle


# ============================================================
# Tipos de Controle
# ============================================================

class TipoControleCreate(BaseModel):
    """Catálogo de códigos de controle. Periodicidade definida em EquipamentoControle."""
    nome: str = Field(..., max_length=10)
    descricao: str | None = None

class TipoControleUpdate(BaseModel):
    """Atualização de tipo de controle existente."""
    nome: str | None = Field(default=None, max_length=10)
    descricao: str | None = None

class TipoControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nome: str
    descricao: str | None
    created_at: datetime


# ============================================================
# EquipamentoControle (Regras por PN)
# ============================================================

class EquipamentoControleCreate(BaseModel):
    modelo_id: uuid.UUID
    tipo_controle_id: uuid.UUID
    periodicidade_meses: int = Field(..., gt=0)

class EquipamentoControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    modelo_id: uuid.UUID
    tipo_controle_id: uuid.UUID
    periodicidade_meses: int
    
    # Campos auxiliares para o frontend
    pn: str | None = None
    tipo_nome: str | None = None


# ============================================================
# ControleVencimento
# ============================================================

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


# ============================================================
# Visão Matricial de Vencimentos (Matriz Frota x Slot x Controle)
# ============================================================

class VencimentoCelulaOut(BaseModel):
    """Uma célula da matrix: dados de um controle de um item instalado."""
    vencimento_id: uuid.UUID | None = None
    tipo_controle_nome: str
    data_ultima_exec: date | None = None
    data_vencimento: date | None = None
    status: str | None = None  # OK, VENCENDO, VENCIDO, PRORROGADO
    prorrogado: bool = False
    data_nova_vencimento: date | None = None
    numero_documento_prorrogacao: str | None = None

class SlotMatrizOut(BaseModel):
    """Um slot/sistema da aeronave com o SN instalado e seus controles."""
    slot_id: uuid.UUID | None = None
    sistema: str          # Ex: EGIR, ELT, V/UHF2
    nome_posicao: str | None = None
    part_number: str
    numero_serie: str | None = None   # SN instalado (None se slot vazio)
    controles: list[VencimentoCelulaOut] = []

class AeronaveMatrizOut(BaseModel):
    """Uma linha da matriz: dados de uma aeronave e todos os seus slots."""
    aeronave_id: uuid.UUID
    matricula: str
    status_aeronave: str
    status_vencimento: str  # OK, VENCENDO, VENCIDO, INCOMPLETA
    slots: list[SlotMatrizOut] = []

class MatrizVencimentosOut(BaseModel):
    """Resposta completa da visão matricial."""
    # Colunas de cabeçalho: sistema -> lista de tipos de controle (nomes)
    cabecalho: dict[str, list[str]]   # Ex: {"EGIR": ["TBO"], "ELT": ["CRI","TBV"]}
    aeronaves: list[AeronaveMatrizOut]


# ============================================================
# Prorrogação de Vencimentos
# ============================================================

class ProrrogacaoVencimentoCreate(BaseModel):
    numero_documento: str
    data_concessao: date
    dias_adicionais: int
    motivo: str | None = None
    observacao: str | None = None

class ProrrogacaoVencimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    controle_id: uuid.UUID
    numero_documento: str
    data_concessao: date
    data_nova_vencimento: date
    dias_adicionais: int
    motivo: str | None
    observacao: str | None
    registrado_por_id: uuid.UUID | None
    ativo: bool
    created_at: datetime
