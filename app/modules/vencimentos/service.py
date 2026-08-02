"""
app/modules/vencimentos/service.py
Camada de serviço para a inteligência temporal de manutenções e vencimentos.
"""

import logging
import uuid
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import ModeloEquipamento, ItemEquipamento, Instalacao
from app.modules.vencimentos.models import (
    TipoControle,
    EquipamentoControle,
    ControleVencimento,
    ProrrogacaoVencimento,
)
from app.modules.vencimentos.schemas import (
    TipoControleCreate, TipoControleUpdate,
    ProrrogacaoVencimentoCreate,
)
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusVencimento, StatusAeronave

logger = logging.getLogger(__name__)


def calcular_status_vencimento(data_vencimento: date | None, hoje: date | None = None) -> str:
    """Deriva o status OK/VENCENDO/VENCIDO a partir da data de vencimento.

    A coluna `ControleVencimento.status` persiste apenas o último valor
    conhecido (útil como histórico do momento da última execução), mas não é
    recalculada pela simples passagem do tempo. Todo ponto de leitura (matriz,
    listagem por item) deve derivar o status exibido a partir desta função,
    em vez de confiar no valor gravado.
    """
    if hoje is None:
        hoje = date.today()
    if data_vencimento is None:
        return StatusVencimento.VENCIDO.value
    if data_vencimento < hoje:
        return StatusVencimento.VENCIDO.value
    if (data_vencimento - hoje).days <= 30:
        return StatusVencimento.VENCENDO.value
    return StatusVencimento.OK.value


async def listar_tipos_controle(db: AsyncSession) -> list[TipoControle]:
    result = await db.execute(select(TipoControle).order_by(TipoControle.nome))
    return list(result.scalars().all())

async def criar_tipo_controle(db: AsyncSession, dados: TipoControleCreate) -> TipoControle:
    existing = await db.execute(select(TipoControle).where(TipoControle.nome == dados.nome.upper()))
    if existing.scalar_one_or_none():
        raise ValueError(f"Tipo de controle '{dados.nome}' já existe.")
    tipo = TipoControle(nome=dados.nome.upper(), descricao=dados.descricao)
    try:
        # SAVEPOINT: em caso de criação concorrente com o mesmo nome, desfaz
        # apenas este insert e mantém a transação da requisição utilizável.
        async with db.begin_nested():
            db.add(tipo)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar tipo de controle %s: %s", dados.nome, exc.orig)
        raise ValueError(f"Tipo de controle '{dados.nome}' já existe.") from exc
    return tipo

async def atualizar_tipo_controle(db: AsyncSession, tipo_id: uuid.UUID, dados: TipoControleUpdate) -> TipoControle:
    result = await db.execute(select(TipoControle).where(TipoControle.id == tipo_id))
    tipo = result.scalar_one_or_none()
    if not tipo:
        raise ValueError("Tipo de controle não encontrado.")
    if dados.nome is not None:
        novo_nome = dados.nome.strip().upper()
        dup = await db.execute(
            select(TipoControle).where(TipoControle.nome == novo_nome, TipoControle.id != tipo_id)
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Já existe um tipo de controle com o código '{novo_nome}'.")
        tipo.nome = novo_nome
    if dados.descricao is not None:
        tipo.descricao = dados.descricao
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao atualizar tipo de controle %s: %s", tipo_id, exc.orig)
        raise ValueError(f"Já existe um tipo de controle com o código '{dados.nome}'.") from exc
    return tipo

async def associar_controle_a_equipamento(
    db: AsyncSession, modelo_id: uuid.UUID, tipo_controle_id: uuid.UUID, periodicidade: int
) -> EquipamentoControle:
    res = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.modelo_id == modelo_id,
            EquipamentoControle.tipo_controle_id == tipo_controle_id
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        old_periodicidade = existing.periodicidade_meses
        existing.periodicidade_meses = periodicidade

        # Se a periodicidade mudou, recalcular vencimentos dos itens que já tenham sido executados
        if old_periodicidade != periodicidade:
            res_vencs = await db.execute(
                select(ControleVencimento)
                .where(
                    ControleVencimento.tipo_controle_id == tipo_controle_id,
                    ControleVencimento.item_id.in_(
                        select(ItemEquipamento.id).where(ItemEquipamento.modelo_id == modelo_id)
                    ),
                    ControleVencimento.data_ultima_exec.is_not(None)
                )
            )
            vencs_to_fix = res_vencs.scalars().all()
            for v in vencs_to_fix:
                v.data_vencimento = v.data_ultima_exec + relativedelta(months=periodicidade)
                # status é derivado em tempo de leitura por calcular_status_vencimento()

        await db.flush()
        return existing

    assoc = EquipamentoControle(
        id=uuid.uuid4(),
        modelo_id=modelo_id,
        tipo_controle_id=tipo_controle_id,
        periodicidade_meses=periodicidade
    )
    try:
        async with db.begin_nested():
            db.add(assoc)
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de UNIQUE ao associar controle %s ao modelo %s: %s",
            tipo_controle_id, modelo_id, exc.orig,
        )
        raise ValueError("Este tipo de controle já está associado a este equipamento.") from exc

    res_itens = await db.execute(select(ItemEquipamento.id).where(ItemEquipamento.modelo_id == modelo_id))
    item_ids = set(res_itens.scalars().all())

    res_existentes = await db.execute(
        select(ControleVencimento.item_id).where(
            ControleVencimento.tipo_controle_id == tipo_controle_id,
            ControleVencimento.item_id.in_(item_ids),
        )
    )
    item_ids_com_controle = set(res_existentes.scalars().all())

    for item_id in item_ids - item_ids_com_controle:
        db.add(
            ControleVencimento(
                id=uuid.uuid4(),
                item_id=item_id,
                tipo_controle_id=tipo_controle_id,
                status=StatusVencimento.VENCIDO.value,
            )
        )

    await db.flush()
    return assoc

