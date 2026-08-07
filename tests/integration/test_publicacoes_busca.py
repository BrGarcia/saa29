"""
tests/integration/test_publicacoes_busca.py
Busca do acervo de manuais, ponta a ponta: PDF real → catalog.db → API.

Roda no CI: os PDFs vêm de `tests/fixtures/fim/`, uma amostra de 4 arquivos
(172 KB) copiada do acervo e versionada por exceção explícita no `.gitignore` —
ao contrário do acervo de 1 GB, que não é versionado. Cada teste indexa a
amostra em `tmp_path`, então nada aqui depende de estado deixado por outro teste
nem do `var/publicacoes/catalog.*.db` da máquina do desenvolvedor.

Três dos testes daqui existem por causa de bugs que falham **em silêncio**
(07_revisao_pre_implementacao.md) e que, sem eles, só apareceriam em produção:

- B5 — formato de UUID divergente entre os dois bancos: comparação crua devolve
  zero resultados sem erro;
- B7 — FTS5 de conteúdo externo não se popula sozinho, e `count(*)` devolve o
  número certo enquanto toda busca retorna vazio;
- E-02 — um PDF corrompido no meio do lote não pode abortar a indexação.
"""

import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicacoes import catalog, search, service
from scripts.publicacoes import indexar

FIM = Path("tests/fixtures/fim")
"""Amostra versionada do acervo — ver `tests/fixtures/fim/README.md`."""

FIM_JSON = Path("docs/fim.json")
"""
Mapa mensagem→procedimento, versionado à parte da amostra por ser texto (92 KB,
1.377 pares). Fica em `docs/`, não em `tests/fixtures/`, porque não é dado de
teste: é referência do domínio, consumida também em produção.
"""

# PDFs escolhidos porque são pequenos e o conteúdo é conhecido: os dois
# primeiros tratam de sangria de ar do motor (ATA 36), que é o termo usado pelo
# CA-04.
PDFS_AMOSTRA = [
    "FIM1741_36-11-00-810-801-A-.PDF",
    "FIM1741_36-21-00-810-801-A-.PDF",
    "FIM1741_21-26-00-810-801-A-.PDF",
]

EDICAO = "teste-fim"
MANUAL = "FIM_1741"


@pytest.fixture
def entrada(tmp_path: Path) -> Path:
    """Diretório de entrada com uma amostra dos PDFs reais do piloto."""
    destino = tmp_path / "fim"
    destino.mkdir()
    for nome in PDFS_AMOSTRA:
        shutil.copy(FIM / nome, destino / nome)
    return destino


def _indexar(
    entrada: Path, indice: Path, *, edicao_rotulo: str = EDICAO
) -> list[service.ManualPayload]:
    """Roda o indexador (sem banco principal) e devolve os payloads."""
    conn, temporario = indexar.abrir_catalog_novo(indice)
    try:
        manuais = indexar.descobrir_manuais(entrada, MANUAL)
        payloads = [
            indexar.processar_manual(
                manual,
                edicao_rotulo=edicao_rotulo,
                categorias=catalog.carregar_categorias(
                    Path("config/categorias_manuais.toml")
                ),
                acervo=Path("var/publicacoes/acervo"),
                conn=conn,
            )
            for manual in manuais
        ]
        indexar.finalizar_catalog(conn)
    finally:
        conn.close()
    temporario.replace(indice)
    return payloads


@pytest_asyncio.fixture
async def indice_e_catalogo(
    entrada: Path, tmp_path: Path, db: AsyncSession
) -> tuple[Path, service.ManualPayload]:
    """
    Índice de busca + catálogo leve gravados, prontos para consulta.

    O arquivo se chama `catalog.<EDICAO>.db`, e não `catalog.db`, porque é assim
    que a aplicação o procura: o índice é por edição e quem decide qual abrir é
    a edição VIGENTE no banco. Um `catalog.db` aqui ainda funcionaria — pela
    queda para o índice legado — e é exatamente por isso que ele NÃO é usado:
    passaria pelo caminho de compatibilidade em vez do caminho real.
    """
    indice = tmp_path / f"catalog.{EDICAO}.db"
    payloads = _indexar(entrada, indice)

    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    await service.sincronizar_catalogo(db, edicao, payloads)
    return indice, payloads[0]


# --------------------------------------------------------------------------
# B7 — o índice só é aceito por busca real
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_indice_responde_a_busca_real(indice_e_catalogo):
    """
    Aceite do índice por MATCH, nunca por contagem.

    `count(*) FROM pages_fts` devolve o número certo mesmo sem o `rebuild`,
    porque lê através da tabela de conteúdo — é exatamente a métrica que não
    pega o B7.
    """
    indice, _ = indice_e_catalogo
    resposta = await search.buscar(indice, "sangria")
    assert resposta["total"] > 0
    assert resposta["results"]


