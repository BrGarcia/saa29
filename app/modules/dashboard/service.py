"""
app/modules/dashboard/service.py
Camada de serviço do Dashboard Central.

Princípios:
    - Apenas queries SELECT (zero DDL, zero escrita)
    - Importa modelos diretamente — não chama services de outros módulos
    - Retorna schemas Pydantic (não objetos ORM)
    - Todas as funções são async/await com AsyncSession
"""

from datetime import date, datetime, time, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.panes.models import Pane
from app.modules.vencimentos.models import ControleVencimento, ProrrogacaoVencimento
from app.modules.inspecoes.models import Inspecao, InspecaoTarefa
from app.modules.equipamentos.models import Instalacao, ItemEquipamento, SlotInventario
from app.modules.aeronaves.models import Aeronave
from app.shared.core.enums import StatusAeronave, StatusTarefaInspecao

from app.modules.dashboard.schemas import (
    DashboardResumo,
    PanesSummary, PaneCritica,
    VencimentosSummary,
    InspecaoAtiva,
    MovimentacaoRecente,
    FrotaSummary,
    FrotaAgregadaItem,
)


def _inicio_mes_atual() -> datetime:
    """Retorna o primeiro instante do mês corrente (UTC)."""
    hoje = datetime.now(timezone.utc)
    return hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# 1. Panes
# ---------------------------------------------------------------------------

async def get_panes_summary(db: AsyncSession) -> PanesSummary:
    """
    Retorna:
        - total de panes abertas e ativas
        - total de panes resolvidas no mês corrente
        - as 5 panes abertas mais antigas (críticas)
    """
    # Contagem de panes abertas
    q_abertas = select(func.count()).where(
        Pane.status == "ABERTA",
        Pane.ativo == True,  # noqa: E712
    )
    total_abertas = (await db.execute(q_abertas)).scalar_one() or 0

    # Contagem de panes resolvidas no mês corrente
    inicio_mes = _inicio_mes_atual()
    q_resolvidas = select(func.count()).where(
        Pane.status == "RESOLVIDA",
        Pane.ativo == True,  # noqa: E712
        Pane.data_conclusao >= inicio_mes,
    )
    total_resolvidas_mes = (await db.execute(q_resolvidas)).scalar_one() or 0

    # 5 panes abertas mais antigas — eager-load aeronave e sistema_ata
    q_criticas = (
        select(Pane)
        .where(Pane.status == "ABERTA", Pane.ativo == True)  # noqa: E712
        .order_by(Pane.data_abertura.asc())
        .limit(5)
        .options(
            selectinload(Pane.aeronave),
            selectinload(Pane.sistema_ata)
        )
    )
    rows = (await db.execute(q_criticas)).scalars().all()

    panes_criticas = [
        PaneCritica(
            id=str(p.id),
            matricula=p.aeronave.matricula if p.aeronave else "—",
            # Sistema ATA quando cadastrado (sistema_ata_id é opcional na Pane);
            # cai para a descrição truncada só quando não há sistema associado.
            sistema=(
                p.sistema_ata.descricao if p.sistema_ata
                else p.descricao[:40] + ("..." if len(p.descricao) > 40 else "")
            ),
            data_abertura=p.data_abertura.isoformat(),
        )
        for p in rows
    ]

    return PanesSummary(
        total_abertas=total_abertas,
        total_resolvidas_mes=total_resolvidas_mes,
        panes_criticas=panes_criticas,
    )


# ---------------------------------------------------------------------------
# 2. Vencimentos
# ---------------------------------------------------------------------------

async def get_vencimentos_summary(db: AsyncSession) -> VencimentosSummary:
    """Retorna contagem de controles de vencimento agrupados por status."""
    q = select(
        ControleVencimento.status,
        func.count().label("total"),
    ).group_by(ControleVencimento.status)

    rows = (await db.execute(q)).all()
    contagens = {row[0]: row[1] for row in rows}

    return VencimentosSummary(
        ok=contagens.get("OK", 0),
        vencendo=contagens.get("VENCENDO", 0),
        vencido=contagens.get("VENCIDO", 0),
        prorrogado=contagens.get("PRORROGADO", 0),
    )


# ---------------------------------------------------------------------------
# 3. Inspeções Ativas
# ---------------------------------------------------------------------------

