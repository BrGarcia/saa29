"""
tests/unit/test_gestao_inventario.py
Cobertura da gestão administrativa de slots e itens (SPEC-CONF-001, fatia 2).

Foco em três coisas que a implementação errada faz silenciosamente:
    - devolver 500 onde deveria devolver 409 com explicação;
    - gravar auditoria com autor vindo do cliente em vez da sessão;
    - deixar um slot inativado inacessível, sem caminho de volta.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.equipamentos.models import (
    AuditoriaDadosMestres,
    Instalacao,
    ItemEquipamento,
    ModeloEquipamento,
    SlotInventario,
)

EQUIP_URL = "/equipamentos"


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

async def _criar_modelo(db: AsyncSession, pn: str | None = None) -> ModeloEquipamento:
    modelo = ModeloEquipamento(
        id=uuid.uuid4(),
        part_number=pn or f"PN-{uuid.uuid4().hex[:8]}",
        nome_generico="RADIO",
    )
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_slot(db: AsyncSession, modelo_id: uuid.UUID, nome: str | None = None) -> SlotInventario:
    nome = nome or f"POS-{uuid.uuid4().hex[:6]}"
    slot = SlotInventario(
        id=uuid.uuid4(), nome_posicao=nome, sistema="CEI",
        posicao_xlsx=nome, modelo_id=modelo_id,
    )
    db.add(slot)
    await db.flush()
    return slot


async def _criar_aeronave(db: AsyncSession) -> Aeronave:
    matricula = f"AN{uuid.uuid4().hex[:4]}"
    aeronave = Aeronave(
        id=uuid.uuid4(), serial_number=f"SN-{matricula}", matricula=matricula,
        modelo="A-29", data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_item(db: AsyncSession, modelo_id: uuid.UUID, sn: str | None = None) -> ItemEquipamento:
    item = ItemEquipamento(
        id=uuid.uuid4(), modelo_id=modelo_id,
        numero_serie=sn or f"SN-{uuid.uuid4().hex[:8]}", status="ATIVO",
    )
    db.add(item)
    await db.flush()
    return item


async def _instalar(db: AsyncSession, item, slot, aeronave) -> Instalacao:
    inst = Instalacao(
        id=uuid.uuid4(), item_id=item.id, slot_id=slot.id,
        aeronave_id=aeronave.id, data_instalacao=date.today(),
    )
    db.add(inst)
    await db.flush()
    return inst


async def _auditoria(db: AsyncSession, entidade_id: uuid.UUID) -> list[AuditoriaDadosMestres]:
    res = await db.execute(
        select(AuditoriaDadosMestres).where(AuditoriaDadosMestres.entidade_id == entidade_id)
    )
    return list(res.scalars().all())


# ------------------------------------------------------------------ #
#  Slots — criação e chave natural
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_slot_sem_posicao_xlsx_retorna_422(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """Regressão do bug de integração: a API não pode mais aceitar slot sem
    posicao_xlsx, senão ele nunca casa com a planilha."""
    modelo = await _criar_modelo(db)
    resp = await client.post(
        f"{EQUIP_URL}/slots/",
        json={"nome_posicao": "X1", "sistema": "CEI", "modelo_id": str(modelo.id)},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 422
    assert any(e["loc"][-1] == "posicao_xlsx" for e in resp.json()["detail"])


@pytest.mark.asyncio
async def test_criar_slot_duplicado_retorna_409(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    payload = {
        "nome_posicao": "DUP1", "sistema": "CEI",
        "posicao_xlsx": "DUP1", "modelo_id": str(modelo.id),
    }
    primeira = await client.post(f"{EQUIP_URL}/slots/", json=payload, headers=usuario_e_token["headers"])
    assert primeira.status_code == 201

    segunda = await client.post(f"{EQUIP_URL}/slots/", json=payload, headers=usuario_e_token["headers"])
    assert segunda.status_code == 409


@pytest.mark.asyncio
async def test_criar_slot_gera_auditoria_com_usuario_da_sessao(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """O autor vem SEMPRE da sessão — nunca de payload (precedente BUG-01)."""
    modelo = await _criar_modelo(db)
    resp = await client.post(
        f"{EQUIP_URL}/slots/",
        json={
            "nome_posicao": "AUD1", "sistema": "CEI",
            "posicao_xlsx": "AUD1", "modelo_id": str(modelo.id),
            # Tentativa de forjar o autor: precisa ser ignorada.
            "usuario_id": str(uuid.uuid4()),
        },
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 201

    registros = await _auditoria(db, uuid.UUID(resp.json()["id"]))
    assert len(registros) == 1
    assert registros[0].acao == "CREATE"
    assert registros[0].usuario_id == usuario_e_token["usuario"].id


# ------------------------------------------------------------------ #
#  Slots — edição
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_editar_slot_registra_diff_na_auditoria(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "EDIT1")

    resp = await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}",
        json={"descricao": "Rádio principal", "ordem_exibicao": 3},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["descricao"] == "Rádio principal"

    registros = [r for r in await _auditoria(db, slot.id) if r.acao == "UPDATE"]
    assert len(registros) == 1
    # Só o que mudou entra no diff — nome_posicao não foi tocado.
    assert set(registros[0].valores_novos) == {"descricao", "ordem_exibicao"}
    assert registros[0].valores_novos["ordem_exibicao"] == 3


@pytest.mark.asyncio
async def test_patch_sem_mudanca_nao_gera_auditoria(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """Um PATCH que não altera nada não pode poluir a trilha."""
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "NOOP1")

    resp = await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}",
        json={"nome_posicao": "NOOP1"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert [r for r in await _auditoria(db, slot.id) if r.acao == "UPDATE"] == []


@pytest.mark.asyncio
async def test_trocar_pn_de_slot_ocupado_retorna_409(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """O slot é global da frota: trocar o PN esperado afetaria a leitura de
    todas as aeronaves, não de uma isolada."""
    modelo = await _criar_modelo(db)
    outro_modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "OCUP1")
    item = await _criar_item(db, modelo.id)
    aeronave = await _criar_aeronave(db)
    await _instalar(db, item, slot, aeronave)

    resp = await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}",
        json={"modelo_id": str(outro_modelo.id)},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 409
    assert "instalação ativa" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trocar_pn_de_slot_livre_sucede(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    outro_modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "LIVRE1")

    resp = await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}",
        json={"modelo_id": str(outro_modelo.id)},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["modelo_id"] == str(outro_modelo.id)


# ------------------------------------------------------------------ #
#  Slots — exclusão, inativação e reativação
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_remover_slot_com_historico_retorna_409_e_sugere_inativar(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """Critério mais rígido que o de item: instalação HISTÓRICA também barra,
    porque apagar o slot levaria a rastreabilidade de toda a frota."""
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "HIST1")
    item = await _criar_item(db, modelo.id)
    aeronave = await _criar_aeronave(db)
    inst = await _instalar(db, item, slot, aeronave)
    inst.data_remocao = date.today()  # instalação encerrada, mas histórica
    await db.flush()

    resp = await client.post(
        f"{EQUIP_URL}/slots/{slot.id}/remover",
        json={"justificativa": "slot criado por engano"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 409
    assert "inativar" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_remover_slot_livre_sucede_e_exige_justificativa(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "DEL1")
    slot_id = slot.id

    sem_justificativa = await client.post(
        f"{EQUIP_URL}/slots/{slot_id}/remover", json={}, headers=usuario_e_token["headers"]
    )
    assert sem_justificativa.status_code == 422

    curta = await client.post(
        f"{EQUIP_URL}/slots/{slot_id}/remover",
        json={"justificativa": "ok"},
        headers=usuario_e_token["headers"],
    )
    assert curta.status_code == 422, "justificativa tem mínimo de 5 caracteres"

    resp = await client.post(
        f"{EQUIP_URL}/slots/{slot_id}/remover",
        json={"justificativa": "cadastrado em duplicidade"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert await db.get(SlotInventario, slot_id) is None

    registros = [r for r in await _auditoria(db, slot_id) if r.acao == "DELETE"]
    assert len(registros) == 1
    assert registros[0].justificativa == "cadastrado em duplicidade"
    # O retrato do slot apagado precisa sobreviver à exclusão.
    assert registros[0].valores_anteriores["nome_posicao"] == "DEL1"


@pytest.mark.asyncio
async def test_ciclo_inativar_reativar_slot(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """Sem /reativar, inativar seria uma operação sem volta: o slot some da
    listagem padrão e não haveria como trazê-lo de volta pela aplicação."""
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "TOGGLE1")
    headers = usuario_e_token["headers"]

    inativar = await client.post(f"{EQUIP_URL}/slots/{slot.id}/inativar", headers=headers)
    assert inativar.status_code == 200
    assert inativar.json()["ativo"] is False

    padrao = await client.get(f"{EQUIP_URL}/slots/", headers=headers)
    assert str(slot.id) not in [s["id"] for s in padrao.json()]

    com_inativos = await client.get(f"{EQUIP_URL}/slots/?incluir_inativos=true", headers=headers)
    assert str(slot.id) in [s["id"] for s in com_inativos.json()]

    reativar = await client.post(f"{EQUIP_URL}/slots/{slot.id}/reativar", headers=headers)
    assert reativar.status_code == 200
    assert reativar.json()["ativo"] is True

    de_volta = await client.get(f"{EQUIP_URL}/slots/", headers=headers)
    assert str(slot.id) in [s["id"] for s in de_volta.json()]


# ------------------------------------------------------------------ #
#  Itens de equipamento
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_editar_sn_para_valor_duplicado_no_mesmo_pn_retorna_409(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    await _criar_item(db, modelo.id, "SN-OCUPADO")
    item = await _criar_item(db, modelo.id, "SN-LIVRE")

    resp = await client.patch(
        f"{EQUIP_URL}/itens/{item.id}",
        json={"numero_serie": "SN-OCUPADO"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_corrigir_sn_digitado_errado(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    item = await _criar_item(db, modelo.id, "SN-ERRAD0")

    resp = await client.patch(
        f"{EQUIP_URL}/itens/{item.id}",
        json={"numero_serie": "sn-correto"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["numero_serie"] == "SN-CORRETO", "S/N deve ser normalizado"

    registros = [r for r in await _auditoria(db, item.id) if r.acao == "UPDATE"]
    assert len(registros) == 1
    assert registros[0].valores_anteriores["numero_serie"] == "SN-ERRAD0"
    assert registros[0].valores_novos["numero_serie"] == "SN-CORRETO"


@pytest.mark.asyncio
async def test_excluir_item_instalado_retorna_409(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id)
    item = await _criar_item(db, modelo.id)
    aeronave = await _criar_aeronave(db)
    await _instalar(db, item, slot, aeronave)

    resp = await client.post(
        f"{EQUIP_URL}/itens/{item.id}/excluir",
        json={"justificativa": "cadastrado por engano"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 409
    assert "REMOVIDO" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_excluir_item_com_controles_retorna_409_e_nao_500(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """O caso COMUM, não a exceção.

    `ControleVencimento.item_id` é FK sem ondelete. Todo item criado pela API
    herda controles do template do PN, então sem a checagem explícita o DELETE
    estouraria IntegrityError e viraria 500 — justamente no caminho que o
    usuário mais percorre.
    """
    from app.modules.vencimentos.models import ControleVencimento, EquipamentoControle, TipoControle

    modelo = await _criar_modelo(db)
    # `nome` de TipoControle é UNIQUE — sufixo evita colisão entre testes.
    tipo = TipoControle(id=uuid.uuid4(), nome=f"T{uuid.uuid4().hex[:4]}", descricao="Teste")
    db.add(tipo)
    await db.flush()
    # periodicidade_meses pertence a EquipamentoControle (o template por PN),
    # não a TipoControle.
    db.add(
        EquipamentoControle(
            id=uuid.uuid4(), modelo_id=modelo.id,
            tipo_controle_id=tipo.id, periodicidade_meses=12,
        )
    )
    await db.flush()

    criado = await client.post(
        f"{EQUIP_URL}/itens/",
        json={"modelo_id": str(modelo.id), "numero_serie": "SN-COM-CTRL"},
        headers=usuario_e_token["headers"],
    )
    assert criado.status_code == 201
    item_id = uuid.UUID(criado.json()["id"])

    # Pré-condição do teste: o item realmente herdou controles.
    res = await db.execute(
        select(ControleVencimento.id).where(ControleVencimento.item_id == item_id)
    )
    assert res.first() is not None, "sem controle herdado o teste não prova nada"

    resp = await client.post(
        f"{EQUIP_URL}/itens/{item_id}/excluir",
        json={"justificativa": "cadastrado por engano"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 409, f"esperado 409, veio {resp.status_code}"
    assert "vencimento" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_excluir_item_sem_vinculo_sucede(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    modelo = await _criar_modelo(db)
    item = await _criar_item(db, modelo.id)
    item_id = item.id

    resp = await client.post(
        f"{EQUIP_URL}/itens/{item_id}/excluir",
        json={"justificativa": "duplicado no cadastro"},
        headers=usuario_e_token["headers"],
    )
    assert resp.status_code == 200
    assert await db.get(ItemEquipamento, item_id) is None

    registros = [r for r in await _auditoria(db, item_id) if r.acao == "DELETE"]
    assert len(registros) == 1
    assert registros[0].justificativa == "duplicado no cadastro"


# ------------------------------------------------------------------ #
#  Controle de acesso
# ------------------------------------------------------------------ #

@pytest.mark.parametrize(
    "metodo,caminho,corpo",
    [
        ("patch", "/slots/{slot}", {"descricao": "x"}),
        ("post", "/slots/{slot}/remover", {"justificativa": "motivo qualquer"}),
        ("post", "/slots/{slot}/inativar", None),
        ("post", "/slots/{slot}/reativar", None),
        ("patch", "/itens/{item}", {"numero_serie": "SN-X"}),
        ("post", "/itens/{item}/excluir", {"justificativa": "motivo qualquer"}),
    ],
)
@pytest.mark.asyncio
async def test_encarregado_nao_escreve_dados_mestres(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict,
    metodo: str, caminho: str, corpo: dict | None,
):
    """Toda escrita de dado mestre é exclusiva do ADMINISTRADOR.

    A UI esconde os botões, mas quem decide é o backend — a verificação
    client-side não é barreira de segurança.
    """
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id)
    item = await _criar_item(db, modelo.id)

    url = EQUIP_URL + caminho.format(slot=slot.id, item=item.id)
    kwargs = {"headers": usuario_encarregado_e_token["headers"]}
    if corpo is not None:
        kwargs["json"] = corpo

    resp = await getattr(client, metodo)(url, **kwargs)
    assert resp.status_code == 403, f"{metodo.upper()} {caminho} deveria ser 403"


@pytest.mark.asyncio
async def test_encarregado_nao_consulta_auditoria(
    client: AsyncClient, usuario_encarregado_e_token: dict
):
    resp = await client.get(
        f"{EQUIP_URL}/auditoria", headers=usuario_encarregado_e_token["headers"]
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------ #
#  Consulta da trilha
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_consultar_auditoria_filtrada_por_entidade(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """A rota /auditoria tem UM segmento e concorre com /{equipamento_id}.

    Se for declarada depois dela, o FastAPI resolve "auditoria" como
    equipamento_id, tenta convertê-lo em UUID e devolve 422 — o endpoint
    nunca é alcançado.
    """
    headers = usuario_e_token["headers"]
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "TRILHA1")
    await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}", json={"descricao": "primeira"}, headers=headers
    )
    await client.patch(
        f"{EQUIP_URL}/slots/{slot.id}", json={"descricao": "segunda"}, headers=headers
    )

    resp = await client.get(
        f"{EQUIP_URL}/auditoria?entidade=SLOT&entidade_id={slot.id}", headers=headers
    )
    assert resp.status_code == 200, "rota capturada por /{equipamento_id}?"

    registros = resp.json()
    assert len(registros) == 2
    assert {r["acao"] for r in registros} == {"UPDATE"}
    # Prova de que o JSON persistido é lido de volta sem erro de serialização
    # (UUID e datetime precisam ter virado str na gravação).
    assert registros[0]["valores_novos"]["descricao"] in ("primeira", "segunda")


# ------------------------------------------------------------------ #
#  Efeitos na grade de inventário
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_ordem_exibicao_reordena_a_grade(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    """`ordem_exibicao` só funciona se o sort em Python de
    `listar_inventario_aeronave` considerar o campo — um ORDER BY na query
    seria sobrescrito por ele."""
    headers = usuario_e_token["headers"]
    aeronave = await _criar_aeronave(db)
    modelo = await _criar_modelo(db)
    # Nomes em ordem alfabética inversa à ordem desejada.
    slot_a = await _criar_slot(db, modelo.id, "AAA")
    slot_z = await _criar_slot(db, modelo.id, "ZZZ")

    await client.patch(f"{EQUIP_URL}/slots/{slot_z.id}", json={"ordem_exibicao": 1}, headers=headers)
    await client.patch(f"{EQUIP_URL}/slots/{slot_a.id}", json={"ordem_exibicao": 2}, headers=headers)

    resp = await client.get(f"{EQUIP_URL}/inventario/{aeronave.id}", headers=headers)
    assert resp.status_code == 200
    ordem = [linha["nome_posicao"] for linha in resp.json()]
    assert ordem.index("ZZZ") < ordem.index("AAA"), "ordem_exibicao foi ignorada"


@pytest.mark.asyncio
async def test_slot_inativo_some_da_grade_de_inventario(
    client: AsyncClient, db: AsyncSession, usuario_e_token: dict
):
    headers = usuario_e_token["headers"]
    aeronave = await _criar_aeronave(db)
    modelo = await _criar_modelo(db)
    slot = await _criar_slot(db, modelo.id, "SUMIR1")

    antes = await client.get(f"{EQUIP_URL}/inventario/{aeronave.id}", headers=headers)
    assert "SUMIR1" in [linha["nome_posicao"] for linha in antes.json()]

    await client.post(f"{EQUIP_URL}/slots/{slot.id}/inativar", headers=headers)

    depois = await client.get(f"{EQUIP_URL}/inventario/{aeronave.id}", headers=headers)
    assert "SUMIR1" not in [linha["nome_posicao"] for linha in depois.json()]


# ------------------------------------------------------------------ #
#  Tela de gestão em /configuracoes — fumaça
#
#  Segue o padrão de test_publicacoes_edicoes.py: sem verificação visual,
#  o que dá para amarrar por teste é a ligação entre template e JS. Um id
#  renomeado no HTML deixa o addEventListener sem alvo e o botão passa a
#  não fazer nada — silenciosamente, sem erro em lugar nenhum.
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_configuracoes_traz_o_botao_de_slots_e_carrega_o_js(
    client_autenticado: AsyncClient
):
    resposta = await client_autenticado.get("/configuracoes")
    assert resposta.status_code == 200
    html = resposta.text

    assert 'id="btn-gerenciar-slots"' in html
    assert "configuracoes_inventario.js" in html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "elemento_id",
    [
        "modal-slots",
        "lista-slots-body",
        "chk-incluir-inativos",
        "btn-novo-slot",
        "modal-form-slot",
        "form-slot",
        "slot-nome-posicao",
        "slot-sistema",
        "slot-posicao-xlsx",
        "slot-modelo-id",
        "slot-descricao",
        "slot-ordem",
        "modal-confirmar-exclusao",
        "exclusao-justificativa",
        "btn-confirmar-exclusao",
        "modal-historico",
        "lista-historico",
    ],
)
async def test_configuracoes_tem_os_alvos_que_o_js_de_inventario_procura(
    client_autenticado: AsyncClient, elemento_id: str
):
    html = (await client_autenticado.get("/configuracoes")).text
    assert f'id="{elemento_id}"' in html


@pytest.mark.asyncio
async def test_template_de_configuracoes_sem_handler_inline(client_autenticado: AsyncClient):
    """A CSP do projeto é `script-src 'self'` sem 'unsafe-inline': um
    onclick no HTML simplesmente não executa, e o botão fica inerte."""
    html = (await client_autenticado.get("/configuracoes")).text
    assert "onclick=" not in html