def test_sem_rebuild_a_busca_volta_vazia_e_a_contagem_engana(entrada, tmp_path):
    """
    Documenta o B7 de forma executável: sem `rebuild`, `count(*)` acerta e o
    `MATCH` devolve zero. É a razão de `finalizar_catalog` não ser opcional.
    """
    indice = tmp_path / "sem_rebuild.db"
    conn, temporario = indexar.abrir_catalog_novo(indice)
    try:
        for manual in indexar.descobrir_manuais(entrada, MANUAL):
            indexar.processar_manual(
                manual,
                edicao_rotulo=EDICAO,
                categorias={"_default": catalog.CategoriaManual("Outros", "{codigo}")},
                acervo=Path("var/publicacoes/acervo"),
                conn=conn,
            )
        # De propósito: NÃO chama finalizar_catalog.
        paginas = conn.execute("SELECT count(*) FROM pages").fetchone()[0]
        fts = conn.execute("SELECT count(*) FROM pages_fts").fetchone()[0]
        casam = conn.execute(
            "SELECT count(*) FROM pages_fts WHERE pages_fts MATCH 'sangria'"
        ).fetchone()[0]
    finally:
        conn.close()
        temporario.unlink(missing_ok=True)

    assert paginas > 0
    assert fts == paginas   # a contagem "passa"...
    assert casam == 0       # ...enquanto a busca não acha nada


# --------------------------------------------------------------------------
# B5 — round-trip de UUID entre catalog.db e banco principal
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_round_trip_de_uuid_entre_os_dois_bancos(
    indice_e_catalogo, db: AsyncSession
):
    """
    O contrato de identidade da §2.2.1, afirmado ponta a ponta.

    Busca → `document_id` (string canônica do catalog.db) → `uuid.UUID(...)` →
    lookup no banco principal. Sem a conversão, o lookup devolve None **sem
    erro**, e o sintoma aponta para "índice vazio" em vez de para o formato.
    """
    indice, _ = indice_e_catalogo
    resposta = await search.buscar(indice, "sangria", limit=1)
    bruto = resposta["results"][0]["document_id"]

    assert isinstance(bruto, str)
    assert "-" in bruto, "catalog.db deve gravar o UUID na forma canônica"

    documento = await service.obter_documento(db, uuid.UUID(bruto))
    assert documento is not None
    assert documento.id == uuid.UUID(bruto)
    assert documento.manual.codigo == MANUAL


@pytest.mark.asyncio
async def test_uuid_do_sqlite_nao_bate_com_a_forma_canonica(indice_e_catalogo, db):
    """
    Guarda do B5: mostra POR QUE a conversão é obrigatória.

    O tipo `Uuid` grava no SQLite como hex de 32 caracteres sem hífens; o
    `catalog.db` grava a forma canônica. As duas strings são diferentes, então
    comparar sem `uuid.UUID()` erra em silêncio.
    """
    indice, _ = indice_e_catalogo
    bruto = (await search.buscar(indice, "sangria", limit=1))["results"][0][
        "document_id"
    ]

    armazenado = (
        await db.execute(
            __import__("sqlalchemy").text(
                "SELECT id FROM manuais_documentos WHERE id = :i"
            ),
            {"i": uuid.UUID(bruto).hex},
        )
    ).scalar_one_or_none()

    assert armazenado is not None, "o SQLite armazena o UUID como hex sem hífens"
    assert str(armazenado) != bruto
    assert uuid.UUID(str(armazenado)) == uuid.UUID(bruto)


# --------------------------------------------------------------------------
# Determinismo e idempotência
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reindexar_nao_duplica_nem_muda_ids(
    entrada: Path, tmp_path: Path, db: AsyncSession
):
    """
    CA-07: reindexar a mesma edição preserva os IDs — é o que faz um link
    compartilhado continuar abrindo o mesmo documento.
    """
    indice = tmp_path / "catalog.db"
    primeira = _indexar(entrada, indice)
    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    c1 = await service.sincronizar_catalogo(db, edicao, primeira)

    segunda = _indexar(entrada, indice)
    c2 = await service.sincronizar_catalogo(db, edicao, segunda)

    assert c1["inseridos"] == len(PDFS_AMOSTRA)
    assert c2["inseridos"] == 0
    assert c2["atualizados"] == len(PDFS_AMOSTRA)
    assert c2["removidos"] == 0
    assert {d.id for d in primeira[0].documentos} == {
        d.id for d in segunda[0].documentos
    }


@pytest.mark.asyncio
async def test_documento_removido_do_disco_sai_do_catalogo(
    entrada: Path, tmp_path: Path, db: AsyncSession
):
    """RN-09: o que sumiu do acervo sai do catálogo na reindexação."""
    indice = tmp_path / "catalog.db"
    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    await service.sincronizar_catalogo(db, edicao, _indexar(entrada, indice))

    (entrada / PDFS_AMOSTRA[-1]).unlink()
    contagem = await service.sincronizar_catalogo(db, edicao, _indexar(entrada, indice))

    assert contagem["removidos"] == 1