async def criar_controles_para_item(
    db: AsyncSession, item_id: uuid.UUID, modelo_id: uuid.UUID
) -> int:
    """Cria os controles de vencimento herdados do template do PN.

    Ponto de entrada público para outros módulos (ex.: equipamentos) — evita que
    eles conheçam regras internas deste domínio, como o status inicial dos
    controles. Todo controle nasce VENCIDO: não há execução registrada para um
    item recém-cadastrado.

    Args:
        item_id: Item físico (S/N) recém-criado.
        modelo_id: PN cujos `EquipamentoControle` servem de template.

    Returns:
        Quantidade de controles criados.
    """
    res = await db.execute(
        select(EquipamentoControle.tipo_controle_id).where(
            EquipamentoControle.modelo_id == modelo_id
        )
    )
    tipos_controle = list(res.scalars().all())

    for tipo_controle_id in tipos_controle:
        db.add(
            ControleVencimento(
                id=uuid.uuid4(),
                item_id=item_id,
                tipo_controle_id=tipo_controle_id,
                status=StatusVencimento.VENCIDO.value,
            )
        )

    if tipos_controle:
        await db.flush()
    return len(tipos_controle)


async def listar_equipamento_controles(db: AsyncSession) -> list[EquipamentoControle]:
    result = await db.execute(
        select(EquipamentoControle)
        .options(
            selectinload(EquipamentoControle.modelo),
            selectinload(EquipamentoControle.tipo_controle)
        )
    )
    return list(result.scalars().all())

async def remover_controle_de_equipamento(
    db: AsyncSession, modelo_id: uuid.UUID, tipo_controle_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.modelo_id == modelo_id,
            EquipamentoControle.tipo_controle_id == tipo_controle_id
        )
    )
    assoc = result.scalar_one_or_none()
    if assoc:
        await db.delete(assoc)
        await db.flush()

async def registrar_execucao(db: AsyncSession, vencimento_id: uuid.UUID, data_exec: date, usuario_id: uuid.UUID) -> ControleVencimento:
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.id == vencimento_id)
        .options(selectinload(ControleVencimento.item))
    )
    vencimento = result.scalar_one_or_none()
    if not vencimento: 
        raise domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")

    res_regra = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.modelo_id == vencimento.item.modelo_id,
            EquipamentoControle.tipo_controle_id == vencimento.tipo_controle_id
        )
    )
    regra = res_regra.scalar_one_or_none()
    
    if not regra:
        raise domain_exc.EntidadeNaoEncontradaError(
            f"Regra de periodicidade não encontrada para o modelo {vencimento.item.modelo_id}. "
            "Configure o controle para este equipamento antes de registrar a execução."
        )
    
    periodicidade = regra.periodicidade_meses
    
    vencimento.data_ultima_exec = data_exec
    vencimento.data_vencimento = data_exec + relativedelta(months=periodicidade)
    vencimento.executado_por_id = usuario_id

    await db.execute(
        ProrrogacaoVencimento.__table__.update()
        .where(
            and_(
                ProrrogacaoVencimento.controle_id == vencimento_id,
                ProrrogacaoVencimento.ativo == True
            )
        )
        .values(ativo=False)
    )
    # Bug 147: Sincronizar cache da sessão após update via SQL puro
    db.expire(vencimento, ["prorrogacoes"])

    hoje = date.today()
    if not vencimento.data_ultima_exec:
        vencimento.status = StatusVencimento.VENCIDO.value
    elif vencimento.data_vencimento < hoje: 
        vencimento.status = StatusVencimento.VENCIDO.value
    elif (vencimento.data_vencimento - hoje).days <= 30: 
        vencimento.status = StatusVencimento.VENCENDO.value
    else: 
        vencimento.status = StatusVencimento.OK.value

    await db.flush()
    return vencimento

