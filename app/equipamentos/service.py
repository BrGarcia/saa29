"""
app/equipamentos/service.py
Camada de serviço para gestão de equipamentos e controle de vencimentos.
"""

import uuid
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.core.enums import OrigemControle, StatusVencimento


# ============================================================
# Equipamentos
# ============================================================

async def listar_equipamentos(db: AsyncSession) -> list[Equipamento]:
    """Retorna todos os tipos de equipamento cadastrados."""
    result = await db.execute(select(Equipamento).order_by(Equipamento.nome))
    return list(result.scalars().all())


async def criar_equipamento(db: AsyncSession, dados: EquipamentoCreate) -> Equipamento:
    """Cadastra um novo tipo de equipamento."""
    equipamento = Equipamento(**dados.model_dump())
    db.add(equipamento)
    await db.flush()
    return equipamento


async def buscar_equipamento(db: AsyncSession, equipamento_id: uuid.UUID) -> Equipamento | None:
    """Busca equipamento por ID."""
    result = await db.execute(
        select(Equipamento).where(Equipamento.id == equipamento_id)
    )
    return result.scalar_one_or_none()


async def atualizar_equipamento(
    db: AsyncSession,
    equipamento_id: uuid.UUID,
    dados: EquipamentoUpdate,
) -> Equipamento:
    """Atualiza parcialmente um equipamento."""
    equipamento = await buscar_equipamento(db, equipamento_id)
    if not equipamento:
        raise ValueError("Equipamento não encontrado.")
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(equipamento, campo, valor)
    await db.flush()
    return equipamento


# ============================================================
# TipoControle
# ============================================================

async def criar_tipo_controle(db: AsyncSession, dados: TipoControleCreate) -> TipoControle:
    """
    Cria um novo tipo de controle.
    """
    # Verificar unicidade do nome
    result = await db.execute(
        select(TipoControle).where(TipoControle.nome == dados.nome)
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Tipo de controle '{dados.nome}' já existe.")

    tipo = TipoControle(**dados.model_dump())
    db.add(tipo)
    await db.flush()
    return tipo


async def listar_tipos_controle(db: AsyncSession) -> list[TipoControle]:
    """Lista todos os tipos de controle cadastrados."""
    result = await db.execute(select(TipoControle).order_by(TipoControle.nome))
    return list(result.scalars().all())


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
    # Verificar se o equipamento existe
    equipamento = await buscar_equipamento(db, equipamento_id)
    if not equipamento:
        raise ValueError("Equipamento não encontrado.")

    # Verificar se o tipo de controle existe
    result_tc = await db.execute(
        select(TipoControle).where(TipoControle.id == tipo_controle_id)
    )
    tipo_controle = result_tc.scalar_one_or_none()
    if not tipo_controle:
        raise ValueError("Tipo de controle não encontrado.")

    # Verificar duplicidade
    result = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.equipamento_id == equipamento_id,
            EquipamentoControle.tipo_controle_id == tipo_controle_id,
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Controle já associado a este equipamento.")

    # 1. Criar registro em EquipamentoControle
    assoc = EquipamentoControle(
        equipamento_id=equipamento_id,
        tipo_controle_id=tipo_controle_id,
    )
    db.add(assoc)
    await db.flush()

    # 2 & 3. Propagar para itens existentes
    await propagar_controle_para_itens(db, equipamento_id, tipo_controle_id)

    return assoc


# ============================================================
# ItemEquipamento
# ============================================================

async def criar_item_com_heranca(
    db: AsyncSession,
    dados: ItemEquipamentoCreate,
) -> ItemEquipamento:
    """
    Cria um item físico e herda automaticamente os controles do equipamento.

    Algoritmo (MODEL_DB §5.1):
        1. Criar ItemEquipamento
        2. Buscar controles do Equipamento (equipamento_controles)
        3. Para cada controle, criar ControleVencimento com origem=PADRAO
    """
    # Verificar se o equipamento existe
    equipamento = await buscar_equipamento(db, dados.equipamento_id)
    if not equipamento:
        raise ValueError("Equipamento não encontrado.")

    # Verificar unicidade do numero_serie
    result = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.numero_serie == dados.numero_serie
        )
    )
    if result.scalar_one_or_none():
        raise ValueError(f"Número de série '{dados.numero_serie}' já cadastrado.")

    # 1. Criar item
    item = ItemEquipamento(
        equipamento_id=dados.equipamento_id,
        numero_serie=dados.numero_serie,
        status=dados.status.value,
    )
    db.add(item)
    await db.flush()

    # 2. Buscar controles template do equipamento
    result_ctrls = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.equipamento_id == dados.equipamento_id
        )
    )
    controles_template: list[EquipamentoControle] = list(result_ctrls.scalars().all())

    # 3. Criar ControleVencimento herdado para cada controle
    for ctrl in controles_template:
        vencimento = ControleVencimento(
            item_id=item.id,
            tipo_controle_id=ctrl.tipo_controle_id,
            status=StatusVencimento.OK.value,
            origem=OrigemControle.PADRAO.value,
        )
        db.add(vencimento)

    await db.flush()
    return item