# --------------------------------------------------------------------------
# E-02 / E-01 — resiliência da extração
# --------------------------------------------------------------------------


def test_pdf_corrompido_nao_derruba_o_lote(entrada: Path, tmp_path: Path):
    """
    E-02: o lote inteiro não pode morrer por causa de um arquivo ruim.

    O documento corrompido continua no catálogo com `has_text=False` — segue
    navegável no viewer (E-01) e apenas não aparece na busca full-text.
    """
    (entrada / "CORROMPIDO.PDF").write_bytes(b"%PDF-1.4 isto nao e um PDF valido")

    payloads = _indexar(entrada, tmp_path / "catalog.db")
    documentos = {d.file_key: d for d in payloads[0].documentos}

    assert len(documentos) == len(PDFS_AMOSTRA) + 1
    assert documentos["CORROMPIDO.PDF"].has_text is False
    assert all(
        documentos[nome].has_text is True for nome in PDFS_AMOSTRA
    ), "os PDFs bons continuam indexados"


def test_documento_sem_texto_nao_gera_pagina_no_indice(entrada: Path, tmp_path: Path):
    """E-01 sai de graça: sem linhas em `pages`, o documento some só da busca."""
    (entrada / "CORROMPIDO.PDF").write_bytes(b"%PDF-1.4 isto nao e um PDF valido")
    indice = tmp_path / "catalog.db"
    payloads = _indexar(entrada, indice)

    corrompido = next(
        d for d in payloads[0].documentos if d.file_key == "CORROMPIDO.PDF"
    )
    conn = sqlite3.connect(indice)
    try:
        paginas = conn.execute(
            "SELECT count(*) FROM pages WHERE document_id = ?", (str(corrompido.id),)
        ).fetchone()[0]
        em_documents = conn.execute(
            "SELECT count(*) FROM documents WHERE document_id = ?",
            (str(corrompido.id),),
        ).fetchone()[0]
    finally:
        conn.close()

    assert paginas == 0          # fora da busca
    assert em_documents == 1     # dentro do catálogo


# --------------------------------------------------------------------------
# CA-04 — acento e caixa
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("termo", ["sangria", "SANGRIA", "sangría", "SaNgRiA"])
async def test_ca04_acento_e_caixa_dao_o_mesmo_conjunto(indice_e_catalogo, termo):
    """`remove_diacritics 2` no tokenizer é o que sustenta isto."""
    indice, _ = indice_e_catalogo
    referencia = await search.buscar(indice, "sangria", limit=100)
    resposta = await search.buscar(indice, termo, limit=100)

    assert resposta["total"] == referencia["total"]
    assert [r["document_id"] for r in resposta["results"]] == [
        r["document_id"] for r in referencia["results"]
    ]


@pytest.mark.asyncio
async def test_filtro_por_ata_restringe_ao_capitulo_certo(indice_e_catalogo):
    """
    M3 tarefa 5: `documents.ata_codigo` (extraído por `catalog.extrair_ata` no
    indexador) filtra a busca unificada por ATA. A amostra tem 2 documentos do
    ATA 36 (sangria) e 1 do ATA 21 — nenhum termo comum entre eles nesta busca.
    """
    indice, _ = indice_e_catalogo

    com_ata_36 = await search.buscar(indice, "sangria", ata="36", limit=100)
    com_ata_21 = await search.buscar(indice, "sangria", ata="21", limit=100)
    sem_filtro = await search.buscar(indice, "sangria", limit=100)

    assert com_ata_36["total"] > 0
    assert com_ata_36["total"] <= sem_filtro["total"]
    # A prova real do filtro: nenhum documento do ATA 21 fala em "sangria"
    # nesta amostra, então o filtro por ATA 21 zera o resultado mesmo com o
    # termo presente no acervo.
    assert com_ata_21["total"] == 0
    assert sem_filtro["total"] > 0
    assert all(r["manual_codigo"] == MANUAL for r in com_ata_36["results"])


@pytest.mark.asyncio
async def test_api_busca_aplica_filtro_de_ata(api, client_autenticado: AsyncClient):
    com_ata = (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "ata": "36"}
        )
    ).json()
    ata_sem_resultado = (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "ata": "99"}
        )
    ).json()

    assert com_ata["total"] > 0
    assert ata_sem_resultado["total"] == 0


