"""
Schemas Pydantic do modulo isolado de inspecoes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from app.shared.core.enums import StatusInspecao, StatusTarefaInspecao
from pydantic import ConfigDict, Field

class AeronaveResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    matricula: str
    serial_number: str | None = None


class UsuarioResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    posto: str | None = None
    trigrama: str | None = None
    username: str | None = None


class TipoInspecaoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = None
    duracao_dias: int = Field(default=0, ge=0, le=180)


class TipoInspecaoUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = None
    duracao_dias: int | None = Field(default=None, ge=0, le=180)
    ativo: bool | None = None


class TipoInspecaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    nome: str
    descricao: str | None
    duracao_dias: int
    ativo: bool
    created_at: datetime
    updated_at: datetime | None


class TarefaCatalogoCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    sistema: str | None = Field(default=None, max_length=100)
    ativa: bool = True


class TarefaCatalogoUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    sistema: str | None = Field(default=None, max_length=100)
    ativa: bool | None = None


class TarefaCatalogoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    descricao: str | None
    sistema: str | None
    ativa: bool
    created_at: datetime
    updated_at: datetime | None


class TarefaTemplateCreate(BaseModel):
    tarefa_catalogo_id: uuid.UUID
    ordem: int = Field(ge=1)
    obrigatoria: bool = True


class TarefaTemplateUpdate(BaseModel):
    ordem: int | None = Field(default=None, ge=1)
    obrigatoria: bool | None = None


class TarefaTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo_inspecao_id: uuid.UUID
    tarefa_catalogo_id: uuid.UUID
    ordem: int
    obrigatoria: bool
    created_at: datetime
    tarefa_catalogo: TarefaCatalogoOut | None = None


class ReordenarTarefaItem(BaseModel):
    id: uuid.UUID
    ordem: int = Field(ge=1)


class ReordenarTarefas(BaseModel):
    tarefas: list[ReordenarTarefaItem] = Field(min_length=1)


class InspecaoCreate(BaseModel):
    aeronave_id: uuid.UUID
    tipos_inspecao_ids: list[uuid.UUID] = Field(min_length=1)
    data_inicio: datetime | None = None
    observacoes: str | None = None


class InspecaoUpdate(BaseModel):
    observacoes: str | None = None


class FiltroInspecao(BaseModel):
    aeronave_id: uuid.UUID | None = None
    tipo_inspecao_id: uuid.UUID | None = None
    status: StatusInspecao | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class InspecaoTarefaCreate(BaseModel):
    ordem: int | None = Field(default=None, ge=1)
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    sistema: str | None = Field(default=None, max_length=100)
    obrigatoria: bool = True


class InspecaoTarefaUpdate(BaseModel):
    status: StatusTarefaInspecao
    observacao_execucao: str | None = None
    executado_por_id: uuid.UUID | None = None
    pane_id: uuid.UUID | None = None


class InspecaoTarefaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inspecao_id: uuid.UUID
    tarefa_catalogo_id: uuid.UUID | None
    ordem: int
    titulo: str
    descricao: str | None
    sistema: str | None
    obrigatoria: bool
    status: StatusTarefaInspecao
    observacao_execucao: str | None
    executado_por_id: uuid.UUID | None
    executado_por: UsuarioResumo | None = None
    data_execucao: datetime | None
    pane_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None


class InspecaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aeronave_id: uuid.UUID
    aeronave: AeronaveResumo | None = None
    tipos_aplicados: list[TipoInspecaoOut] = []
    status: StatusInspecao
    data_abertura: datetime
    data_inicio: datetime
    data_fim_prevista: datetime | None
    data_conclusao: datetime | None
    observacoes: str | None
    aberto_por_id: uuid.UUID
    aberto_por: UsuarioResumo | None = None
    concluido_por_id: uuid.UUID | None
    concluido_por: UsuarioResumo | None = None
    created_at: datetime
    updated_at: datetime | None
    tarefas: list[InspecaoTarefaOut] = []


class InspecaoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aeronave_id: uuid.UUID
    aeronave: AeronaveResumo | None = None
    tipos_aplicados: list[TipoInspecaoOut] = []
    status: StatusInspecao
    data_abertura: datetime
    data_inicio: datetime
    data_fim_prevista: datetime | None
    data_conclusao: datetime | None
    observacoes: str | None
    total_tarefas: int = 0
    tarefas_concluidas: int = 0
    progresso_percentual: int = 0
