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
from app.shared.core.enums import StatusAeronave


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
            tipo_inspecao_id=tipo_id,
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

    assert inspecao.status == schemas.StatusInspecao.ABERTA.value
    assert inspecao.aeronave_id == aeronave.id
    assert len(inspecao.tarefas) == len(templates)
    assert [t.ordem for t in inspecao.tarefas] == [1, 2, 3]
    assert all(t.status == schemas.StatusTarefaInspecao.PENDENTE.value for t in inspecao.tarefas)

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
                status=schemas.StatusTarefaInspecao.CONCLUIDA,
                observacao_execucao="Executada sem executor",
            ),
            usuario_padrao_id=None,
        )

    atualizada = await service.atualizar_tarefa_inspecao(
        db,
        tarefa.id,
        schemas.InspecaoTarefaUpdate(
            status=schemas.StatusTarefaInspecao.CONCLUIDA,
            observacao_execucao="Executada conforme checklist",
        ),
        usuario_padrao_id=usuario.id,
    )

    assert atualizada.status == schemas.StatusTarefaInspecao.CONCLUIDA.value
    assert atualizada.executado_por_id == usuario.id
    assert atualizada.data_execucao is not None

    recarregada = await service.buscar_inspecao(db, inspecao.id)
    assert recarregada.status == schemas.StatusInspecao.EM_ANDAMENTO.value


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
            schemas.StatusTarefaInspecao.CONCLUIDA
            if tarefa.obrigatoria
            else schemas.StatusTarefaInspecao.PENDENTE
        )
        await service.atualizar_tarefa_inspecao(
            db,
            tarefa.id,
            schemas.InspecaoTarefaUpdate(status=status),
            usuario_padrao_id=usuario.id,
        )

    concluida = await service.concluir_inspecao(db, inspecao.id, usuario.id)

    assert concluida.status == schemas.StatusInspecao.CONCLUIDA.value
    assert concluida.concluido_por_id == usuario.id
    assert concluida.data_conclusao is not None


@pytest.mark.asyncio
async def test_inspecoes_permanece_isolado_do_app_principal(client: AsyncClient, usuario_e_token: dict):
    response = await client.get(f"{INSPECOES_URL}/tipos", headers=usuario_e_token["headers"])

    assert response.status_code == 404


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
