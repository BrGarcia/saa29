"""
tests/integration/test_publicacoes_busca.py
Busca do acervo de manuais, ponta a ponta: PDF real → catalog.db → API.

Roda no CI: os PDFs vêm de `docs/fim/`, que É versionado (412 arquivos) — ao
contrário do acervo de 1 GB, que não é. Cada teste indexa um punhado deles em
`tmp_path`, então nada aqui depende de estado deixado por outro teste nem do
`var/publicacoes/catalog.db` da máquina do desenvolvedor.

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

from app.modules.publicacoes import catalog, router as publicacoes_router, search, service
from scripts.publicacoes import indexar

FIM = Path("docs/fim")

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


def _indexar(entrada: Path, indice: Path) -> list[service.ManualPayload]:
    """Roda o indexador (sem banco principal) e devolve os payloads."""
    conn, temporario = indexar.abrir_catalog_novo(indice)
    try:
        manuais = indexar.descobrir_manuais(entrada, MANUAL)
        payloads = [
            indexar.processar_manual(
                manual,
                edicao_rotulo=EDICAO,
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
    """Índice de busca + catálogo leve gravados, prontos para consulta."""
    indice = tmp_path / "catalog.db"
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
    """Aponta os handlers para o índice do teste, não para o da máquina."""
    indice, payload = indice_e_catalogo

    class _SettingsFake:
        publicacoes_index_path = str(indice)

    monkeypatch.setattr(publicacoes_router, "get_settings", lambda: _SettingsFake())
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
        for p in catalog.carregar_fim_json(FIM / "fim.json")
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
