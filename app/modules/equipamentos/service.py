"""
app/equipamentos/service.py
Camada de serviço para gestão de equipamentos seguindo a arquitetura PN vs Slot.
"""

import uuid
import app.modules.aeronaves.models
from datetime import date
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, and_, or_, desc, union_all, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.shared.core import exceptions as domain_exc
from app.modules.equipamentos.models import (
    ModeloEquipamento,
    SlotInventario,
    TipoControle,
    EquipamentoControle,
    ItemEquipamento,
    Instalacao,
    ControleVencimento,
)
from app.modules.equipamentos.schemas import (
    ModeloEquipamentoCreate,
    SlotInventarioCreate,
    ItemEquipamentoCreate,
    TipoControleCreate,
    InventarioItemOut,
    AjusteInventarioCreate,
    AjusteInventarioResponse,
)
from app.shared.core.enums import OrigemControle, StatusVencimento, StatusItem


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

async def listar_modelos(db: AsyncSession) -> list[ModeloEquipamento]:
    result = await db.execute(select(ModeloEquipamento).order_by(ModeloEquipamento.part_number))
    return list(result.scalars().all())


# ============================================================
# Tipos de Controle (Periodicidades)
# ============================================================

async def listar_tipos_controle(db: AsyncSession) -> list[TipoControle]:
    """Lista todos os tipos de controle cadastrados."""
    result = await db.execute(select(TipoControle).order_by(TipoControle.nome))
    return list(result.scalars().all())

async def criar_tipo_controle(db: AsyncSession, dados: TipoControleCreate) -> TipoControle:
    # Verificar duplicidade
    existing = await db.execute(select(TipoControle).where(TipoControle.nome == dados.nome.upper()))
    if existing.scalar_one_or_none():
        raise ValueError(f"Tipo de controle '{dados.nome}' já existe.")
    tipo = TipoControle(nome=dados.nome.upper(), descricao=dados.descricao)
    db.add(tipo)
    await db.commit()
    return tipo

