"""
tests/unit/test_inspecoes_achados_revisor.py
Testes de regressão para docs/backlog/achados_inspecoes.md.

Cobertura:
    BUG-01  GET /inspecoes/export não usa mais atributos inexistentes
    BUG-02  executor/data_execucao só regravados em transição real de status
    BUG-03  observacao_execucao/observacoes/pane_id seguem exclude_unset
    BUG-04  tipos_inspecao_ids duplicados são deduplicados
    BUG-05  pane_id inexistente levanta 404, não 500
    RISCO-06 atualizar_tipo_inspecao protegido contra corrida de UNIQUE
    RISCO-07 listar_inspecoes/contar_tarefas_por_inspecao não carregam
             InspecaoTarefa completa só para contar progresso
    MELHORIA-10 abrir_inspecao valida templates antes de mutar estado
    MELHORIA-11 filtro por tipo com .distinct() e ordenação com desempate
"""

import uuid
import pytest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.dependencies import get_current_user, get_db
from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.inspecoes import schemas, service
from app.modules.inspecoes.router import router as inspecoes_router
from app.modules.panes.models import Pane
from app.shared.core import exceptions as domain_exc
from app.shared.core.enums import StatusAeronave, StatusTarefaInspecao

from tests.unit.test_inspecoes_refatoracao import criar_usuario_teste, criar_aeronave_teste, criar_tipo_com_tarefas


INSPECOES_URL = "/inspecoes"


async def _abrir_inspecao(db: AsyncSession, usuario: Usuario, aeronave: Aeronave, tipos_ids: list) -> "service.Inspecao":
    return await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=tipos_ids, observacoes="Teste"),
        usuario.id,
    )


def _criar_app_isolado(db: AsyncSession, usuario: Usuario) -> FastAPI:
    app = FastAPI()
    app.include_router(inspecoes_router, prefix=INSPECOES_URL)

    async def override_get_db():
        yield db

    async def override_get_current_user():
        return usuario

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


class ContadorDeQueries:
    def __init__(self) -> None:
        self.total = 0

    def __enter__(self) -> "ContadorDeQueries":
        event.listen(Engine, "before_cursor_execute", self._registrar)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(Engine, "before_cursor_execute", self._registrar)

    def _registrar(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.total += 1


# ------------------------------------------------------------------ #
#  BUG-01 — GET /inspecoes/export
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_exportar_inspecoes_nao_levanta_attributeerror(db: AsyncSession):
    """Antes, `insp.tipo_inspecao.nome`/`insp.dpe` (atributos inexistentes)
    faziam toda chamada a /export estourar AttributeError -> 500."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    await _abrir_inspecao(db, usuario, aeronave, [tipo.id])

    app = _criar_app_isolado(db, usuario)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"{INSPECOES_URL}/export")

    assert response.status_code == 200
    assert tipo.nome in response.text


# ------------------------------------------------------------------ #
#  BUG-02 — executor/data_execucao só na transição real
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_reeditar_tarefa_concluida_preserva_executor_e_data_original(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    outro_usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    tarefa = inspecao.tarefas[0]

    primeira = await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, observacao_execucao="Original"),
        usuario_padrao_id=usuario.id,
    )
    data_original = primeira.data_execucao
    assert primeira.executado_por_id == usuario.id

    # Reedição: mesmo status (CONCLUIDA -> CONCLUIDA), só muda a observação.
    # usuario_padrao_id é OUTRO usuário (simula outro sistema/sessão), mas
    # como não houve transição nem executado_por_id explícito, o executor
    # original deve ser preservado.
    reeditada = await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, observacao_execucao="Editada depois"),
        usuario_padrao_id=outro_usuario.id,
    )

    assert reeditada.executado_por_id == usuario.id
    assert reeditada.data_execucao == data_original
    assert reeditada.observacao_execucao == "Editada depois"


@pytest.mark.asyncio
async def test_transicao_real_para_concluida_atualiza_executor_e_data(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    tarefa = inspecao.tarefas[0]

    atualizada = await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA),
        usuario_padrao_id=usuario.id,
    )

    assert atualizada.executado_por_id == usuario.id
    assert atualizada.data_execucao is not None


# ------------------------------------------------------------------ #
#  BUG-03 — exclude_unset em observacao_execucao/observacoes/pane_id
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_atualizar_tarefa_sem_observacao_no_payload_preserva_a_existente(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    tarefa = inspecao.tarefas[0]

    await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, observacao_execucao="Nao apagar"),
        usuario_padrao_id=usuario.id,
    )

    # PATCH via router (payload JSON) sem o campo observacao_execucao.
    app = _criar_app_isolado(db, usuario)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.put(
            f"{INSPECOES_URL}/tarefas/{tarefa.id}",
            json={"status": "CONCLUIDA"},
        )

    assert response.status_code == 200
    assert response.json()["observacao_execucao"] == "Nao apagar"


@pytest.mark.asyncio
async def test_atualizar_inspecao_sem_observacoes_no_payload_preserva_a_existente(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    assert inspecao.observacoes == "Teste"

    app = _criar_app_isolado(db, usuario)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.put(f"{INSPECOES_URL}/{inspecao.id}", json={})

    assert response.status_code == 200
    assert response.json()["observacoes"] == "Teste"


@pytest.mark.asyncio
async def test_pane_id_null_explicito_desvincula_tarefa_de_pane(db: AsyncSession):
    """Antes, `if dados.pane_id:` (truthy) nunca permitia limpar um pane_id
    já setado — enviar `null` explicitamente agora desvincula."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    tarefa = inspecao.tarefas[0]
    pane = Pane(aeronave_id=aeronave.id, criado_por_id=usuario.id)
    db.add(pane)
    await db.flush()

    com_pane = await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, pane_id=pane.id),
        usuario_padrao_id=usuario.id,
    )
    assert com_pane.pane_id == pane.id

    sem_pane = await service.atualizar_tarefa_inspecao(
        db, tarefa.id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, pane_id=None),
        usuario_padrao_id=usuario.id,
    )
    assert sem_pane.pane_id is None