@pytest.mark.asyncio
async def test_filtro_por_documento_restringe_a_um_unico_pdf(indice_e_catalogo):
    """
    Busca de texto DENTRO de um documento, usada pelo viewer
    (`publicacoes_viewer.js`). A amostra tem 2 PDFs que falam em "sangria"
    (ATA 36); filtrar por `documento_id` de só um deles tem que zerar o outro
    sem afetar a busca sem filtro.
    """
    indice, payload = indice_e_catalogo
    doc_36_11 = next(d for d in payload.documentos if "36-11-00" in d.file_key)

    sem_filtro = await search.buscar(indice, "sangria", limit=100)
    com_filtro = await search.buscar(
        indice, "sangria", documento_id=str(doc_36_11.id), limit=100
    )

    assert sem_filtro["total"] >= 2  # os dois PDFs de sangria da amostra
    assert com_filtro["total"] > 0
    assert com_filtro["total"] < sem_filtro["total"]
    assert all(
        uuid.UUID(str(r["document_id"])) == doc_36_11.id for r in com_filtro["results"]
    )


@pytest.mark.asyncio
async def test_api_busca_aplica_filtro_de_documento(api, client_autenticado: AsyncClient):
    indice, payload = api
    doc_36_11 = next(d for d in payload.documentos if "36-11-00" in d.file_key)

    com_filtro = (
        await client_autenticado.get(
            "/publicacoes/api/busca",
            params={"q": "sangria", "documento_id": str(doc_36_11.id)},
        )
    ).json()
    outro_documento = (
        await client_autenticado.get(
            "/publicacoes/api/busca",
            params={"q": "sangria", "documento_id": str(uuid.uuid4())},
        )
    ).json()

    assert com_filtro["total"] > 0
    assert all(r["doc_id"] == str(doc_36_11.id) for r in com_filtro["results"])
    assert outro_documento["total"] == 0  # UUID aleatório não bate com nenhum documento


@pytest.mark.asyncio
async def test_ordenacao_por_bm25_traz_o_mais_relevante_primeiro(indice_e_catalogo):
    """
    `bm25()` do SQLite é negativo — a ordenação correta é ASC.

    `DESC` inverteria o ranking inteiro e passaria em qualquer teste que só
    verificasse "veio resultado".
    """
    indice, _ = indice_e_catalogo
    resultados = (await search.buscar(indice, "sangria", limit=100))["results"]
    scores = [r["score"] for r in resultados]

    assert len(scores) > 1
    assert scores == sorted(scores)
    assert scores[0] < 0


# --------------------------------------------------------------------------
# E-06 / RN-10 — sanitização
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bruta",
    ['sangria "', "sangria AND OR NOT", "NEAR(a b", "*", "()", '"""'],
)
def test_sanitizacao_nunca_deixa_o_sqlite_receber_sintaxe_do_usuario(bruta):
    """
    RN-10: ou a query vira uma expressão de frases, ou é recusada — nunca chega
    ao SQLite como sintaxe FTS, que viraria 500 (E-06).
    """
    try:
        expressao = search.sanitizar_query(bruta)
    except search.QueryInvalidaError:
        return
    assert '"' in expressao
    for operador in ("AND", "OR", "NOT", "NEAR"):
        assert f" {operador} " not in expressao


def test_sanitizacao_preserva_codigo_de_procedimento():
    """`34-15-00-810-801-A` é um token só — quebrá-lo destruiria a busca por procedimento."""
    assert search.sanitizar_query("34-15-00-810-801-A") == '"34-15-00-810-801-A"'


@pytest.mark.asyncio
async def test_injecao_de_fts_nao_derruba_a_busca(indice_e_catalogo):
    """Entrada hostil devolve zero resultados, não erro."""
    indice, _ = indice_e_catalogo
    resposta = await search.buscar(indice, '"; DROP TABLE pages; --')
    assert resposta["total"] == 0

    # E a tabela continua lá.
    assert (await search.status_indice(indice))["paginas"] > 0


# --------------------------------------------------------------------------
# Índice ausente (E-12)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_indice_ausente_e_estado_valido_nao_erro(tmp_path: Path):
    """Antes da primeira indexação, `/api/status` reporta ausência — não 500."""
    estado = await search.status_indice(tmp_path / "nao_existe.db")
    assert estado["disponivel"] is False
    assert estado["documentos"] == 0

    with pytest.raises(search.IndiceIndisponivelError):
        await search.buscar(tmp_path / "nao_existe.db", "sangria")


def test_indice_ausente_nao_cria_arquivo_vazio(tmp_path: Path):
    """
    `mode=ro` na URI é o que impede o SQLite de criar um banco vazio — sem ele,
    "acervo não indexado" viraria "busca sempre vazia", que aponta para o lugar
    errado.
    """
    alvo = tmp_path / "nao_existe.db"
    with pytest.raises(search.IndiceIndisponivelError):
        search._abrir_catalog_ro(alvo)
    assert not alvo.exists()


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