async def atualizar_tipo_controle(db: AsyncSession, tipo_id: uuid.UUID, dados) -> TipoControle:
    """Atualiza um tipo de controle existente."""
    result = await db.execute(select(TipoControle).where(TipoControle.id == tipo_id))
    tipo = result.scalar_one_or_none()
    if not tipo:
        raise ValueError("Tipo de controle não encontrado.")
    if dados.nome is not None:
        novo_nome = dados.nome.strip().upper()
        # Verificar duplicidade com outro registro
        dup = await db.execute(
            select(TipoControle).where(TipoControle.nome == novo_nome, TipoControle.id != tipo_id)
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Já existe um tipo de controle com o código '{novo_nome}'.")
        tipo.nome = novo_nome
    if dados.descricao is not None:
        tipo.descricao = dados.descricao
    await db.commit()
    return tipo


# ============================================================
# Itens (Serial Number)
# ============================================================

async def criar_item_com_heranca(db: AsyncSession, dados: ItemEquipamentoCreate) -> ItemEquipamento:
    """Cria um item e herda os controles definidos no modelo (PN)."""
    # 1. Verificar se SN já existe para este PN
    res_ex = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.numero_serie == dados.numero_serie,
            ItemEquipamento.modelo_id == dados.modelo_id
        )
    )
    if res_ex.scalar_one_or_none():
        raise ValueError(f"S/N '{dados.numero_serie}' já cadastrado para este P/N.")

    item = ItemEquipamento(**dados.model_dump())
    db.add(item)
    await db.flush()

    # 2. Herdar controles do Modelo (EquipamentoControle -> ControleVencimento)
    res_ctrl = await db.execute(
        select(EquipamentoControle).where(EquipamentoControle.modelo_id == item.modelo_id)
    )
    controles = res_ctrl.scalars().all()

    for ctrl in controles:
        vencimento = ControleVencimento(
            id=uuid.uuid4(),
            item_id=item.id,
            tipo_controle_id=ctrl.tipo_id,
            status=StatusVencimento.OK.value
        )
        db.add(vencimento)

    await db.flush()
    return item


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
    from app.modules.aeronaves.service import buscar_aeronave
    aeronave_atual = await buscar_aeronave(db, aeronave_id)
    if not aeronave_atual:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave não encontrada.")

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

        # 2. OTIMIZAÇÃO: Buscar todas as instalações ativas da aeronave de uma vez
        stmt_todas_inst = (
            select(Instalacao, ItemEquipamento, Usuario.trigrama)
            .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
            .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
            .where(
                Instalacao.aeronave_id == aeronave_id,
                Instalacao.data_remocao.is_(None)
            )
        )
        res_inst = await db.execute(stmt_todas_inst)
        inst_list = res_inst.all()
        inst_map = {row[0].slot_id: row for row in inst_list}

        # 3. OTIMIZAÇÃO: Buscar Aeronave Anterior para todos os itens de uma vez
        item_ids = [row[1].id for row in inst_list]
        ant_map = {}
        if item_ids:
            # Busca a última instalação (removida) para cada item em aeronaves diferentes da atual
            subq = (
                select(
                    Instalacao.item_id,
                    Aeronave.matricula,
                    func.row_number().over(
                        partition_by=Instalacao.item_id,
                        order_by=[desc(Instalacao.data_remocao), desc(Instalacao.created_at)]
                    ).label("rn")
                )
                .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
                .where(
                    Instalacao.item_id.in_(item_ids),
                    Instalacao.data_remocao.is_not(None),
                    Instalacao.aeronave_id != aeronave_id
                )
            ).subquery()
            
            stmt_ant_all = select(subq.c.item_id, subq.c.matricula).where(subq.c.rn == 1)
            res_ant_all = await db.execute(stmt_ant_all)
            ant_map = {r.item_id: r.matricula for r in res_ant_all.all()}

        inventario: list[InventarioItemOut] = []

        for slot in slots:
            # Recuperar do mapa em memória em vez de fazer nova query
            row = inst_map.get(slot.id)

            instalacao, item, user_trigrama = row if row else (None, None, None)
            anv_anterior = ant_map.get(item.id) if item else None
            data_rastreio = instalacao.created_at if instalacao else None

            if not instalacao:
                # Se slot vazio, buscar a última remoção para mostrar quem desinstalou
                # (Esta query ainda é pontual por slot vazio, mas agora apenas para slots vazios)
                stmt_last_rem = (
                    select(Instalacao, Usuario.trigrama)
                    .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
                    .where(
                        Instalacao.slot_id == slot.id,
                        Instalacao.aeronave_id == aeronave_id,
                        Instalacao.data_remocao.is_not(None)
                    )
                    .order_by(desc(Instalacao.updated_at), desc(Instalacao.created_at))
                    .limit(1)
                )
                res_last = await db.execute(stmt_last_rem)
                row_last = res_last.first()
                if row_last:
                    last_inst, user_trigrama = row_last
                    data_rastreio = last_inst.updated_at or last_inst.created_at

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
                    data_atualizacao=data_rastreio,
                    usuario_trigrama=user_trigrama,
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

    # 1. Obter Slot e Validar Existência
    slot = await _obter_slot_com_modelo(db, slot_id)
    if not slot:
        return AjusteInventarioResponse(sucesso=False, mensagem="Slot de inventário não encontrado.")

    # 2. Verificar se o S/N já está no lugar certo
    inst_atual = await _obter_instalacao_ativa_no_slot(db, aeronave_id, slot_id)
    if inst_atual and inst_atual.item.numero_serie == sn_real:
        return AjusteInventarioResponse(sucesso=True, mensagem="S/N já está sincronizado.")

    # 3. Obter ou Criar o Item Físico
    item_real = await _obter_ou_criar_item_por_pn(db, slot.modelo_id, sn_real)

    # 4. Validar e Resolver Conflitos de Instalação (Transferência entre ACFTs)
    conflito_resp = await _validar_e_resolver_conflitos(db, item_real, dados)
    if conflito_resp:
        return conflito_resp

    # 5. Efetivar a Troca (Remover antigo e Instalar novo)
    await _efetivar_troca_no_slot(db, inst_atual, item_real, dados)
    
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        if "FOREIGN KEY constraint failed" in str(e):
            return AjusteInventarioResponse(
                sucesso=False, 
                mensagem="Erro de integridade: Usuário ou Aeronave não encontrados. Tente fazer logoff e login novamente."
            )
        raise e

    return AjusteInventarioResponse(sucesso=True, mensagem="Inventário ajustado com sucesso.")


# --- Funções Auxiliares (Desacoplamento de Domínio) ---

async def _obter_slot_com_modelo(db: AsyncSession, slot_id: uuid.UUID) -> SlotInventario | None:
    res = await db.execute(
        select(SlotInventario).where(SlotInventario.id == slot_id).options(selectinload(SlotInventario.modelo))
    )
    return res.scalar_one_or_none()