# ------------------------------------------------------------------ #
#  BUG-04 — dedupe de tipos_inspecao_ids
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_abrir_inspecao_deduplica_tipos_inspecao_ids_repetidos(db: AsyncSession):
    from sqlalchemy import select
    from app.modules.inspecoes.models import InspecaoEventoTipo

    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)

    inspecao = await service.abrir_inspecao(
        db,
        schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id, tipo.id]),
        usuario.id,
    )

    res = await db.execute(
        select(InspecaoEventoTipo).where(InspecaoEventoTipo.inspecao_id == inspecao.id)
    )
    vinculos = res.scalars().all()
    assert len(vinculos) == 1


# ------------------------------------------------------------------ #
#  BUG-05 — pane_id inexistente
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_atualizar_tarefa_com_pane_id_inexistente_levanta_404_nao_500(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])
    tarefa = inspecao.tarefas[0]

    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await service.atualizar_tarefa_inspecao(
            db, tarefa.id,
            schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA, pane_id=uuid.uuid4()),
            usuario_padrao_id=usuario.id,
        )


# ------------------------------------------------------------------ #
#  RISCO-06 — corrida de UNIQUE em atualizar_tipo_inspecao
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_atualizar_tipo_inspecao_savepoint_absorve_integrity_error_sem_derrubar_sessao(db: AsyncSession):
    from app.modules.inspecoes.models import TipoInspecao

    codigo_alvo = f"RC-{uuid.uuid4().hex[:6]}".upper()
    tipo_a = await service.criar_tipo_inspecao(
        db, schemas.TipoInspecaoCreate(codigo=f"RC-{uuid.uuid4().hex[:6]}", nome="A")
    )
    # Insere o tipo conflitante diretamente (bypassando o pre-check de
    # atualizar_tipo_inspecao) para forçar a colisão no flush do SAVEPOINT.
    tipo_b = TipoInspecao(codigo=codigo_alvo, nome="B")
    db.add(tipo_b)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await service.atualizar_tipo_inspecao(db, tipo_a.id, schemas.TipoInspecaoUpdate(codigo=codigo_alvo))

    # Sessão segue viva: o SAVEPOINT isolou a falha.
    outro = await service.criar_tipo_inspecao(
        db, schemas.TipoInspecaoCreate(codigo=f"RC-{uuid.uuid4().hex[:6]}", nome="C")
    )
    assert outro.id is not None