@pytest_asyncio.fixture
async def api(indice_e_catalogo, monkeypatch):
    """
    Aponta os handlers para o índice do teste, não para o da máquina.

    Patch em `service`, não em `router`: quem resolve o caminho do índice é
    `service.caminho_indice_vigente`. O valor aponta para um `catalog.db` que
    NÃO existe — é só a origem do diretório-base; o arquivo realmente aberto é
    o `catalog.<EDICAO>.db` que a fixture gravou ali ao lado.
    """
    indice, payload = indice_e_catalogo

    class _SettingsFake:
        publicacoes_index_path = str(indice.parent / "catalog.db")

    monkeypatch.setattr(service, "get_settings", lambda: _SettingsFake())
    return indice, payload


@pytest.mark.asyncio
async def test_api_busca_devolve_o_contrato(api, client_autenticado: AsyncClient):
    resposta = await client_autenticado.get(
        "/publicacoes/api/busca", params={"q": "sangria"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["query"] == "sangria"
    assert corpo["total"] > 0
    assert set(corpo["results"][0]) == {
        "doc_id",
        "title",
        "manual",
        "chapter",
        "page",
        "snippet",
        "viewer_url",
    }
    primeiro = corpo["results"][0]
    assert primeiro["manual"]["path"] == MANUAL
    # O viewer abre na PÁGINA DO TRECHO, não na página 1 — é o ganho que a
    # extração por página entrega e o Lucene sozinho não permitiria.
    assert primeiro["viewer_url"].endswith(f"#page={primeiro['page']}")
    assert uuid.UUID(primeiro["doc_id"])


@pytest.mark.asyncio
async def test_api_snippet_usa_sentinela_e_nunca_html(
    api, client_autenticado: AsyncClient
):
    """
    B8: o realce sai como `\\x02`/`\\x03`, não como `<mark>`.

    Se o SQLite emitisse HTML, o cliente teria de escolher entre mostrar
    `&lt;mark&gt;` literal e executar o que viesse dentro do texto.
    """
    corpo = (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria"}
        )
    ).json()

    snippets = [r["snippet"] for r in corpo["results"]]
    assert any("\x02" in s and "\x03" in s for s in snippets)
    assert all("<mark>" not in s for s in snippets)
    assert all("<" not in s.replace("\x02", "").replace("\x03", "") for s in snippets)


@pytest.mark.asyncio
async def test_api_busca_recusa_query_impossivel_com_400(
    api, client_autenticado: AsyncClient
):
    """E-06: sintaxe que o FTS não aceita vira 400, nunca 500."""
    resposta = await client_autenticado.get(
        "/publicacoes/api/busca", params={"q": "***"}
    )
    assert resposta.status_code == 400


@pytest.mark.asyncio
async def test_api_busca_aplica_filtro_de_manual(api, client_autenticado: AsyncClient):
    com_filtro = (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "manual": MANUAL}
        )
    ).json()
    inexistente = (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "manual": "NAO_EXISTE"}
        )
    ).json()

    assert com_filtro["total"] > 0
    assert inexistente["total"] == 0