async def _obter_instalacao_ativa_no_slot(db: AsyncSession, aeronave_id: uuid.UUID, slot_id: uuid.UUID) -> Instalacao | None:
    res = await db.execute(
        select(Instalacao)
        .where(Instalacao.slot_id == slot_id, Instalacao.aeronave_id == aeronave_id, Instalacao.data_remocao.is_(None))
        .options(selectinload(Instalacao.item))
    )
    return res.scalar_one_or_none()

async def _obter_ou_criar_item_por_pn(db: AsyncSession, modelo_id: uuid.UUID, sn: str) -> ItemEquipamento:
    res = await db.execute(
        select(ItemEquipamento).where(
            ItemEquipamento.numero_serie == sn,
            ItemEquipamento.modelo_id == modelo_id
        )
    )
    item = res.scalar_one_or_none()
    if not item:
        item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo_id, numero_serie=sn, status=StatusItem.ATIVO)
        db.add(item)
        await db.flush()
    return item

async def _validar_e_resolver_conflitos(
    db: AsyncSession, item: ItemEquipamento, dados: AjusteInventarioCreate
) -> AjusteInventarioResponse | None:
    """Verifica se o item está instalado em outro lugar e gerencia a transferência."""
    res = await db.execute(
        select(Instalacao).where(Instalacao.item_id == item.id, Instalacao.data_remocao.is_(None))
    )
    inst_conflito = res.scalar_one_or_none()

    if inst_conflito and (inst_conflito.aeronave_id != dados.aeronave_id or inst_conflito.slot_id != (dados.slot_id or dados.equipamento_id)):
        if not dados.forcar_transferencia:
            res_acft = await db.execute(select(Aeronave.matricula).where(Aeronave.id == inst_conflito.aeronave_id))
            matricula = res_acft.scalar_one()
            return AjusteInventarioResponse(
                sucesso=False,
                mensagem=f"O item {item.numero_serie} está instalado na aeronave {matricula}.",
                requer_confirmacao=True,
                aeronave_conflito=matricula
            )
        else:
            inst_conflito.data_remocao = date.today()
            inst_conflito.updated_at = func.now()
    return None

async def _efetivar_troca_no_slot(
    db: AsyncSession, inst_atual: Instalacao | None, item_novo: ItemEquipamento, dados: AjusteInventarioCreate
):
    """Realiza a remoção do item antigo e a instalação do novo no slot."""
    hoje = date.today()
    if inst_atual:
        inst_atual.data_remocao = hoje
        inst_atual.updated_at = func.now()

    nova_inst = Instalacao(
        id=uuid.uuid4(),
        item_id=item_novo.id,
        aeronave_id=dados.aeronave_id,
        slot_id=dados.slot_id or dados.equipamento_id,
        usuario_id=dados.usuario_id,
        data_instalacao=hoje
    )
    db.add(nova_inst)


async def instalar_item(
    db: AsyncSession, item_id: uuid.UUID, aeronave_id: uuid.UUID, data_instalacao: date
) -> Instalacao:
    """Instala um item em uma aeronave."""
    # Encerrar instalação anterior do item (se houver)
    stmt_old = select(Instalacao).where(Instalacao.item_id == item_id, Instalacao.data_remocao.is_(None))
    res_old = await db.execute(stmt_old)
    old_inst = res_old.scalar_one_or_none()
    if old_inst:
        old_inst.data_remocao = data_instalacao
        old_inst.updated_at = func.now()

    instalacao = Instalacao(
        id=uuid.uuid4(),
        item_id=item_id,
        aeronave_id=aeronave_id,
        data_instalacao=data_instalacao,
        created_at=func.now()
    )
    db.add(instalacao)
    await db.commit()
    return instalacao


async def associar_controle_a_equipamento(
    db: AsyncSession, modelo_id: uuid.UUID, tipo_controle_id: uuid.UUID
) -> EquipamentoControle:
    """Vincula um tipo de controle (ex: TBV) a um modelo (ex: MDP)."""
    # 1. Verificar se já existe
    res = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.modelo_id == modelo_id,
            EquipamentoControle.tipo_controle_id == tipo_controle_id
        )
    )
    if res.scalar_one_or_none():
        raise ValueError("Este controle já está associado ao equipamento.")

    assoc = EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo_id, tipo_controle_id=tipo_controle_id)
    db.add(assoc)
    await db.flush()

    # 2. Propagar para itens existentes (criar ControleVencimento se não houver)
    res_itens = await db.execute(select(ItemEquipamento).where(ItemEquipamento.modelo_id == modelo_id))
    itens = res_itens.scalars().all()

    for item in itens:
        res_venc = await db.execute(
            select(ControleVencimento).where(
                ControleVencimento.item_id == item.id,
                ControleVencimento.tipo_controle_id == tipo_controle_id
            )
        )
        if not res_venc.scalar_one_or_none():
            venc = ControleVencimento(
                id=uuid.uuid4(),
                item_id=item.id,
                tipo_controle_id=tipo_controle_id,
                status=StatusVencimento.OK.value
            )
            db.add(venc)

    await db.flush()
    return assoc