async def get_inspecoes_ativas(db: AsyncSession) -> list[InspecaoAtiva]:
    """Retorna as 5 inspeções ativas (ABERTA ou EM_ANDAMENTO) mais antigas, com eager-load."""
    q = (
        select(Inspecao)
        .where(Inspecao.status.in_(["ABERTA", "EM_ANDAMENTO"]))
        .order_by(Inspecao.data_abertura.asc())
        .limit(5)
        .options(
            selectinload(Inspecao.aeronave),
            selectinload(Inspecao.tipos_aplicados),
        )
    )
    rows = (await db.execute(q)).scalars().all()

    resultado = []
    for insp in rows:
        tipos = [t.codigo for t in (insp.tipos_aplicados or [])]
        dpe = insp.data_fim_prevista.isoformat() if insp.data_fim_prevista else None
        resultado.append(
            InspecaoAtiva(
                inspecao_id=str(insp.id),
                matricula=insp.aeronave.matricula if insp.aeronave else "—",
                tipos=tipos,
                status=insp.status,
                data_fim_prevista=dpe,
            )
        )

    return resultado


# ---------------------------------------------------------------------------
# 4. Movimentações Recentes (Instalações)
# ---------------------------------------------------------------------------

def _instalacao_opcoes_eager_load():
    return (
        selectinload(Instalacao.aeronave),
        selectinload(Instalacao.slot),
        selectinload(Instalacao.item).selectinload(ItemEquipamento.modelo),
    )


def _montar_evento_movimentacao(inst: Instalacao, tipo: str, quando: datetime) -> MovimentacaoRecente:
    nome_equip = inst.item.modelo.nome_generico if inst.item and inst.item.modelo else "Equipamento"
    slot_nome = inst.slot.nome_posicao if inst.slot else "?"
    verbo = "removido" if tipo == "REMOCAO" else "instalado"
    return MovimentacaoRecente(
        tipo=tipo,
        descricao=f"{nome_equip} {verbo} (slot {slot_nome})",
        aeronave_matricula=inst.aeronave.matricula if inst.aeronave else None,
        data=quando.isoformat(),
    )


async def get_movimentacoes_recentes(db: AsyncSession) -> list[MovimentacaoRecente]:
    """
    Retorna os 5 eventos mais recentes de movimentação de equipamentos.

    Uma `Instalacao` pode gerar até dois eventos no feed: a instalação
    original (`created_at`) e, se já removida, a remoção (`removido_em` —
    timestamp dedicado ao evento, gravado na mesma linha por
    `equipamentos.service._registrar_remocao`). Os dois tipos de evento são
    combinados e reordenados pelo timestamp real de cada um, para que uma
    remoção recente apareça como evento próprio mesmo quando a instalação
    original é antiga.
    """
    opcoes = _instalacao_opcoes_eager_load()

    q_instaladas = (
        select(Instalacao)
        .order_by(Instalacao.created_at.desc())
        .limit(5)
        .options(*opcoes)
    )
    q_removidas = (
        select(Instalacao)
        .where(Instalacao.removido_em.is_not(None))
        .order_by(Instalacao.removido_em.desc())
        .limit(5)
        .options(*opcoes)
    )
    instaladas = (await db.execute(q_instaladas)).scalars().all()
    removidas = (await db.execute(q_removidas)).scalars().all()

    eventos: list[MovimentacaoRecente] = []
    for inst in instaladas:
        quando = inst.created_at or datetime.combine(inst.data_instalacao, time.min)
        eventos.append(_montar_evento_movimentacao(inst, "INSTALACAO", quando))
    for inst in removidas:
        eventos.append(_montar_evento_movimentacao(inst, "REMOCAO", inst.removido_em))

    # Ordena pela data ISO (string) em vez do objeto datetime: created_at e
    # removido_em vêm ambos de func.now() e produzem o mesmo formato, então a
    # ordenação lexicográfica equivale à cronológica, sem risco de comparar
    # datetime aware × naive entre as duas origens.
    eventos.sort(key=lambda evento: evento.data, reverse=True)
    return eventos[:5]


# ---------------------------------------------------------------------------
# 5. Frota
# ---------------------------------------------------------------------------

