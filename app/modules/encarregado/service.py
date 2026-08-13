"""
app/modules/encarregado/service.py
Camada de serviço do módulo Encarregado — Ciência de Alterações
(feature_encarregado_ciencia.md v2.0).

Este módulo é EXCLUSIVAMENTE DE LEITURA sobre panes/inspecao_tarefas/
instalacoes/controle_vencimentos (RN-ENC-05): nenhuma função aqui escreve,
atualiza ou apaga uma linha dessas tabelas. A única escrita é em
`encarregado_ciencias`, via `dar_ciencia`/`desfazer_ciencia`.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, cast, exists, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.encarregado.models import EncarregadoCiencia
from app.modules.encarregado.schemas import (
    AlteracaoPendenteItem,
    CienciaOut,
    DarCienciaRequest,
    ListaPendentesResponse,
)
from app.modules.equipamentos.models import Instalacao, ItemEquipamento, ModeloEquipamento, SlotInventario
from app.modules.inspecoes.models import Inspecao, InspecaoTarefa
from app.modules.panes.models import Pane
from app.modules.vencimentos.models import (
    ControleVencimento,
    ExecucaoVencimentoHistorico,
    ProrrogacaoVencimento,
    TipoControle,
)
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import CategoriaCiencia, EventoCiencia, StatusPane, StatusTarefaInspecao

# RN-ENC-01 / RN-ENC-02.
JANELA_DIAS = 90
LIMITE_POR_CATEGORIA = 100

ESTOQUE_LABEL = "ESTOQUE"


def _sem_ciencia(categoria: CategoriaCiencia, evento: EventoCiencia, registro_id_col):
    """Anti-join (RN-ENC-01): verdadeiro quando o registro de origem ainda
    não tem uma linha correspondente em `encarregado_ciencias`. Aplicado no
    WHERE da própria query de origem — antes do LIMIT — para não truncar a
    lista descartando itens que na verdade já foram vistados.

    `cast(registro_id_col, String)` no SQLite devolve o hex sem hífens (o
    formato de armazenamento real de `Uuid`, não `str(uuid.UUID)`) — por
    isso `AlteracaoPendenteItem.registro_id` é sempre construído com
    `.hex`, nunca `str(...)`. Divergir os dois quebra o anti-join
    silenciosamente (a ciência é gravada, mas nunca é encontrada aqui)."""
    return ~exists().where(
        EncarregadoCiencia.categoria == categoria.value,
        EncarregadoCiencia.evento == evento.value,
        EncarregadoCiencia.registro_id == cast(registro_id_col, String),
    )


# --------------------------------------------------------------------- #
# PANES — pane resolvida
# --------------------------------------------------------------------- #

async def _pendentes_panes(db: AsyncSession, cutoff: datetime, limite: int) -> list[AlteracaoPendenteItem]:
    """Card: `[AERONAVE] [DESCRICAO] [OBSERVACAO_CONCLUSAO] [TRIGRAMA]`."""
    stmt = (
        select(
            Pane.id,
            Pane.descricao,
            Pane.observacao_conclusao,
            Pane.data_conclusao,
            Aeronave.matricula,
            Usuario.trigrama,
        )
        .join(Aeronave, Pane.aeronave_id == Aeronave.id)
        .outerjoin(Usuario, Pane.concluido_por_id == Usuario.id)
        .where(
            Pane.status == StatusPane.RESOLVIDA.value,
            Pane.ativo == True,  # noqa: E712 — RN-ENC-06
            Pane.data_conclusao.is_not(None),
            Pane.data_conclusao >= cutoff,
            _sem_ciencia(CategoriaCiencia.PANES, EventoCiencia.CONCLUSAO, Pane.id),
        )
        .order_by(Pane.data_conclusao.desc())
        .limit(limite)
    )
    rows = (await db.execute(stmt)).all()
    return [
        AlteracaoPendenteItem(
            categoria=CategoriaCiencia.PANES,
            evento=EventoCiencia.CONCLUSAO,
            registro_id=pane_id.hex,
            aeronave_matricula=matricula,
            titulo=descricao,
            detalhe=observacao_conclusao,
            responsavel_trigrama=trigrama,
            data_evento=data_conclusao,
        )
        for pane_id, descricao, observacao_conclusao, data_conclusao, matricula, trigrama in rows
    ]


# --------------------------------------------------------------------- #
# INSPECAO — tarefa concluída
# --------------------------------------------------------------------- #

async def _pendentes_inspecao(db: AsyncSession, cutoff: datetime, limite: int) -> list[AlteracaoPendenteItem]:
    """Card: `[AERONAVE] [TITULO] [TRIGRAMA]`."""
    stmt = (
        select(
            InspecaoTarefa.id,
            InspecaoTarefa.titulo,
            InspecaoTarefa.data_execucao,
            Aeronave.matricula,
            Usuario.trigrama,
        )
        .join(Inspecao, InspecaoTarefa.inspecao_id == Inspecao.id)
        .join(Aeronave, Inspecao.aeronave_id == Aeronave.id)
        .outerjoin(Usuario, InspecaoTarefa.executado_por_id == Usuario.id)
        .where(
            InspecaoTarefa.status == StatusTarefaInspecao.CONCLUIDA.value,
            InspecaoTarefa.data_execucao.is_not(None),
            InspecaoTarefa.data_execucao >= cutoff,
            _sem_ciencia(CategoriaCiencia.INSPECAO, EventoCiencia.EXECUCAO, InspecaoTarefa.id),
        )
        .order_by(InspecaoTarefa.data_execucao.desc())
        .limit(limite)
    )
    rows = (await db.execute(stmt)).all()
    return [
        AlteracaoPendenteItem(
            categoria=CategoriaCiencia.INSPECAO,
            evento=EventoCiencia.EXECUCAO,
            registro_id=tarefa_id.hex,
            aeronave_matricula=matricula,
            titulo=titulo,
            detalhe=None,
            responsavel_trigrama=trigrama,
            data_evento=data_execucao,
        )
        for tarefa_id, titulo, data_execucao, matricula, trigrama in rows
    ]


# --------------------------------------------------------------------- #
# INVENTARIO — instalação e remoção (2 eventos por linha, esclarecimento §2.2)
# --------------------------------------------------------------------- #

async def _pendentes_inventario(db: AsyncSession, cutoff: datetime, limite: int) -> list[AlteracaoPendenteItem]:
    """Card: `[AERONAVE] [SLOT] [SN SAIU] [SN ENTROU] [TRIGRAMA]`."""
    InstalacaoAnterior = aliased(Instalacao)
    ItemAnterior = aliased(ItemEquipamento)

    # "SN que saiu" (esclarecimento §4): instalação anterior no mesmo
    # (aeronave_id, slot_id), com data_remocao preenchida e anterior à
    # data_instalacao da linha corrente. Ausente => slot estava vago.
    sn_saiu_subq = (
        select(ItemAnterior.numero_serie)
        .join(InstalacaoAnterior, InstalacaoAnterior.item_id == ItemAnterior.id)
        .where(
            InstalacaoAnterior.aeronave_id == Instalacao.aeronave_id,
            InstalacaoAnterior.slot_id == Instalacao.slot_id,
            InstalacaoAnterior.data_remocao.is_not(None),
            InstalacaoAnterior.data_remocao < Instalacao.data_instalacao,
        )
        .order_by(InstalacaoAnterior.data_remocao.desc())
        .limit(1)
        .correlate(Instalacao)
        .scalar_subquery()
    )

    stmt_instalacao = (
        select(
            Instalacao.id,
            Instalacao.created_at,
            Aeronave.matricula,
            SlotInventario.nome_posicao,
            ItemEquipamento.numero_serie,
            sn_saiu_subq,
            Usuario.trigrama,
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(
            Instalacao.created_at >= cutoff,
            _sem_ciencia(CategoriaCiencia.INVENTARIO, EventoCiencia.INSTALACAO, Instalacao.id),
        )
        .order_by(Instalacao.created_at.desc())
        .limit(limite)
    )
    stmt_remocao = (
        select(
            Instalacao.id,
            Instalacao.removido_em,
            Aeronave.matricula,
            SlotInventario.nome_posicao,
            ItemEquipamento.numero_serie,
            Usuario.trigrama,
        )
        .join(ItemEquipamento, Instalacao.item_id == ItemEquipamento.id)
        .join(Aeronave, Instalacao.aeronave_id == Aeronave.id)
        .join(SlotInventario, Instalacao.slot_id == SlotInventario.id)
        .outerjoin(Usuario, Instalacao.usuario_id == Usuario.id)
        .where(
            Instalacao.data_remocao.is_not(None),
            Instalacao.removido_em.is_not(None),
            Instalacao.removido_em >= cutoff,
            _sem_ciencia(CategoriaCiencia.INVENTARIO, EventoCiencia.REMOCAO, Instalacao.id),
        )
        .order_by(Instalacao.removido_em.desc())
        .limit(limite)
    )

    linhas_instalacao = (await db.execute(stmt_instalacao)).all()
    linhas_remocao = (await db.execute(stmt_remocao)).all()

    itens: list[AlteracaoPendenteItem] = []
    for inst_id, data_evento, matricula, slot_nome, sn_entrou, sn_saiu, trigrama in linhas_instalacao:
        itens.append(
            AlteracaoPendenteItem(
                categoria=CategoriaCiencia.INVENTARIO,
                evento=EventoCiencia.INSTALACAO,
                registro_id=inst_id.hex,
                aeronave_matricula=matricula,
                titulo=slot_nome,
                detalhe=f"{sn_saiu or '—'} → {sn_entrou}",
                responsavel_trigrama=trigrama,
                data_evento=data_evento,
            )
        )
    for inst_id, data_evento, matricula, slot_nome, sn_saiu, trigrama in linhas_remocao:
        itens.append(
            AlteracaoPendenteItem(
                categoria=CategoriaCiencia.INVENTARIO,
                evento=EventoCiencia.REMOCAO,
                registro_id=inst_id.hex,
                aeronave_matricula=matricula,
                titulo=slot_nome,
                detalhe=f"{sn_saiu} → —",
                responsavel_trigrama=trigrama,
                data_evento=data_evento,
            )
        )

    itens.sort(key=lambda item: item.data_evento, reverse=True)
    return itens[:limite]


# --------------------------------------------------------------------- #
# VENCIMENTOS — execução e prorrogação
# --------------------------------------------------------------------- #

async def _pendentes_vencimentos(db: AsyncSession, cutoff: datetime, limite: int) -> list[AlteracaoPendenteItem]:
    """Card: `[AERONAVE] [EQUIPAMENTO] [TIPO CONTROLE] [NOVO VENCIMENTO] [TRIGRAMA]`."""
    # Aeronave é indireta (esclarecimento §4): item -> instalação ativa
    # (data_remocao IS NULL) -> aeronave. Sem instalação ativa => ESTOQUE.
    aeronave_atual_subq = (
        select(Aeronave.matricula)
        .join(Instalacao, Instalacao.aeronave_id == Aeronave.id)
        .where(
            Instalacao.item_id == ItemEquipamento.id,
            Instalacao.data_remocao.is_(None),
        )
        .order_by(Instalacao.data_instalacao.desc())
        .limit(1)
        .correlate(ItemEquipamento)
        .scalar_subquery()
    )
    aeronave_ou_estoque = func.coalesce(aeronave_atual_subq, literal(ESTOQUE_LABEL))

    stmt_execucao = (
        select(
            ExecucaoVencimentoHistorico.id,
            ExecucaoVencimentoHistorico.registrado_em,
            ExecucaoVencimentoHistorico.data_vencimento_calculada,
            ModeloEquipamento.nome_generico,
            TipoControle.nome,
            aeronave_ou_estoque,
            Usuario.trigrama,
        )
        .join(ControleVencimento, ExecucaoVencimentoHistorico.controle_id == ControleVencimento.id)
        .join(ItemEquipamento, ControleVencimento.item_id == ItemEquipamento.id)
        .join(ModeloEquipamento, ItemEquipamento.modelo_id == ModeloEquipamento.id)
        .join(TipoControle, ControleVencimento.tipo_controle_id == TipoControle.id)
        .outerjoin(Usuario, ExecucaoVencimentoHistorico.executado_por_id == Usuario.id)
        .where(
            ExecucaoVencimentoHistorico.registrado_em >= cutoff,
            _sem_ciencia(
                CategoriaCiencia.VENCIMENTOS, EventoCiencia.EXECUCAO, ExecucaoVencimentoHistorico.id
            ),
        )
        .order_by(ExecucaoVencimentoHistorico.registrado_em.desc())
        .limit(limite)
    )
    stmt_prorrogacao = (
        select(
            ProrrogacaoVencimento.id,
            ProrrogacaoVencimento.created_at,
            ProrrogacaoVencimento.data_nova_vencimento,
            ModeloEquipamento.nome_generico,
            TipoControle.nome,
            aeronave_ou_estoque,
            Usuario.trigrama,
        )
        .join(ControleVencimento, ProrrogacaoVencimento.controle_id == ControleVencimento.id)
        .join(ItemEquipamento, ControleVencimento.item_id == ItemEquipamento.id)
        .join(ModeloEquipamento, ItemEquipamento.modelo_id == ModeloEquipamento.id)
        .join(TipoControle, ControleVencimento.tipo_controle_id == TipoControle.id)
        .outerjoin(Usuario, ProrrogacaoVencimento.registrado_por_id == Usuario.id)
        .where(
            ProrrogacaoVencimento.ativo == True,  # noqa: E712
            ProrrogacaoVencimento.created_at >= cutoff,
            _sem_ciencia(
                CategoriaCiencia.VENCIMENTOS, EventoCiencia.PRORROGACAO, ProrrogacaoVencimento.id
            ),
        )
        .order_by(ProrrogacaoVencimento.created_at.desc())
        .limit(limite)
    )

    linhas_execucao = (await db.execute(stmt_execucao)).all()
    linhas_prorrogacao = (await db.execute(stmt_prorrogacao)).all()

    itens: list[AlteracaoPendenteItem] = []
    for reg_id, data_evento, nova_data, equipamento, tipo_controle, matricula, trigrama in linhas_execucao:
        itens.append(
            AlteracaoPendenteItem(
                categoria=CategoriaCiencia.VENCIMENTOS,
                evento=EventoCiencia.EXECUCAO,
                registro_id=reg_id.hex,
                aeronave_matricula=matricula,
                titulo=f"{equipamento} ({tipo_controle})",
                detalhe=f"Novo vencimento: {nova_data.isoformat()}",
                responsavel_trigrama=trigrama,
                data_evento=data_evento,
            )
        )
    for reg_id, data_evento, nova_data, equipamento, tipo_controle, matricula, trigrama in linhas_prorrogacao:
        itens.append(
            AlteracaoPendenteItem(
                categoria=CategoriaCiencia.VENCIMENTOS,
                evento=EventoCiencia.PRORROGACAO,
                registro_id=reg_id.hex,
                aeronave_matricula=matricula,
                titulo=f"{equipamento} ({tipo_controle})",
                detalhe=f"Prorrogado até: {nova_data.isoformat()}",
                responsavel_trigrama=trigrama,
                data_evento=data_evento,
            )
        )

    itens.sort(key=lambda item: item.data_evento, reverse=True)
    return itens[:limite]


# --------------------------------------------------------------------- #
# Agregador
# --------------------------------------------------------------------- #

async def listar_pendentes(db: AsyncSession) -> ListaPendentesResponse:
    """RN-ENC-01/02: agrega as 4 categorias, janela de 90 dias, teto de 100
    itens por categoria. As consultas usam a mesma `AsyncSession` — rodam
    sequencialmente (uma `AsyncSession` não é segura para uso concorrente)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=JANELA_DIAS)

    itens_por_categoria = {
        CategoriaCiencia.PANES: await _pendentes_panes(db, cutoff, LIMITE_POR_CATEGORIA),
        CategoriaCiencia.INSPECAO: await _pendentes_inspecao(db, cutoff, LIMITE_POR_CATEGORIA),
        CategoriaCiencia.INVENTARIO: await _pendentes_inventario(db, cutoff, LIMITE_POR_CATEGORIA),
        CategoriaCiencia.VENCIMENTOS: await _pendentes_vencimentos(db, cutoff, LIMITE_POR_CATEGORIA),
    }
    total = sum(len(itens) for itens in itens_por_categoria.values())
    return ListaPendentesResponse(total=total, itens_por_categoria=itens_por_categoria)


