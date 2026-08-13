"""
tests/unit/test_encarregado.py
Testes do módulo Encarregado — Ciência de Alterações
(feature_encarregado_ciencia.md v2.0, §10).
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.auth.models import Usuario
from app.modules.auth.security import hash_senha
from app.modules.encarregado.models import EncarregadoCiencia
from app.modules.equipamentos.models import Instalacao, ItemEquipamento, ModeloEquipamento, SlotInventario
from app.modules.inspecoes.models import Inspecao, InspecaoTarefa
from app.modules.panes.models import Pane
from app.modules.vencimentos.models import (
    ControleVencimento,
    ExecucaoVencimentoHistorico,
    ProrrogacaoVencimento,
    TipoControle,
)
from app.shared.core.enums import StatusAeronave, StatusPane, StatusTarefaInspecao

ENDPOINT_PENDENTES = "/api/v1/encarregado/pendentes"
ENDPOINT_CIENCIA = "/api/v1/encarregado/ciencia"


# ------------------------------------------------------------------ #
#  Helpers de fixture (construção direta via ORM, fora da API)
# ------------------------------------------------------------------ #

async def _criar_usuario(db: AsyncSession, funcao: str = "MANTENEDOR") -> Usuario:
    suffix = uuid.uuid4().hex[:8]
    usuario = Usuario(
        nome=f"Usuario Enc {suffix}",
        posto="Sgt",
        especialidade="ELT",
        funcao=funcao,
        ramal="2500",
        trigrama=suffix[:3].upper(),
        username=f"enc_{funcao.lower()}_{suffix}",
        senha_hash=hash_senha("senha_teste_123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def _criar_aeronave(db: AsyncSession) -> Aeronave:
    suffix = uuid.uuid4().hex[:8].upper()
    aeronave = Aeronave(
        serial_number=f"SN-ENC-{suffix}",
        matricula=f"EN-{suffix[:6]}",
        modelo="A-29",
        status=StatusAeronave.DISPONIVEL,
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_pane_resolvida(
    db: AsyncSession, aeronave_id: uuid.UUID, usuario_id: uuid.UUID,
    data_conclusao: datetime, ativo: bool = True,
) -> Pane:
    pane = Pane(
        id=uuid.uuid4(),
        aeronave_id=aeronave_id,
        status=StatusPane.RESOLVIDA.value,
        descricao="Falha no rádio VHF",
        observacao_conclusao="Substituído o módulo defeituoso",
        ativo=ativo,
        criado_por_id=usuario_id,
        concluido_por_id=usuario_id,
        data_conclusao=data_conclusao,
    )
    db.add(pane)
    await db.flush()
    return pane


async def _criar_tarefa_concluida(
    db: AsyncSession, aeronave_id: uuid.UUID, usuario_id: uuid.UUID, data_execucao: datetime,
) -> InspecaoTarefa:
    inspecao = Inspecao(id=uuid.uuid4(), aeronave_id=aeronave_id, aberto_por_id=usuario_id)
    db.add(inspecao)
    await db.flush()

    tarefa = InspecaoTarefa(
        id=uuid.uuid4(),
        inspecao_id=inspecao.id,
        ordem=1,
        titulo="Verificação do sistema hidráulico",
        status=StatusTarefaInspecao.CONCLUIDA.value,
        executado_por_id=usuario_id,
        data_execucao=data_execucao,
    )
    db.add(tarefa)
    await db.flush()
    return tarefa


async def _criar_instalacao(
    db: AsyncSession, aeronave_id: uuid.UUID, usuario_id: uuid.UUID,
    data_instalacao: date, criado_em: datetime,
    data_remocao: date | None = None, removido_em: datetime | None = None,
) -> Instalacao:
    """Cada chamada cria modelo/slot/item próprios — evita colidir com a
    UNIQUE parcial (slot_id, aeronave_id) WHERE data_remocao IS NULL."""
    suffix = uuid.uuid4().hex[:8]
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=f"PN-ENC-{suffix}", nome_generico="RADIO VHF")
    db.add(modelo)
    await db.flush()
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"MDP-{suffix[:4]}", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-ENC-{suffix}")
    db.add(item)
    await db.flush()

    instalacao = Instalacao(
        id=uuid.uuid4(),
        item_id=item.id,
        aeronave_id=aeronave_id,
        slot_id=slot.id,
        usuario_id=usuario_id,
        data_instalacao=data_instalacao,
        data_remocao=data_remocao,
        removido_em=removido_em,
    )
    db.add(instalacao)
    await db.flush()
    # `created_at` (timestamp do evento de INSTALACAO) tem default server-side
    # — sobrescrito aqui para controlar a janela de 90 dias nos testes.
    instalacao.created_at = criado_em
    await db.flush()
    return instalacao


async def _criar_controle_vencimento(
    db: AsyncSession, aeronave_id: uuid.UUID, usuario_id: uuid.UUID,
) -> ControleVencimento:
    suffix = uuid.uuid4().hex[:8]
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=f"PN-VENC-{suffix}", nome_generico="TRANSPONDER")
    db.add(modelo)
    await db.flush()
    slot = SlotInventario(id=uuid.uuid4(), nome_posicao=f"XPD-{suffix[:4]}", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    item = ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo.id, numero_serie=f"SN-VENC-{suffix}")
    db.add(item)
    await db.flush()
    instalacao = Instalacao(
        id=uuid.uuid4(), item_id=item.id, aeronave_id=aeronave_id, slot_id=slot.id,
        usuario_id=usuario_id, data_instalacao=date.today(),
    )
    db.add(instalacao)
    await db.flush()
    # Fora da janela de 90 dias por design: esta instalação existe só para
    # dar suporte ao item/controle de vencimento do teste — não deve
    # aparecer como um evento de INVENTARIO pendente por conta própria.
    instalacao.created_at = datetime.now(timezone.utc) - timedelta(days=200)
    await db.flush()

    tipo_controle = TipoControle(id=uuid.uuid4(), nome=f"TC-{suffix[:6]}")
    db.add(tipo_controle)
    await db.flush()

    controle = ControleVencimento(id=uuid.uuid4(), item_id=item.id, tipo_controle_id=tipo_controle.id)
    db.add(controle)
    await db.flush()
    return controle


async def _criar_execucao_vencimento(
    db: AsyncSession, controle_id: uuid.UUID, usuario_id: uuid.UUID, registrado_em: datetime,
) -> ExecucaoVencimentoHistorico:
    execucao = ExecucaoVencimentoHistorico(
        id=uuid.uuid4(),
        controle_id=controle_id,
        data_execucao=date.today(),
        data_vencimento_calculada=date.today() + timedelta(days=365),
        periodicidade_meses=12,
        executado_por_id=usuario_id,
        registrado_em=registrado_em,
    )
    db.add(execucao)
    await db.flush()
    return execucao


async def _criar_prorrogacao(
    db: AsyncSession, controle_id: uuid.UUID, usuario_id: uuid.UUID,
    criado_em: datetime, ativo: bool = True,
) -> ProrrogacaoVencimento:
    prorrogacao = ProrrogacaoVencimento(
        id=uuid.uuid4(),
        controle_id=controle_id,
        numero_documento=f"DOC-{uuid.uuid4().hex[:6]}",
        data_concessao=date.today(),
        data_nova_vencimento=date.today() + timedelta(days=180),
        dias_adicionais=180,
        registrado_por_id=usuario_id,
        ativo=ativo,
    )
    db.add(prorrogacao)
    await db.flush()
    prorrogacao.created_at = criado_em
    await db.flush()
    return prorrogacao


def _ids_por_categoria(dados: dict, categoria: str) -> set[str]:
    return {item["registro_id"] for item in dados["itens_por_categoria"][categoria]}


# ------------------------------------------------------------------ #
#  1. Agregação por categoria (inclui o discriminador de evento)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_agregacao_por_categoria(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db, funcao="MANTENEDOR")
    aeronave = await _criar_aeronave(db)
    agora = datetime.now(timezone.utc)

    pane = await _criar_pane_resolvida(db, aeronave.id, ator.id, data_conclusao=agora - timedelta(days=1))
    tarefa = await _criar_tarefa_concluida(db, aeronave.id, ator.id, data_execucao=agora - timedelta(days=1))
    # Uma única instalação, já removida: gera 2 eventos (INSTALACAO + REMOCAO)
    # com o mesmo registro_id — é exatamente a correção §2.2 da spec.
    instalacao = await _criar_instalacao(
        db, aeronave.id, ator.id,
        data_instalacao=date.today() - timedelta(days=10),
        criado_em=agora - timedelta(days=9),
        data_remocao=date.today() - timedelta(days=1),
        removido_em=agora - timedelta(days=1),
    )
    controle = await _criar_controle_vencimento(db, aeronave.id, ator.id)
    execucao = await _criar_execucao_vencimento(db, controle.id, ator.id, registrado_em=agora - timedelta(days=1))
    prorrogacao = await _criar_prorrogacao(db, controle.id, ator.id, criado_em=agora - timedelta(days=1))

    resposta = await client.get(ENDPOINT_PENDENTES, headers=usuario_encarregado_e_token["headers"])
    assert resposta.status_code == 200
    dados = resposta.json()

    # >= 6, não ==: a suíte completa reaproveita a mesma conexão SQLite entre
    # testes (conftest.py documenta o quirk de SAVEPOINT/rollback do
    # aiosqlite), então outro teste pode deixar registros residuais no
    # mesmo banco em memória. A asserção relevante é a de membership abaixo,
    # que confirma os 6 eventos desta fixture especificamente.
    assert dados["total"] >= 6

    assert pane.id.hex in _ids_por_categoria(dados, "PANES")
    assert tarefa.id.hex in _ids_por_categoria(dados, "INSPECAO")

    eventos_inventario = {
        (item["registro_id"], item["evento"]) for item in dados["itens_por_categoria"]["INVENTARIO"]
    }
    assert (instalacao.id.hex, "INSTALACAO") in eventos_inventario
    assert (instalacao.id.hex, "REMOCAO") in eventos_inventario

    eventos_vencimentos = {
        (item["registro_id"], item["evento"]) for item in dados["itens_por_categoria"]["VENCIMENTOS"]
    }
    assert (execucao.id.hex, "EXECUCAO") in eventos_vencimentos
    assert (prorrogacao.id.hex, "PRORROGACAO") in eventos_vencimentos


# ------------------------------------------------------------------ #
#  2. Janela de 90 dias
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_janela_90_dias_exclui_evento_antigo(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    agora = datetime.now(timezone.utc)

    pane_antiga = await _criar_pane_resolvida(db, aeronave.id, ator.id, data_conclusao=agora - timedelta(days=100))
    pane_recente = await _criar_pane_resolvida(db, aeronave.id, ator.id, data_conclusao=agora - timedelta(days=1))

    resposta = await client.get(ENDPOINT_PENDENTES, headers=usuario_encarregado_e_token["headers"])
    ids = _ids_por_categoria(resposta.json(), "PANES")

    assert pane_antiga.id.hex not in ids
    assert pane_recente.id.hex in ids


# ------------------------------------------------------------------ #
#  3. Ciência oculta o item
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_ciencia_oculta_item_da_lista_de_pendentes(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane = await _criar_pane_resolvida(
        db, aeronave.id, ator.id, data_conclusao=datetime.now(timezone.utc) - timedelta(days=1)
    )

    headers = usuario_encarregado_e_token["headers"]
    resposta_antes = await client.get(ENDPOINT_PENDENTES, headers=headers)
    assert pane.id.hex in _ids_por_categoria(resposta_antes.json(), "PANES")

    resposta_ciencia = await client.post(
        ENDPOINT_CIENCIA,
        headers=headers,
        json={"categoria": "PANES", "evento": "CONCLUSAO", "registro_id": pane.id.hex},
    )
    assert resposta_ciencia.status_code == 200

    resposta_depois = await client.get(ENDPOINT_PENDENTES, headers=headers)
    assert pane.id.hex not in _ids_por_categoria(resposta_depois.json(), "PANES")


# ------------------------------------------------------------------ #
#  4. Idempotência (RN-ENC-03)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_dar_ciencia_e_idempotente(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane = await _criar_pane_resolvida(
        db, aeronave.id, ator.id, data_conclusao=datetime.now(timezone.utc) - timedelta(days=1)
    )

    headers = usuario_encarregado_e_token["headers"]
    payload = {"categoria": "PANES", "evento": "CONCLUSAO", "registro_id": pane.id.hex}

    primeira = await client.post(ENDPOINT_CIENCIA, headers=headers, json=payload)
    segunda = await client.post(ENDPOINT_CIENCIA, headers=headers, json=payload)

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert primeira.json()["id"] == segunda.json()["id"]

    total = (
        await db.execute(
            select(func.count()).select_from(EncarregadoCiencia).where(
                EncarregadoCiencia.categoria == "PANES",
                EncarregadoCiencia.registro_id == pane.id.hex,
            )
        )
    ).scalar_one()
    assert total == 1


# ------------------------------------------------------------------ #
#  5. Desfazer (RN-ENC-04)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_desfazer_ciencia_traz_item_de_volta(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane = await _criar_pane_resolvida(
        db, aeronave.id, ator.id, data_conclusao=datetime.now(timezone.utc) - timedelta(days=1)
    )

    headers = usuario_encarregado_e_token["headers"]
    resposta_ciencia = await client.post(
        ENDPOINT_CIENCIA, headers=headers,
        json={"categoria": "PANES", "evento": "CONCLUSAO", "registro_id": pane.id.hex},
    )
    ciencia_id = resposta_ciencia.json()["id"]

    resposta_undo = await client.delete(f"{ENDPOINT_CIENCIA}/{ciencia_id}", headers=headers)
    assert resposta_undo.status_code == 204

    resposta_depois = await client.get(ENDPOINT_PENDENTES, headers=headers)
    assert pane.id.hex in _ids_por_categoria(resposta_depois.json(), "PANES")


# ------------------------------------------------------------------ #
#  6. RBAC
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_rbac_leitura_aberta_escrita_restrita(
    client: AsyncClient, db: AsyncSession, usuario_mantenedor_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane = await _criar_pane_resolvida(
        db, aeronave.id, ator.id, data_conclusao=datetime.now(timezone.utc) - timedelta(days=1)
    )

    # MANTENEDOR: leitura permitida.
    resposta_get = await client.get(ENDPOINT_PENDENTES, headers=usuario_mantenedor_e_token["headers"])
    assert resposta_get.status_code == 200

    # MANTENEDOR: escrita negada (RBAC restringe a ENCARREGADO/ADMINISTRADOR).
    resposta_post = await client.post(
        ENDPOINT_CIENCIA,
        headers=usuario_mantenedor_e_token["headers"],
        json={"categoria": "PANES", "evento": "CONCLUSAO", "registro_id": pane.id.hex},
    )
    assert resposta_post.status_code == 403

    # Não autenticado: 401.
    resposta_anonima = await client.get(ENDPOINT_PENDENTES)
    assert resposta_anonima.status_code == 401


# ------------------------------------------------------------------ #
#  7. Read-only (RN-ENC-05) — snapshot antes/depois do fluxo completo
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_modulo_nao_altera_tabelas_de_origem(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane = await _criar_pane_resolvida(
        db, aeronave.id, ator.id, data_conclusao=datetime.now(timezone.utc) - timedelta(days=1)
    )

    async def _snapshot_pane() -> dict:
        atualizado = await db.get(Pane, pane.id)
        return {
            "status": atualizado.status,
            "ativo": atualizado.ativo,
            "descricao": atualizado.descricao,
            "observacao_conclusao": atualizado.observacao_conclusao,
            "data_conclusao": atualizado.data_conclusao,
            "updated_at": atualizado.updated_at,
        }

    antes = await _snapshot_pane()

    headers = usuario_encarregado_e_token["headers"]
    resposta_get = await client.get(ENDPOINT_PENDENTES, headers=headers)
    resposta_post = await client.post(
        ENDPOINT_CIENCIA, headers=headers,
        json={"categoria": "PANES", "evento": "CONCLUSAO", "registro_id": pane.id.hex},
    )
    ciencia_id = resposta_post.json()["id"]
    resposta_delete = await client.delete(f"{ENDPOINT_CIENCIA}/{ciencia_id}", headers=headers)

    assert resposta_get.status_code == 200
    assert resposta_post.status_code == 200
    assert resposta_delete.status_code == 204

    depois = await _snapshot_pane()
    assert antes == depois


# ------------------------------------------------------------------ #
#  8. Soft delete de panes (RN-ENC-06)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_pane_excluida_nao_aparece_em_pendentes(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
):
    ator = await _criar_usuario(db)
    aeronave = await _criar_aeronave(db)
    pane_excluida = await _criar_pane_resolvida(
        db, aeronave.id, ator.id,
        data_conclusao=datetime.now(timezone.utc) - timedelta(days=1),
        ativo=False,
    )

    resposta = await client.get(ENDPOINT_PENDENTES, headers=usuario_encarregado_e_token["headers"])
    assert pane_excluida.id.hex not in _ids_por_categoria(resposta.json(), "PANES")
