"""
Testes do modulo isolado de inspecoes.

O modulo nao e registrado no app principal durante estes testes. Quando o router
precisa ser exercitado, ele e montado em um FastAPI local apenas dentro do teste.
"""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inspecoes import models as inspecoes_models
from app.bootstrap.dependencies import get_current_user, get_db
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.inspecoes import schemas, service
from app.modules.inspecoes.router import router as inspecoes_router
from app.shared.core.enums import StatusAeronave, StatusInspecao, StatusTarefaInspecao


INSPECOES_URL = "/inspecoes"


async def criar_usuario_teste(db: AsyncSession, funcao: str = "ENCARREGADO") -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Usuario Inspecao {suffix}",
        posto="Sgt",
        especialidade="ELT",
        funcao=funcao,
        ramal="2500",
        trigrama=suffix[:3].upper(),
        username=f"inspecao_{funcao.lower()}_{suffix}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def criar_aeronave_teste(db: AsyncSession) -> Aeronave:
    suffix = uuid.uuid4().hex[:8].upper()
    aeronave = Aeronave(
        serial_number=f"SN-INSP-{suffix}",
        matricula=f"IN-{suffix[:6]}",
        modelo="A-29",
        status=StatusAeronave.DISPONIVEL,
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def criar_tipo_com_tarefas(
    db: AsyncSession,
    obrigatorias: int = 2,
    opcionais: int = 0,
) -> tuple[inspecoes_models.TipoInspecao, list[inspecoes_models.TarefaTemplate]]:
    codigo = f"IF-{uuid.uuid4().hex[:6].upper()}"
    tipo = await service.criar_tipo_inspecao(
        db,
        schemas.TipoInspecaoCreate(
            codigo=codigo,
            nome=f"Inspecao {codigo}",
            descricao="Tipo criado pelo teste",
        ),
    )

    tarefas = []
    ordem = 1
    for idx in range(obrigatorias):
        tarefa = await service.criar_tarefa_template(
            db,
            tipo.id,
            schemas.TarefaTemplateCreate(
                ordem=ordem,
                titulo=f"Tarefa obrigatoria {idx + 1}",
                sistema="AVI",
                obrigatoria=True,
            ),
        )
        tarefas.append(tarefa)
        ordem += 1

    for idx in range(opcionais):
        tarefa = await service.criar_tarefa_template(
            db,
            tipo.id,
            schemas.TarefaTemplateCreate(
                ordem=ordem,
                titulo=f"Tarefa opcional {idx + 1}",
                sistema="COM",
                obrigatoria=False,
            ),
        )
        tarefas.append(tarefa)
        ordem += 1

    return tipo, tarefas


async def abrir_inspecao_teste(
    db: AsyncSession,
    usuario: Usuario,
    aeronave: Aeronave,
    tipo_id,
):
    return await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(
            aeronave_id=aeronave.id,
            tipos_inspecao_ids=[tipo_id],
            observacoes="Inspecao aberta por teste",
        ),
        usuario.id,
    )


def criar_app_isolado(db: AsyncSession, usuario: Usuario | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(inspecoes_router, prefix=INSPECOES_URL)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if usuario is not None:
        async def override_get_current_user():
            return usuario

        app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.mark.asyncio
async def test_criar_tipo_inspecao_normaliza_codigo_e_rejeita_duplicado(db: AsyncSession):
    tipo = await service.criar_tipo_inspecao(
        db,
        schemas.TipoInspecaoCreate(
            codigo=" if-50h ",
            nome="Inspecao de Fase 50h",
        ),
    )

    assert tipo.codigo == "IF-50H"

    with pytest.raises(ValueError, match="ja cadastrado"):
        await service.criar_tipo_inspecao(
            db,
            schemas.TipoInspecaoCreate(
                codigo="IF-50H",
                nome="Duplicada",
            ),
        )


@pytest.mark.asyncio
async def test_abrir_inspecao_instancia_tarefas_e_bloqueia_duplicidade_ativa(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, templates = await criar_tipo_com_tarefas(db, obrigatorias=2, opcionais=1)

    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)

    assert inspecao.status == StatusInspecao.ABERTA.value
    assert inspecao.aeronave_id == aeronave.id
    assert len(inspecao.tarefas) == len(templates)
    assert [t.ordem for t in inspecao.tarefas] == [1, 2, 3]
    assert all(t.status == StatusTarefaInspecao.PENDENTE.value for t in inspecao.tarefas)

    with pytest.raises(ValueError, match="Ja existe inspecao ativa"):
        await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)