async def get_frota_summary(db: AsyncSession) -> FrotaSummary:
    """
    Retorna contagem de aeronaves e lista individual com status dinâmico.
    O status é calculado em tempo real para garantir que o Dashboard reflita
    a realidade operacional (ex: se há inspeção aberta, status é INSPEÇÃO).
    """
    from app.modules.dashboard.schemas import AeronaveStatus

    # 1. Identificar aeronaves com Inspeções Ativas
    q_insp = select(Inspecao.aeronave_id).where(
        Inspecao.status.in_(["ABERTA", "EM_ANDAMENTO"])
    )
    inspecoes_ativas = {str(id_) for id_ in (await db.execute(q_insp)).scalars().all()}

    # 2. Identificar aeronaves com Panes Abertas
    q_panes = select(Pane.aeronave_id).where(
        Pane.status == "ABERTA",
        Pane.ativo == True  # noqa: E712
    )
    # BUG-01: precisa do mesmo tratamento de string que inspecoes_ativas —
    # sem isso, o "in panes_ativas" abaixo compara str contra set[UUID] e
    # nunca é True.
    panes_ativas = {str(id_) for id_ in (await db.execute(q_panes)).scalars().all()}

    # 3. Buscar todas as aeronaves
    q = select(Aeronave).order_by(Aeronave.matricula.asc())
    aeronaves_rows = (await db.execute(q)).scalars().all()

    contagens = {}
    lista_aeronaves = []

    for a in aeronaves_rows:
        # Status base do banco - normalizado para string
        status_final = a.status.value if hasattr(a.status, 'value') else str(a.status)
        
        # Forçar string para comparação de ID (garante compatibilidade UUID vs UUID)
        ac_id_str = str(a.id)

        # Hierarquia de status do Controle de Frota:
        # 1. Se há inspeção ativa ➔ INSPEÇÃO
        # 2. Se há pane aberta e não está sob inspeção/inativa/estocada ➔ INDISPONIVEL
        if ac_id_str in inspecoes_ativas:
            status_final = "INSPEÇÃO"
        elif ac_id_str in panes_ativas and status_final not in ["INSPEÇÃO", "INATIVA", "ESTOCADA"]:
            status_final = "INDISPONIVEL"

        # Incrementar contagem consolidada
        contagens[status_final] = contagens.get(status_final, 0) + 1
        
        lista_aeronaves.append(AeronaveStatus(
            matricula=a.matricula,
            status=status_final
        ))

    return FrotaSummary(
        disponivel=contagens.get("DISPONIVEL", 0),
        operacional=contagens.get("OPERACIONAL", 0),
        indisponivel=contagens.get("INDISPONIVEL", 0),
        inspecao=contagens.get("INSPEÇÃO", 0),
        estocada=contagens.get("ESTOCADA", 0),
        inativa=contagens.get("INATIVA", 0),
        aeronaves=lista_aeronaves
    )


# ---------------------------------------------------------------------------
# 6. Frota agregada (mobile — GET /dashboard/frota)
# ---------------------------------------------------------------------------

