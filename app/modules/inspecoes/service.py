"""
Regras de negocio do modulo isolado de inspecoes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes import schemas
from app.modules.inspecoes.models import Inspecao, InspecaoEventoTipo, InspecaoTarefa, TarefaTemplate, TipoInspecao, TarefaCatalogo
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusAeronave, StatusInspecao, StatusTarefaInspecao

logger = logging.getLogger(__name__)


STATUS_FINAIS = {
    StatusInspecao.CONCLUIDA.value,
    StatusInspecao.CANCELADA.value,
}
STATUS_ATIVOS = {
    StatusInspecao.ABERTA.value,
    StatusInspecao.EM_ANDAMENTO.value,
}

# Teto de segurança para listagens paginadas (mesmo padrão de equipamentos.service.LIMITE_MAXIMO_LISTAGEM)
LIMITE_MAXIMO_LISTAGEM = 200


def _normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper()


def _garantir_inspecao_editavel(inspecao: Inspecao) -> None:
    if inspecao.status in STATUS_FINAIS:
        raise domain_exc.ConflitoNegocioError("Inspecoes concluidas ou canceladas nao podem ser editadas.")


def _aplicar_mudancas(
    entidade,
    changes: dict,
    campos: set[str] = frozenset(),
    campos_nulaveis: set[str] = frozenset(),
    campos_strip: set[str] = frozenset(),
) -> None:
    """Aplica um dict de mudanças (`model_dump(exclude_unset=True)`) a uma
    entidade, campo a campo — reduz a duplicação do padrão repetido em
    atualizar_tipo_inspecao/atualizar_tarefa_catalogo/atualizar_tarefa_template
    (MELHORIA-13, achados_inspecoes.md).

    Args:
        campos: só aplicados se presentes E não-None (ex.: `ativo`, `titulo`).
        campos_nulaveis: aplicados sempre que presentes, mesmo com valor
            None (ex.: `descricao`, que o cliente pode querer limpar).
        campos_strip: valores de texto que recebem `.strip()` antes de gravar.
    """
    for campo in campos:
        if campo in changes and changes[campo] is not None:
            valor = changes[campo]
            if campo in campos_strip:
                valor = valor.strip()
            setattr(entidade, campo, valor)
    for campo in campos_nulaveis:
        if campo in changes:
            setattr(entidade, campo, changes[campo])


async def _buscar_aeronave(db: AsyncSession, aeronave_id: uuid.UUID) -> Aeronave | None:
    result = await db.execute(select(Aeronave).where(Aeronave.id == aeronave_id))
    return result.scalar_one_or_none()


async def _buscar_usuario(db: AsyncSession, usuario_id: uuid.UUID) -> Usuario | None:
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id, Usuario.ativo.is_(True)))
    return result.scalar_one_or_none()


async def _sincronizar_status_aeronave(db: AsyncSession, aeronave_id: uuid.UUID) -> None:
    """Delega a sincronização de status ao ponto único de verdade da regra
    (panes e inspeções decidem juntos o status da aeronave). Import local
    para evitar ciclo de import em tempo de carregamento do módulo — o
    mesmo padrão usado por `panes.service.sincronizar_status_aeronave`.
    """
    from app.modules.panes.service import sincronizar_status_aeronave
    await sincronizar_status_aeronave(db, aeronave_id)


async def criar_tipo_inspecao(db: AsyncSession, dados: schemas.TipoInspecaoCreate) -> TipoInspecao:
    codigo = _normalizar_codigo(dados.codigo)
    existente = await db.execute(select(TipoInspecao).where(TipoInspecao.codigo == codigo))
    if existente.scalar_one_or_none():
        raise domain_exc.ConflitoNegocioError(f"Tipo de inspecao '{codigo}' ja cadastrado.")

    tipo = TipoInspecao(
        codigo=codigo,
        nome=dados.nome.strip(),
        descricao=dados.descricao,
        duracao_dias=dados.duracao_dias,
    )
    try:
        # SAVEPOINT: em caso de criação concorrente com o mesmo código, desfaz
        # apenas este insert e mantém a transação da requisição utilizável.
        async with db.begin_nested():
            db.add(tipo)
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao criar tipo de inspecao %s: %s", codigo, exc.orig)
        raise domain_exc.ConflitoNegocioError(f"Tipo de inspecao '{codigo}' ja cadastrado.") from exc
    await db.refresh(tipo)
    return tipo


async def listar_tipos_inspecao(db: AsyncSession, incluir_inativos: bool = False) -> list[TipoInspecao]:
    query = select(TipoInspecao).order_by(TipoInspecao.codigo)
    if not incluir_inativos:
        query = query.where(TipoInspecao.ativo.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_tipo_inspecao(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> TipoInspecao | None:
    query = select(TipoInspecao).where(TipoInspecao.id == tipo_id)
    if not incluir_inativos:
        query = query.where(TipoInspecao.ativo.is_(True))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def atualizar_tipo_inspecao(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    dados: schemas.TipoInspecaoUpdate,
) -> TipoInspecao:
    tipo = await buscar_tipo_inspecao(db, tipo_id, incluir_inativos=True)
    if not tipo:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de inspecao nao encontrado.")

    changes = dados.model_dump(exclude_unset=True)
    if "codigo" in changes and changes["codigo"] is not None:
        codigo = _normalizar_codigo(changes["codigo"])
        if codigo != tipo.codigo:
            result = await db.execute(select(TipoInspecao).where(TipoInspecao.codigo == codigo))
            if result.scalar_one_or_none():
                raise domain_exc.ConflitoNegocioError(f"Tipo de inspecao '{codigo}' ja cadastrado.")
        tipo.codigo = codigo

    _aplicar_mudancas(
        tipo, changes,
        campos={"nome", "duracao_dias", "ativo"},
        campos_nulaveis={"descricao"},
        campos_strip={"nome"},
    )

    try:
        # SAVEPOINT: mesmo padrão de criar_tipo_inspecao — em caso de corrida
        # com outra requisição trocando o código para o mesmo valor, desfaz
        # apenas este flush em vez de vazar um IntegrityError cru (500).
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        logger.warning("Conflito de UNIQUE ao atualizar tipo de inspecao %s: %s", tipo_id, exc.orig)
        raise domain_exc.ConflitoNegocioError(f"Tipo de inspecao '{tipo.codigo}' ja cadastrado.") from exc
    await db.refresh(tipo)
    return tipo


async def desativar_tipo_inspecao(db: AsyncSession, tipo_id: uuid.UUID) -> None:
    tipo = await buscar_tipo_inspecao(db, tipo_id, incluir_inativos=True)
    if not tipo:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de inspecao nao encontrado.")
    tipo.ativo = False
    await db.flush()


async def criar_tarefa_catalogo(db: AsyncSession, dados: schemas.TarefaCatalogoCreate) -> TarefaCatalogo:
    tarefa = TarefaCatalogo(
        titulo=dados.titulo.strip(),
        descricao=dados.descricao,
        sistema=dados.sistema,
        ativa=dados.ativa,
    )
    db.add(tarefa)
    await db.flush()
    await db.refresh(tarefa)
    return tarefa


async def listar_tarefas_catalogo(db: AsyncSession, incluir_inativos: bool = False) -> list[TarefaCatalogo]:
    query = select(TarefaCatalogo).order_by(TarefaCatalogo.titulo)
    if not incluir_inativos:
        query = query.where(TarefaCatalogo.ativa.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_tarefa_catalogo(db: AsyncSession, tarefa_id: uuid.UUID, incluir_inativos: bool = False) -> TarefaCatalogo | None:
    query = select(TarefaCatalogo).where(TarefaCatalogo.id == tarefa_id)
    if not incluir_inativos:
        query = query.where(TarefaCatalogo.ativa.is_(True))
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def atualizar_tarefa_catalogo(db: AsyncSession, tarefa_id: uuid.UUID, dados: schemas.TarefaCatalogoUpdate) -> TarefaCatalogo:
    tarefa = await buscar_tarefa_catalogo(db, tarefa_id, incluir_inativos=True)
    if not tarefa:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa do catalogo nao encontrada.")

    changes = dados.model_dump(exclude_unset=True)
    _aplicar_mudancas(
        tarefa, changes,
        campos={"titulo", "ativa"},
        campos_nulaveis={"descricao", "sistema"},
        campos_strip={"titulo"},
    )

    await db.flush()
    await db.refresh(tarefa)
    return tarefa


async def desativar_tarefa_catalogo(db: AsyncSession, tarefa_id: uuid.UUID) -> None:
    tarefa = await buscar_tarefa_catalogo(db, tarefa_id, incluir_inativos=True)
    if not tarefa:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa do catalogo nao encontrada.")
    tarefa.ativa = False
    await db.flush()


async def listar_tarefas_template(db: AsyncSession, tipo_id: uuid.UUID) -> list[TarefaTemplate]:
    result = await db.execute(
        select(TarefaTemplate)
        .options(selectinload(TarefaTemplate.tarefa_catalogo))
        .where(TarefaTemplate.tipo_inspecao_id == tipo_id)
        .order_by(TarefaTemplate.ordem)
    )
    return list(result.scalars().all())


async def criar_tarefa_template(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    dados: schemas.TarefaTemplateCreate,
) -> TarefaTemplate:
    tipo = await buscar_tipo_inspecao(db, tipo_id)
    if not tipo:
        raise domain_exc.EntidadeNaoEncontradaError("Tipo de inspecao nao encontrado ou inativo.")

    catalogo = await buscar_tarefa_catalogo(db, dados.tarefa_catalogo_id)
    if not catalogo:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa do catalogo nao encontrada ou inativa.")

    existente = await db.execute(
        select(TarefaTemplate).where(
            TarefaTemplate.tipo_inspecao_id == tipo_id,
            TarefaTemplate.ordem == dados.ordem,
        )
    )
    if existente.scalar_one_or_none():
        raise domain_exc.ConflitoNegocioError("Ja existe uma tarefa template com esta ordem para o tipo selecionado.")

    existente_tarefa = await db.execute(
        select(TarefaTemplate).where(
            TarefaTemplate.tipo_inspecao_id == tipo_id,
            TarefaTemplate.tarefa_catalogo_id == dados.tarefa_catalogo_id,
        )
    )
    if existente_tarefa.scalar_one_or_none():
        raise domain_exc.ConflitoNegocioError("Esta tarefa ja esta vinculada a este tipo de inspecao.")

    tarefa = TarefaTemplate(
        tipo_inspecao_id=tipo_id,
        tarefa_catalogo_id=dados.tarefa_catalogo_id,
        ordem=dados.ordem,
        obrigatoria=dados.obrigatoria,
    )
    try:
        async with db.begin_nested():
            db.add(tarefa)
            await db.flush()
    except IntegrityError as exc:
        logger.warning(
            "Conflito de UNIQUE ao criar tarefa template (tipo=%s, ordem=%s): %s",
            tipo_id, dados.ordem, exc.orig,
        )
        raise domain_exc.ConflitoNegocioError(
            "Ja existe uma tarefa template com esta ordem ou esta tarefa ja esta vinculada a este tipo."
        ) from exc
    await db.refresh(tarefa, ["tarefa_catalogo"])
    return tarefa


async def atualizar_tarefa_template(
    db: AsyncSession,
    tarefa_id: uuid.UUID,
    dados: schemas.TarefaTemplateUpdate,
) -> TarefaTemplate:
    result = await db.execute(select(TarefaTemplate).options(selectinload(TarefaTemplate.tarefa_catalogo)).where(TarefaTemplate.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa template nao encontrada.")

    changes = dados.model_dump(exclude_unset=True)
    if "ordem" in changes and changes["ordem"] is not None and changes["ordem"] != tarefa.ordem:
        existente = await db.execute(
            select(TarefaTemplate).where(
                TarefaTemplate.tipo_inspecao_id == tarefa.tipo_inspecao_id,
                TarefaTemplate.ordem == changes["ordem"],
                TarefaTemplate.id != tarefa.id,
            )
        )
        if existente.scalar_one_or_none():
            raise domain_exc.ConflitoNegocioError("Ja existe uma tarefa template com esta ordem para o tipo selecionado.")
        tarefa.ordem = changes["ordem"]

    _aplicar_mudancas(tarefa, changes, campos={"obrigatoria"})

    await db.flush()
    return tarefa


async def remover_tarefa_template(db: AsyncSession, tarefa_id: uuid.UUID) -> None:
    result = await db.execute(select(TarefaTemplate).where(TarefaTemplate.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa template nao encontrada.")
    await db.delete(tarefa)
    await db.flush()


async def reordenar_tarefas_template(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    dados: schemas.ReordenarTarefas,
) -> list[TarefaTemplate]:
    tarefas = await listar_tarefas_template(db, tipo_id)
    tarefas_por_id = {tarefa.id: tarefa for tarefa in tarefas}
    novas_ordens = {item.id: item.ordem for item in dados.tarefas}

    if set(novas_ordens) != set(tarefas_por_id):
        raise domain_exc.ConflitoNegocioError("A reordenacao deve conter exatamente todas as tarefas do tipo.")
    if len(set(novas_ordens.values())) != len(novas_ordens):
        raise domain_exc.ConflitoNegocioError("A nova ordem nao pode conter posicoes duplicadas.")

    # Evita colisao temporaria com a constraint unica durante a troca de ordens.
    for index, tarefa in enumerate(tarefas, start=1):
        tarefa.ordem = -index
    await db.flush()

    for tarefa_id, nova_ordem in novas_ordens.items():
        tarefas_por_id[tarefa_id].ordem = nova_ordem
    await db.flush()
    return await listar_tarefas_template(db, tipo_id)


async def listar_inspecoes(
    db: AsyncSession,
    filtros: schemas.FiltroInspecao | None = None,
) -> list[Inspecao]:
    # RISCO-07: sem `Inspecao.tarefas` no eager-load — o único consumidor
    # (calcular_progresso, via router) só precisa de duas contagens por
    # inspeção, não das linhas completas de tarefa (título, descrição,
    # observação, executor). Use `contar_tarefas_por_inspecao` para isso.
    query = select(Inspecao).options(
        selectinload(Inspecao.aeronave),
        selectinload(Inspecao.tipos_aplicados),
    )
    if filtros:
        if filtros.aeronave_id:
            query = query.where(Inspecao.aeronave_id == filtros.aeronave_id)
        if filtros.tipo_inspecao_id:
            # MELHORIA-11: .distinct() evita linhas repetidas se a inspeção
            # tiver mais de um vínculo para o mesmo tipo (cenário do BUG-04).
            query = query.join(Inspecao.tipos_aplicados).where(TipoInspecao.id == filtros.tipo_inspecao_id).distinct()
        if filtros.status:
            query = query.where(Inspecao.status == filtros.status.value)
        query = query.offset(filtros.skip).limit(min(filtros.limit, LIMITE_MAXIMO_LISTAGEM))
    else:
        query = query.limit(LIMITE_MAXIMO_LISTAGEM)

    # MELHORIA-11: desempate por `id` — sem isso, duas inspeções abertas no
    # mesmo instante podem ter ordem instável entre páginas.
    result = await db.execute(query.order_by(Inspecao.data_abertura.desc(), Inspecao.id))
    return list(result.scalars().all())


async def contar_tarefas_por_inspecao(
    db: AsyncSession, inspecao_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Mapa inspecao_id -> (total_tarefas, tarefas_concluidas), via agregação
    no banco — usado por `listar_inspecoes`/`exportar_inspecoes` em vez de
    carregar as linhas completas de `InspecaoTarefa` só para contar (RISCO-07).
    """
    if not inspecao_ids:
        return {}
    status_concluida = (
        StatusTarefaInspecao.CONCLUIDA.value,
        StatusTarefaInspecao.NA.value,
    )
    result = await db.execute(
        select(
            InspecaoTarefa.inspecao_id,
            func.count().label("total"),
            func.sum(
                case((InspecaoTarefa.status.in_(status_concluida), 1), else_=0)
            ).label("concluidas"),
        )
        .where(InspecaoTarefa.inspecao_id.in_(inspecao_ids))
        .group_by(InspecaoTarefa.inspecao_id)
    )
    return {row.inspecao_id: (row.total, int(row.concluidas or 0)) for row in result.all()}


