"""
tests/unit/test_publicacoes_navegacao.py
Navegação do catálogo — Etapa 2 de `09_plano_configuracoes.md` (lacuna do M1).

Só o banco principal: nada aqui toca `catalog.db` nem `pypdfium2` — é
catálogo leve (SQLAlchemy), não busca full-text. Por isso roda como `unit`,
mesmo padrão de `test_publicacoes_avulsas.py` e `test_publicacoes_edicoes.py`.

Toda consulta é escopada pela edição VIGENTE — `test_listar_manuais_so_da_edicao_vigente`
é o teste central da etapa: sem o escopo certo, o mesmo manual apareceria
duplicado entre edições (achado B2, o `document_id` inclui a edição no UUID v5).

Armadilhas do harness (já custaram tempo — ver Fase N1 de `09_plano_configuracoes.md`):
- `client_autenticado` sobrescreve `get_current_user` e ignora o header
  `Authorization` pelo resto do teste — para exercitar outro perfil, insira via
  ORM direto (`_inserir_manual`/`_documento`) e use `client` + o header do
  fixture do perfil desejado.
- `override_get_db` do conftest faz `rollback()` da transação de teste inteira
  em qualquer exceção que passe pela dependência, inclusive um 404 intencional.
- Sufixo único (`uuid.uuid4().hex[:6]`) em qualquer campo `UNIQUE`
  (`manuais_edicoes.rotulo`, `manuais.codigo` dentro da mesma edição).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicacoes import service
from app.modules.publicacoes.models import Manual, ManualDocumento, ManualEdicao
from app.shared.core.enums import StatusEdicao

URL = "/publicacoes/api/manuais"


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
    revisao: str | None = None,
) -> Manual:
    manual = Manual(
        edicao_id=edicao.id,
        codigo=codigo,
        descricao_pt=descricao,
        categoria=categoria,
        path=codigo,
        revisao=revisao,
    )
    db.add(manual)
    await db.flush()
    return manual


def _documento(
    manual: Manual,
    *,
    capitulo: str,
    titulo: str,
    sort_order: int = 0,
    ata_codigo: str | None = None,
    paginas: int | None = 10,
    has_text: bool = True,
) -> ManualDocumento:
    return ManualDocumento(
        id=uuid.uuid4(),
        manual_id=manual.id,
        capitulo=capitulo,
        ata_codigo=ata_codigo,
        file_key=f"{capitulo}/{titulo}-{uuid.uuid4().hex[:4]}.pdf",
        titulo=titulo,
        sort_order=sort_order,
        paginas=paginas,
        has_text=has_text,
    )


# --------------------------------------------------------------------------
# GET /api/manuais
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_manuais_agrupa_contagens(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add_all(
        [
            _documento(manual, capitulo="CHAPTER_21", titulo="Doc 1"),
            _documento(manual, capitulo="CHAPTER_21", titulo="Doc 2"),
            _documento(manual, capitulo="CHAPTER_36", titulo="Doc 3"),
        ]
    )
    await db.flush()

    corpo = (await client_autenticado.get(URL)).json()
    item = next(m for m in corpo if m["codigo"] == "FIM_1741")
    assert item["capitulos"] == 2
    assert item["documentos"] == 3


@pytest.mark.asyncio
async def test_manual_sem_documentos_ainda_aparece(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """O `outerjoin` — o modo de falha é o manual sumir quando a indexação falhou para ele."""
    edicao = await _inserir_edicao(db)
    await _inserir_manual(db, edicao, codigo="VAZIO_0001")
    await db.flush()

    corpo = (await client_autenticado.get(URL)).json()
    item = next(m for m in corpo if m["codigo"] == "VAZIO_0001")
    assert item["capitulos"] == 0
    assert item["documentos"] == 0


@pytest.mark.asyncio
async def test_listar_manuais_so_da_edicao_vigente(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """
    Teste central da etapa: mesmo código de manual em duas edições, só a
    VIGENTE aparece — sem isso o document_id (que inclui a edição, achado B2)
    faria o mesmo manual parecer duplicado.
    """
    vigente = await _inserir_edicao(db, status=StatusEdicao.VIGENTE)
    anterior = await _inserir_edicao(db, status=StatusEdicao.ANTERIOR)

    manual_vigente = await _inserir_manual(
        db, vigente, codigo="FIM_1741", descricao="Edição vigente"
    )
    await _inserir_manual(db, anterior, codigo="FIM_1741", descricao="Edição anterior")
    db.add(_documento(manual_vigente, capitulo="CHAPTER_21", titulo="Doc"))
    await db.flush()

    corpo = (await client_autenticado.get(URL)).json()
    itens = [m for m in corpo if m["codigo"] == "FIM_1741"]
    assert len(itens) == 1
    assert itens[0]["descricao"] == "Edição vigente"


# --------------------------------------------------------------------------
# GET /api/manuais/{codigo}/capitulos
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capitulos_ordenados_por_prefixo(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """RN-05: o prefixo numérico do nome do capítulo já ordena."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="AMM_PART2_1651")
    db.add_all(
        [
            _documento(manual, capitulo="040_FISEC_CHAPTER_21", titulo="Doc B"),
            _documento(manual, capitulo="010_FRONTMATTER", titulo="Doc A"),
            _documento(manual, capitulo="015_TRINDEX", titulo="Doc C"),
        ]
    )
    await db.flush()

    corpo = (await client_autenticado.get(f"{URL}/AMM_PART2_1651/capitulos")).json()
    ordem = [c["capitulo"] for c in corpo["capitulos"]]
    assert ordem == ["010_FRONTMATTER", "015_TRINDEX", "040_FISEC_CHAPTER_21"]


