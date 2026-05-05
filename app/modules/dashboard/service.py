"""
app/modules/dashboard/service.py
Camada de serviço do Dashboard Central.

Princípios:
    - Apenas queries SELECT (zero DDL, zero escrita)
    - Importa modelos diretamente — não chama services de outros módulos
    - Retorna schemas Pydantic (não objetos ORM)
    - Todas as funções são async/await com AsyncSession
"""

from datetime import datetime, timezone, date
from calendar import monthrange

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.panes.models import Pane
from app.modules.vencimentos.models import ControleVencimento
from app.modules.inspecoes.models import Inspecao
from app.modules.equipamentos.models import (
    Instalacao, ItemEquipamento, ModeloEquipamento, SlotInventario,
)
from app.modules.aeronaves.models import Aeronave

from app.modules.dashboard.schemas import (
    DashboardResumo,
    PanesSummary, PaneCritica,
    VencimentosSummary,
    InspecaoAtiva,
    MovimentacaoRecente,
    FrotaSummary,
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

    # 5 panes abertas mais antigas — eager-load aeronave para a matrícula
    q_criticas = (
        select(Pane)
        .where(Pane.status == "ABERTA", Pane.ativo == True)  # noqa: E712
        .order_by(Pane.data_abertura.asc())
        .limit(5)
        .options(selectinload(Pane.aeronave))
    )
    rows = (await db.execute(q_criticas)).scalars().all()

    panes_criticas = [
        PaneCritica(
            id=str(p.id),
            matricula=p.aeronave.matricula if p.aeronave else "—",
            sistema=p.sistema_subsistema,
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
    """Retorna inspeções com status ABERTA ou EM_ANDAMENTO com eager-load."""
    q = (
        select(Inspecao)
        .where(Inspecao.status.in_(["ABERTA", "EM_ANDAMENTO"]))
        .order_by(Inspecao.data_abertura.asc())
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

async def get_movimentacoes_recentes(db: AsyncSession) -> list[MovimentacaoRecente]:
    """
    Retorna as 5 instalações de equipamentos mais recentes como mini-feed.
    Nota: A tabela `instalacoes` registra apenas instalações — não remoções.
    """
    q = (
        select(Instalacao)
        .order_by(Instalacao.created_at.desc())
        .limit(5)
        .options(
            selectinload(Instalacao.aeronave),
            selectinload(Instalacao.slot),
            selectinload(Instalacao.item).selectinload(ItemEquipamento.modelo),
        )
    )
    rows = (await db.execute(q)).scalars().all()

    resultado = []
    for inst in rows:
        nome_equip = inst.item.modelo.nome_generico if inst.item and inst.item.modelo else "Equipamento"
        slot_nome = inst.slot.nome_posicao if inst.slot else "?"
        descricao = f"{nome_equip} (slot {slot_nome})"
        matricula = inst.aeronave.matricula if inst.aeronave else None
        data_str = inst.created_at.isoformat() if inst.created_at else inst.data_instalacao.isoformat()

        resultado.append(
            MovimentacaoRecente(
                descricao=descricao,
                aeronave_matricula=matricula,
                data=data_str,
            )
        )

    return resultado


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
    from app.modules.inspecoes.models import Inspecao
    from app.modules.panes.models import Pane

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
    panes_ativas = set((await db.execute(q_panes)).scalars().all())

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

        # 1. Se há inspeção ativa, o status é obrigatoriamente INSPEÇÃO no dashboard.
        if ac_id_str in inspecoes_ativas:
            status_final = "INSPEÇÃO"
        
        # Nota: Removemos o override automático de "INDISPONIVEL" para Panes.
        # Agora o dashboard respeita o status definido pelo Encarregado no banco (Aeronave.status),
        # a menos que a aeronave esteja em inspeção.

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
# 6. Orquestrador
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