async def buscar_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao | None:
    result = await db.execute(
        select(Inspecao)
        .where(Inspecao.id == inspecao_id)
        .options(
            selectinload(Inspecao.aeronave),
            selectinload(Inspecao.tipos_aplicados),
            selectinload(Inspecao.aberto_por),
            selectinload(Inspecao.concluido_por),
            selectinload(Inspecao.tarefas).selectinload(InspecaoTarefa.executado_por),
        )
    )
    return result.scalar_one_or_none()


async def abrir_inspecao(
    db: AsyncSession,
    dados: schemas.InspecaoCreate,
    aberto_por_id: uuid.UUID,
) -> Inspecao:
    aeronave = await _buscar_aeronave(db, dados.aeronave_id)
    if not aeronave:
        raise domain_exc.EntidadeNaoEncontradaError("Aeronave nao encontrada.")
    if aeronave.status == StatusAeronave.INATIVA.value:
        raise domain_exc.ConflitoNegocioError("Aeronave inativa. Reative a aeronave antes de registrar uma inspecao.")

    # BUG-04: deduplica preservando a ordem de chegada — sem isso, um payload
    # com IDs repetidos ([A, A, B]) sobrevivia à checagem de "faltantes" (que
    # já deduplicava via dict) mas reconstruía a lista a partir do payload
    # original, inserindo duas linhas de vínculo (InspecaoEventoTipo) para o
    # mesmo par (inspecao, tipo).
    tipos_ids = list(dict.fromkeys(dados.tipos_inspecao_ids))

    res_tipos = await db.execute(
        select(TipoInspecao).where(
            TipoInspecao.id.in_(tipos_ids),
            TipoInspecao.ativo.is_(True),
        )
    )
    tipos_por_id = {t.id: t for t in res_tipos.scalars().all()}
    faltantes = [tid for tid in tipos_ids if tid not in tipos_por_id]
    if faltantes:
        raise domain_exc.EntidadeNaoEncontradaError(f"Tipo de inspecao {faltantes[0]} nao encontrado ou inativo.")
    # Preserva a ordem de chegada (usada para calcular a duracao maxima abaixo).
    tipos = [tipos_por_id[tid] for tid in tipos_ids]

    usuario = await _buscar_usuario(db, aberto_por_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuario de abertura nao encontrado ou inativo.")

    query_ativa = (
        select(Inspecao)
        .join(InspecaoEventoTipo)
        .where(
            Inspecao.aeronave_id == dados.aeronave_id,
            Inspecao.status.in_(STATUS_ATIVOS),
            InspecaoEventoTipo.tipo_inspecao_id.in_(tipos_ids),
        )
    )
    ativa = await db.execute(query_ativa)
    if ativa.scalars().first():
        raise domain_exc.ConflitoNegocioError("Ja existe inspecao ativa com um dos tipos selecionados para esta aeronave.")

    # MELHORIA-10: valida a disponibilidade de templates ANTES de qualquer
    # db.add/mutação de estado (aeronave.status) — antes, essa checagem só
    # acontecia depois da Inspecao já criada e da aeronave já movida para
    # INSPECAO, dependendo do rollback automático de get_db() para não deixar
    # a aeronave presa nesse status com uma inspeção órfã.
    res_templates = await db.execute(
        select(TarefaTemplate)
        .options(selectinload(TarefaTemplate.tarefa_catalogo))
        .where(TarefaTemplate.tipo_inspecao_id.in_([t.id for t in tipos]))
        .order_by(TarefaTemplate.ordem)
    )
    templates_por_tipo: dict[uuid.UUID, list[TarefaTemplate]] = {}
    for tmpl in res_templates.scalars().all():
        templates_por_tipo.setdefault(tmpl.tipo_inspecao_id, []).append(tmpl)
    # Preserva a mesma ordem de iteração original: por tipo (na ordem informada
    # pelo cliente), depois por `ordem` dentro de cada tipo.
    templates = [tmpl for tipo in tipos for tmpl in templates_por_tipo.get(tipo.id, [])]

    if not templates:
        raise domain_exc.ConflitoNegocioError("Os tipos de inspecao nao possuem tarefas template cadastradas.")

    inspecao = Inspecao(
        aeronave_id=dados.aeronave_id,
        status=StatusInspecao.ABERTA.value,
        data_inicio=dados.data_inicio or datetime.now(timezone.utc),
        observacoes=dados.observacoes,
        aberto_por_id=aberto_por_id,
        aberto_por_trigrama=usuario.trigrama,
    )

    # Calculo da DPE (Data Prevista de Encerramento)
    if dados.data_fim_prevista:
        inspecao.data_fim_prevista = dados.data_fim_prevista
    else:
        duracao_maxima = max((t.duracao_dias for t in tipos), default=0)
        if duracao_maxima > 0:
            inspecao.data_fim_prevista = inspecao.data_inicio + timedelta(days=duracao_maxima)
    db.add(inspecao)
    await db.flush()

    for tipo in tipos:
        db.add(InspecaoEventoTipo(inspecao_id=inspecao.id, tipo_inspecao_id=tipo.id))

    aeronave.status = StatusAeronave.INSPECAO.value

    # DÚVIDA-08 (achados_inspecoes.md), respondida pelo desenvolvedor: a
    # deduplicação é por TÍTULO (case-insensitive), não por
    # `tarefa_catalogo_id` — intencional e coberta por
    # test_rn01_abrir_inspecao_com_multiplos_tipos_e_deduplicar_tarefas.
    # Combinar dois tipos de inspeção que tenham, por coincidência, uma
    # tarefa de catálogo com o mesmo título produz UMA tarefa na inspeção
    # (obrigatória se qualquer um dos templates de origem for obrigatório),
    # em vez de duas entradas repetidas — o `tarefa_catalogo_id` gravado é o
    # do primeiro template visto na ordem de iteração (por tipo, depois por
    # `ordem`), não uma escolha aleatória.
    vistos = {}  # chave -> {'template': t, 'obrigatoria': bool}
    for t in templates:
        chave = t.tarefa_catalogo.titulo.strip().lower()
        if chave not in vistos:
            vistos[chave] = {
                "template": t,
                "obrigatoria": t.obrigatoria
            }
        else:
            vistos[chave]["obrigatoria"] = vistos[chave]["obrigatoria"] or t.obrigatoria

    for i, item in enumerate(vistos.values(), start=1):
        template = item["template"]
        db.add(
            InspecaoTarefa(
                inspecao_id=inspecao.id,
                tarefa_catalogo_id=template.tarefa_catalogo_id,
                ordem=i,
                titulo=template.tarefa_catalogo.titulo,
                descricao=template.tarefa_catalogo.descricao,
                sistema=template.tarefa_catalogo.sistema,
                obrigatoria=item["obrigatoria"],
                status=StatusTarefaInspecao.PENDENTE.value,
            )
        )

    await db.flush()
    inspecao_carregada = await buscar_inspecao(db, inspecao.id)
    if not inspecao_carregada:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar inspecao criada.")
    return inspecao_carregada


async def atualizar_inspecao(
    db: AsyncSession,
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoUpdate,
) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)

    # BUG-03: exclude_unset — omitir `observacoes` no payload não deve mais
    # apagá-las (antes, `inspecao.observacoes = dados.observacoes` zerava o
    # campo sempre que o cliente não reenviava o texto completo de volta).
    changes = dados.model_dump(exclude_unset=True)
    if "observacoes" in changes:
        inspecao.observacoes = changes["observacoes"]

    await db.flush()
    # MELHORIA-12: esta função não cria/altera nenhuma relação (aeronave,
    # tipos_aplicados, aberto_por, concluido_por, tarefas) — `inspecao` já
    # está carregado e atualizado na mesma sessão, refazer os 5 selectinload
    # de buscar_inspecao() aqui seria uma consulta redundante. `updated_at`
    # (onupdate=func.now()) fica expirado após o flush — refresh pontual
    # evita MissingGreenlet num lazy-load implícito ao serializar a resposta.
    await db.refresh(inspecao, attribute_names=["updated_at"])
    return inspecao