@pytest.mark.asyncio
async def test_capitulo_sem_ata_devolve_nulo(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """Os 31% dos documentos sem `ata_codigo` — o capítulo cai no nome cru."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add(_documento(manual, capitulo="010_FRONTMATTER", titulo="Doc", ata_codigo=None))
    await db.flush()

    corpo = (await client_autenticado.get(f"{URL}/FIM_1741/capitulos")).json()
    capitulo = next(c for c in corpo["capitulos"] if c["capitulo"] == "010_FRONTMATTER")
    assert capitulo["ata_codigo"] is None


@pytest.mark.asyncio
async def test_capitulo_vazio_e_representado(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """O caso do `piloto-fim`: PDFs soltos na raiz têm `capitulo == ''` — não pode sumir nem quebrar."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add(_documento(manual, capitulo="", titulo="Doc solto na raiz"))
    await db.flush()

    corpo = (await client_autenticado.get(f"{URL}/FIM_1741/capitulos")).json()
    assert any(c["capitulo"] == "" for c in corpo["capitulos"])


@pytest.mark.asyncio
async def test_manual_inexistente_retorna_404(client_autenticado: AsyncClient, db: AsyncSession):
    await _inserir_edicao(db)  # existe edição vigente, mas não o manual pedido
    resposta = await client_autenticado.get(f"{URL}/NAO_EXISTE/capitulos")
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# GET /api/manuais/{codigo}/documentos
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documentos_paginados_e_ordenados_por_sort_order(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add_all(
        [
            _documento(manual, capitulo="CHAPTER_21", titulo="Terceiro", sort_order=3),
            _documento(manual, capitulo="CHAPTER_21", titulo="Primeiro", sort_order=1),
            _documento(manual, capitulo="CHAPTER_21", titulo="Segundo", sort_order=2),
        ]
    )
    await db.flush()

    corpo = (
        await client_autenticado.get(f"{URL}/FIM_1741/documentos?limit=2&offset=0")
    ).json()
    assert corpo["total"] == 3
    assert [d["titulo"] for d in corpo["results"]] == ["Primeiro", "Segundo"]

    corpo_pagina_2 = (
        await client_autenticado.get(f"{URL}/FIM_1741/documentos?limit=2&offset=2")
    ).json()
    assert [d["titulo"] for d in corpo_pagina_2["results"]] == ["Terceiro"]


@pytest.mark.asyncio
async def test_documentos_filtrados_por_capitulo(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add_all(
        [
            _documento(manual, capitulo="CHAPTER_21", titulo="Doc 21"),
            _documento(manual, capitulo="CHAPTER_36", titulo="Doc 36"),
        ]
    )
    await db.flush()

    corpo = (
        await client_autenticado.get(f"{URL}/FIM_1741/documentos?capitulo=CHAPTER_36")
    ).json()
    assert corpo["total"] == 1
    assert corpo["results"][0]["titulo"] == "Doc 36"


@pytest.mark.asyncio
async def test_documento_sem_texto_e_sinalizado(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """`has_text=false` precisa chegar na resposta — é o PDF que a busca (E-01) não alcança."""
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add(_documento(manual, capitulo="CHAPTER_21", titulo="Escaneado", has_text=False))
    await db.flush()

    corpo = (await client_autenticado.get(f"{URL}/FIM_1741/documentos")).json()
    assert corpo["results"][0]["has_text"] is False


@pytest.mark.asyncio
async def test_documentos_de_manual_inexistente_retorna_404(
    client_autenticado: AsyncClient, db: AsyncSession
):
    await _inserir_edicao(db)
    resposta = await client_autenticado.get(f"{URL}/NAO_EXISTE/documentos")
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# RBAC — a matriz §7 libera "navegar catálogo" para os quatro perfis
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_navegacao_exige_autenticacao(client: AsyncClient):
    resposta = await client.get(URL)
    assert resposta.status_code == 401


@pytest.mark.asyncio
async def test_mantenedor_pode_navegar(
    client: AsyncClient, db: AsyncSession, usuario_mantenedor_e_token: dict
):
    """O perfil mais restrito da matriz também navega — não é ação de gerência."""
    await _inserir_edicao(db)
    resposta = await client.get(URL, headers=usuario_mantenedor_e_token["headers"])
    assert resposta.status_code == 200


# --------------------------------------------------------------------------
# Páginas HTML (Fase N2) — renderizadas direto do `service`, sem passar pela API
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_lista_os_manuais_por_categoria(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    await _inserir_manual(
        db,
        edicao,
        codigo="FIM_1741",
        descricao="FIM — Isolamento de Falhas",
        categoria="Manutenção",
    )
    await db.flush()

    html = (await client_autenticado.get("/publicacoes")).text
    assert "FIM — Isolamento de Falhas" in html
    assert "/publicacoes/manuais/FIM_1741" in html
    assert "Manutenção" in html


@pytest.mark.asyncio
async def test_pagina_manual_lista_capitulos(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add(_documento(manual, capitulo="040_FISEC_CHAPTER_21", titulo="Doc", ata_codigo="21"))
    await db.flush()

    resposta = await client_autenticado.get("/publicacoes/manuais/FIM_1741")
    assert resposta.status_code == 200
    assert "040_FISEC_CHAPTER_21" in resposta.text
    assert "/publicacoes/manuais/FIM_1741/040_FISEC_CHAPTER_21" in resposta.text


@pytest.mark.asyncio
async def test_pagina_manual_inexistente_retorna_404(
    client_autenticado: AsyncClient, db: AsyncSession
):
    await _inserir_edicao(db)
    resposta = await client_autenticado.get("/publicacoes/manuais/NAO_EXISTE")
    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_pagina_capitulo_lista_documentos_e_link_para_o_viewer(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    documento = _documento(manual, capitulo="CHAPTER_21", titulo="Bleed Air Leak Detection")
    db.add(documento)
    await db.flush()

    resposta = await client_autenticado.get("/publicacoes/manuais/FIM_1741/CHAPTER_21")
    assert resposta.status_code == 200
    assert "Bleed Air Leak Detection" in resposta.text
    assert f"/publicacoes/viewer/{documento.id}" in resposta.text


@pytest.mark.asyncio
async def test_pagina_capitulo_raiz_usa_sentinela_de_url(
    client_autenticado: AsyncClient, db: AsyncSession
):
    """`capitulo == ''` (piloto-fim): um segmento de URL vazio não roteia, daí o sentinela."""
    from app.web.pages.router import CAPITULO_RAIZ_SLUG

    edicao = await _inserir_edicao(db)
    manual = await _inserir_manual(db, edicao, codigo="FIM_1741")
    db.add(_documento(manual, capitulo="", titulo="Doc solto na raiz"))
    await db.flush()

    resposta = await client_autenticado.get(f"/publicacoes/manuais/FIM_1741/{CAPITULO_RAIZ_SLUG}")
    assert resposta.status_code == 200
    assert "Doc solto na raiz" in resposta.text


# --------------------------------------------------------------------------
# Navegação no mobile (Fase N3) — reusa as mesmas rotas do desktop
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mobile_publicacoes_lista_o_acervo_por_categoria(
    client_autenticado: AsyncClient, db: AsyncSession
):
    edicao = await _inserir_edicao(db)
    await _inserir_manual(
        db,
        edicao,
        codigo="FIM_1741",
        descricao="FIM — Isolamento de Falhas",
        categoria="Manutenção",
    )
    await db.flush()

    html = (await client_autenticado.get("/m/publicacoes")).text
    assert "FIM — Isolamento de Falhas" in html
    assert "/publicacoes/manuais/FIM_1741" in html