@pytest.mark.asyncio
async def test_api_busca_respeita_os_limites_de_paginacao(
    api, client_autenticado: AsyncClient
):
    assert (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "limit": 0}
        )
    ).status_code == 422
    assert (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "limit": 500}
        )
    ).status_code == 422
    assert (
        await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria", "offset": -1}
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_api_busca_exige_autenticacao(api, client: AsyncClient):
    resposta = await client.get("/publicacoes/api/busca", params={"q": "sangria"})
    assert resposta.status_code == 401


@pytest.mark.asyncio
async def test_api_status_reporta_catalogo_e_indice(
    api, client_autenticado: AsyncClient
):
    corpo = (await client_autenticado.get("/publicacoes/api/status")).json()

    assert corpo["indice_disponivel"] is True
    assert corpo["edicao"] == EDICAO
    assert corpo["manuais"] == 1
    assert corpo["documentos"] == len(PDFS_AMOSTRA)
    assert corpo["paginas_indexadas"] > 0


@pytest.mark.asyncio
async def test_api_pdf_entrega_o_arquivo_e_audita_o_acesso(
    api, client_autenticado: AsyncClient, db: AsyncSession
):
    """M1 tarefa 9: toda abertura de documento deixa rastro."""
    from sqlalchemy import select

    from app.modules.publicacoes.models import PublicacaoAcesso

    _, payload = api
    doc = payload.documentos[0]

    resposta = await client_autenticado.get(
        f"/publicacoes/doc/{doc.id}/pdf", params={"pagina": 2}
    )
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")

    acesso = (
        await db.execute(
            select(PublicacaoAcesso).where(PublicacaoAcesso.documento_id == doc.id)
        )
    ).scalar_one()
    assert acesso.pagina == 2
    # Snapshot do título: a auditoria continua legível se o documento sair do
    # acervo (B4).
    assert acesso.documento_titulo == doc.titulo


@pytest.mark.asyncio
async def test_api_pdf_de_documento_inexistente_da_404(
    api, client_autenticado: AsyncClient
):
    resposta = await client_autenticado.get(f"/publicacoes/doc/{uuid.uuid4()}/pdf")
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# Mapa do FIM
# --------------------------------------------------------------------------


@pytest_asyncio.fixture
async def com_fim_map(indice_e_catalogo, db: AsyncSession):
    """Carrega o `fim.json` real, restrito às mensagens da amostra indexada."""
    pares = [
        p
        for p in catalog.carregar_fim_json(FIM_JSON)
        if catalog.nome_pdf_de_procedimento(p[1]) in PDFS_AMOSTRA
    ]
    # `ADC 001` aponta para um procedimento fora da amostra — entra para provar
    # que procedimento sem PDF vira documento_id NULL, e não erro.
    pares.append(("ZZZ 999", "99-99-99-810-801-A"))

    edicao = await service.obter_ou_criar_edicao(db, EDICAO)
    resultado = await service.sincronizar_fim_map(db, pares, edicao)
    return pares, resultado


@pytest.mark.asyncio
async def test_fim_map_resolve_procedimento_para_documento(com_fim_map):
    pares, resultado = com_fim_map
    assert resultado["total"] == len(pares)
    assert resultado["com_documento"] == len(pares) - 1


@pytest.mark.asyncio
async def test_api_fim_busca_por_prefixo_de_mensagem(
    api, com_fim_map, client_autenticado: AsyncClient
):
    pares, _ = com_fim_map
    mensagem = pares[0][0]

    corpo = (
        await client_autenticado.get(
            "/publicacoes/api/fim", params={"mensagem": mensagem[:3]}
        )
    ).json()

    assert corpo["total"] > 0
    achado = next(r for r in corpo["results"] if r["mensagem"] == mensagem)
    assert achado["procedimento"] == pares[0][1]
    assert achado["doc_id"] is not None
    assert achado["viewer_url"].startswith("/publicacoes/viewer/")


@pytest.mark.asyncio
async def test_api_fim_procedimento_sem_pdf_devolve_doc_id_nulo(
    api, com_fim_map, client_autenticado: AsyncClient
):
    """
    4 dos 253 procedimentos do piloto não têm PDF. A mensagem continua útil —
    resolve para um código que o mecânico procura no manual em papel.
    """
    corpo = (
        await client_autenticado.get(
            "/publicacoes/api/fim", params={"mensagem": "ZZZ"}
        )
    ).json()

    assert corpo["total"] == 1
    assert corpo["results"][0]["doc_id"] is None
    assert corpo["results"][0]["viewer_url"] is None


# --------------------------------------------------------------------------
# Metadados do viewer e banner de revisão anterior (§2.2)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_documento_viewer_devolve_metadados(
    api, client_autenticado: AsyncClient
):
    _, payload = api
    doc = payload.documentos[0]

    corpo = (
        await client_autenticado.get(f"/publicacoes/api/documentos/{doc.id}")
    ).json()

    assert corpo["id"] == str(doc.id)
    assert corpo["titulo"] == doc.titulo
    assert corpo["manual"]["path"] == MANUAL
    assert corpo["edicao_rotulo"] == EDICAO
    assert corpo["edicao_vigente"] is True
    assert corpo["equivalente_vigente_id"] is None


@pytest.mark.asyncio
async def test_api_documento_viewer_inexistente_da_404(
    api, client_autenticado: AsyncClient
):
    resposta = await client_autenticado.get(f"/publicacoes/api/documentos/{uuid.uuid4()}")
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_equivalente_vigente_aponta_da_edicao_antiga_para_a_nova(
    entrada: Path, tmp_path: Path, db: AsyncSession, client_autenticado: AsyncClient,
):
    """
    §2.2: o `document_id` inclui a edição de propósito (achado B2) — reindexar
    com um rótulo novo NÃO reaproveita o id antigo, mesmo para o mesmo arquivo.
    A UI precisa de outro caminho para "voltar" à edição vigente, e é isso que
    `obter_equivalente_vigente` resolve por (manual.codigo, file_key).
    """
    from app.shared.core.enums import StatusEdicao

    indice_antigo = tmp_path / "antigo.db"
    antigo = _indexar(entrada, indice_antigo)
    edicao_antiga = await service.obter_ou_criar_edicao(
        db, "2026", status=StatusEdicao.ANTERIOR
    )
    await service.sincronizar_catalogo(db, edicao_antiga, antigo)

    indice_novo = tmp_path / "novo.db"
    conn, tmp_novo = indexar.abrir_catalog_novo(indice_novo)
    try:
        for manual in indexar.descobrir_manuais(entrada, MANUAL):
            indexar.processar_manual(
                manual,
                edicao_rotulo="2027",
                categorias=catalog.carregar_categorias(
                    Path("config/categorias_manuais.toml")
                ),
                acervo=Path("var/publicacoes/acervo"),
                conn=conn,
            )
        indexar.finalizar_catalog(conn)
    finally:
        conn.close()
    tmp_novo.replace(indice_novo)
    novo = indexar.descobrir_manuais(entrada, MANUAL)
    novo_payload = [
        indexar.processar_manual(
            m, edicao_rotulo="2027",
            categorias=catalog.carregar_categorias(Path("config/categorias_manuais.toml")),
            acervo=Path("var/publicacoes/acervo"), conn=None,
        )
        for m in novo
    ]
    edicao_nova = await service.obter_ou_criar_edicao(db, "2027", status=StatusEdicao.VIGENTE)
    await service.sincronizar_catalogo(db, edicao_nova, novo_payload)

    doc_antigo = antigo[0].documentos[0]
    doc_novo_equivalente = next(
        d for d in novo_payload[0].documentos if d.file_key == doc_antigo.file_key
    )
    assert doc_antigo.id != doc_novo_equivalente.id, (
        "edições diferentes devem gerar UUIDs diferentes para o mesmo arquivo (B2)"
    )

    # `/api/documentos/{id}` só lê o banco principal — não abre índice nenhum,
    # então não há caminho de índice a apontar aqui.
    corpo = (
        await client_autenticado.get(f"/publicacoes/api/documentos/{doc_antigo.id}")
    ).json()

    assert corpo["edicao_vigente"] is False
    assert corpo["equivalente_vigente_id"] == str(doc_novo_equivalente.id)


