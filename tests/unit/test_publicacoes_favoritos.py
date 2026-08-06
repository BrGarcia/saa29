"""
tests/unit/test_publicacoes_favoritos.py
Favoritos transversais (acervo A + acervo B) e a busca do FIM por ATA — M3.

Favoritos usam PDFs reais de `tests/fixtures/fim/` (amostra versionada do
acervo — ver o README de lá) via o mesmo helper de
indexação de `tests/integration/test_publicacoes_busca.py`, porque
`documento_id` precisa existir de verdade para exercitar o `CheckConstraint`
XOR e a `UniqueConstraint` do achado B1.
"""

import shutil
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicacoes import catalog, service
from tests.integration.test_publicacoes_busca import EDICAO, _indexar

URL_AVULSAS = "/publicacoes/api/avulsas"
URL_FAVORITOS = "/publicacoes/api/favoritos"


NOME_PDF_ATA_36 = "FIM1741_36-21-00-810-802-A-.PDF"
"""Corresponde a `36-21-00-810-802-A`, que TEM mensagem em fim.json (EICAS1/2 055)."""


@pytest.fixture
def entrada(tmp_path: Path) -> Path:
    destino = tmp_path / "fim"
    destino.mkdir()
    shutil.copy(Path("tests/fixtures/fim") / NOME_PDF_ATA_36, destino / NOME_PDF_ATA_36)
    return destino


@pytest_asyncio.fixture
async def documento_real(entrada: Path, tmp_path: Path, db: AsyncSession):
    """Um `ManualDocumento` real, gravado no banco principal via o indexador."""
    indice = tmp_path / "catalog.db"
    payloads = _indexar(entrada, indice)
    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    await service.sincronizar_catalogo(db, edicao, payloads)
    return payloads[0].documentos[0]