async def registrar_execucao(db: AsyncSession, vencimento_id: uuid.UUID, data_exec: date) -> ControleVencimento:
    """Registra que um controle foi executado e calcula o próximo vencimento."""
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.id == vencimento_id)
        .options(selectinload(ControleVencimento.tipo_controle))
    )
    vencimento = result.scalar_one_or_none()
    if not vencimento: raise domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")

    periodicidade = vencimento.tipo_controle.periodicidade_meses
    vencimento.data_ultima_exec = data_exec
    vencimento.data_vencimento = data_exec + relativedelta(months=periodicidade)

    # Atualizar Status (Lógica simplificada para o MVP)
    hoje = date.today()
    if vencimento.data_vencimento < hoje: vencimento.status = StatusVencimento.VENCIDO.value
    elif (vencimento.data_vencimento - hoje).days <= 30: vencimento.status = StatusVencimento.VENCENDO.value
    else: vencimento.status = StatusVencimento.OK.value

    await db.flush()
    return vencimento


async def listar_historico_recente(db: AsyncSession, limit: int = 15, offset: int = 0) -> list[dict]:
    """Retorna as últimas movimentações (instalações e remoções) de inventário."""
    from app.modules.aeronaves.models import Aeronave
    from app.modules.auth.models import Usuario

    # Eventos de Instalação (baseados em created_at)
    stmt_ins = (
        select(
            Instalacao.id.label("id"),
            Instalacao.created_at.label("event_at"),
            ItemEquipamento.numero_serie.label("item_sn"),
            Aeronave.matricula.label("aeronave_matricula"),
            SlotInventario.nome_posicao.label("slot_nome"),
            Usuario.trigrama.label("usuario_trigrama"),
            func.cast("INSTALAÇÃO", String).label("tipo_acao")
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
    )

    # Eventos de Remoção (baseados em updated_at onde data_remocao existe)
    stmt_rem = (
        select(
            Instalacao.id.label("id"),
            Instalacao.updated_at.label("event_at"),
            ItemEquipamento.numero_serie.label("item_sn"),
            Aeronave.matricula.label("aeronave_matricula"),
            SlotInventario.nome_posicao.label("slot_nome"),
            Usuario.trigrama.label("usuario_trigrama"),
            func.cast("REMOÇÃO", String).label("tipo_acao")
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(Instalacao.data_remocao.is_not(None), Instalacao.updated_at.is_not(None))
    )
    
    # Combinar e ordenar
    query_union = union_all(stmt_ins, stmt_rem).alias("historico_union")
    # Nota: alias.c.coluna é o padrão SQLAlchemy para colunas em subqueries/unions
    stmt_final = select(
        query_union.c.id,
        query_union.c.event_at,
        query_union.c.item_sn,
        query_union.c.aeronave_matricula,
        query_union.c.slot_nome,
        query_union.c.usuario_trigrama,
        query_union.c.tipo_acao
    ).order_by(desc(query_union.c.event_at)).limit(limit).offset(offset)
    
    result = await db.execute(stmt_final)
    rows = result.all()
    
    return [
        {
            "id": r.id,
            "created_at": r.event_at, # Usando event_at para o campo created_at do schema
            "item_sn": r.item_sn,
            "aeronave_matricula": r.aeronave_matricula,
            "slot_nome": r.slot_nome,
            "usuario_trigrama": r.usuario_trigrama,
            "tipo_acao": r.tipo_acao
        }
        for r in rows
    ]


async def remover_item(db: AsyncSession, instalacao_id: uuid.UUID, data_remocao: date, usuario_id: uuid.UUID | None = None) -> Instalacao:
    """Marca uma instalação como removida."""
    result = await db.execute(select(Instalacao).where(Instalacao.id == instalacao_id))
    instalacao = result.scalar_one_or_none()
    if not instalacao:
        raise domain_exc.EntidadeNaoEncontradaError("Instalação não encontrada.")
    
    instalacao.data_remocao = data_remocao
    instalacao.updated_at = func.now()
    if usuario_id:
        instalacao.usuario_id = usuario_id
        
    await db.commit()
    return instalacao


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
    if not vencimento: raise domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")

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
