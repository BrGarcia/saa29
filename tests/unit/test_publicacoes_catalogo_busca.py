"""
tests/unit/test_publicacoes_catalogo_busca.py
Busca por NOME/CAMINHO no catálogo — usada pela caixa de busca do explorador
do acervo (`publicacoes_explorador.js`, modo "Por nome").

Só o banco principal (SQLAlchemy) — nada aqui toca `catalog.db` nem
`pypdfium2`, mesmo padrão de `test_publicacoes_navegacao.py`. A diferença
central que estes testes existem para provar: isto casa contra NOME (título,
capítulo, código de manual), não contra conteúdo de página — um termo como
"CHAPTER_21" ou o nome de um arquivo nunca aparece no FTS de `catalog.db`.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicacoes import service
from app.modules.publicacoes.models import Manual, ManualDocumento, ManualEdicao
from app.shared.core.enums import StatusEdicao

URL = "/publicacoes/api/catalogo/busca"


def _rotulo() -> str:
    return f"ed-{uuid.uuid4().hex[:6]}"


async def _inserir_edicao(
    db: AsyncSession, *, status: StatusEdicao = StatusEdicao.VIGENTE
) -> ManualEdicao:
    return await service.obter_ou_criar_edicao(db, _rotulo(), status=status)


async def _inserir_manual(
    db: AsyncSession,
    edicao: ManualEdicao,
    *,
    codigo: str,
    descricao: str = "Descrição de teste",
    categoria: str = "Manutenção",
) -> Manual:
    manual = Manual(
        edicao_id=edicao.id, codigo=codigo, descricao_pt=descricao,
        categoria=categoria, path=codigo,
    )
    db.add(manual)
    await db.flush()
    return manual


def _documento(
    manual: Manual, *, capitulo: str, titulo: str, sort_order: int = 0
) -> ManualDocumento:
    return ManualDocumento(
        id=uuid.uuid4(), manual_id=manual.id, capitulo=capitulo,
        file_key=f"{capitulo}/{titulo}-{uuid.uuid4().hex[:4]}.pdf",
        titulo=titulo, sort_order=sort_order, paginas=10, has_text=True,
    )


@pytest.mark.asyncio
async def test_busca_por_titulo_acha_documento(client_autenticado: AsyncClient, db: AsyncSession):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART1_1651")
    db.add(_documento(manual, capitulo="CHAPTER_36", titulo="Sangria do compressor"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "sangria"})).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["titulo"] == "Sangria do compressor"


@pytest.mark.asyncio
async def test_busca_por_nome_de_capitulo_acha_documento(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """O caso que o FTS de conteúdo não cobre: nome de PASTA, não texto de página."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART1_1651")
    db.add(_documento(manual, capitulo="CHAPTER_21", titulo="Qualquer título"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "CHAPTER_21"})).json()
    assert corpo["total"] == 1


@pytest.mark.asyncio
async def test_busca_por_codigo_do_manual_acha_documento(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="SWPM_1749")
    db.add(_documento(manual, capitulo="CHAPTER_20", titulo="Qualquer título"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "swpm"})).json()
    assert corpo["total"] == 1  # `ilike` — sem diferenciar caixa


@pytest.mark.asyncio
async def test_busca_devolve_caminho_legivel(client_autenticado: AsyncClient, db: AsyncSession):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(
        db, edicao, codigo="AMM_PART1_1651", categoria="Manutenção"
    )
    db.add(_documento(manual, capitulo="CHAPTER_36", titulo="Sangria do compressor"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "sangria"})).json()
    item = corpo["results"][0]
    assert item["caminho"] == "Manutenção › AMM_PART1_1651 › CHAPTER_36"
    assert item["manual"]["path"] == "AMM_PART1_1651"
    assert item["viewer_url"].startswith("/publicacoes/viewer/")


@pytest.mark.asyncio
async def test_busca_so_alcanca_a_edicao_vigente(client_autenticado: AsyncClient, db: AsyncSession):
    """Mesmo escopo de `service.listar_manuais_vigentes` — achado B2, edições não se misturam."""
    vigente = await _inserir_edicao(db, status=StatusEdicao.VIGENTE)
    anterior = await _inserir_edicao(db, status=StatusEdicao.ANTERIOR)

    manual_vigente = await _inserir_manual(db, vigente, codigo="FIM_1741")
    manual_anterior = await _inserir_manual(db, anterior, codigo="FIM_1741")
    db.add(_documento(manual_vigente, capitulo="CHAPTER_34", titulo="Procedimento novo"))
    db.add(_documento(manual_anterior, capitulo="CHAPTER_34", titulo="Procedimento antigo"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "procedimento"})).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["titulo"] == "Procedimento novo"


@pytest.mark.asyncio
async def test_busca_sem_edicao_vigente_devolve_vazio(client_autenticado: AsyncClient):
    corpo = (await client_autenticado.get(URL, params={"q": "qualquer coisa"})).json()
    assert corpo == {"total": 0, "results": []}


@pytest.mark.asyncio
async def test_busca_exige_autenticacao(client: AsyncClient):
    resposta = await client.get(URL, params={"q": "sangria"})
    assert resposta.status_code in (401, 403)


# --------------------------------------------------------------------------
# BUG-02: `_`/`%` do usuário precisam ser tratados como texto literal, não
# como curinga de LIKE/ILIKE (SEC-07) — domínio dominado por nomes com `_`.
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_busca_trata_sublinhado_como_literal_nao_curinga(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """`_` é curinga de LIKE — sem escape, `CHAPTER_21` também casaria `CHAPTERX21`."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART1_1651")
    db.add(_documento(manual, capitulo="CHAPTER_21", titulo="Documento literal"))
    db.add(_documento(manual, capitulo="CHAPTERX21", titulo="Documento sem sublinhado"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "CHAPTER_21"})).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["titulo"] == "Documento literal"


@pytest.mark.asyncio
async def test_busca_trata_porcentagem_como_literal_nao_curinga(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """`%` é curinga de LIKE — sem escape, buscar `%` devolveria o acervo inteiro."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART1_1651")
    db.add(_documento(manual, capitulo="CHAPTER_36", titulo="Documento qualquer"))
    await db.flush()

    corpo = (await client_autenticado.get(URL, params={"q": "%"})).json()
    assert corpo["total"] == 0


@pytest.mark.asyncio
async def test_busca_no_catalogo_limita_a_limite_maximo_listagem(db: AsyncSession):
    """
    RISCO-03: o service também é chamado por scripts, que não passam por
    `Query(le=100)`. `limit` precisa ser clampado dentro do próprio service.
    """
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART1_1651")
    for i in range(105):
        db.add(_documento(manual, capitulo="CHAPTER_20", titulo=f"Documento {i:03d}"))
    await db.flush()

    total, linhas = await service.buscar_no_catalogo(db, "Documento", limit=10_000)
    assert total == 105
    assert len(linhas) == service.LIMITE_MAXIMO_LISTAGEM
