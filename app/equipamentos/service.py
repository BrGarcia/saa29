"""
app/equipamentos/service.py
Camada de serviço para gestão de equipamentos seguindo a arquitetura PN vs Slot.
"""

import uuid
import app.aeronaves.models
from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.aeronaves.models import Aeronave
from app.equipamentos.models import (
    ModeloEquipamento,
    SlotInventario,
    TipoControle,
    EquipamentoControle,
    ItemEquipamento,
    Instalacao,
    ControleVencimento,
)
from app.equipamentos.schemas import (
    ModeloEquipamentoCreate,
    SlotInventarioCreate,
    ItemEquipamentoCreate,
    TipoControleCreate,
    InventarioItemOut,
    AjusteInventarioCreate,
    AjusteInventarioResponse,
)
from app.core.enums import OrigemControle, StatusVencimento, StatusItem


# ============================================================
# Catálogo (ModeloEquipamento / PN)
# ============================================================

async def criar_modelo(db: AsyncSession, dados: ModeloEquipamentoCreate) -> ModeloEquipamento:
    """Cadastra um novo Part Number no catálogo."""
    modelo = ModeloEquipamento(**dados.model_dump())
    db.add(modelo)
    await db.flush()
    return modelo

async def buscar_modelo_por_pn(db: AsyncSession, pn: str) -> ModeloEquipamento | None:
    result = await db.execute(select(ModeloEquipamento).where(ModeloEquipamento.part_number == pn))
    return result.scalar_one_or_none()


# ============================================================
# Slots (Configuração da Aeronave)
# ============================================================

async def criar_slot(db: AsyncSession, dados: SlotInventarioCreate) -> SlotInventario:
    """Define um novo slot/posição de inventário."""
    slot = SlotInventario(**dados.model_dump())
    db.add(slot)
    await db.flush()
    return slot


# ============================================================
# Inventário de Aeronave
# ============================================================

async def listar_inventario_aeronave(
    db: AsyncSession,
    aeronave_id: uuid.UUID,
    nome: str | None = None,
) -> list[InventarioItemOut]:
    """Retorna a situação de TODOS os slots da aeronave."""
    from app.aeronaves.service import buscar_aeronave
    aeronave_atual = await buscar_aeronave(db, aeronave_id)
    if not aeronave_atual:
        raise ValueError("Aeronave não encontrada.")

    # 1. Buscar todos os slots (posições) configurados
    stmt_slots = select(SlotInventario).options(selectinload(SlotInventario.modelo))
    if nome:
        # Filtra pelo nome da posição (ex: MDP) ou nome genérico do equipamento
        stmt_slots = stmt_slots.join(ModeloEquipamento).where(
            or_(
                SlotInventario.nome_posicao.ilike(f"%{nome}%"),
                ModeloEquipamento.nome_generico.ilike(f"%{nome}%")
            )
        )
    
    try:
        res_slots = await db.execute(stmt_slots)
        slots = res_slots.scalars().all()

        inventario: list[InventarioItemOut] = []

        for slot in slots:
            # 2. Buscar instalação ativa NESTE SLOT desta aeronave
            stmt_inst = (
                select(Instalacao, ItemEquipamento)
                .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
                .where(
                    Instalacao.slot_id == slot.id,
                    Instalacao.aeronave_id == aeronave_id,
                    Instalacao.data_remocao.is_(None)
                )
            )
            res_inst = await db.execute(stmt_inst)
            row = res_inst.first()
            
            instalacao, item = row if row else (None, None)
            anv_anterior = None

            if item:
                # 3. Buscar histórico (Aeronave Anterior)
                stmt_ant = (
                    select(Aeronave.matricula)
                    .join(Instalacao, Instalacao.aeronave_id == Aeronave.id)
                    .where(
                        Instalacao.item_id == item.id,
                        Instalacao.data_remocao.is_not(None),
                        Instalacao.aeronave_id != aeronave_id
                    )
                    .order_by(desc(Instalacao.data_remocao))
                    .limit(1)
                )
                res_ant = await db.execute(stmt_ant)
                anv_anterior = res_ant.scalar_one_or_none()

            inventario.append(
                InventarioItemOut(
                    slot_id=slot.id,
                    nome_posicao=slot.nome_posicao,
                    sistema=slot.sistema,
                    part_number=slot.modelo.part_number,
                    nome_generico=slot.modelo.nome_generico,
                    equipamento_nome=slot.nome_posicao,
                    equipamento_id=slot.id,
                    item_id=item.id if item else None,
                    numero_serie=item.numero_serie if item else None,
                    status_item=item.status if item else None,
                    instalacao_id=instalacao.id if instalacao else None,
                    data_instalacao=instalacao.data_instalacao if instalacao else None,
                    aeronave_anterior=anv_anterior,
                )
            )

        # Ordenar por sistema e posição
        inventario.sort(key=lambda x: (x.sistema or "ZZZ", x.nome_posicao))
        return inventario

    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in listar_inventario_aeronave: {e}")
        traceback.print_exc()
        raise