# --------------------------------------------------------------------- #
# Ciência — única escrita do módulo
# --------------------------------------------------------------------- #

def _to_ciencia_out(ciencia: EncarregadoCiencia) -> CienciaOut:
    """Pressupõe que `ciencia.usuario` já foi carregado (selectinload) —
    acessá-lo sem isso dispararia lazy-load síncrono sob AsyncSession."""
    return CienciaOut(
        id=ciencia.id,
        categoria=CategoriaCiencia(ciencia.categoria),
        evento=EventoCiencia(ciencia.evento),
        registro_id=ciencia.registro_id,
        usuario_trigrama=ciencia.usuario.trigrama if ciencia.usuario else None,
        dado_em=ciencia.dado_em,
    )


async def _buscar_ciencia_existente(
    db: AsyncSession, categoria: CategoriaCiencia, evento: EventoCiencia, registro_id: str
) -> EncarregadoCiencia | None:
    stmt = (
        select(EncarregadoCiencia)
        .where(
            EncarregadoCiencia.categoria == categoria.value,
            EncarregadoCiencia.evento == evento.value,
            EncarregadoCiencia.registro_id == registro_id,
        )
        .options(selectinload(EncarregadoCiencia.usuario))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def dar_ciencia(
    db: AsyncSession, dados: DarCienciaRequest, usuario_id: uuid.UUID
) -> CienciaOut:
    """RN-ENC-03: idempotente — repetir para o mesmo (categoria, evento,
    registro_id) devolve o registro já existente em vez de 409."""
    existente = await _buscar_ciencia_existente(db, dados.categoria, dados.evento, dados.registro_id)
    if existente:
        return _to_ciencia_out(existente)

    ciencia = EncarregadoCiencia(
        categoria=dados.categoria.value,
        evento=dados.evento.value,
        registro_id=dados.registro_id,
        usuario_id=usuario_id,
    )
    try:
        # SAVEPOINT: cobre a corrida entre duas chamadas concorrentes de
        # ciência para o mesmo item (mesmo padrão de pedidos.service).
        async with db.begin_nested():
            db.add(ciencia)
            await db.flush()
    except IntegrityError:
        existente = await _buscar_ciencia_existente(db, dados.categoria, dados.evento, dados.registro_id)
        if existente:
            return _to_ciencia_out(existente)
        raise

    await db.refresh(ciencia, ["usuario"])
    return _to_ciencia_out(ciencia)


async def desfazer_ciencia(db: AsyncSession, ciencia_id: uuid.UUID) -> None:
    """RN-ENC-04: o item volta a aparecer como pendente."""
    ciencia = await db.get(EncarregadoCiencia, ciencia_id)
    if not ciencia:
        raise domain_exc.EntidadeNaoEncontradaError("Registro de ciência não encontrado.")
    await db.delete(ciencia)
    await db.flush()
