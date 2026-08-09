"""
tests/unit/test_efetivo.py
Testes de regressão para docs/backlog/revisor/achados_efetivo.md.

Cobertura:
    RISCO-01  tipo PARTICULAR oculta observacao para qualquer solicitante;
              leitura permanece pública (decisão do desenvolvedor)
    BUG-02    usuario_id inexistente levanta ValueError/400, não IntegrityError/500
    RISCO-03  sem mudança de código (registro de risco); coberto indiretamente
              pelo caminho feliz e pela checagem de sobreposição
    MELHORIA-04/05  sem comportamento novo a testar (docstring e eager-load)
"""

import uuid
import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.efetivo import service
from app.modules.efetivo.schemas import IndisponibilidadeCreate
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha


async def _criar_usuario(db: AsyncSession, **overrides) -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    dados = {
        "nome": f"Usuario {suffix}",
        "posto": "Sgt",
        "especialidade": "ELT",
        "funcao": "MANTENEDOR",
        "ramal": "0000",
        "username": f"user_{suffix}",
        "senha_hash": hash_senha("senha_123"),
    }
    dados.update(overrides)
    usuario = Usuario(**dados)
    db.add(usuario)
    await db.flush()
    return usuario


def _dados_indisp(usuario_id: uuid.UUID, **overrides) -> IndisponibilidadeCreate:
    dados = {
        "usuario_id": usuario_id,
        "tipo": "FERIAS",
        "data_inicio": date.today() + timedelta(days=1),
        "data_fim": date.today() + timedelta(days=5),
        "observacao": "Motivo detalhado",
    }
    dados.update(overrides)
    return IndisponibilidadeCreate(**dados)


# ------------------------------------------------------------------ #
#  Caminho feliz
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_registrar_listar_e_remover_caminho_feliz(db: AsyncSession):
    usuario = await _criar_usuario(db)

    criado = await service.registrar_indisponibilidade(db, _dados_indisp(usuario.id))
    assert criado.usuario_id == usuario.id
    assert criado.observacao == "Motivo detalhado"

    ativas = await service.listar_indisponibilidades_ativas(db, date.today() + timedelta(days=2))
    assert any(i.id == criado.id for i in ativas)

    por_usuario = await service.listar_indisponibilidades_por_usuario(db, usuario.id)
    assert [i.id for i in por_usuario] == [criado.id]

    removido = await service.remover_indisponibilidade(db, criado.id)
    assert removido is True
    assert await service.remover_indisponibilidade(db, criado.id) is False


@pytest.mark.asyncio
async def test_data_fim_menor_que_data_inicio_e_rejeitada(db: AsyncSession):
    usuario = await _criar_usuario(db)
    dados = _dados_indisp(usuario.id, data_inicio=date.today() + timedelta(days=5), data_fim=date.today())
    with pytest.raises(ValueError, match="data de término"):
        await service.registrar_indisponibilidade(db, dados)


@pytest.mark.asyncio
async def test_sobreposicao_de_periodo_para_mesmo_usuario_e_rejeitada(db: AsyncSession):
    usuario = await _criar_usuario(db)
    await service.registrar_indisponibilidade(
        db, _dados_indisp(usuario.id, data_inicio=date.today() + timedelta(days=1), data_fim=date.today() + timedelta(days=10))
    )
    sobreposta = _dados_indisp(usuario.id, data_inicio=date.today() + timedelta(days=5), data_fim=date.today() + timedelta(days=15))
    with pytest.raises(ValueError, match="Já existe uma indisponibilidade"):
        await service.registrar_indisponibilidade(db, sobreposta)


# ------------------------------------------------------------------ #
#  BUG-02 — usuario_id inexistente
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_usuario_id_inexistente_levanta_valueerror_nao_integrityerror(db: AsyncSession):
    """Antes, um usuario_id inexistente só falhava no flush() com IntegrityError
    crua, não capturada pelo router (que só trata ValueError) — virava 500."""
    dados = _dados_indisp(uuid.uuid4())
    with pytest.raises(ValueError, match="Usuário não encontrado"):
        await service.registrar_indisponibilidade(db, dados)


@pytest.mark.asyncio
async def test_post_efetivo_usuario_id_inexistente_retorna_400_nao_500(client: AsyncClient, client_autenticado: AsyncClient):
    payload = {
        "usuario_id": str(uuid.uuid4()),
        "tipo": "FERIAS",
        "data_inicio": str(date.today() + timedelta(days=1)),
        "data_fim": str(date.today() + timedelta(days=5)),
    }
    resp = await client_autenticado.post("/efetivo/", json=payload)
    assert resp.status_code == 400
    assert "não encontrado" in resp.json()["detail"].lower()


# ------------------------------------------------------------------ #
#  RISCO-01 — tipo PARTICULAR oculta observacao; leitura continua pública
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_tipo_particular_oculta_observacao_em_todas_as_saidas(db: AsyncSession):
    usuario = await _criar_usuario(db)
    criado = await service.registrar_indisponibilidade(
        db, _dados_indisp(usuario.id, tipo="PARTICULAR", observacao="Assunto sensível")
    )
    assert criado.tipo == "PARTICULAR"
    assert criado.observacao is None

    ativas = await service.listar_indisponibilidades_ativas(db, date.today() + timedelta(days=2))
    encontrada = next(i for i in ativas if i.id == criado.id)
    assert encontrada.observacao is None

    por_usuario = await service.listar_indisponibilidades_por_usuario(db, usuario.id)
    encontrada = next(i for i in por_usuario if i.id == criado.id)
    assert encontrada.observacao is None


@pytest.mark.asyncio
async def test_tipo_nao_particular_preserva_observacao(db: AsyncSession):
    usuario = await _criar_usuario(db)
    criado = await service.registrar_indisponibilidade(
        db, _dados_indisp(usuario.id, tipo="DISPENSA", observacao="Afastamento médico")
    )
    assert criado.observacao == "Afastamento médico"


@pytest.mark.asyncio
async def test_leitura_de_indisponibilidade_de_terceiro_permanece_publica(
    client: AsyncClient, usuario_mantenedor_e_token: dict, db: AsyncSession
):
    """Decisão do desenvolvedor (achados_efetivo.md, RISCO-01): a leitura
    continua aberta a qualquer usuário autenticado — não restrita a
    dono/privilegiado. O que muda é a censura da observacao para PARTICULAR."""
    outro_usuario = await _criar_usuario(db)
    await service.registrar_indisponibilidade(db, _dados_indisp(outro_usuario.id))

    data_ref = date.today() + timedelta(days=2)
    resp = await client.get(
        "/efetivo/ativas", params={"data_ref": str(data_ref)}, headers=usuario_mantenedor_e_token["headers"]
    )
    assert resp.status_code == 200
    assert any(i["usuario_id"] == str(outro_usuario.id) for i in resp.json())


@pytest.mark.asyncio
async def test_leitura_publica_de_tipo_particular_nao_expoe_observacao_via_api(
    client: AsyncClient, usuario_mantenedor_e_token: dict, db: AsyncSession
):
    outro_usuario = await _criar_usuario(db)
    await service.registrar_indisponibilidade(
        db, _dados_indisp(outro_usuario.id, tipo="PARTICULAR", observacao="Não é da conta de ninguém")
    )

    resp = await client.get(f"/efetivo/usuario/{outro_usuario.id}", headers=usuario_mantenedor_e_token["headers"])
    assert resp.status_code == 200
    registros = resp.json()
    assert len(registros) == 1
    assert registros[0]["tipo"] == "PARTICULAR"
    assert registros[0]["observacao"] is None