# --------------------------------------------------------------------------
# Índice por edição — a busca segue a edição VIGENTE
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trocar_edicao_vigente_muda_o_que_a_busca_devolve(
    entrada: Path, tmp_path: Path, db: AsyncSession, client_autenticado: AsyncClient,
    monkeypatch,
):
    """
    O teste que impede "ativar edição" de ser teatro.

    Duas edições indexam os MESMOS PDFs em arquivos separados
    (`catalog.ed-a.db` e `catalog.ed-b.db`). Como o `document_id` inclui a
    edição no UUID v5 (achado B2), os ids das duas são necessariamente
    disjuntos — então basta olhar QUAIS ids a busca devolve para saber QUAL
    arquivo ela abriu.

    Se a resolução por edição não existisse, ou se a busca voltasse a ler um
    caminho fixo, os dois conjuntos seriam idênticos e este teste falharia. É
    ele que sustenta a promessa da Fase 0 — mudar o status no banco muda de
    fato o resultado da busca, sem mover arquivo nenhum.
    """
    from app.modules.auth.models import Usuario
    from app.modules.auth.security import hash_senha
    from app.shared.core.enums import StatusEdicao

    # `publicado_por_id` tem FK para `usuarios` com ondelete RESTRICT, e o
    # SQLite do projeto roda com `PRAGMA foreign_keys=ON` — um uuid4 solto seria
    # recusado. `client_autenticado` cria um usuário mas não o expõe.
    usuario_ativador = Usuario(
        nome="Ativador", posto="Cap", especialidade="ELT", funcao="ADMINISTRADOR",
        ramal="9001", username=f"ativador.{uuid.uuid4().hex[:6]}",
        senha_hash=hash_senha("x"),
    )
    db.add(usuario_ativador)
    await db.flush()

    ed_a = await service.obter_ou_criar_edicao(db, "ed-a", status=StatusEdicao.VIGENTE)
    await service.sincronizar_catalogo(
        db, ed_a, _indexar(entrada, tmp_path / "catalog.ed-a.db", edicao_rotulo="ed-a")
    )

    ed_b = await service.obter_ou_criar_edicao(
        db, "ed-b", status=StatusEdicao.AGUARDANDO_ATIVACAO
    )
    await service.sincronizar_catalogo(
        db, ed_b, _indexar(entrada, tmp_path / "catalog.ed-b.db", edicao_rotulo="ed-b")
    )
    await db.flush()

    class _SettingsFake:
        publicacoes_index_path = str(tmp_path / "catalog.db")

    monkeypatch.setattr(service, "get_settings", lambda: _SettingsFake())

    async def _ids_da_busca() -> set[str]:
        resposta = await client_autenticado.get(
            "/publicacoes/api/busca", params={"q": "sangria"}
        )
        assert resposta.status_code == 200
        return {r["doc_id"] for r in resposta.json()["results"]}

    ids_a = await _ids_da_busca()
    assert ids_a, "pré-condição: a edição vigente inicial precisa responder à busca"

    # A ativação inteira: dois UPDATEs, nenhum arquivo movido.
    #
    # Pelo `service`, e não trocando `status` na mão: o índice único parcial
    # `uq_manuais_edicoes_vigente_unica` (Fase 1) é verificado por statement, e
    # num flush único o SQLAlchemy ordena os UPDATEs por chave primária — com
    # UUID aleatório, a promoção vinha antes do rebaixamento em ~1/3 das
    # execuções e o teste falhava com IntegrityError. `service.ativar_edicao`
    # faz o flush em duas etapas justamente por isso; usar o caminho real aqui
    # elimina a instabilidade E exercita a Fase 1 de quebra.
    await service.ativar_edicao(db, ed_b.id, usuario_id=usuario_ativador.id)

    ids_b = await _ids_da_busca()
    assert ids_b, "a edição recém-ativada precisa responder à mesma busca"
    assert ids_a.isdisjoint(ids_b), (
        "a busca continuou lendo o índice da edição anterior — a troca de "
        "edição vigente não surtiu efeito"
    )