async def listar_vencimentos_por_item(db: AsyncSession, item_id: uuid.UUID) -> list[ControleVencimento]:
    result = await db.execute(
        select(ControleVencimento)
        .where(ControleVencimento.item_id == item_id)
        .options(selectinload(ControleVencimento.tipo_controle))
    )
    return list(result.scalars().all())

async def montar_matriz_vencimentos(db: AsyncSession) -> dict:
    res_modelos = await db.execute(
        select(ModeloEquipamento)
        .join(EquipamentoControle, EquipamentoControle.modelo_id == ModeloEquipamento.id)
        .options(
            selectinload(ModeloEquipamento.controles_template)
            .selectinload(EquipamentoControle.tipo_controle)
        )
        .order_by(ModeloEquipamento.nome_generico)
        .distinct()
    )
    modelos = list(res_modelos.scalars().unique().all())

    if not modelos:
        return {"cabecalho": {}, "aeronaves": []}

    cabecalho: dict[str, list[str]] = {}
    modelo_map: dict[uuid.UUID, ModeloEquipamento] = {}
    for modelo in modelos:
        nome = modelo.nome_generico
        cabecalho[nome] = [ctrl.tipo_controle.nome for ctrl in modelo.controles_template]
        modelo_map[modelo.id] = modelo

    res_acft = await db.execute(
        select(Aeronave)
        .where(Aeronave.status != StatusAeronave.INATIVA)
        .order_by(Aeronave.matricula)
    )
    aeronaves = res_acft.scalars().all()

    if not aeronaves:
        return {"cabecalho": cabecalho, "aeronaves": []}

    aeronave_ids = [a.id for a in aeronaves]
    res_inst = await db.execute(
        select(Instalacao)
        .options(
            selectinload(Instalacao.slot),
            selectinload(Instalacao.item)
            .selectinload(ItemEquipamento.controles_vencimento).options(
                selectinload(ControleVencimento.tipo_controle),
                selectinload(ControleVencimento.prorrogacoes),
                selectinload(ControleVencimento.executado_por)
            ),
        )
        .where(
            Instalacao.aeronave_id.in_(aeronave_ids),
            Instalacao.data_remocao.is_(None),
        )
    )
    instalacoes = res_inst.scalars().all()

    inst_map: dict[uuid.UUID, dict[uuid.UUID, Instalacao]] = {}
    for inst in instalacoes:
        slot_modelo_id = inst.slot.modelo_id
        if slot_modelo_id not in modelo_map:
            continue
        if inst.aeronave_id not in inst_map:
            inst_map[inst.aeronave_id] = {}
        if slot_modelo_id not in inst_map[inst.aeronave_id]:
            inst_map[inst.aeronave_id][slot_modelo_id] = inst

    hoje = date.today()
    aeronaves_out = []
    for aeronave in aeronaves:
        acft_inst = inst_map.get(aeronave.id, {})
        slots_out = []

        has_desinstalado = False
        has_vencido = False
        has_vencendo = False

        for modelo in modelos:
            inst = acft_inst.get(modelo.id)
            item = inst.item if inst else None

            venc_map: dict[str, ControleVencimento] = {}
            if item:
                for venc in item.controles_vencimento:
                    venc_map[venc.tipo_controle.nome] = venc

            controles_out = []
            for ctrl in modelo.controles_template:
                tipo_nome = ctrl.tipo_controle.nome
                venc = venc_map.get(tipo_nome)
                
                if not item:
                    status_final = "DESINSTALADO"
                elif venc:
                    status_final = calcular_status_vencimento(venc.data_vencimento, hoje)
                else:
                    status_final = StatusVencimento.VENCIDO.value
                prorrogado = False
                data_nova = None
                doc_prorrogacao = None

                if venc:
                    prorrogacao_ativa = next((p for p in venc.prorrogacoes if p.ativo), None)
                    if prorrogacao_ativa:
                        prorrogado = True
                        data_nova = prorrogacao_ativa.data_nova_vencimento
                        doc_prorrogacao = prorrogacao_ativa.numero_documento

                        if hoje > data_nova:
                            status_final = "VENCIDO"
                        else:
                            status_final = "PRORROGADO"
                
                if status_final == "VENCIDO": has_vencido = True
                elif status_final == "DESINSTALADO": has_desinstalado = True
                elif status_final == "VENCENDO": has_vencendo = True

                controles_out.append({
                    "vencimento_id": str(venc.id) if venc else None,
                    "tipo_controle_nome": tipo_nome,
                    "data_ultima_exec": venc.data_ultima_exec.isoformat() if venc and venc.data_ultima_exec else None,
                    "executado_por_trigrama": venc.executado_por.trigrama if venc and venc.executado_por else None,
                    "data_vencimento": venc.data_vencimento.isoformat() if venc and venc.data_vencimento else None,
                    "status": status_final,
                    "prorrogado": prorrogado,
                    "data_nova_vencimento": data_nova.isoformat() if data_nova else None,
                    "numero_documento_prorrogacao": doc_prorrogacao,
                })

            slots_out.append({
                "sistema": modelo.nome_generico,
                "part_number": modelo.part_number,
                "numero_serie": item.numero_serie if item else None,
                "controles": controles_out,
            })

        if has_vencido: status_venc = "VENCIDO"
        elif has_desinstalado: status_venc = "INCOMPLETA"
        elif has_vencendo: status_venc = "VENCENDO"
        else: status_venc = "OK"

        aeronaves_out.append({
            "aeronave_id": str(aeronave.id),
            "matricula": aeronave.matricula,
            "status_aeronave": aeronave.status,
            "status_vencimento": status_venc,
            "slots": slots_out,
        })

    return {"cabecalho": cabecalho, "aeronaves": aeronaves_out}