@pytest.mark.asyncio
async def test_atualizar_tarefa_concluida_exige_executor_e_move_inspecao_para_andamento(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)
    tarefa = inspecao.tarefas[0]

    with pytest.raises(ValueError, match="Executor obrigatorio"):
        await service.atualizar_tarefa_inspecao(
            db,
            tarefa.id,
            schemas.InspecaoTarefaUpdate(
                status=StatusTarefaInspecao.CONCLUIDA,
                observacao_execucao="Executada sem executor",
            ),
            usuario_padrao_id=None,
        )

    atualizada = await service.atualizar_tarefa_inspecao(
        db,
        tarefa.id,
        schemas.InspecaoTarefaUpdate(
            status=StatusTarefaInspecao.CONCLUIDA,
            observacao_execucao="Executada conforme checklist",
        ),
        usuario_padrao_id=usuario.id,
    )

    assert atualizada.status == StatusTarefaInspecao.CONCLUIDA.value
    assert atualizada.executado_por_id == usuario.id
    assert atualizada.data_execucao is not None

    recarregada = await service.buscar_inspecao(db, inspecao.id)
    assert recarregada.status == StatusInspecao.EM_ANDAMENTO.value


@pytest.mark.asyncio
async def test_concluir_inspecao_bloqueia_obrigatorias_pendentes(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=2, opcionais=1)
    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)

    with pytest.raises(ValueError, match="tarefas obrigatorias pendentes"):
        await service.concluir_inspecao(db, inspecao.id, usuario.id)

    for tarefa in inspecao.tarefas:
        status = (
            StatusTarefaInspecao.CONCLUIDA
            if tarefa.obrigatoria
            else StatusTarefaInspecao.PENDENTE
        )
        await service.atualizar_tarefa_inspecao(
            db,
            tarefa.id,
            schemas.InspecaoTarefaUpdate(status=status),
            usuario_padrao_id=usuario.id,
        )

    concluida = await service.concluir_inspecao(db, inspecao.id, usuario.id)

    assert concluida.status == StatusInspecao.CONCLUIDA.value
    assert concluida.concluido_por_id == usuario.id
    assert concluida.data_conclusao is not None


@pytest.mark.asyncio
async def test_inspecoes_registrado_no_app_principal(client: AsyncClient, usuario_e_token: dict):
    response = await client.get(f"{INSPECOES_URL}/tipos", headers=usuario_e_token["headers"])

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_router_isolado_exige_autenticacao_para_listar(db: AsyncSession):
    app = criar_app_isolado(db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(INSPECOES_URL)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_router_isolado_bloqueia_mantenedor_em_endpoint_de_gestao(db: AsyncSession):
    mantenedor = await criar_usuario_teste(db, funcao="MANTENEDOR")
    app = criar_app_isolado(db, mantenedor)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"{INSPECOES_URL}/tipos",
            json={
                "codigo": "IF-100H",
                "nome": "Inspecao de Fase 100h",
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_router_isolado_encarregado_pode_criar_tipo(db: AsyncSession):
    encarregado = await criar_usuario_teste(db, funcao="ENCARREGADO")
    app = criar_app_isolado(db, encarregado)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"{INSPECOES_URL}/tipos",
            json={
                "codigo": "IF-200H",
                "nome": "Inspecao de Fase 200h",
            },
        )

    assert response.status_code == 201
    assert response.json()["codigo"] == "IF-200H"

    result = await db.execute(select(inspecoes_models.TipoInspecao))
    assert result.scalar_one_or_none() is not None


# --- Novos Testes TDD Baseados no Backlog (RN-01, RN-02, RN-04, RN-05) ---

@pytest.mark.asyncio
async def test_rn02_adicionar_tarefa_manual_a_evento_existente(db: AsyncSession):
    """
    RN-02: Permite adicionar tarefas de origem MANUAL diretamente ao evento (tarefa_id nulo).
    """
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)

    tarefa_manual = await service.adicionar_tarefa_avulsa(
        db,
        inspecao.id,
        schemas.InspecaoTarefaCreate(
            titulo="Tarefa Adicional Manual",
            descricao="Inspecao extra detectada no patio",
            obrigatoria=True,
        )
    )

    assert tarefa_manual.id is not None
    assert tarefa_manual.inspecao_id == inspecao.id
    # Validando a intencao da RN-02: a tarefa avulsa nao esta atrelada a um template
    assert tarefa_manual.tarefa_template_id is None
    assert tarefa_manual.titulo == "Tarefa Adicional Manual"