async def ajustar_inventario_item(
    db: AsyncSession,
    dados: AjusteInventarioCreate,
) -> AjusteInventarioResponse:
    """
    Sincroniza o S/N REAL com um SLOT de uma aeronave.
    Garante unicidade de SN por PN e gerencia transferências.
    """
    aeronave_id = dados.aeronave_id
    slot_id = dados.slot_id or dados.equipamento_id
    if not slot_id:
        return AjusteInventarioResponse(sucesso=False, mensagem="ID do slot/equipamento não fornecido.")
        
    sn_real = dados.numero_serie_real.strip().upper()

    # 1. Buscar o slot e o PN exigido
    res_slot = await db.execute(
        select(SlotInventario).where(SlotInventario.id == slot_id).options(selectinload(SlotInventario.modelo))
    )
    slot = res_slot.scalar_one_or_none()
    if not slot:
        return AjusteInventarioResponse(sucesso=False, mensagem="Slot de inventário não encontrado.")

    modelo_id = slot.modelo_id

    # 2. Buscar instalação atual nesse slot
    res_inst_atual = await db.execute(
        select(Instalacao)
        .where(Instalacao.slot_id == slot_id, Instalacao.aeronave_id == aeronave_id, Instalacao.data_remocao.is_(None))
        .options(selectinload(Instalacao.item))
    )
    inst_atual = res_inst_atual.scalar_one_or_none()

    if inst_atual and inst_atual.item.numero_serie == sn_real:
        return AjusteInventarioResponse(sucesso=True, mensagem="S/N já está sincronizado.")

    # 3. Buscar/Criar o item físico vinculado ao PN
    res_item = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.numero_serie == sn_real,
            ItemEquipamento.modelo_id == modelo_id
        )
    )
    item_real = res_item.scalar_one_or_none()

    if not item_real:
        item_real = ItemEquipamento(
            id=uuid.uuid4(),
            modelo_id=modelo_id,
            numero_serie=sn_real,
            status=StatusItem.ATIVO
        )
        db.add(item_real)
        await db.flush()

    # 4. Verificar se o item_real está em uso em OUTRA aeronave (ou outro slot)
    res_conflito = await db.execute(
        select(Instalacao)
        .where(Instalacao.item_id == item_real.id, Instalacao.data_remocao.is_(None))
    )
    inst_conflito = res_conflito.scalar_one_or_none()

    if inst_conflito and (inst_conflito.aeronave_id != aeronave_id or inst_conflito.slot_id != slot_id):
        if not dados.forcar_transferencia:
            res_acft = await db.execute(select(Aeronave.matricula).where(Aeronave.id == inst_conflito.aeronave_id))
            matricula = res_acft.scalar_one()
            return AjusteInventarioResponse(
                sucesso=False,
                mensagem=f"O item {sn_real} está instalado na aeronave {matricula}.",
                requer_confirmacao=True,
                aeronave_conflito=matricula
            )
        else:
            inst_conflito.data_remocao = date.today()

    # 5. Encerrar instalação atual do slot (se houver)
    if inst_atual:
        inst_atual.data_remocao = date.today()

    # 6. Criar nova instalação
    nova_inst = Instalacao(
        id=uuid.uuid4(),
        item_id=item_real.id,
        aeronave_id=aeronave_id,
        slot_id=slot_id,
        data_instalacao=date.today()
    )
    db.add(nova_inst)
    
    await db.commit()
    return AjusteInventarioResponse(sucesso=True, mensagem="Inventário ajustado com sucesso.")


# ============================================================
# Legado / Manutenção (Controles)
# ============================================================

async def registrar_execucao(db: AsyncSession, vencimento_id: uuid.UUID, data_exec: date) -> ControleVencimento:
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.id == vencimento_id)
        .options(selectinload(ControleVencimento.tipo_controle))
    )
    vencimento = result.scalar_one_or_none()
    if not vencimento: raise ValueError("Vencimento não encontrado.")

    periodicidade = vencimento.tipo_controle.periodicidade_meses
    vencimento.data_ultima_exec = data_exec
    vencimento.data_vencimento = data_exec + relativedelta(months=periodicidade)

    hoje = date.today()
    if vencimento.data_vencimento < hoje: vencimento.status = StatusVencimento.VENCIDO.value
    elif (vencimento.data_vencimento - hoje).days <= 30: vencimento.status = StatusVencimento.VENCENDO.value
    else: vencimento.status = StatusVencimento.OK.value

    await db.flush()
    return vencimento

async def listar_modelos(db: AsyncSession) -> list[ModeloEquipamento]:
    result = await db.execute(select(ModeloEquipamento).order_by(ModeloEquipamento.part_number))
    return list(result.scalars().all())