async def prorrogar_vencimento(
    db: AsyncSession, 
    vencimento_id: uuid.UUID, 
    dados_prorrogacao: ProrrogacaoVencimentoCreate,
    usuario_id: uuid.UUID | None = None
) -> ProrrogacaoVencimento:
    vencimento = await db.get(ControleVencimento, vencimento_id)
    if not vencimento:
        raise domain_exc.EntidadeNaoEncontradaError("Vencimento não encontrado.")
        
    await db.execute(
        ProrrogacaoVencimento.__table__.update()
        .where(
            and_(
                ProrrogacaoVencimento.controle_id == vencimento_id,
                ProrrogacaoVencimento.ativo == True
            )
        )
        .values(ativo=False)
    )
    # Bug 147: Sincronizar cache
    db.expire(vencimento, ["prorrogacoes"])
    
    data_base = vencimento.data_vencimento or dados_prorrogacao.data_concessao
    data_nova_vencimento = data_base + timedelta(days=dados_prorrogacao.dias_adicionais)

    nova_prorrogacao = ProrrogacaoVencimento(
        controle_id=vencimento_id,
        numero_documento=dados_prorrogacao.numero_documento,
        data_concessao=dados_prorrogacao.data_concessao,
        data_nova_vencimento=data_nova_vencimento,
        dias_adicionais=dados_prorrogacao.dias_adicionais,
        motivo=dados_prorrogacao.motivo,
        observacao=dados_prorrogacao.observacao,
        registrado_por_id=usuario_id,
        ativo=True
    )
    
    db.add(nova_prorrogacao)
    await db.flush()
    await db.refresh(nova_prorrogacao)
    return nova_prorrogacao

async def cancelar_prorrogacao(db: AsyncSession, vencimento_id: uuid.UUID) -> bool:
    result = await db.execute(
        ProrrogacaoVencimento.__table__.update()
        .where(
            and_(
                ProrrogacaoVencimento.controle_id == vencimento_id,
                ProrrogacaoVencimento.ativo == True
            )
        )
        .values(ativo=False)
    )
    # Bug 147: Sincronizar cache
    vencimento = await db.get(ControleVencimento, vencimento_id)
    if vencimento:
        db.expire(vencimento, ["prorrogacoes"])
    await db.flush()
    return result.rowcount > 0
