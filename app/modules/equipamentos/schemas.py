"""
app/modules/equipamentos/schemas.py
Schemas Pydantic v2 para Modelos, Slots, Itens e Inventário.
"""

import uuid
from datetime import datetime, date
from typing import Annotated
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from app.shared.core.enums import StatusItem


def _normalizar_identificador(valor: str) -> str:
    """Normaliza PN/SN para a forma canônica (sem espaços nas pontas, maiúsculas)."""
    return valor.strip().upper()


# Fonte única de verdade da normalização de PN/SN: evita duplicatas lógicas
# ("abc123" vs "ABC123") sem espalhar `.strip().upper()` pelos services.
Identificador = Annotated[str, AfterValidator(_normalizar_identificador)]


# ============================================================
# ModeloEquipamento (Part Number)
# ============================================================

class ModeloEquipamentoCreate(BaseModel):
    part_number: Identificador = Field(..., max_length=50)
    nome_generico: str = Field(..., max_length=100)
    descricao: str | None = None

class ModeloEquipamentoUpdate(BaseModel):
    part_number: Identificador | None = Field(None, max_length=50)
    nome_generico: str | None = Field(None, max_length=100)
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
    numero_serie: Identificador = Field(..., max_length=100)
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
    slot_id: uuid.UUID
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
    data_atualizacao: datetime | None = None
    usuario_trigrama: str | None = None
    aeronave_anterior: str | None = None

class AjusteInventarioCreate(BaseModel):
    aeronave_id: uuid.UUID
    slot_id: uuid.UUID | None = None
    equipamento_id: uuid.UUID | None = None  # DEPRECATED: compatibilidade Frontend (V1)
    numero_serie_real: Identificador = Field(..., min_length=0)
    forcar_transferencia: bool = False
    usuario_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _resolver_slot_id(self) -> "AjusteInventarioCreate":
        """Garante `slot_id` preenchido, aceitando o alias legado `equipamento_id`.

        Resolver aqui (e não no service) elimina a repetição de
        `slot_id or equipamento_id` e dá ao service a garantia de valor.

        Raises:
            ValueError: nenhum dos dois identificadores foi informado (→ HTTP 422).
        """
        if self.slot_id is None:
            if self.equipamento_id is None:
                raise ValueError("Informe 'slot_id' (ou o campo legado 'equipamento_id').")
            self.slot_id = self.equipamento_id
        return self

class InventarioHistoricoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    item_sn: str
    aeronave_matricula: str
    slot_nome: str
    usuario_trigrama: str | None
    tipo_acao: str # "INSTALAÇÃO" ou "REMOÇÃO"

class AjusteInventarioResponse(BaseModel):
    sucesso: bool
    mensagem: str
    requer_confirmacao: bool = False
    aeronave_conflito: str | None = None

# ============================================================
# XLSX Upload / Preview
# ============================================================

class XlsxPreviewItemOut(BaseModel):
    slot_id: uuid.UUID
    nome_posicao: str
    pn: str
    posicao_xlsx: str
    sn_encontrado: str | None
    status: str
    status_msg: str

class XlsxPreviewOut(BaseModel):
    matricula: str
    aeronave_id: uuid.UUID | None
    total_linhas: int
    pns_encontrados: int
    pns_ignorados: int
    itens: list[XlsxPreviewItemOut]
    erros: list[str]

class XlsxProcessConfirmItem(BaseModel):
    slot_id: uuid.UUID
    sn_final: str

class XlsxProcessRequest(BaseModel):
    aeronave_id: uuid.UUID
    itens: list[XlsxProcessConfirmItem]
