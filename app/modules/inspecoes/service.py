"""
Regras de negocio do modulo isolado de inspecoes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, or_, select
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

    if "nome" in changes and changes["nome"] is not None:
        tipo.nome = changes["nome"].strip()
    if "descricao" in changes:
        tipo.descricao = changes["descricao"]
    if "duracao_dias" in changes and changes["duracao_dias"] is not None:
        tipo.duracao_dias = changes["duracao_dias"]
    if "ativo" in changes and changes["ativo"] is not None:
        tipo.ativo = changes["ativo"]

    await db.flush()
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
    if "titulo" in changes and changes["titulo"] is not None:
        tarefa.titulo = changes["titulo"].strip()
    if "descricao" in changes:
        tarefa.descricao = changes["descricao"]
    if "sistema" in changes:
        tarefa.sistema = changes["sistema"]
    if "ativa" in changes and changes["ativa"] is not None:
        tarefa.ativa = changes["ativa"]

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

    if "obrigatoria" in changes and changes["obrigatoria"] is not None:
        tarefa.obrigatoria = changes["obrigatoria"]

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
    query = select(Inspecao).options(
        selectinload(Inspecao.aeronave),
        selectinload(Inspecao.tipos_aplicados),
        selectinload(Inspecao.tarefas),
    )
    if filtros:
        if filtros.aeronave_id:
            query = query.where(Inspecao.aeronave_id == filtros.aeronave_id)
        if filtros.tipo_inspecao_id:
            query = query.join(Inspecao.tipos_aplicados).where(TipoInspecao.id == filtros.tipo_inspecao_id)
        if filtros.status:
            query = query.where(Inspecao.status == filtros.status.value)
        query = query.offset(filtros.skip).limit(min(filtros.limit, LIMITE_MAXIMO_LISTAGEM))
    else:
        query = query.limit(LIMITE_MAXIMO_LISTAGEM)

    result = await db.execute(query.order_by(Inspecao.data_abertura.desc()))
    return list(result.scalars().all())


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

    res_tipos = await db.execute(
        select(TipoInspecao).where(
            TipoInspecao.id.in_(dados.tipos_inspecao_ids),
            TipoInspecao.ativo.is_(True),
        )
    )
    tipos_por_id = {t.id: t for t in res_tipos.scalars().all()}
    faltantes = [tid for tid in dados.tipos_inspecao_ids if tid not in tipos_por_id]
    if faltantes:
        raise domain_exc.EntidadeNaoEncontradaError(f"Tipo de inspecao {faltantes[0]} nao encontrado ou inativo.")
    # Preserva a ordem de chegada (usada para calcular a duracao maxima abaixo).
    tipos = [tipos_por_id[tid] for tid in dados.tipos_inspecao_ids]

    usuario = await _buscar_usuario(db, aberto_por_id)
    if not usuario:
        raise domain_exc.EntidadeNaoEncontradaError("Usuario de abertura nao encontrado ou inativo.")

    query_ativa = (
        select(Inspecao)
        .join(InspecaoEventoTipo)
        .where(
            Inspecao.aeronave_id == dados.aeronave_id,
            Inspecao.status.in_(STATUS_ATIVOS),
            InspecaoEventoTipo.tipo_inspecao_id.in_(dados.tipos_inspecao_ids),
        )
    )
    ativa = await db.execute(query_ativa)
    if ativa.scalars().first():
        raise domain_exc.ConflitoNegocioError("Ja existe inspecao ativa com um dos tipos selecionados para esta aeronave.")

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
    inspecao.observacoes = dados.observacoes
    await db.flush()
    
    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar inspecao atualizada.")
    return inspecao_carregada


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

    status_novo = dados.status
    executor_id = dados.executado_por_id or usuario_padrao_id

    if status_novo in {StatusTarefaInspecao.CONCLUIDA, StatusTarefaInspecao.NA}:
        if not executor_id:
            raise domain_exc.ConflitoNegocioError("Executor obrigatorio para atualizar tarefa.")
        executor = await _buscar_usuario(db, executor_id)
        if not executor:
            raise domain_exc.EntidadeNaoEncontradaError("Executor nao encontrado ou inativo.")
        tarefa.executado_por_id = executor_id
        tarefa.data_execucao = datetime.now(timezone.utc)
    elif status_novo == StatusTarefaInspecao.PENDENTE:
        tarefa.executado_por_id = None
        tarefa.data_execucao = None

    tarefa.status = status_novo.value
    tarefa.observacao_execucao = dados.observacao_execucao
    
    if dados.pane_id:
        tarefa.pane_id = dados.pane_id

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
    inspecao.concluido_por_id = concluido_por_id
    inspecao.concluido_por_trigrama = usuario.trigrama

    await db.flush()
    if inspecao.aeronave_id:
        await _sincronizar_status_aeronave(db, inspecao.aeronave_id)

    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar inspecao concluida.")
    return inspecao_carregada


async def cancelar_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise domain_exc.EntidadeNaoEncontradaError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)
    inspecao.status = StatusInspecao.CANCELADA.value

    await db.flush()
    if inspecao.aeronave_id:
        await _sincronizar_status_aeronave(db, inspecao.aeronave_id)

    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise domain_exc.ConflitoNegocioError("Falha ao carregar inspecao cancelada.")
    return inspecao_carregada


_STATUS_TAREFA_CONCLUIDA = {StatusTarefaInspecao.CONCLUIDA.value, StatusTarefaInspecao.NA.value}


def calcular_progresso(inspecao: Inspecao) -> tuple[int, int, int]:
    total = len(inspecao.tarefas)
    concluidas = sum(1 for tarefa in inspecao.tarefas if tarefa.status in _STATUS_TAREFA_CONCLUIDA)
    percentual = round((concluidas / total) * 100) if total else 0
    return total, concluidas, percentual