async def adicionar_tarefa_avulsa(
    db: AsyncSession,
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoTarefaCreate,
) -> InspecaoTarefa:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)

    ordem = dados.ordem
    if ordem is None:
        maior_ordem = await db.execute(
            select(func.max(InspecaoTarefa.ordem)).where(InspecaoTarefa.inspecao_id == inspecao_id)
        )
        ordem = (maior_ordem.scalar_one_or_none() or 0) + 1

    tarefa = InspecaoTarefa(
        inspecao_id=inspecao_id,
        ordem=ordem,
        titulo=dados.titulo.strip(),
        descricao=dados.descricao,
        sistema=dados.sistema,
        obrigatoria=dados.obrigatoria,
        status=StatusTarefaInspecao.PENDENTE.value,
    )
    db.add(tarefa)
    await db.flush()
    await db.refresh(tarefa)
    return tarefa


async def atualizar_tarefa_inspecao(
    db: AsyncSession,
    tarefa_id: uuid.UUID,
    dados: schemas.InspecaoTarefaUpdate,
    usuario_padrao_id: uuid.UUID | None = None,
) -> InspecaoTarefa:
    result = await db.execute(
        select(InspecaoTarefa)
        .where(InspecaoTarefa.id == tarefa_id)
        .options(selectinload(InspecaoTarefa.inspecao), selectinload(InspecaoTarefa.executado_por))
    )
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise domain_exc.EntidadeNaoEncontradaError("Tarefa de inspecao nao encontrada.")

    _garantir_inspecao_editavel(tarefa.inspecao)

    changes = dados.model_dump(exclude_unset=True)
    status_novo = dados.status
    executor_id = dados.executado_por_id or usuario_padrao_id
    # BUG-02 (achados_inspecoes.md): só carimbar executor/data na TRANSIÇÃO de
    # status — sem isso, reeditar uma tarefa já concluída (ex.: só para trocar
    # a observação, reenviando o mesmo status) apagava o registro original de
    # quem executou e quando, mesmo sem nenhuma execução nova ter ocorrido.
    transicionou = tarefa.status != status_novo.value

    if status_novo in {StatusTarefaInspecao.CONCLUIDA, StatusTarefaInspecao.NA}:
        if not executor_id:
            raise domain_exc.ConflitoNegocioError("Executor obrigatorio para atualizar tarefa.")
        executor = await _buscar_usuario(db, executor_id)
        if not executor:
            raise domain_exc.EntidadeNaoEncontradaError("Executor nao encontrado ou inativo.")
        if transicionou or dados.executado_por_id is not None:
            tarefa.executado_por_id = executor_id
        if transicionou:
            tarefa.data_execucao = datetime.now(timezone.utc)
    elif status_novo == StatusTarefaInspecao.PENDENTE:
        tarefa.executado_por_id = None
        tarefa.data_execucao = None

    tarefa.status = status_novo.value

    # BUG-03: só grava campos opcionais realmente enviados pelo cliente
    # (exclude_unset) — antes, omitir `observacao_execucao` apagava a
    # observação já registrada em qualquer PATCH que só mudasse o status.
    if "observacao_execucao" in changes:
        tarefa.observacao_execucao = changes["observacao_execucao"]

    if "pane_id" in changes:
        novo_pane_id = changes["pane_id"]
        if novo_pane_id is not None:
            # BUG-05: valida a existência da Pane antes de gravar — sem isso,
            # um pane_id inexistente (mas UUID válido) só falhava no flush()
            # com IntegrityError cru, virando 500 em vez de 404.
            from app.modules.panes.models import Pane
            existe = await db.execute(select(Pane.id).where(Pane.id == novo_pane_id))
            if existe.first() is None:
                raise domain_exc.EntidadeNaoEncontradaError("Pane nao encontrada.")
        # BUG-03: `if dados.pane_id:` (truthy) tornava impossível desvincular
        # uma pane já associada — enviar `pane_id: null` agora limpa o vínculo.
        tarefa.pane_id = novo_pane_id

    if tarefa.inspecao.status == StatusInspecao.ABERTA.value and status_novo != StatusTarefaInspecao.PENDENTE:
        tarefa.inspecao.status = StatusInspecao.EM_ANDAMENTO.value

    await db.flush()
    tarefa_carregada = await _buscar_tarefa_com_relacoes(db, tarefa.id)
    if not tarefa_carregada:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar tarefa atualizada.")
    return tarefa_carregada