@pytest.mark.asyncio
async def test_rn04_tarefa_com_anomalia_deve_gerar_pane_vinculada(db: AsyncSession):
    """
    RN-04: Se houver anomalia, uma Pane deve ser criada e vinculada via inspecao_tarefas.pane_id.
    """
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)
    tarefa = inspecao.tarefas[0]

    mock_pane_id = uuid.uuid4()

    atualizada = await service.atualizar_tarefa_inspecao(
        db,
        tarefa.id,
        schemas.InspecaoTarefaUpdate(
            status=StatusTarefaInspecao.CONCLUIDA,
            observacao_execucao="Vazamento encontrado no pneu direito",
            pane_id=mock_pane_id,
        ),
        usuario_padrao_id=usuario.id,
    )
    
    assert atualizada.pane_id == mock_pane_id


@pytest.mark.asyncio
async def test_rn05_status_aeronave_atualizado_ao_abrir_e_concluir_inspecao(db: AsyncSession):
    """
    RN-05: A aeronave muda para INSPECAO na abertura do evento. 
    Ao concluir, retorna para DISPONIVEL (ou INDISPONIVEL caso restem panes impeditivas).
    """
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    assert aeronave.status == StatusAeronave.DISPONIVEL

    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await abrir_inspecao_teste(db, usuario, aeronave, tipo.id)

    # Validacao 1: Deve mudar o status da aeronave na abertura
    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.INSPECAO

    # Concluir a inspecao
    tarefa = inspecao.tarefas[0]
    await service.atualizar_tarefa_inspecao(
        db,
        tarefa.id,
        schemas.InspecaoTarefaUpdate(
            status=StatusTarefaInspecao.CONCLUIDA,
        ),
        usuario_padrao_id=usuario.id,
    )
    await service.concluir_inspecao(db, inspecao.id, usuario.id)

    # Validacao 2: Deve retornar a aeronave para DISPONIVEL
    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.DISPONIVEL


@pytest.mark.asyncio
async def test_rn01_abrir_inspecao_com_multiplos_tipos_e_deduplicar_tarefas(db: AsyncSession):
    """
    RN-01: O modelo suporta a aplicacao de multiplos tipos de inspecao em um unico evento.
    Deve unificar e deduplicar as tarefas.
    """
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    
    tipo1, templates1 = await criar_tipo_com_tarefas(db, obrigatorias=2)
    tipo2, templates2 = await criar_tipo_com_tarefas(db, obrigatorias=2)
    
    dados = schemas.InspecaoCreate(
        aeronave_id=aeronave.id,
        tipos_inspecao_ids=[tipo1.id, tipo2.id], 
        observacoes="Inspecao Combinada"
    )
    
    inspecao = await service.abrir_inspecao(db, dados, usuario.id)
    
    # Ambos os tipos tem "Tarefa obrigatoria 1" e "Tarefa obrigatoria 2", a deduplicacao
    # garante que resultem em apenas 2 tarefas totais instanciadas no evento.
    assert len(inspecao.tarefas) == 2
    
    assert hasattr(inspecao, "tipos_aplicados")
    assert len(inspecao.tipos_aplicados) == 2