@pytest.mark.asyncio
async def test_busca_cai_para_o_indice_legado_quando_nao_ha_por_edicao(
    indice_e_catalogo, tmp_path: Path, client_autenticado: AsyncClient, monkeypatch
):
    """
    Compatibilidade: instalação indexada antes da Fase 0 tem só `catalog.db`.
    A busca precisa continuar respondendo até alguém reindexar.
    """
    indice, _ = indice_e_catalogo
    legado = tmp_path / "legado" / "catalog.db"
    legado.parent.mkdir()
    shutil.copy(indice, legado)

    class _SettingsFake:
        publicacoes_index_path = str(legado)

    monkeypatch.setattr(service, "get_settings", lambda: _SettingsFake())

    resposta = await client_autenticado.get(
        "/publicacoes/api/busca", params={"q": "sangria"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["total"] > 0


# --------------------------------------------------------------------------
# Páginas HTML (fumaça — sem verificação visual, ver 08_status_de_implementacao.md)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagina_lista_retorna_200_autenticado(client_autenticado: AsyncClient):
    """
    `publicacoes_explorador.js` faz `getElementById` para cada um destes — um
    id renomeado só no template ou só no JS não quebra em lint nem em testes
    de API, e passaria despercebido até alguém abrir a página.
    """
    resposta = await client_autenticado.get("/publicacoes")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    for id_esperado in [
        "pub-acervo-arvore", "pub-acervo-painel", "pub-acervo-breadcrumb",
        "pub-acervo-voltar", "pub-acervo-avancar", "pub-acervo-raiz",
        "pub-acervo-view-lista", "pub-acervo-view-icones", "pub-acervo-ordenar",
        "pub-acervo-busca-input", "pub-acervo-busca-resultados",
        "pub-acervo-fim-input", "pub-acervo-fim-btn", "pub-acervo-fim-resultados",
    ]:
        assert f'id="{id_esperado}"' in resposta.text, f"id ausente no template: {id_esperado}"
    assert 'href="/publicacoes/avulsas"' in resposta.text
    assert "/static/js/publicacoes_explorador.js" in resposta.text


@pytest.mark.asyncio
async def test_pagina_lista_honra_deep_link_de_busca(client_autenticado: AsyncClient):
    """
    Contrato com `inspecao_detalhe.js` (checklist de inspeção, M3): o link
    `/publicacoes?q=...` precisa continuar abrindo a página — a busca em si
    (disparada pelo JS ao ler `?q=`) não é testável aqui, é client-side.
    """
    resposta = await client_autenticado.get("/publicacoes", params={"q": "sangria do compressor"})
    assert resposta.status_code == 200


@pytest.mark.asyncio
async def test_pagina_viewer_retorna_200_autenticado(client_autenticado: AsyncClient):
    resposta = await client_autenticado.get(f"/publicacoes/viewer/{uuid.uuid4()}")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    for id_esperado in [
        "pub-viewer-canvas", "pub-viewer-miniaturas", "pub-viewer-pagina-input",
        "pub-viewer-zoom-mais", "pub-viewer-zoom-menos", "pub-viewer-rotacionar",
        "pub-viewer-tela-cheia", "pub-viewer-busca-input", "pub-viewer-favorito",
    ]:
        assert f'id="{id_esperado}"' in resposta.text, f"id ausente no template: {id_esperado}"
    assert "/static/js/publicacoes_viewer.js" in resposta.text


@pytest.mark.asyncio
async def test_atalho_mobile_retorna_200_autenticado(client_autenticado: AsyncClient):
    resposta = await client_autenticado.get("/m/publicacoes")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


@pytest.mark.asyncio
async def test_pagina_lista_sem_autenticacao_nao_retorna_200(client: AsyncClient):
    """R20: página HTML sem sessão não pode vazar 200 — 401 ou redirect para /login."""
    resposta = await client.get("/publicacoes", follow_redirects=False)
    assert resposta.status_code != 200


def test_static_mjs_resolve_para_mime_de_javascript():
    """
    Sem isto, `<script type="module">` recusaria executar o PDF.js: navegadores
    exigem Content-Type de JavaScript para módulos ES, e `.mjs` nem sempre está
    no mapa de MIME types do SO (main.py:_mount_static registra explicitamente).
    """
    import mimetypes

    tipo, _ = mimetypes.guess_type("pdf.min.mjs")
    assert tipo in ("text/javascript", "application/javascript", "text/ecmascript")