async def _buscar_tarefa_com_relacoes(db: AsyncSession, tarefa_id: uuid.UUID) -> InspecaoTarefa | None:
    result = await db.execute(
        select(InspecaoTarefa)
        .where(InspecaoTarefa.id == tarefa_id)
        .options(selectinload(InspecaoTarefa.executado_por))
    )
    return result.scalar_one_or_none()


async def concluir_inspecao(
    db: AsyncSession,
    inspecao_id: uuid.UUID,
    concluido_por_id: uuid.UUID,
) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)

    usuario = await _buscar_usuario(db, concluido_por_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuario de conclusao nao encontrado ou inativo.")

    pendentes = [
        tarefa
        for tarefa in inspecao.tarefas
        if tarefa.obrigatoria and tarefa.status == StatusTarefaInspecao.PENDENTE.value
    ]
    if pendentes:
        raise domain_exc.ConflitoNegocioError("Inspecao possui tarefas obrigatorias pendentes.")

    inspecao.status = StatusInspecao.CONCLUIDA.value
    inspecao.data_conclusao = datetime.now(timezone.utc)
    # Atribui o objeto (não só o FK cru): mantém `inspecao.concluido_por` já
    # populado em memória, sem precisar de um refetch só para essa relação —
    # `usuario` já foi carregado acima.
    inspecao.concluido_por = usuario
    inspecao.concluido_por_trigrama = usuario.trigrama

    await db.flush()
    if inspecao.aeronave_id:
        await _sincronizar_status_aeronave(db, inspecao.aeronave_id)

    # MELHORIA-12: nenhuma das relações eager-loaded por buscar_inspecao()
    # (aeronave, tipos_aplicados, aberto_por, tarefas) muda aqui; `aeronave`
    # é o mesmo objeto do identity map, já refletindo o status sincronizado
    # acima; `concluido_por` foi atribuído diretamente. Refazer os 5
    # selectinload seria uma consulta redundante. `updated_at` é refrescado
    # à parte (onupdate=func.now() fica expirado após o flush).
    await db.refresh(inspecao, attribute_names=["updated_at"])
    return inspecao


async def cancelar_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)
    inspecao.status = StatusInspecao.CANCELADA.value

    await db.flush()
    if inspecao.aeronave_id:
        await _sincronizar_status_aeronave(db, inspecao.aeronave_id)

    # MELHORIA-12: nenhuma relação eager-loaded muda aqui — ver nota em
    # concluir_inspecao. `updated_at` refrescado pelo mesmo motivo.
    await db.refresh(inspecao, attribute_names=["updated_at"])
    return inspecao


_STATUS_TAREFA_CONCLUIDA = {StatusTarefaInspecao.CONCLUIDA.value, StatusTarefaInspecao.NA.value}


def calcular_progresso(inspecao: Inspecao) -> tuple[int, int, int]:
    total = len(inspecao.tarefas)
    concluidas = sum(1 for tarefa in inspecao.tarefas if tarefa.status in _STATUS_TAREFA_CONCLUIDA)
    percentual = round((concluidas / total) * 100) if total else 0
    return total, concluidas, percentual
