"""
app/modules/pedidos/schemas.py
Schemas Pydantic v2 para o módulo Central de Pedidos.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.core.enums import StatusPedido, TipoPedido


class FiltroPedido(BaseModel):
    """Parâmetros de filtro para listagem/resumo de pedidos."""
    texto: str | None = None
    status: StatusPedido | None = None
    tipo_pedido: TipoPedido | None = None
    aeronave_id: uuid.UUID | None = None
    excluidos: bool = Field(default=False, description="Exibir apenas pedidos excluídos (soft delete)")
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class PedidoCreate(BaseModel):
    aeronave_id: uuid.UUID
    part_number: str = Field(..., min_length=1, max_length=50)
    nomenclatura: str = Field(..., min_length=1, max_length=100)
    tipo_pedido: TipoPedido = TipoPedido.NORMAL
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int = Field(default=1, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _validar_regras(self):
        # RN-03 / RN-04. Reforçado também no service (defesa em profundidade).
        if self.tipo_pedido == TipoPedido.EMERGENCIA and not self.numero_emergencia:
            raise ValueError("numero_emergencia é obrigatório para pedidos de EMERGENCIA")
        if self.tipo_pedido == TipoPedido.NORMAL:
            self.numero_emergencia = None
        return self


class PedidoUpdate(BaseModel):
    """RN-09: só é aceito quando o pedido está PENDENTE (checado no service).

    `extra="forbid"`: mesma proteção usada em PaneUpdate contra campos
    desconhecidos silenciosamente ignorados.
    """
    model_config = ConfigDict(extra="forbid")

    part_number: str | None = Field(None, min_length=1, max_length=50)
    nomenclatura: str | None = Field(None, min_length=1, max_length=100)
    tipo_pedido: TipoPedido | None = None
    numero_emergencia: str | None = Field(None, max_length=50)
    quantidade: int | None = Field(None, ge=1, le=999)
    observacao: str | None = Field(None, max_length=1000)


class PedidoCancelar(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)


class PedidoOut(BaseModel):
    """Representação plana do pedido.

    ATENÇÃO: aeronave_matricula/solicitante_trigrama/atendido_por_trigrama/
    cancelado_por_trigrama NÃO são atributos do ORM `Pedido` — não usar
    `PedidoOut.model_validate(pedido)` diretamente. Montar via
    `service._to_out(pedido)`, que já garante que as relações necessárias
    foram carregadas (selectinload) antes de acessá-las.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_pedido: str
    aeronave_id: uuid.UUID
    aeronave_matricula: str
    part_number: str
    nomenclatura: str
    tipo_pedido: str
    numero_emergencia: str | None
    status: str
    quantidade: int
    observacao: str | None
    data_pedido: date
    data_atendimento: datetime | None
    data_cancelamento: datetime | None
    motivo_cancelamento: str | None
    solicitante_trigrama: str | None
    atendido_por_trigrama: str | None
    cancelado_por_trigrama: str | None
    ativo: bool
    created_at: datetime


class PedidoResumo(BaseModel):
    """Contadores para os cards de resumo da tela — GET /pedidos/resumo.
    Respeita os mesmos filtros (exceto paginação) da listagem."""
    total: int
    pendentes: int
    atendidos: int
    cancelados: int
    emergencias: int