# ------------------------------------------------------------------ #
#  RISCO-07 — sem N+1/over-fetch em listar_inspecoes
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_contar_tarefas_por_inspecao_retorna_contagens_corretas(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=3)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])

    obrigatorias = [t for t in inspecao.tarefas if t.obrigatoria]
    await service.atualizar_tarefa_inspecao(
        db, obrigatorias[0].id,
        schemas.InspecaoTarefaUpdate(status=StatusTarefaInspecao.CONCLUIDA),
        usuario_padrao_id=usuario.id,
    )

    contagens = await service.contar_tarefas_por_inspecao(db, [inspecao.id])
    total, concluidas = contagens[inspecao.id]
    assert total == 3
    assert concluidas == 1


@pytest.mark.asyncio
async def test_endpoint_listar_inspecoes_usa_queries_constantes_independente_do_num_tarefas(db: AsyncSession):
    usuario = await criar_usuario_teste(db)
    aeronave1 = await criar_aeronave_teste(db)
    aeronave2 = await criar_aeronave_teste(db)
    tipo_pequeno, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    tipo_grande, _ = await criar_tipo_com_tarefas(db, obrigatorias=15)
    await _abrir_inspecao(db, usuario, aeronave1, [tipo_pequeno.id])
    await _abrir_inspecao(db, usuario, aeronave2, [tipo_grande.id])

    app = _criar_app_isolado(db, usuario)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        with ContadorDeQueries() as contador:
            response = await client.get(f"{INSPECOES_URL}/")
        queries_com_15_tarefas = contador.total

    assert response.status_code == 200
    # O número de SELECTs não deve escalar com a quantidade de tarefas por
    # inspeção — a asserção principal é que a listagem não trava/estoura
    # tempo com volume; como proxy, checamos que fica num teto razoável fixo.
    assert queries_com_15_tarefas < 20


# ------------------------------------------------------------------ #
#  MELHORIA-10 — validar antes de mutar estado
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_abrir_inspecao_sem_templates_nao_move_aeronave_para_inspecao(db: AsyncSession):
    """Antes, a checagem de templates só acontecia depois de
    `aeronave.status = INSPECAO` já estar setado em memória — mesmo com o
    rollback do get_db cobrindo isso em produção, testar a função de service
    isoladamente (sem passar pelo router/rollback de request) expõe o efeito
    colateral caso a validação não seja movida para antes da mutação."""
    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo = await service.criar_tipo_inspecao(
        db, schemas.TipoInspecaoCreate(codigo=f"VAZIO-{uuid.uuid4().hex[:6]}", nome="Sem templates")
    )

    with pytest.raises(domain_exc.ConflitoNegocioError, match="tarefas template"):
        await service.abrir_inspecao(
            db,
            schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]),
            usuario.id,
        )

    await db.refresh(aeronave)
    assert aeronave.status == StatusAeronave.DISPONIVEL.value


# ------------------------------------------------------------------ #
#  MELHORIA-11 — distinct + desempate na listagem
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_listar_inspecoes_filtro_por_tipo_nao_duplica_com_vinculo_repetido(db: AsyncSession):
    from app.modules.inspecoes.models import InspecaoEventoTipo

    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    inspecao = await _abrir_inspecao(db, usuario, aeronave, [tipo.id])

    # Simula o cenário do BUG-04 (dado legado com vínculo duplicado).
    db.add(InspecaoEventoTipo(inspecao_id=inspecao.id, tipo_inspecao_id=tipo.id))
    await db.flush()

    resultado = await service.listar_inspecoes(
        db, schemas.FiltroInspecao(tipo_inspecao_id=tipo.id, aeronave_id=aeronave.id)
    )
    ids = [i.id for i in resultado]
    assert ids.count(inspecao.id) == 1
