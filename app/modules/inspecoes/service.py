"""
Regras de negocio do modulo isolado de inspecoes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes import schemas
from app.modules.inspecoes.models import Inspecao, InspecaoEventoTipo, InspecaoTarefa, TarefaTemplate, TipoInspecao, TarefaCatalogo
from app.shared.core.enums import StatusAeronave, StatusInspecao, StatusTarefaInspecao


STATUS_FINAIS = {
    StatusInspecao.CONCLUIDA.value,
    StatusInspecao.CANCELADA.value,
}
STATUS_ATIVOS = {
    StatusInspecao.ABERTA.value,
    StatusInspecao.EM_ANDAMENTO.value,
}


def _normalizar_codigo(codigo: str) -> str:
    return codigo.strip().upper()


def _garantir_inspecao_editavel(inspecao: Inspecao) -> None:
    if inspecao.status in STATUS_FINAIS:
        raise ValueError("Inspecoes concluidas ou canceladas nao podem ser editadas.")


async def _buscar_aeronave(db: AsyncSession, aeronave_id: uuid.UUID) -> Aeronave | None:
    result = await db.execute(select(Aeronave).where(Aeronave.id == aeronave_id))
    return result.scalar_one_or_none()


async def _buscar_usuario(db: AsyncSession, usuario_id: uuid.UUID) -> Usuario | None:
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id, Usuario.ativo == True))  # noqa: E712
    return result.scalar_one_or_none()


async def criar_tipo_inspecao(db: AsyncSession, dados: schemas.TipoInspecaoCreate) -> TipoInspecao:
    codigo = _normalizar_codigo(dados.codigo)
    existente = await db.execute(select(TipoInspecao).where(TipoInspecao.codigo == codigo))
    if existente.scalar_one_or_none():
        raise ValueError(f"Tipo de inspecao '{codigo}' ja cadastrado.")

    tipo = TipoInspecao(
        codigo=codigo,
        nome=dados.nome.strip(),
        descricao=dados.descricao,
    )
    db.add(tipo)
    await db.flush()
    await db.refresh(tipo)
    return tipo


async def listar_tipos_inspecao(db: AsyncSession, incluir_inativos: bool = False) -> list[TipoInspecao]:
    query = select(TipoInspecao).order_by(TipoInspecao.codigo)
    if not incluir_inativos:
        query = query.where(TipoInspecao.ativo == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_tipo_inspecao(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    incluir_inativos: bool = False,
) -> TipoInspecao | None:
    query = select(TipoInspecao).where(TipoInspecao.id == tipo_id)
    if not incluir_inativos:
        query = query.where(TipoInspecao.ativo == True)  # noqa: E712
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def atualizar_tipo_inspecao(
    db: AsyncSession,
    tipo_id: uuid.UUID,
    dados: schemas.TipoInspecaoUpdate,
) -> TipoInspecao:
    tipo = await buscar_tipo_inspecao(db, tipo_id, incluir_inativos=True)
    if not tipo:
        raise ValueError("Tipo de inspecao nao encontrado.")

    changes = dados.model_dump(exclude_unset=True)
    if "codigo" in changes and changes["codigo"] is not None:
        codigo = _normalizar_codigo(changes["codigo"])
        if codigo != tipo.codigo:
            result = await db.execute(select(TipoInspecao).where(TipoInspecao.codigo == codigo))
            if result.scalar_one_or_none():
                raise ValueError(f"Tipo de inspecao '{codigo}' ja cadastrado.")
        tipo.codigo = codigo

    if "nome" in changes and changes["nome"] is not None:
        tipo.nome = changes["nome"].strip()
    if "descricao" in changes:
        tipo.descricao = changes["descricao"]
    if "ativo" in changes and changes["ativo"] is not None:
        tipo.ativo = changes["ativo"]

    await db.flush()
    await db.refresh(tipo)
    return tipo


async def desativar_tipo_inspecao(db: AsyncSession, tipo_id: uuid.UUID) -> None:
    tipo = await buscar_tipo_inspecao(db, tipo_id, incluir_inativos=True)
    if not tipo:
        raise ValueError("Tipo de inspecao nao encontrado.")
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
        query = query.where(TarefaCatalogo.ativa == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_tarefa_catalogo(db: AsyncSession, tarefa_id: uuid.UUID, incluir_inativos: bool = False) -> TarefaCatalogo | None:
    query = select(TarefaCatalogo).where(TarefaCatalogo.id == tarefa_id)
    if not incluir_inativos:
        query = query.where(TarefaCatalogo.ativa == True)  # noqa: E712
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def atualizar_tarefa_catalogo(db: AsyncSession, tarefa_id: uuid.UUID, dados: schemas.TarefaCatalogoUpdate) -> TarefaCatalogo:
    tarefa = await buscar_tarefa_catalogo(db, tarefa_id, incluir_inativos=True)
    if not tarefa:
        raise ValueError("Tarefa do catalogo nao encontrada.")

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
        raise ValueError("Tarefa do catalogo nao encontrada.")
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
        raise ValueError("Tipo de inspecao nao encontrado ou inativo.")

    catalogo = await buscar_tarefa_catalogo(db, dados.tarefa_catalogo_id)
    if not catalogo:
        raise ValueError("Tarefa do catalogo nao encontrada ou inativa.")

    existente = await db.execute(
        select(TarefaTemplate).where(
            TarefaTemplate.tipo_inspecao_id == tipo_id,
            TarefaTemplate.ordem == dados.ordem,
        )
    )
    if existente.scalar_one_or_none():
        raise ValueError("Ja existe uma tarefa template com esta ordem para o tipo selecionado.")

    existente_tarefa = await db.execute(
        select(TarefaTemplate).where(
            TarefaTemplate.tipo_inspecao_id == tipo_id,
            TarefaTemplate.tarefa_catalogo_id == dados.tarefa_catalogo_id,
        )
    )
    if existente_tarefa.scalar_one_or_none():
        raise ValueError("Esta tarefa ja esta vinculada a este tipo de inspecao.")

    tarefa = TarefaTemplate(
        tipo_inspecao_id=tipo_id,
        tarefa_catalogo_id=dados.tarefa_catalogo_id,
        ordem=dados.ordem,
        obrigatoria=dados.obrigatoria,
    )
    db.add(tarefa)
    await db.flush()
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
        raise ValueError("Tarefa template nao encontrada.")

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
            raise ValueError("Ja existe uma tarefa template com esta ordem para o tipo selecionado.")
        tarefa.ordem = changes["ordem"]

    if "obrigatoria" in changes and changes["obrigatoria"] is not None:
        tarefa.obrigatoria = changes["obrigatoria"]

    await db.flush()
    return tarefa


async def remover_tarefa_template(db: AsyncSession, tarefa_id: uuid.UUID) -> None:
    result = await db.execute(select(TarefaTemplate).where(TarefaTemplate.id == tarefa_id))
    tarefa = result.scalar_one_or_none()
    if not tarefa:
        raise ValueError("Tarefa template nao encontrada.")
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
        raise ValueError("A reordenacao deve conter exatamente todas as tarefas do tipo.")
    if len(set(novas_ordens.values())) != len(novas_ordens):
        raise ValueError("A nova ordem nao pode conter posicoes duplicadas.")

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
        query = query.offset(filtros.skip).limit(filtros.limit)
    else:
        query = query.limit(100)

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
        raise ValueError("Aeronave nao encontrada.")

    tipos = []
    for tipo_id in dados.tipos_inspecao_ids:
        tipo = await buscar_tipo_inspecao(db, tipo_id)
        if not tipo:
            raise ValueError(f"Tipo de inspecao {tipo_id} nao encontrado ou inativo.")
        tipos.append(tipo)

    usuario = await _buscar_usuario(db, aberto_por_id)
    if not usuario:
        raise ValueError("Usuario de abertura nao encontrado ou inativo.")

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
        raise ValueError("Ja existe inspecao ativa com um dos tipos selecionados para esta aeronave.")

    inspecao = Inspecao(
        aeronave_id=dados.aeronave_id,
        status=StatusInspecao.ABERTA.value,
        observacoes=dados.observacoes,
        aberto_por_id=aberto_por_id,
    )
    db.add(inspecao)
    await db.flush()

    for tipo in tipos:
        db.add(InspecaoEventoTipo(inspecao_id=inspecao.id, tipo_inspecao_id=tipo.id))

    aeronave.status = StatusAeronave.INSPECAO.value

    templates = []
    for tipo in tipos:
        templates.extend(await listar_tarefas_template(db, tipo.id))

    if not templates:
        raise ValueError("Os tipos de inspecao nao possuem tarefas template cadastradas.")

    vistos = set()
    templates_deduplicados = []
    for t in templates:
        chave = t.tarefa_catalogo.titulo.strip().lower()
        if chave not in vistos:
            vistos.add(chave)
            templates_deduplicados.append(t)

    for i, template in enumerate(templates_deduplicados, start=1):
        db.add(
            InspecaoTarefa(
                inspecao_id=inspecao.id,
                tarefa_catalogo_id=template.tarefa_catalogo_id,
                ordem=i,
                titulo=template.tarefa_catalogo.titulo,
                descricao=template.tarefa_catalogo.descricao,
                sistema=template.tarefa_catalogo.sistema,
                obrigatoria=template.obrigatoria,
                status=StatusTarefaInspecao.PENDENTE.value,
            )
        )

    await db.flush()
    inspecao_carregada = await buscar_inspecao(db, inspecao.id)
    if not inspecao_carregada:
        raise ValueError("Falha ao carregar inspecao criada.")
    return inspecao_carregada


async def atualizar_inspecao(
    db: AsyncSession,
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoUpdate,
) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise ValueError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)
    inspecao.observacoes = dados.observacoes
    await db.flush()
    
    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise ValueError("Falha ao carregar inspecao atualizada.")
    return inspecao_carregada


async def adicionar_tarefa_avulsa(
    db: AsyncSession,
    inspecao_id: uuid.UUID,
    dados: schemas.InspecaoTarefaCreate,
) -> InspecaoTarefa:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise ValueError("Inspecao nao encontrada.")
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
        raise ValueError("Tarefa de inspecao nao encontrada.")

    _garantir_inspecao_editavel(tarefa.inspecao)

    status_novo = dados.status
    executor_id = dados.executado_por_id or usuario_padrao_id

    if status_novo in {StatusTarefaInspecao.CONCLUIDA, StatusTarefaInspecao.NA}:
        if not executor_id:
            raise ValueError("Executor obrigatorio para atualizar tarefa.")
        executor = await _buscar_usuario(db, executor_id)
        if not executor:
            raise ValueError("Executor nao encontrado ou inativo.")
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
        raise ValueError("Falha ao carregar tarefa atualizada.")
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
        raise ValueError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)

    usuario = await _buscar_usuario(db, concluido_por_id)
    if not usuario:
        raise ValueError("Usuario de conclusao nao encontrado ou inativo.")

    pendentes = [
        tarefa
        for tarefa in inspecao.tarefas
        if tarefa.obrigatoria and tarefa.status == StatusTarefaInspecao.PENDENTE.value
    ]
    if pendentes:
        raise ValueError("Inspecao possui tarefas obrigatorias pendentes.")

    inspecao.status = StatusInspecao.CONCLUIDA.value
    inspecao.data_conclusao = datetime.now(timezone.utc)
    inspecao.concluido_por_id = concluido_por_id
    if inspecao.aeronave:
        inspecao.aeronave.status = StatusAeronave.DISPONIVEL.value
    await db.flush()
    
    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise ValueError("Falha ao carregar inspecao concluida.")
    return inspecao_carregada


async def cancelar_inspecao(db: AsyncSession, inspecao_id: uuid.UUID) -> Inspecao:
    inspecao = await buscar_inspecao(db, inspecao_id)
    if not inspecao:
        raise ValueError("Inspecao nao encontrada.")
    _garantir_inspecao_editavel(inspecao)
    inspecao.status = StatusInspecao.CANCELADA.value
    if inspecao.aeronave:
        inspecao.aeronave.status = StatusAeronave.DISPONIVEL.value
    await db.flush()
    
    inspecao_carregada = await buscar_inspecao(db, inspecao_id)
    if not inspecao_carregada:
        raise ValueError("Falha ao carregar inspecao cancelada.")
    return inspecao_carregada


def calcular_progresso(inspecao: Inspecao) -> tuple[int, int, int]:
    total = len(inspecao.tarefas)
    concluidas = sum(1 for tarefa in inspecao.tarefas if tarefa.status in {"CONCLUIDA", "N/A"})
    percentual = round((concluidas / total) * 100) if total else 0
    return total, concluidas, percentual