def payload_bs(**overrides) -> dict:
    base = {
        "tipo": "BS",
        "numero": "500-24-0001",
        "ano": 2026,
        "data_emissao": "2026-01-10",
        "data_recebimento": "2026-01-15",
        "emissor": "Embraer",
        "titulo": "Boletim de teste",
        "ementa": "Ementa de teste com pelo menos vinte caracteres.",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Favoritar documento do acervo A
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favoritar_documento_sucesso(
    client_autenticado: AsyncClient, documento_real
):
    resposta = await client_autenticado.post(
        URL_FAVORITOS, json={"documento_id": str(documento_real.id)}
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["documento_id"] == str(documento_real.id)
    assert corpo["avulsa_id"] is None


@pytest.mark.asyncio
async def test_favoritar_documento_e_idempotente(
    client_autenticado: AsyncClient, documento_real
):
    """B1: favoritar duas vezes devolve o mesmo favorito, não 409."""
    primeiro = (
        await client_autenticado.post(
            URL_FAVORITOS, json={"documento_id": str(documento_real.id)}
        )
    ).json()
    segundo = (
        await client_autenticado.post(
            URL_FAVORITOS, json={"documento_id": str(documento_real.id)}
        )
    ).json()
    assert primeiro["id"] == segundo["id"]


@pytest.mark.asyncio
async def test_favoritar_documento_inexistente_retorna_404(client_autenticado: AsyncClient):
    resposta = await client_autenticado.post(
        URL_FAVORITOS, json={"documento_id": str(uuid.uuid4())}
    )
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# Favoritar publicação avulsa
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favoritar_avulsa_sucesso(client_autenticado: AsyncClient):
    avulsa = (await client_autenticado.post(URL_AVULSAS, json=payload_bs())).json()

    resposta = await client_autenticado.post(
        URL_FAVORITOS, json={"avulsa_id": avulsa["id"]}
    )
    assert resposta.status_code == 201
    assert resposta.json()["avulsa_id"] == avulsa["id"]


# --------------------------------------------------------------------------
# XOR (achado B1)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favorito_sem_nenhum_alvo_retorna_400(client_autenticado: AsyncClient):
    resposta = await client_autenticado.post(URL_FAVORITOS, json={})
    assert resposta.status_code == 400


@pytest.mark.asyncio
async def test_favorito_com_os_dois_alvos_retorna_400(
    client_autenticado: AsyncClient, documento_real
):
    avulsa = (await client_autenticado.post(URL_AVULSAS, json=payload_bs())).json()
    resposta = await client_autenticado.post(
        URL_FAVORITOS,
        json={"documento_id": str(documento_real.id), "avulsa_id": avulsa["id"]},
    )
    assert resposta.status_code == 400


# --------------------------------------------------------------------------
# Listar e remover
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_favoritos_do_usuario(client_autenticado: AsyncClient, documento_real):
    avulsa = (await client_autenticado.post(URL_AVULSAS, json=payload_bs())).json()
    await client_autenticado.post(URL_FAVORITOS, json={"documento_id": str(documento_real.id)})
    await client_autenticado.post(URL_FAVORITOS, json={"avulsa_id": avulsa["id"]})

    resposta = await client_autenticado.get(URL_FAVORITOS)
    assert resposta.status_code == 200
    assert len(resposta.json()) == 2


@pytest.mark.asyncio
async def test_remover_favorito(client_autenticado: AsyncClient, documento_real):
    criado = (
        await client_autenticado.post(
            URL_FAVORITOS, json={"documento_id": str(documento_real.id)}
        )
    ).json()

    resposta = await client_autenticado.delete(f"{URL_FAVORITOS}/{criado['id']}")
    assert resposta.status_code == 204

    listagem = (await client_autenticado.get(URL_FAVORITOS)).json()
    assert listagem == []


@pytest.mark.asyncio
async def test_remover_favorito_inexistente_retorna_404(client_autenticado: AsyncClient):
    resposta = await client_autenticado.delete(f"{URL_FAVORITOS}/{uuid.uuid4()}")
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_remover_favorito_de_outro_usuario_retorna_404(
    client: AsyncClient,
    db: AsyncSession,
    usuario_encarregado_e_token: dict,
    documento_real,
):
    """
    Um favorito é pessoal — não pode ser removido por outro usuário.

    Setup via `service` direto (não `client_autenticado`): o override de
    `get_current_user` daquele fixture ignora qualquer header de
    Authorization pelo resto do teste, então cadastrar com um usuário e
    tentar agir como outro no MESMO teste exigiria dois processos de auth
    que não coexistem nesse harness (mesma armadilha de
    `test_publicacoes_avulsas.py::_inserir_avulsa_direto`).
    """
    from app.modules.auth.models import Usuario
    from app.modules.auth.security import hash_senha

    dono = Usuario(
        nome="Dono do favorito", posto="Sgt", especialidade="ELT", funcao="MANTENEDOR",
        ramal="1111", username="dono.favorito", senha_hash=hash_senha("x"),
    )
    db.add(dono)
    await db.flush()

    favorito = await service.favoritar_documento(db, dono.id, documento_real.id)

    resposta = await client.delete(
        f"{URL_FAVORITOS}/{favorito.id}", headers=usuario_encarregado_e_token["headers"]
    )
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# FIM por ATA (bloco no detalhe da pane, M3 tarefa 1)
# --------------------------------------------------------------------------


@pytest_asyncio.fixture
async def com_fim_map_ata(entrada: Path, tmp_path: Path, db: AsyncSession):
    indice = tmp_path / "catalog.db"
    payloads = _indexar(entrada, indice)
    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    await service.sincronizar_catalogo(db, edicao, payloads)

    pares = [
        p
        for p in catalog.carregar_fim_json(Path("docs/fim.json"))
        if catalog.nome_pdf_de_procedimento(p[1]) == NOME_PDF_ATA_36
    ]
    assert pares, "pré-condição: precisa existir ao menos uma mensagem para este procedimento"
    resultado = await service.sincronizar_fim_map(db, pares, edicao)
    return pares, resultado


@pytest.mark.asyncio
async def test_fim_por_ata_encontra_procedimento_do_capitulo(
    client_autenticado: AsyncClient, com_fim_map_ata
):
    resposta = await client_autenticado.get("/publicacoes/api/fim/por-ata/36")
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["total"] > 0
    assert all(r["procedimento"].startswith("36-") for r in corpo["results"])
    assert any(r["doc_id"] is not None for r in corpo["results"])


@pytest.mark.asyncio
async def test_fim_por_ata_sem_correspondencia_devolve_lista_vazia(
    client_autenticado: AsyncClient, com_fim_map_ata
):
    resposta = await client_autenticado.get("/publicacoes/api/fim/por-ata/99")
    assert resposta.status_code == 200
    assert resposta.json()["total"] == 0


# --------------------------------------------------------------------------
# Duplicação por hash entre edições (M4 tarefa 5)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicacao_sem_edicao_anterior_devolve_zero(
    db: AsyncSession, documento_real
):
    """Só existe a edição vigente (piloto-fim) — não há o que comparar ainda."""
    medicao = await service.medir_duplicacao_entre_edicoes(db)
    assert medicao["anterior"] is None
    assert medicao["duplicados_por_hash"] == 0


@pytest.mark.asyncio
async def test_duplicacao_conta_hashes_repetidos_entre_vigente_e_anterior(
    entrada: Path, tmp_path: Path, db: AsyncSession, documento_real
):
    """
    Simula uma segunda edição (ANTERIOR) reindexando o MESMO PDF sob outro
    rótulo — mesmo conteúdo, mesmo hash, IDs diferentes (achado B2). É
    exatamente o cenário real: duas edições retidas online compartilhando a
    maioria dos arquivos entre uma publicação anual e outra.
    """
    from app.shared.core.enums import StatusEdicao

    indice_anterior = tmp_path / "anterior.db"
    payload_anterior = _indexar(entrada, indice_anterior, edicao_rotulo="edicao-anterior")
    edicao_anterior = await service.obter_ou_criar_edicao(
        db, "edicao-anterior", status=StatusEdicao.ANTERIOR
    )
    await service.sincronizar_catalogo(db, edicao_anterior, payload_anterior)

    medicao = await service.medir_duplicacao_entre_edicoes(db)

    assert medicao["vigente"] == EDICAO
    assert medicao["anterior"] == "edicao-anterior"
    assert medicao["duplicados_por_hash"] == 1  # o único documento da amostra, mesmo conteúdo
