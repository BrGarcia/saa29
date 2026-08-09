"""
tests/unit/test_publicacoes_avulsas.py
Publicações avulsas (BO/BS/NPO/BT) — acervo B do módulo `publicacoes` (M2).

Independente do M1: nada aqui toca `catalog.db` nem `pypdfium2`, só o banco
principal — por isso estes testes rodam como `unit`, não `integration`.

RBAC coberto com os fixtures que já existem em conftest.py:
`client_autenticado` usa `dados_usuario_valido`, que é ADMINISTRADOR por
padrão — cobre o teto da matriz. `usuario_mantenedor_e_token` e
`usuario_encarregado_e_token` cobrem os dois lados da fronteira
`EncarregadoInspetorOuAdmin` (Mantenedor fora, Encarregado dentro); INSPETOR
não tem fixture própria mas é tratado de forma idêntica a ENCARREGADO pelo
mesmo `require_role(*roles)`, então testar um dos dois já cobre a lógica.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.aeronaves.models import Aeronave
from app.modules.panes.models import SistemaAta
from app.modules.publicacoes.models import PublicacaoAvulsa, PublicacaoAvulsaAeronave

URL = "/publicacoes/api/avulsas"


def payload_bs(**overrides) -> dict:
    base = {
        "tipo": "BS",
        "numero": "314-24-0021",
        "ano": 2026,
        "data_emissao": "2026-01-10",
        "data_recebimento": "2026-01-15",
        "emissor": "Embraer",
        "titulo": "Boletim de Serviço — sangria do compressor",
        "ementa": "Procedimento de inspeção da válvula de sangria do compressor do motor.",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Cadastro
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_criar_avulsa_sucesso(client_autenticado: AsyncClient):
    resposta = await client_autenticado.post(URL, json=payload_bs())
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo"] == "BS"
    assert corpo["numero"] == "314-24-0021"
    assert corpo["status"] == "VIGENTE"
    assert corpo["ativo"] is True
    assert uuid.UUID(corpo["id"])


@pytest.mark.asyncio
async def test_criar_avulsa_duplicata_retorna_409(client_autenticado: AsyncClient):
    await client_autenticado.post(URL, json=payload_bs())
    resposta = await client_autenticado.post(URL, json=payload_bs())
    assert resposta.status_code == 409


@pytest.mark.asyncio
async def test_criar_avulsa_ementa_curta_retorna_422(client_autenticado: AsyncClient):
    """R15: a ementa é o principal insumo de busca — comprimento mínimo no schema."""
    resposta = await client_autenticado.post(URL, json=payload_bs(ementa="curta"))
    assert resposta.status_code == 422


# --------------------------------------------------------------------------
# RBAC (D-S6)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_criar_avulsa_mantenedor_retorna_403(
    client: AsyncClient, usuario_mantenedor_e_token: dict
):
    resposta = await client.post(
        URL, json=payload_bs(), headers=usuario_mantenedor_e_token["headers"]
    )
    assert resposta.status_code == 403


@pytest.mark.asyncio
async def test_criar_avulsa_encarregado_sucesso(
    client: AsyncClient, usuario_encarregado_e_token: dict
):
    resposta = await client.post(
        URL, json=payload_bs(), headers=usuario_encarregado_e_token["headers"]
    )
    assert resposta.status_code == 201


async def _inserir_avulsa_direto(db: AsyncSession, usuario_id: uuid.UUID) -> PublicacaoAvulsa:
    """
    Insere via ORM, sem passar pela API.

    Usado nos testes de fronteira de RBAC que precisam de duas identidades
    diferentes no mesmo teste: `client_autenticado` SUBSTITUI inteiramente a
    dependência `get_current_user` (ignora qualquer header), então cadastrar
    com `client_autenticado` (Admin) e depois tentar outra ação com
    `client` + header de outro papel, no MESMO teste, testaria sempre o
    usuário do override — nunca o do header. Contornado inserindo o dado de
    setup direto no banco, sem passar pela camada HTTP.
    """
    avulsa = PublicacaoAvulsa(
        tipo="BS",
        numero="314-24-0021",
        ano=2026,
        data_emissao=date(2026, 1, 10),
        data_recebimento=date(2026, 1, 15),
        emissor="Embraer",
        titulo="Boletim de Serviço — sangria do compressor",
        ementa="Procedimento de inspeção da válvula de sangria do compressor do motor.",
        cadastrada_por_id=usuario_id,
    )
    db.add(avulsa)
    await db.flush()
    return avulsa


@pytest.mark.asyncio
async def test_excluir_avulsa_encarregado_retorna_403(
    client: AsyncClient, db: AsyncSession, usuario_encarregado_e_token: dict
):
    """D-S6: exclusão é privilégio exclusivo de Admin, mesmo para quem cadastra."""
    avulsa = await _inserir_avulsa_direto(db, usuario_encarregado_e_token["usuario"].id)

    resposta = await client.delete(
        f"{URL}/{avulsa.id}", headers=usuario_encarregado_e_token["headers"]
    )
    assert resposta.status_code == 403


@pytest.mark.asyncio
async def test_upload_anexo_mantenedor_retorna_403(
    client: AsyncClient, db: AsyncSession, usuario_mantenedor_e_token: dict
):
    avulsa = await _inserir_avulsa_direto(db, usuario_mantenedor_e_token["usuario"].id)

    resposta = await client.post(
        f"{URL}/{avulsa.id}/anexos",
        files={"arquivo": ("bo.pdf", b"%PDF-1.4 conteudo", "application/pdf")},
        headers=usuario_mantenedor_e_token["headers"],
    )
    assert resposta.status_code == 403


# --------------------------------------------------------------------------
# Vigência e substituição
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_atualizar_avulsa_corrige_metadados(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()

    resposta = await client_autenticado.patch(
        f"{URL}/{criada['id']}", json={"titulo": "Título corrigido"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["titulo"] == "Título corrigido"
    assert resposta.json()["status"] == "VIGENTE"  # inalterado


@pytest.mark.asyncio
async def test_substituicao_sem_id_alvo_retorna_409(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    resposta = await client_autenticado.patch(
        f"{URL}/{criada['id']}", json={"status": "SUBSTITUIDO"}
    )
    assert resposta.status_code == 409


@pytest.mark.asyncio
async def test_substituicao_encadeia_para_a_nova_publicacao(client_autenticado: AsyncClient):
    antiga = (await client_autenticado.post(URL, json=payload_bs())).json()
    nova = (
        await client_autenticado.post(URL, json=payload_bs(numero="314-24-0022"))
    ).json()

    resposta = await client_autenticado.patch(
        f"{URL}/{antiga['id']}",
        json={"status": "SUBSTITUIDO", "substituida_por_id": nova["id"]},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "SUBSTITUIDO"
    assert corpo["substituida_por_id"] == nova["id"]

    # A publicação nova permanece intocada — a cadeia é unidirecional.
    ainda_vigente = (await client_autenticado.get(f"{URL}/{nova['id']}")).json()
    assert ainda_vigente["status"] == "VIGENTE"


@pytest.mark.asyncio
async def test_substituicao_com_alvo_inexistente_retorna_404(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    resposta = await client_autenticado.patch(
        f"{URL}/{criada['id']}",
        json={"status": "SUBSTITUIDO", "substituida_por_id": str(uuid.uuid4())},
    )
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# Soft delete
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluir_avulsa_soft_delete(
    client_autenticado: AsyncClient, db: AsyncSession
):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()

    resposta = await client_autenticado.delete(f"{URL}/{criada['id']}")
    assert resposta.status_code == 204

    # A linha continua no banco, só marcada — verificado ANTES do próximo
    # passo de propósito: o `override_get_db` de teste faz rollback em
    # qualquer exceção que atravesse a dependência (`except Exception: await
    # db.rollback()`), e o 404 esperado no passo seguinte É uma dessas
    # exceções (EntidadeNaoEncontradaError). Fazer a leitura crua depois do
    # 404 desfaria esta mesma verificação — não é bug do serviço, é o
    # `db`/`client_autenticado` compartilhando uma única transação entre
    # chamadas HTTP sequenciais do teste.
    linha = (
        await db.execute(
            select(PublicacaoAvulsa).where(PublicacaoAvulsa.id == uuid.UUID(criada["id"]))
        )
    ).scalar_one()
    assert linha.ativo is False

    # Some da busca/consulta padrão — é a última asserção do teste porque o
    # 404 aciona o rollback descrito acima.
    assert (await client_autenticado.get(f"{URL}/{criada['id']}")).status_code == 404


# --------------------------------------------------------------------------
# Busca por metadados (gate do M2)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_busca_por_numero(client_autenticado: AsyncClient):
    await client_autenticado.post(URL, json=payload_bs())
    resposta = await client_autenticado.get(URL, params={"numero": "314-24-0021"})
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["numero"] == "314-24-0021"


@pytest.mark.asyncio
async def test_busca_por_ano(client_autenticado: AsyncClient):
    await client_autenticado.post(URL, json=payload_bs())
    await client_autenticado.post(URL, json=payload_bs(numero="OUTRO-001", ano=2020))

    corpo = (await client_autenticado.get(URL, params={"ano": 2026})).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["ano"] == 2026


@pytest.mark.asyncio
async def test_busca_por_palavra_da_ementa(client_autenticado: AsyncClient):
    await client_autenticado.post(URL, json=payload_bs())
    corpo = (
        await client_autenticado.get(URL, params={"texto": "sangria"})
    ).json()
    assert corpo["total"] == 1
    assert "sangria" in corpo["results"][0]["snippet"].lower().replace("\x02", "").replace("\x03", "")


@pytest.mark.asyncio
async def test_busca_por_ata(client_autenticado: AsyncClient, db: AsyncSession):
    ata = SistemaAta(codigo="36", descricao="Sistema Pneumático")
    db.add(ata)
    await db.flush()

    criada = (
        await client_autenticado.post(URL, json=payload_bs())
    ).json()
    await client_autenticado.patch(
        f"{URL}/{criada['id']}", json={"sistema_ata_id": str(ata.id)}
    )

    corpo = (await client_autenticado.get(URL, params={"ata": "36"})).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["numero"] == "314-24-0021"

    vazio = (await client_autenticado.get(URL, params={"ata": "99"})).json()
    assert vazio["total"] == 0


@pytest.mark.asyncio
async def test_busca_nao_retorna_inativas_por_padrao(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    await client_autenticado.delete(f"{URL}/{criada['id']}")

    corpo = (await client_autenticado.get(URL, params={"numero": "314-24-0021"})).json()
    assert corpo["total"] == 0

    com_inativas = (
        await client_autenticado.get(
            URL, params={"numero": "314-24-0021", "incluir_inativas": True}
        )
    ).json()
    assert com_inativas["total"] == 1


@pytest.mark.asyncio
async def test_busca_query_status_nao_sombreia_fastapi_status(client_autenticado: AsyncClient):
    """C3: `status` é `alias`, não o nome do parâmetro — trap de panes/router.py."""
    await client_autenticado.post(URL, json=payload_bs())
    resposta = await client_autenticado.get(URL, params={"status": "VIGENTE"})
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 1


# --------------------------------------------------------------------------
# Aplicabilidade (N:N, §9.2)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aplicabilidade_vazia_significa_frota_inteira(
    client_autenticado: AsyncClient, db: AsyncSession
):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    vinculos = (
        await db.execute(
            select(PublicacaoAvulsaAeronave).where(
                PublicacaoAvulsaAeronave.avulsa_id == uuid.UUID(criada["id"])
            )
        )
    ).scalars().all()
    assert vinculos == []


@pytest.mark.asyncio
async def test_aplicabilidade_especifica_grava_vinculo(
    client_autenticado: AsyncClient, db: AsyncSession
):
    # Matrícula com sufixo aleatório: um valor hardcoded já colidiu, nesta
    # mesma sessão de implementação, com `tests/architecture/test_performance_audit.py`
    # (que também usa "5999") — os dois arquivos são isolados por transação,
    # mas o sufixo remove a dependência de nenhum outro teste do repositório
    # inteiro escolher o mesmo valor por coincidência.
    aeronave = Aeronave(
        serial_number=f"SN-PUB-{uuid.uuid4().hex[:8]}",
        matricula=f"PUB{uuid.uuid4().hex[:6]}",
        data_inicio_operacao=date(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()

    criada = (
        await client_autenticado.post(
            URL, json=payload_bs(aplicabilidade=[str(aeronave.id)])
        )
    ).json()

    vinculos = (
        await db.execute(
            select(PublicacaoAvulsaAeronave).where(
                PublicacaoAvulsaAeronave.avulsa_id == uuid.UUID(criada["id"])
            )
        )
    ).scalars().all()
    assert len(vinculos) == 1
    assert vinculos[0].aeronave_id == aeronave.id


# --------------------------------------------------------------------------
# Upload de anexo (fora do pipeline de imagem)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_anexo_pdf_sucesso(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()

    resposta = await client_autenticado.post(
        f"{URL}/{criada['id']}/anexos",
        files={"arquivo": ("bs_314.pdf", b"%PDF-1.4\n" + b"x" * 200, "application/pdf")},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nome_original"] == "bs_314.pdf"
    assert corpo["tamanho_bytes"] > 0
    assert corpo["principal"] is False


@pytest.mark.asyncio
async def test_upload_anexo_tipo_invalido_retorna_422(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()

    resposta = await client_autenticado.post(
        f"{URL}/{criada['id']}/anexos",
        files={"arquivo": ("nota.txt", b"so texto puro", "text/plain")},
    )
    assert resposta.status_code == 422


@pytest.mark.asyncio
async def test_upload_anexo_excede_limite_retorna_413(
    client_autenticado: AsyncClient, monkeypatch
):
    from app.modules.publicacoes import router as publicacoes_router

    class _SettingsFake:
        publicacoes_avulsas_max_upload_mb = 0.0001  # ~100 bytes

    monkeypatch.setattr(publicacoes_router, "get_settings", lambda: _SettingsFake())

    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    conteudo_grande = b"%PDF-1.4\n" + b"x" * 5000

    resposta = await client_autenticado.post(
        f"{URL}/{criada['id']}/anexos",
        files={"arquivo": ("grande.pdf", conteudo_grande, "application/pdf")},
    )
    assert resposta.status_code == 413


@pytest.mark.asyncio
async def test_upload_anexo_avulsa_inexistente_retorna_404(client_autenticado: AsyncClient):
    resposta = await client_autenticado.post(
        f"{URL}/{uuid.uuid4()}/anexos",
        files={"arquivo": ("bo.pdf", b"%PDF-1.4 x", "application/pdf")},
    )
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_anexo_entrega_o_arquivo(client_autenticado: AsyncClient):
    criada = (await client_autenticado.post(URL, json=payload_bs())).json()
    anexo = (
        await client_autenticado.post(
            f"{URL}/{criada['id']}/anexos",
            files={"arquivo": ("bo.pdf", b"%PDF-1.4 conteudo real", "application/pdf")},
        )
    ).json()

    resposta = await client_autenticado.get(
        f"/publicacoes/avulsas/{criada['id']}/anexo/{anexo['id']}"
    )
    assert resposta.status_code == 200
    assert resposta.content.startswith(b"%PDF")


# --------------------------------------------------------------------------
# Gate do M2 (04_plano_de_execucao.md): achar por número, por ATA e por
# palavra da ementa — os três num único cadastro.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagina_avulsas_retorna_200_autenticado(client_autenticado: AsyncClient):
    resposta = await client_autenticado.get("/publicacoes/avulsas")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


@pytest.mark.asyncio
async def test_gate_m2_encontrar_por_numero_ata_e_ementa(
    client_autenticado: AsyncClient, db: AsyncSession
):
    ata = SistemaAta(codigo="36", descricao="Sistema Pneumático")
    db.add(ata)
    await db.flush()

    criada = (
        await client_autenticado.post(
            URL, json=payload_bs(sistema_ata_id=str(ata.id))
        )
    ).json()
    await client_autenticado.post(
        f"{URL}/{criada['id']}/anexos",
        files={"arquivo": ("bs_escaneado.pdf", b"%PDF-1.4 escaneado", "application/pdf")},
    )

    por_numero = (
        await client_autenticado.get(URL, params={"numero": "314-24-0021"})
    ).json()
    por_ata = (await client_autenticado.get(URL, params={"ata": "36"})).json()
    por_ementa = (
        await client_autenticado.get(URL, params={"texto": "compressor"})
    ).json()

    for resultado in (por_numero, por_ata, por_ementa):
        assert resultado["total"] == 1
        assert resultado["results"][0]["id"] == criada["id"]
