"""
app/equipamentos/service.py
Camada de serviço para gestão de equipamentos e controle de vencimentos.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.equipamentos.models import (
    Equipamento,
    TipoControle,
    EquipamentoControle,
    ItemEquipamento,
    Instalacao,
    ControleVencimento,
)
from app.equipamentos.schemas import (
    EquipamentoCreate,
    EquipamentoUpdate,
    ItemEquipamentoCreate,
    TipoControleCreate,
)


# ============================================================
# Equipamentos
# ============================================================

async def listar_equipamentos(db: AsyncSession) -> list[Equipamento]:
    """Retorna todos os tipos de equipamento cadastrados."""
    # TODO (Dia 4)
    raise NotImplementedError


async def criar_equipamento(db: AsyncSession, dados: EquipamentoCreate) -> Equipamento:
    """Cadastra um novo tipo de equipamento."""
    # TODO (Dia 4)
    raise NotImplementedError


async def buscar_equipamento(db: AsyncSession, equipamento_id: uuid.UUID) -> Equipamento | None:
    """Busca equipamento por ID."""
    # TODO (Dia 4)
    raise NotImplementedError


async def atualizar_equipamento(db: AsyncSession, equipamento_id: uuid.UUID, dados: EquipamentoUpdate) -> Equipamento:
    """Atualiza parcialmente um equipamento."""
    # TODO (Dia 4)
    raise NotImplementedError


# ============================================================
# TipoControle
# ============================================================

async def criar_tipo_controle(db: AsyncSession, dados: TipoControleCreate) -> TipoControle:
    """
    Cria um novo tipo de controle.

    RN: Após criar, propagar para todos os itens já existentes
    nos equipamentos que utilizarem este tipo.
    """
    # TODO (Dia 4)
    raise NotImplementedError


async def listar_tipos_controle(db: AsyncSession) -> list[TipoControle]:
    """Lista todos os tipos de controle cadastrados."""
    # TODO (Dia 4)
    raise NotImplementedError


async def associar_controle_a_equipamento(
    db: AsyncSession,
    equipamento_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
) -> EquipamentoControle:
    """
    Associa um TipoControle a um Equipamento e propaga para itens existentes.

    Algoritmo (MODEL_DB §5.2):
        1. Criar registro em EquipamentoControle
        2. Buscar todos os itens do equipamento
        3. Para cada item sem este controle, criar ControleVencimento com origem=PADRAO
    """
    # TODO (Dia 4)
    raise NotImplementedError


# ============================================================
# ItemEquipamento
# ============================================================

async def criar_item_com_heranca(db: AsyncSession, dados: ItemEquipamentoCreate) -> ItemEquipamento:
    """
    Cria um item físico e herda automaticamente os controles do equipamento.

    Algoritmo (MODEL_DB §5.1):
        1. Criar ItemEquipamento
        2. Buscar controles do Equipamento (equipamento_controles)
        3. Para cada controle, criar ControleVencimento com origem=PADRAO
    """
    # TODO (Dia 4)
    raise NotImplementedError


async def listar_itens(db: AsyncSession, equipamento_id: uuid.UUID | None = None) -> list[ItemEquipamento]:
    """Lista itens, opcionalmente filtrados por equipamento."""
    # TODO (Dia 4)
    raise NotImplementedError


async def buscar_item(db: AsyncSession, item_id: uuid.UUID) -> ItemEquipamento | None:
    """Busca item por ID."""
    # TODO (Dia 4)
    raise NotImplementedError


# ============================================================
# Instalacao
# ============================================================

async def instalar_item(
    db: AsyncSession,
    item_id: uuid.UUID,
    aeronave_id: uuid.UUID,
    data_instalacao: date,
) -> Instalacao:
    """
    Registra a instalação de um item em uma aeronave.

    Raises:
        ValueError: se o item já estiver instalado (data_remocao=None).
    """
    # TODO (Dia 4)
    raise NotImplementedError


async def remover_item(
    db: AsyncSession,
    instalacao_id: uuid.UUID,
    data_remocao: date,
) -> Instalacao:
    """Registra a remoção de um item de uma aeronave."""
    # TODO (Dia 4)
    raise NotImplementedError


# ============================================================
# ControleVencimento
# ============================================================

async def registrar_execucao(
    db: AsyncSession,
    vencimento_id: uuid.UUID,
    data_exec: date,
) -> ControleVencimento:
    """
    Registra a execução de um controle de manutenção.

    Recalcula data_vencimento = data_exec + periodicidade_meses.
    Atualiza status (OK / VENCENDO / VENCIDO).
    """
    # TODO (Dia 4)
    raise NotImplementedError


async def calcular_vencimento(
    data_exec: date,
    periodicidade_meses: int,
) -> date:
    """
    Calcula a data de vencimento a partir da data de execução.

    Args:
        data_exec: data em que o controle foi executado.
        periodicidade_meses: intervalo em meses do tipo de controle.

    Returns:
        Data calculada para o próximo vencimento.
    """
    # TODO (Dia 4):
    # from dateutil.relativedelta import relativedelta
    # return data_exec + relativedelta(months=periodicidade_meses)
    raise NotImplementedError


async def propagar_controle_para_itens(
    db: AsyncSession,
    equipamento_id: uuid.UUID,
    tipo_controle_id: uuid.UUID,
) -> int:
    """
    Propaga um novo controle para todos os itens existentes de um equipamento.

    Returns:
        Número de registros ControleVencimento criados.
    """
    # TODO (Dia 4)
    raise NotImplementedError