async def listar_itens(
    db: AsyncSession,
    equipamento_id: uuid.UUID | None = None,
) -> list[ItemEquipamento]:
    """Lista itens, opcionalmente filtrados por equipamento."""
    query = select(ItemEquipamento)
    if equipamento_id:
        query = query.where(ItemEquipamento.equipamento_id == equipamento_id)
    query = query.order_by(ItemEquipamento.numero_serie)
    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_item(db: AsyncSession, item_id: uuid.UUID) -> ItemEquipamento | None:
    """Busca item por ID."""
    result = await db.execute(
        select(ItemEquipamento).where(ItemEquipamento.id == item_id)
    )
    return result.scalar_one_or_none()


async def listar_vencimentos_por_item(
    db: AsyncSession,
    item_id: uuid.UUID,
) -> list[ControleVencimento]:
    """Lista todos os controles de vencimento de um item específico."""
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.item_id == item_id)
        .options(selectinload(ControleVencimento.tipo_controle))
    )
    return list(result.scalars().all())


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
    # Verificar se o item existe
    item = await buscar_item(db, item_id)
    if not item:
        raise ValueError("Item não encontrado.")

    # Verificar se a aeronave existe
    from app.aeronaves.service import buscar_aeronave
    aeronave = await buscar_aeronave(db, aeronave_id)
    if not aeronave:
        raise ValueError("Aeronave não encontrada.")

    # Verificar se o item já está instalado em alguma aeronave
    result = await db.execute(
        select(Instalacao).where(
            Instalacao.item_id == item_id,
            Instalacao.data_remocao.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise ValueError("Item já está instalado em uma aeronave. Remova antes de reinstalar.")

    instalacao = Instalacao(
        item_id=item_id,
        aeronave_id=aeronave_id,
        data_instalacao=data_instalacao,
    )
    db.add(instalacao)
    await db.flush()
    return instalacao


async def remover_item(
    db: AsyncSession,
    instalacao_id: uuid.UUID,
    data_remocao: date,
) -> Instalacao:
    """Registra a remoção de um item de uma aeronave."""
    result_inst = await db.execute(
        select(Instalacao).where(Instalacao.id == instalacao_id)
    )
    instalacao = result_inst.scalar_one_or_none()
    if not instalacao:
        raise ValueError("Instalação não encontrada.")
    if instalacao.data_remocao is not None:
        raise ValueError("Item já foi removido desta instalação.")

    instalacao.data_remocao = data_remocao
    await db.flush()
    return instalacao


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
    # Buscar vencimento com tipo_controle carregado
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.id == vencimento_id)
        .options(selectinload(ControleVencimento.tipo_controle))
    )
    vencimento = result.scalar_one_or_none()
    if not vencimento:
        raise ValueError("Controle de vencimento não encontrado.")

    periodicidade = vencimento.tipo_controle.periodicidade_meses

    # Atualizar datas
    vencimento.data_ultima_exec = data_exec
    vencimento.data_vencimento = await calcular_vencimento(data_exec, periodicidade)

    # Recalcular status baseado na data_vencimento
    hoje = date.today()
    if vencimento.data_vencimento < hoje:
        vencimento.status = StatusVencimento.VENCIDO.value
    elif (vencimento.data_vencimento - hoje).days <= 30:
        vencimento.status = StatusVencimento.VENCENDO.value
    else:
        vencimento.status = StatusVencimento.OK.value

    await db.flush()
    return vencimento


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
    return data_exec + relativedelta(months=periodicidade_meses)


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
    # Buscar todos os itens do equipamento
    result = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.equipamento_id == equipamento_id
        )
    )
    itens = list(result.scalars().all())

    count = 0
    for item in itens:
        # Verificar se o item já tem este controle
        result_ctrl = await db.execute(
            select(ControleVencimento).where(
                ControleVencimento.item_id == item.id,
                ControleVencimento.tipo_controle_id == tipo_controle_id,
            )
        )
        if result_ctrl.scalar_one_or_none() is None:
            vencimento = ControleVencimento(
                item_id=item.id,
                tipo_controle_id=tipo_controle_id,
                status=StatusVencimento.OK.value,
                origem=OrigemControle.PADRAO.value,
            )
            db.add(vencimento)
            count += 1

    if count > 0:
        await db.flush()

    return count