async def get_frota_agregada(db: AsyncSession) -> list[FrotaAgregadaItem]:
    """
    Agregação por aeronave para a Frota mobile: uma única resposta com os
    contadores de pendência de cada módulo (panes, inspeções, vencimentos,
    inventário), eliminando o N+1 (1 requisição de panes por aeronave) que a
    tela inicial do mobile fazia antes — achado #6,
    docs/backlog/modulo_mobile/01_especificacao_mobile.md.

    Número fixo de queries, independente da quantidade de aeronaves.
    """
    from app.modules.vencimentos.service import calcular_status_vencimento

    q_aeronaves = (
        select(Aeronave)
        .where(Aeronave.status != StatusAeronave.INATIVA)
        .order_by(Aeronave.matricula)
    )
    aeronaves = (await db.execute(q_aeronaves)).scalars().all()
    if not aeronaves:
        return []

    # 1. Panes abertas por aeronave
    q_panes = (
        select(Pane.aeronave_id, func.count())
        .where(Pane.status == "ABERTA", Pane.ativo == True)  # noqa: E712
        .group_by(Pane.aeronave_id)
    )
    panes_map = {str(aeronave_id): total for aeronave_id, total in (await db.execute(q_panes)).all()}

    # 2. Inspeções ativas por aeronave + tarefas PENDENTES dessas inspeções
    status_ativos = ("ABERTA", "EM_ANDAMENTO")
    q_insp = select(Inspecao.id, Inspecao.aeronave_id).where(Inspecao.status.in_(status_ativos))
    inspecoes_ativas_rows = (await db.execute(q_insp)).all()

    inspecoes_map: dict[str, int] = {}
    inspecao_para_aeronave: dict = {}
    for insp_id, aeronave_id in inspecoes_ativas_rows:
        chave = str(aeronave_id)
        inspecoes_map[chave] = inspecoes_map.get(chave, 0) + 1
        inspecao_para_aeronave[insp_id] = chave

    tarefas_map: dict[str, int] = {}
    if inspecao_para_aeronave:
        q_tarefas = (
            select(InspecaoTarefa.inspecao_id, func.count())
            .where(
                InspecaoTarefa.inspecao_id.in_(inspecao_para_aeronave.keys()),
                InspecaoTarefa.status == StatusTarefaInspecao.PENDENTE.value,
            )
            .group_by(InspecaoTarefa.inspecao_id)
        )
        for insp_id, total in (await db.execute(q_tarefas)).all():
            chave = inspecao_para_aeronave.get(insp_id)
            if chave:
                tarefas_map[chave] = tarefas_map.get(chave, 0) + total

    # 3. Vencimentos vencidos/vencendo — só controles de itens atualmente
    # instalados (mesmo recorte de montar_matriz_vencimentos). Status sempre
    # derivado por calcular_status_vencimento (nunca o campo persistido),
    # com o mesmo tratamento de prorrogação ativa da matriz.
    q_vencs = (
        select(Instalacao.aeronave_id, ControleVencimento.id, ControleVencimento.data_vencimento)
        .select_from(Instalacao)
        .join(ItemEquipamento, ItemEquipamento.id == Instalacao.item_id)
        .join(ControleVencimento, ControleVencimento.item_id == ItemEquipamento.id)
        .where(Instalacao.data_remocao.is_(None))
    )
    venc_rows = (await db.execute(q_vencs)).all()

    prorrog_map: dict = {}
    if venc_rows:
        controle_ids = {controle_id for _, controle_id, _ in venc_rows}
        q_prorrog = select(
            ProrrogacaoVencimento.controle_id, ProrrogacaoVencimento.data_nova_vencimento
        ).where(
            ProrrogacaoVencimento.controle_id.in_(controle_ids),
            ProrrogacaoVencimento.ativo.is_(True),
        )
        prorrog_map = {controle_id: data_nova for controle_id, data_nova in (await db.execute(q_prorrog)).all()}

    hoje = date.today()
    vencidos_map: dict[str, int] = {}
    vencendo_map: dict[str, int] = {}
    for aeronave_id, controle_id, data_vencimento in venc_rows:
        chave = str(aeronave_id)
        if controle_id in prorrog_map:
            status_venc = "VENCIDO" if hoje > prorrog_map[controle_id] else "PRORROGADO"
        else:
            status_venc = calcular_status_vencimento(data_vencimento, hoje)

        if status_venc == "VENCIDO":
            vencidos_map[chave] = vencidos_map.get(chave, 0) + 1
        elif status_venc == "VENCENDO":
            vencendo_map[chave] = vencendo_map.get(chave, 0) + 1

    # 4. Slots vazios: total de posições configuradas (frota de tipo único —
    # slots não são filtrados por aeronave, mesma base de
    # equipamentos.service.listar_inventario_aeronave) menos instalações
    # ativas de cada aeronave.
    total_slots = (await db.execute(select(func.count()).select_from(SlotInventario))).scalar_one() or 0

    q_instaladas = (
        select(Instalacao.aeronave_id, func.count())
        .where(Instalacao.data_remocao.is_(None))
        .group_by(Instalacao.aeronave_id)
    )
    instaladas_map = {str(aeronave_id): total for aeronave_id, total in (await db.execute(q_instaladas)).all()}

    resultado: list[FrotaAgregadaItem] = []
    for aeronave in aeronaves:
        chave = str(aeronave.id)
        status_final = aeronave.status.value if hasattr(aeronave.status, "value") else str(aeronave.status)

        # Mesma hierarquia de status ao vivo de get_frota_summary (não confia
        # apenas no campo persistido): inspeção ativa > pane aberta > status
        # gravado — necessária para a ordenação por criticidade (RF-M01).
        if chave in inspecoes_map:
            status_final = "INSPEÇÃO"
        elif chave in panes_map and status_final not in (
            StatusAeronave.INATIVA.value, StatusAeronave.ESTOCADA.value
        ):
            status_final = "INDISPONIVEL"

        resultado.append(
            FrotaAgregadaItem(
                aeronave_id=chave,
                matricula=aeronave.matricula,
                status=status_final,
                panes_abertas=panes_map.get(chave, 0),
                inspecoes_ativas=inspecoes_map.get(chave, 0),
                tarefas_pendentes=tarefas_map.get(chave, 0),
                vencimentos_vencidos=vencidos_map.get(chave, 0),
                vencimentos_vencendo=vencendo_map.get(chave, 0),
                slots_vazios=max(0, total_slots - instaladas_map.get(chave, 0)),
            )
        )

    return resultado


# ---------------------------------------------------------------------------
# 7. Orquestrador
# ---------------------------------------------------------------------------

async def get_dashboard_resumo(db: AsyncSession) -> DashboardResumo:
    """
    Função orquestradora: executa todas as queries e consolida
    o resumo completo do Dashboard em um único objeto.
    """
    panes = await get_panes_summary(db)
    vencimentos = await get_vencimentos_summary(db)
    inspecoes = await get_inspecoes_ativas(db)
    movimentacoes = await get_movimentacoes_recentes(db)
    frota = await get_frota_summary(db)

    return DashboardResumo(
        panes=panes,
        vencimentos=vencimentos,
        inspecoes_ativas=inspecoes,
        movimentacoes_recentes=movimentacoes,
        frota=frota,
    )
